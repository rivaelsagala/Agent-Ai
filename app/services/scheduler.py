"""Background scheduler for periodic market news collection, AI analysis, and automatic dispatching."""
from datetime import datetime
from typing import List, Set

from apscheduler.schedulers.background import BackgroundScheduler
from langchain_core.tools import ToolException
from loguru import logger

from app.config import settings
from app.collectors.registry import CollectorRegistry
from app.collectors.base import format_indonesian_datetime, DAYS_ID, MONTHS_ID
from app.market_models import CollectedNews
from app.services.database.store import JSONStore
from app.services.tools.news_tools import (
    OFFICIAL_SOURCES,
    send_market_alert,
    analyze_news_item_structured,
)


# Persistent JSON store to keep track of sent news URLs to prevent duplicate alerts
sent_news_store = JSONStore("sent_news")
_scheduler = None


def get_sent_urls() -> Set[str]:
    """Retrieve the set of canonical URLs already processed/sent."""
    records = sent_news_store.load()
    return {r.get("url").strip().rstrip("/") for r in records if r.get("url")}


def get_sent_titles() -> Set[str]:
    """Retrieve the set of normalized titles already processed/sent."""
    records = sent_news_store.load()
    return {r.get("title").strip().lower() for r in records if r.get("title")}


def check_and_dispatch_news():
    """Periodic job: fetch news from official sources, run AI analysis (impact & tickers), and send alerts for new articles."""
    logger.info("Executing periodic news monitoring & AI analysis job...")
    registry = CollectorRegistry()
    sent_urls = get_sent_urls()
    sent_titles = get_sent_titles()
    new_items: List[tuple] = []

    for source in OFFICIAL_SOURCES:
        try:
            collector = registry.create(source)
            items = collector.collect()
            for item in items:
                url = item.canonical_url.strip().rstrip("/") if item.canonical_url else ""
                title_key = item.title.strip().lower() if item.title else ""

                if url and url in sent_urls:
                    continue
                if title_key and title_key in sent_titles:
                    continue

                new_items.append((source.get("name", "Market News"), item))
                if url:
                    sent_urls.add(url)
                if title_key:
                    sent_titles.add(title_key)
        except Exception as e:
            logger.warning(f"Failed to fetch news from source '{source.get('code')}': {e}")

    if not new_items:
        logger.info("No new market news found during this check.")
        return

    logger.info(f"Found {len(new_items)} new article(s) to process with AI analysis.")

    # Process up to 5 newest articles per tick to avoid rate limits
    for source_name, item in new_items[:5]:
        date_str = format_indonesian_datetime(item.published_at) if item.published_at else "Terbaru"
        
        # 1. Run AI analysis for affected stock tickers & impact direction
        analysis = analyze_news_item_structured(title=item.title, excerpt=item.source_excerpt)
        
        tickers_list = analysis.get("tickers", [])
        tickers_str = ", ".join(tickers_list) if tickers_list else "Tidak Ada (Makro/Umum)"
        dampak = analysis.get("dampak", "Netral ⚖️")
        impact_level = analysis.get("impact_level", 3)
        summary_ai = analysis.get("summary", item.title)
        impact_reason = analysis.get("impact_reason", "-")
        category = analysis.get("category", "General")

        header_title = f"[{source_name}] {item.title}"
        body = (
            f"📅 Tanggal & Waktu: {date_str}\n"
            f"🏢 Sumber: {source_name}\n"
            f"🏷️ Kategori: {category}\n"
            f"📊 Saham Terdampak: {tickers_str}\n"
            f"🎯 Dampak Saham: {dampak} (Level {impact_level}/5)\n\n"
            f"📝 Ringkasan AI:\n{summary_ai}\n\n"
            f"💡 Alasan Dampak:\n{impact_reason}\n\n"
            f"🔗 Link Berita:\n{item.canonical_url}"
        )

        sent_any = False

        # Dispatch via Telegram if configured
        if settings.NOTIFICATION_TELEGRAM_TO and settings.TELEGRAM_BOT_TOKEN:
            try:
                res = send_market_alert.invoke({
                    "channel": "telegram",
                    "destination": settings.NOTIFICATION_TELEGRAM_TO,
                    "title": header_title,
                    "message": body,
                })
                logger.info(f"Telegram alert result for '{item.title}': {res}")
                sent_any = True
            except Exception as e:
                logger.error(f"Error sending Telegram alert for '{item.title}': {e}")

        # Record in sent_news store with full AI analysis metadata so it is not processed again
        now = datetime.now()
        now_formatted = format_indonesian_datetime(now, include_seconds=True)
        sent_news_store.append({
            "url": item.canonical_url,
            "title": item.title,
            "external_id": item.external_id,
            "source": source_name,
            "sent_at": now_formatted,
            "sent_status": sent_any,
            "analysis": analysis,
            "detail_waktu": {
                "hari": DAYS_ID.get(now.weekday(), ""),
                "tanggal": f"{now.day:02d} {MONTHS_ID.get(now.month, '')} {now.year}",
                "jam": f"{now.strftime('%H:%M:%S')} WIB",
                "sent_at_iso": now.isoformat()
            }
        })
        sent_urls.add(item.canonical_url)
        if item.title:
            sent_titles.add(item.title.strip().lower())


def start_scheduler():
    """Start the APScheduler background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler is already running.")
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)
    interval_seconds = 300  # 5 menit (300 detik)

    # Schedule the news check job
    _scheduler.add_job(
        check_and_dispatch_news,
        trigger="interval",
        seconds=interval_seconds,
        id="check_market_news_job",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(f"Background News Scheduler started. Running every {interval_seconds}.")

    # Run an initial check immediately if configured
    if settings.RUN_ON_STARTUP:
        try:
            _scheduler.get_job("check_market_news_job").func()
        except Exception as e:
            logger.error(f"Initial news check failed on startup: {e}")

    return _scheduler


def stop_scheduler():
    """Stop the APScheduler background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Background News Scheduler stopped.")
