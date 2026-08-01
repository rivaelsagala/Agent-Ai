"""Dispatch queued market-news notifications to external channels."""
from typing import Dict, Optional

from app.channels.email import EmailChannel
from app.channels.telegram import TelegramChannel
from app.channels.whatsapp import WhatsAppChannel


class NotificationService:
    def __init__(self, repository, senders: Optional[Dict] = None):
        self.repository = repository
        self.senders = senders or {
            "telegram": TelegramChannel(),
            "whatsapp": WhatsAppChannel(),
            "email": EmailChannel(),
        }

    def send_test(
        self,
        channel_type: str,
        destination: str,
        message: str,
        channel_config: Optional[dict] = None,
    ) -> dict:
        sender = self.senders.get(channel_type)
        if not sender:
            raise ValueError(f"Unsupported channel: {channel_type}")
        result = sender.send(destination, message, channel_config or {})
        return {
            "channel": channel_type,
            "destination": destination,
            "provider_message_id": result.provider_message_id,
        }

    def dispatch_pending(self, limit: int = 25) -> dict:
        deliveries = self.repository.claim_pending_deliveries(limit=limit)
        sent = 0
        failed = 0
        for delivery in deliveries:
            sender = self.senders.get(delivery.get("channel_type"))
            if not sender:
                error = f"Unsupported channel: {delivery.get('channel_type')}"
                self.repository.mark_delivery_failed(
                    delivery["id"],
                    error,
                    delivery["attempts"],
                )
                failed += 1
                continue
            try:
                result = sender.send(
                    delivery["destination"],
                    delivery.get("message_text") or "",
                    delivery.get("channel_config") or {},
                )
                self.repository.mark_delivery_sent(
                    delivery["id"],
                    result.provider_message_id or "",
                )
                sent += 1
            except Exception as exc:
                self.repository.mark_delivery_failed(
                    delivery["id"],
                    str(exc),
                    delivery["attempts"],
                )
                failed += 1
        return {
            "claimed": len(deliveries),
            "sent": sent,
            "failed": failed,
        }
