"""Telegram Bot API notification channel."""
from typing import Dict, Optional
import requests
from loguru import logger

from app.config import settings
from app.market_models import SendResult


class TelegramChannel:
    def __init__(self, token: str = "", session: Optional[requests.Session] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.session = session or requests.Session()

    def send(self, destination: str, message: str, config: Optional[Dict] = None) -> SendResult:
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN is missing or not configured.")
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        
        logger.info(f"Sending Telegram notification to chat_id '{destination}'")
        try:
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
                error_desc = data.get("description", "Telegram rejected the message")
                logger.error(f"Telegram API rejected message: {error_desc}")
                raise RuntimeError(error_desc)
            result = data.get("result", {})
            msg_id = str(result.get("message_id", "")) or None
            logger.info(f"Telegram notification sent successfully | message_id: {msg_id}")
            return SendResult(
                provider_message_id=msg_id,
                raw_response=data,
            )
        except Exception as e:
            logger.exception(f"Failed to send Telegram message to '{destination}': {e}")
            raise

