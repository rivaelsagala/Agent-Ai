"""Lazy singletons used by the worker and manual admin endpoints."""
from functools import lru_cache

from app.database.repository import MarketNewsRepository
from app.services.news_monitor import NewsMonitorService
from app.services.notification_service import NotificationService


@lru_cache(maxsize=1)
def get_repository() -> MarketNewsRepository:
    return MarketNewsRepository()


@lru_cache(maxsize=1)
def get_notification_service() -> NotificationService:
    return NotificationService(get_repository())


@lru_cache(maxsize=1)
def get_monitor_service() -> NewsMonitorService:
    return NewsMonitorService(
        get_repository(),
        get_notification_service(),
    )
