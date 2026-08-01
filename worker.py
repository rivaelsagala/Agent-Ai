"""Autonomous market-news worker; no Postman request is required."""
import logging

from app.config import settings
from app.market_runtime import get_repository
from app.scheduler.jobs import build_scheduler, run_monitor_cycle


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if settings.AUTO_MIGRATE:
        get_repository().migrate()
        logging.info("Database migration completed.")

    scheduler = build_scheduler()
    if settings.RUN_ON_STARTUP:
        run_monitor_cycle()
    logging.info("Market-news worker started.")
    scheduler.start()


if __name__ == "__main__":
    main()
