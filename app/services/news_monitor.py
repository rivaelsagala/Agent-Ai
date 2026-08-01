"""Orchestrate collection, processing, watchlist matching, and queue creation."""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.collectors.registry import CollectorRegistry
from app.config import settings
from app.services.news_processor import NewsProcessor

logger = logging.getLogger(__name__)


class NewsMonitorService:
    def __init__(
        self,
        repository,
        notification_service,
        collector_registry: Optional[CollectorRegistry] = None,
        processor: Optional[NewsProcessor] = None,
    ):
        self.repository = repository
        self.notification_service = notification_service
        self.collector_registry = collector_registry or CollectorRegistry()
        self.processor = processor or NewsProcessor()

    def collect_due_sources(self) -> dict:
        sources = self.repository.list_due_sources()
        totals = {
            "sources": len(sources),
            "fetched": 0,
            "inserted": 0,
            "duplicates": 0,
            "failed_sources": 0,
        }
        for source in sources:
            poll_id = self.repository.start_poll_run(source["id"])
            fetched = inserted = duplicates = 0
            error_message = ""
            try:
                collector = self.collector_registry.create(source)
                items = collector.collect()
                fetched = len(items)
                for item in items:
                    _, was_inserted = self.repository.insert_news(source["id"], item)
                    if was_inserted:
                        inserted += 1
                    else:
                        duplicates += 1
                self.repository.mark_source_fetched(source["id"])
            except Exception as exc:
                logger.exception("Failed to collect source %s", source.get("code"))
                error_message = str(exc)
                totals["failed_sources"] += 1
            finally:
                self.repository.finish_poll_run(
                    poll_id,
                    fetched_count=fetched,
                    inserted_count=inserted,
                    duplicate_count=duplicates,
                    error_message=error_message,
                )
            totals["fetched"] += fetched
            totals["inserted"] += inserted
            totals["duplicates"] += duplicates
        return totals

    def process_new_items(self, limit: int = 25) -> dict:
        items = self.repository.claim_new_news(limit=limit)
        known_tickers = self.repository.list_active_tickers()
        processed = failed = queued = 0
        for item in items:
            try:
                analysis = self.processor.analyze(item, known_tickers)
                llm_model = settings.LLM_MODEL if settings.has_llm_key else ""
                self.repository.save_analysis(item["id"], analysis, llm_model)
                message = self.format_instant_message(item, analysis)
                channels = self.repository.find_target_channels(item["id"], "instant")
                for channel in channels:
                    delivery_id = self.repository.create_delivery(
                        channel_id=channel["id"],
                        delivery_type="instant",
                        dedupe_key=f"instant:{channel['id']}:{item['id']}",
                        message_text=message,
                        news_ids=[item["id"]],
                    )
                    if delivery_id:
                        queued += 1
                processed += 1
            except Exception as exc:
                logger.exception("Failed to process news %s", item.get("id"))
                self.repository.mark_news_failed(item["id"], str(exc))
                failed += 1
        return {
            "claimed": len(items),
            "processed": processed,
            "failed": failed,
            "queued": queued,
        }

    def create_digests(self, period_key: str = "") -> dict:
        since = datetime.now(timezone.utc) - timedelta(
            hours=settings.DIGEST_LOOKBACK_HOURS
        )
        candidates = self.repository.list_digest_candidates(since)
        grouped = defaultdict(list)
        for item in candidates:
            grouped[item["channel_id"]].append(item)

        queued = 0
        effective_period = period_key or datetime.now(timezone.utc).strftime("%Y%m%d%H")
        for channel_id, items in grouped.items():
            selected = items[:10]
            message = self.format_digest_message(selected)
            delivery_id = self.repository.create_delivery(
                channel_id=channel_id,
                delivery_type="digest",
                dedupe_key=f"digest:{channel_id}:{effective_period}",
                message_text=message,
                news_ids=[item["news_id"] for item in selected],
            )
            if delivery_id:
                queued += 1
        return {
            "candidates": len(candidates),
            "channels": len(grouped),
            "queued": queued,
        }

    def run_cycle(self) -> dict:
        return {
            "collection": self.collect_due_sources(),
            "processing": self.process_new_items(),
            "delivery": self.notification_service.dispatch_pending(),
        }

    @staticmethod
    def format_instant_message(item: dict, analysis) -> str:
        emoji = {1: "⚪", 2: "🔵", 3: "🟡", 4: "🟠", 5: "🔴"}[
            analysis.impact_level
        ]
        tickers = ", ".join(analysis.tickers) or "Pasar Indonesia"
        published_at = item.get("published_at")
        published = (
            published_at.strftime("%d %b %Y %H:%M %Z")
            if published_at
            else "Waktu publikasi tidak tersedia"
        )
        return (
            f"{emoji} IMPACT {analysis.impact_level}/5 — {tickers}\n\n"
            f"{item.get('title', '')}\n\n"
            f"{analysis.summary}\n\n"
            f"Mengapa penting: {analysis.impact_reason}\n"
            f"Kategori: {analysis.category}\n"
            f"Sumber: {item.get('source_name', '')}\n"
            f"Waktu: {published}\n"
            f"Link: {item.get('canonical_url', '')}\n\n"
            "Informasi ini bukan rekomendasi investasi."
        )

    @staticmethod
    def format_digest_message(items: list) -> str:
        lines = ["📰 Ringkasan Pasar Saham Indonesia", ""]
        for index, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"{index}. [{item['impact_level']}/5] {item['title']}",
                    item.get("summary") or "",
                    f"Sumber: {item.get('source_name', '')}",
                    f"Link: {item.get('canonical_url', '')}",
                    "",
                ]
            )
        lines.append("Informasi ini bukan rekomendasi investasi.")
        return "\n".join(lines)[:12000]
