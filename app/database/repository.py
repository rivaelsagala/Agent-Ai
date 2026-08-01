"""PostgreSQL repository for market-news monitoring."""
import json
import socket
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

from app.config import settings
from app.database.postgres import Database
from app.market_models import CollectedNews, NewsAnalysis


class MarketNewsRepository:
    def __init__(self, database: Optional[Database] = None):
        self.database = database or Database()

    def migrate(self) -> None:
        self.database.migrate()

    def list_due_sources(self) -> List[dict]:
        query = """
            SELECT *
            FROM news_sources
            WHERE is_active = TRUE
              AND (
                  last_fetched_at IS NULL
                  OR last_fetched_at <=
                     NOW() - (poll_interval_minutes * INTERVAL '1 minute')
              )
            ORDER BY last_fetched_at NULLS FIRST, code
        """
        with self.database.connect() as connection:
            return list(connection.execute(query).fetchall())

    def start_poll_run(self, source_id) -> str:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO source_poll_runs (source_id, status)
                VALUES (%s, 'running')
                RETURNING id
                """,
                (source_id,),
            ).fetchone()
            return str(row["id"])

    def finish_poll_run(
        self,
        poll_run_id,
        *,
        fetched_count: int,
        inserted_count: int,
        duplicate_count: int,
        error_message: str = "",
    ) -> None:
        status = "failed" if error_message else "success"
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE source_poll_runs
                SET status = %s,
                    finished_at = NOW(),
                    fetched_count = %s,
                    inserted_count = %s,
                    duplicate_count = %s,
                    error_message = NULLIF(%s, '')
                WHERE id = %s
                """,
                (
                    status,
                    fetched_count,
                    inserted_count,
                    duplicate_count,
                    error_message[:2000],
                    poll_run_id,
                ),
            )

    def mark_source_fetched(self, source_id) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE news_sources
                SET last_fetched_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (source_id,),
            )

    def insert_news(self, source_id, item: CollectedNews) -> Tuple[Optional[str], bool]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO news_items (
                    source_id,
                    external_id,
                    canonical_url,
                    title,
                    source_excerpt,
                    published_at,
                    content_hash,
                    raw_metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::JSONB)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (
                    source_id,
                    item.external_id,
                    item.canonical_url,
                    item.title,
                    item.source_excerpt,
                    item.published_at,
                    item.content_hash,
                    json.dumps(item.raw_metadata),
                ),
            ).fetchone()
            return (str(row["id"]), True) if row else (None, False)

    def claim_new_news(self, limit: int = 25) -> List[dict]:
        query = """
            WITH candidates AS (
                SELECT n.id
                FROM news_items n
                WHERE n.processing_status = 'new'
                ORDER BY COALESCE(n.published_at, n.collected_at)
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE news_items n
            SET processing_status = 'processing', updated_at = NOW()
            FROM candidates c
            WHERE n.id = c.id
            RETURNING n.*
        """
        with self.database.connect() as connection:
            rows = list(connection.execute(query, (limit,)).fetchall())
            if not rows:
                return []
            source_ids = {row["source_id"] for row in rows}
            sources = connection.execute(
                """
                SELECT id, code, name
                FROM news_sources
                WHERE id = ANY(%s)
                """,
                (list(source_ids),),
            ).fetchall()
            source_map = {source["id"]: source for source in sources}
            for row in rows:
                source = source_map.get(row["source_id"], {})
                row["source_code"] = source.get("code", "")
                row["source_name"] = source.get("name", "")
            return rows

    def list_active_tickers(self) -> List[str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT ticker FROM securities WHERE is_active = TRUE"
            ).fetchall()
            return [row["ticker"] for row in rows]

    def save_analysis(
        self,
        news_id,
        analysis: NewsAnalysis,
        llm_model: str,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE news_items
                SET summary = %s,
                    impact_reason = %s,
                    category = %s,
                    impact_level = %s,
                    sentiment = %s,
                    confidence = %s,
                    processing_status = 'processed',
                    llm_model = %s,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    analysis.summary,
                    analysis.impact_reason,
                    analysis.category,
                    analysis.impact_level,
                    analysis.sentiment,
                    analysis.confidence,
                    llm_model,
                    news_id,
                ),
            )
            for index, ticker in enumerate(analysis.tickers):
                connection.execute(
                    """
                    INSERT INTO securities (ticker, company_name)
                    VALUES (%s, %s)
                    ON CONFLICT (ticker) DO NOTHING
                    """,
                    (ticker, ticker),
                )
                connection.execute(
                    """
                    INSERT INTO news_securities (
                        news_id, ticker, relevance_score, match_method, is_primary
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (news_id, ticker) DO UPDATE SET
                        relevance_score = EXCLUDED.relevance_score,
                        match_method = EXCLUDED.match_method,
                        is_primary = EXCLUDED.is_primary
                    """,
                    (
                        news_id,
                        ticker,
                        analysis.confidence,
                        "llm" if llm_model else "rule",
                        index == 0,
                    ),
                )

    def mark_news_failed(self, news_id, error_message: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE news_items
                SET processing_status = 'failed',
                    impact_reason = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (error_message[:2000], news_id),
            )

    def find_target_channels(self, news_id, delivery_mode: str) -> List[dict]:
        mode_column = (
            "instant_notification"
            if delivery_mode == "instant"
            else "digest_notification"
        )
        query = f"""
            SELECT DISTINCT
                c.id,
                c.channel_type,
                c.destination,
                c.channel_config
            FROM news_items n
            JOIN subscribers s
              ON s.is_active = TRUE
            JOIN notification_channels c
              ON c.subscriber_id = s.id
             AND c.is_active = TRUE
             AND c.is_verified = TRUE
            JOIN watchlists w
              ON w.subscriber_id = s.id
             AND w.is_active = TRUE
             AND w.{mode_column} = TRUE
            WHERE n.id = %s
              AND n.impact_level >= w.minimum_impact
              AND (
                  CARDINALITY(w.categories) = 0
                  OR n.category = ANY(w.categories)
              )
              AND (
                  w.receive_all = TRUE
                  OR EXISTS (
                      SELECT 1
                      FROM watchlist_securities ws
                      JOIN news_securities ns
                        ON ns.ticker = ws.ticker
                       AND ns.news_id = n.id
                      WHERE ws.watchlist_id = w.id
                  )
              )
        """
        with self.database.connect() as connection:
            return list(connection.execute(query, (news_id,)).fetchall())

    def create_delivery(
        self,
        *,
        channel_id,
        delivery_type: str,
        dedupe_key: str,
        message_text: str,
        news_ids: Sequence,
    ) -> Optional[str]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO notification_deliveries (
                    channel_id, delivery_type, dedupe_key, message_text
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dedupe_key) DO NOTHING
                RETURNING id
                """,
                (channel_id, delivery_type, dedupe_key, message_text),
            ).fetchone()
            if not row:
                return None
            delivery_id = row["id"]
            for order, news_id in enumerate(news_ids, start=1):
                connection.execute(
                    """
                    INSERT INTO delivery_items (delivery_id, news_id, display_order)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (delivery_id, news_id, order),
                )
            return str(delivery_id)

    def list_digest_candidates(self, since: datetime) -> List[dict]:
        query = """
            SELECT DISTINCT
                c.id AS channel_id,
                c.channel_type,
                c.destination,
                c.channel_config,
                n.id AS news_id,
                n.title,
                n.summary,
                n.category,
                n.impact_level,
                n.canonical_url,
                n.published_at,
                src.name AS source_name
            FROM news_items n
            JOIN news_sources src ON src.id = n.source_id
            JOIN subscribers s ON s.is_active = TRUE
            JOIN notification_channels c
              ON c.subscriber_id = s.id
             AND c.is_active = TRUE
             AND c.is_verified = TRUE
            JOIN watchlists w
              ON w.subscriber_id = s.id
             AND w.is_active = TRUE
             AND w.digest_notification = TRUE
            WHERE n.processing_status = 'processed'
              AND COALESCE(n.published_at, n.collected_at) >= %s
              AND n.impact_level >= w.minimum_impact
              AND (
                  CARDINALITY(w.categories) = 0
                  OR n.category = ANY(w.categories)
              )
              AND (
                  w.receive_all = TRUE
                  OR EXISTS (
                      SELECT 1
                      FROM watchlist_securities ws
                      JOIN news_securities ns
                        ON ns.ticker = ws.ticker
                       AND ns.news_id = n.id
                      WHERE ws.watchlist_id = w.id
                  )
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM delivery_items di
                  JOIN notification_deliveries d ON d.id = di.delivery_id
                  WHERE di.news_id = n.id
                    AND d.channel_id = c.id
                    AND d.delivery_type = 'digest'
                    AND d.status <> 'cancelled'
              )
            ORDER BY n.impact_level DESC, n.published_at DESC NULLS LAST
        """
        with self.database.connect() as connection:
            return list(connection.execute(query, (since,)).fetchall())

    def claim_pending_deliveries(self, limit: int = 25) -> List[dict]:
        worker_id = f"{socket.gethostname()}:{uuid4().hex[:8]}"
        query = """
            WITH candidates AS (
                SELECT d.id
                FROM notification_deliveries d
                WHERE (
                    d.status = 'pending'
                    OR (
                        d.status = 'processing'
                        AND d.locked_at < NOW() - INTERVAL '10 minutes'
                    )
                )
                  AND d.scheduled_at <= NOW()
                  AND (d.next_retry_at IS NULL OR d.next_retry_at <= NOW())
                ORDER BY d.scheduled_at
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE notification_deliveries d
            SET status = 'processing',
                attempts = attempts + 1,
                locked_at = NOW(),
                locked_by = %s,
                updated_at = NOW()
            FROM candidates selected
            WHERE d.id = selected.id
            RETURNING d.*
        """
        with self.database.connect() as connection:
            rows = list(connection.execute(query, (limit, worker_id)).fetchall())
            if not rows:
                return []
            channel_ids = {row["channel_id"] for row in rows}
            channels = connection.execute(
                """
                SELECT id AS resolved_channel_id,
                       channel_type,
                       destination,
                       channel_config
                FROM notification_channels
                WHERE id = ANY(%s)
                """,
                (list(channel_ids),),
            ).fetchall()
            channel_map = {
                channel["resolved_channel_id"]: {
                    "channel_type": channel["channel_type"],
                    "destination": channel["destination"],
                    "channel_config": channel["channel_config"],
                }
                for channel in channels
            }
            for row in rows:
                row.update(channel_map.get(row["channel_id"], {}))
            return rows

    def mark_delivery_sent(self, delivery_id, provider_message_id: str = "") -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE notification_deliveries
                SET status = 'sent',
                    provider_message_id = NULLIF(%s, ''),
                    sent_at = NOW(),
                    locked_at = NULL,
                    locked_by = NULL,
                    error_message = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (provider_message_id, delivery_id),
            )

    def mark_delivery_failed(
        self,
        delivery_id,
        error_message: str,
        attempts: int,
    ) -> None:
        should_retry = attempts < settings.MAX_DELIVERY_ATTEMPTS
        retry_at = (
            datetime.now(timezone.utc) + timedelta(minutes=2 ** max(attempts - 1, 0))
            if should_retry
            else None
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE notification_deliveries
                SET status = %s,
                    error_message = %s,
                    next_retry_at = %s,
                    locked_at = NULL,
                    locked_by = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    "pending" if should_retry else "failed",
                    error_message[:2000],
                    retry_at,
                    delivery_id,
                ),
            )

    def create_subscriber(
        self,
        *,
        display_name: str,
        channel_type: str,
        destination: str,
        tickers: Iterable[str],
        receive_all: bool,
        minimum_impact: int,
        categories: Sequence[str],
        is_verified: bool,
        channel_config: Optional[Dict] = None,
    ) -> dict:
        normalized_tickers = sorted({ticker.upper().strip() for ticker in tickers})
        with self.database.connect() as connection:
            subscriber = connection.execute(
                """
                INSERT INTO subscribers (display_name)
                VALUES (%s)
                RETURNING id
                """,
                (display_name,),
            ).fetchone()
            subscriber_id = subscriber["id"]
            channel = connection.execute(
                """
                INSERT INTO notification_channels (
                    subscriber_id,
                    channel_type,
                    destination,
                    is_verified,
                    consented_at,
                    channel_config
                )
                VALUES (%s, %s, %s, %s, NOW(), %s::JSONB)
                RETURNING id
                """,
                (
                    subscriber_id,
                    channel_type,
                    destination,
                    is_verified,
                    json.dumps(channel_config or {}),
                ),
            ).fetchone()
            watchlist = connection.execute(
                """
                INSERT INTO watchlists (
                    subscriber_id,
                    receive_all,
                    minimum_impact,
                    categories
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    subscriber_id,
                    receive_all,
                    minimum_impact,
                    list(categories),
                ),
            ).fetchone()
            for ticker in normalized_tickers:
                connection.execute(
                    """
                    INSERT INTO securities (ticker, company_name)
                    VALUES (%s, %s)
                    ON CONFLICT (ticker) DO NOTHING
                    """,
                    (ticker, ticker),
                )
                connection.execute(
                    """
                    INSERT INTO watchlist_securities (watchlist_id, ticker)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (watchlist["id"], ticker),
                )
            return {
                "subscriber_id": str(subscriber_id),
                "channel_id": str(channel["id"]),
                "watchlist_id": str(watchlist["id"]),
                "tickers": normalized_tickers,
            }

    def status_counts(self) -> dict:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM news_sources WHERE is_active) AS sources,
                    (SELECT COUNT(*) FROM news_items) AS news_items,
                    (
                        SELECT COUNT(*)
                        FROM notification_deliveries
                        WHERE status = 'pending'
                    ) AS pending_deliveries,
                    (
                        SELECT COUNT(*)
                        FROM notification_deliveries
                        WHERE status = 'failed'
                    ) AS failed_deliveries,
                    (SELECT MAX(last_fetched_at) FROM news_sources) AS last_fetch
                """
            ).fetchone()
            return dict(row)
