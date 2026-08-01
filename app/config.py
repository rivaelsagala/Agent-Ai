"""Application configuration loaded from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    # OpenRouter (OpenAI-compatible) configuration
    @property
    def OPENROUTER_API_KEY(self) -> str:
        return os.getenv("OPENROUTER_API_KEY", "")

    @property
    def OPENROUTER_BASE_URL(self) -> str:
        return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    @property
    def LLM_MODEL(self) -> str:
        return os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

    @property
    def LLM_TEMPERATURE(self) -> float:
        return float(os.getenv("LLM_TEMPERATURE", "0.0"))

    @property
    def HTTP_TIMEOUT(self) -> float:
        return float(os.getenv("HTTP_TIMEOUT", "30"))

    # PostgreSQL market-news database
    @property
    def DATABASE_URL(self) -> str:
        return os.getenv("DATABASE_URL", "")

    @property
    def DATABASE_SCHEMA(self) -> str:
        return os.getenv("DATABASE_SCHEMA", "market_news")

    @property
    def AUTO_MIGRATE(self) -> bool:
        return os.getenv("AUTO_MIGRATE", "true").lower() == "true"

    # Admin endpoints used for manual runs and setup
    @property
    def ADMIN_API_KEY(self) -> str:
        return os.getenv("ADMIN_API_KEY", "")

    # News monitoring
    @property
    def NEWS_USER_AGENT(self) -> str:
        return os.getenv("NEWS_USER_AGENT", "AtlasMarketNewsBot/1.0 (+contact: admin@localhost)")

    @property
    def NEWS_FETCH_TIMEOUT(self) -> float:
        return float(os.getenv("NEWS_FETCH_TIMEOUT", "30"))

    @property
    def MONITOR_TICK_SECONDS(self) -> int:
        return int(os.getenv("MONITOR_TICK_SECONDS", "60"))

    @property
    def DISPATCH_INTERVAL_SECONDS(self) -> int:
        return int(os.getenv("DISPATCH_INTERVAL_SECONDS", "30"))

    @property
    def MAX_DELIVERY_ATTEMPTS(self) -> int:
        return int(os.getenv("MAX_DELIVERY_ATTEMPTS", "3"))

    @property
    def DIGEST_LOOKBACK_HOURS(self) -> int:
        return int(os.getenv("DIGEST_LOOKBACK_HOURS", "24"))

    @property
    def RUN_ON_STARTUP(self) -> bool:
        return os.getenv("RUN_ON_STARTUP", "true").lower() == "true"

    # Outbound channels
    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        return os.getenv("TELEGRAM_BOT_TOKEN", "")

    @property
    def WHATSAPP_ACCESS_TOKEN(self) -> str:
        return os.getenv("WHATSAPP_ACCESS_TOKEN", "")

    @property
    def WHATSAPP_PHONE_NUMBER_ID(self) -> str:
        return os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

    @property
    def WHATSAPP_GRAPH_VERSION(self) -> str:
        return os.getenv("WHATSAPP_GRAPH_VERSION", "v23.0")

    # Email (SMTP for sending, IMAP for reading)
    @property
    def SMTP_HOST(self) -> str:
        return os.getenv("SMTP_HOST", "")

    @property
    def SMTP_PORT(self) -> int:
        return int(os.getenv("SMTP_PORT", "587"))

    @property
    def SMTP_USERNAME(self) -> str:
        return os.getenv("SMTP_USERNAME", "")

    @property
    def SMTP_PASSWORD(self) -> str:
        return os.getenv("SMTP_PASSWORD", "")

    @property
    def SMTP_USE_TLS(self) -> bool:
        return os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    @property
    def IMAP_HOST(self) -> str:
        return os.getenv("IMAP_HOST", "")

    @property
    def IMAP_PORT(self) -> int:
        return int(os.getenv("IMAP_PORT", "993"))

    @property
    def IMAP_USERNAME(self) -> str:
        return os.getenv("IMAP_USERNAME", "")

    @property
    def IMAP_PASSWORD(self) -> str:
        return os.getenv("IMAP_PASSWORD", "")

    # User identity (used when signing drafts/emails)
    @property
    def USER_NAME(self) -> str:
        return os.getenv("USER_NAME", "")

    @property
    def USER_EMAIL(self) -> str:
        return os.getenv("USER_EMAIL", "")

    @property
    def NOTIFICATION_WA_TO(self) -> str:
        return os.getenv("NOTIFICATION_WA_TO", "")

    @property
    def NOTIFICATION_TELEGRAM_TO(self) -> str:
        return os.getenv("NOTIFICATION_TELEGRAM_TO", "")

    @property
    def NOTIFICATION_EMAIL_TO(self) -> str:
        return os.getenv("NOTIFICATION_EMAIL_TO", "")

    @property
    def has_llm_key(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    @property
    def has_database(self) -> bool:
        return bool(self.DATABASE_URL)


settings = Settings()
