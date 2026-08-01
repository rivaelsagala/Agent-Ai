"""Email notification channel backed by the existing SMTP tool."""
from typing import Dict, Optional

from app.market_models import SendResult
from app.service.tools.email_tools import send_email


class EmailChannel:
    def send(self, destination: str, message: str, config: Optional[Dict] = None) -> SendResult:
        channel_config = config or {}
        result = send_email.invoke(
            {
                "to": destination,
                "subject": channel_config.get(
                    "subject",
                    "Atlas AI — Informasi Pasar Saham Indonesia",
                ),
                "body": message,
                "cc": None,
                "bcc": None,
                "is_html": False,
            }
        )
        if str(result).lower().startswith("error"):
            raise RuntimeError(str(result))
        return SendResult(raw_response={"message": str(result)})
