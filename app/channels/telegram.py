"""Telegram Bot API notification channel."""
from typing import Dict, Optional

import requests

from app.config import settings
from app.market_models import SendResult


class TelegramChannel:
    def __init__(self, token: str = "", session: Optional[requests.Session] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.session = session or requests.Session()

    def send(self, destination: str, message: str, config: Optional[Dict] = None) -> SendResult:
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        response = self.session.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={
                "chat_id": destination,
                "text": message[:4096],
                "disable_web_page_preview": True,
                "disable_notification": bool((config or {}).get("silent", False)),
            },
            timeout=settings.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "Telegram rejected the message"))
        result = data.get("result", {})
        return SendResult(
            provider_message_id=str(result.get("message_id", "")) or None,
            raw_response=data,
        )
