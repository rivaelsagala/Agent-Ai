"""Background scheduler jobs for market-news monitoring."""
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import settings

logger = logging.getLogger(__name__)


def run_monitor_cycle() -> dict:
    """Run full collection, processing, and delivery cycle."""
    from app.market_runtime import get_monitor_service

    try:
        result = get_monitor_service().run_cycle()
        logger.info("Monitor cycle completed: %s", result)
        return result
    except Exception:
        logger.exception("Error running monitor cycle")
        return {}


def build_scheduler() -> BlockingScheduler:
    """Build and configure the background scheduler."""
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_monitor_cycle,
        "interval",
        seconds=settings.MONITOR_TICK_SECONDS,
        id="market_news_monitor",
        replace_existing=True,
    )
    return scheduler
