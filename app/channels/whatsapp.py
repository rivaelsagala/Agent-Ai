"""WhatsApp Cloud API notification channel."""
from typing import Dict, Optional

import requests

from app.config import settings
from app.market_models import SendResult


class WhatsAppChannel:
    def __init__(
        self,
        access_token: str = "",
        phone_number_id: str = "",
        session: Optional[requests.Session] = None,
    ):
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.session = session or requests.Session()

    def send(self, destination: str, message: str, config: Optional[Dict] = None) -> SendResult:
        if not self.access_token or not self.phone_number_id:
            raise RuntimeError("WhatsApp Cloud API credentials are not configured")

        channel_config = config or {}
        template_name = channel_config.get("template_name")
        if template_name:
            payload = {
                "messaging_product": "whatsapp",
                "to": destination,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": channel_config.get("language", "id"),
                    },
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {
                                    "type": "text",
                                    "text": message[:1024],
                                }
                            ],
                        }
                    ],
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": destination,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": message[:4096],
                },
            }

        response = self.session.post(
            (
                "https://graph.facebook.com/"
                f"{settings.WHATSAPP_GRAPH_VERSION}/{self.phone_number_id}/messages"
            ),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        messages = data.get("messages", [])
        message_id = messages[0].get("id") if messages else None
        return SendResult(provider_message_id=message_id, raw_response=data)
