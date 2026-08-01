"""Application configuration loaded from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    # OpenRouter (OpenAI-compatible) configuration
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30"))

    # PostgreSQL market-news database
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "market_news")
    AUTO_MIGRATE = os.getenv("AUTO_MIGRATE", "true").lower() == "true"

    # Admin endpoints used for manual runs and setup
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

    # News monitoring
    NEWS_USER_AGENT = os.getenv(
        "NEWS_USER_AGENT",
        "AtlasMarketNewsBot/1.0 (+contact: admin@localhost)",
    )
    NEWS_FETCH_TIMEOUT = float(os.getenv("NEWS_FETCH_TIMEOUT", "30"))
    MONITOR_TICK_SECONDS = int(os.getenv("MONITOR_TICK_SECONDS", "60"))
    DISPATCH_INTERVAL_SECONDS = int(os.getenv("DISPATCH_INTERVAL_SECONDS", "30"))
    MAX_DELIVERY_ATTEMPTS = int(os.getenv("MAX_DELIVERY_ATTEMPTS", "3"))
    DIGEST_LOOKBACK_HOURS = int(os.getenv("DIGEST_LOOKBACK_HOURS", "24"))
    RUN_ON_STARTUP = os.getenv("RUN_ON_STARTUP", "true").lower() == "true"

    # Outbound channels
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_GRAPH_VERSION = os.getenv("WHATSAPP_GRAPH_VERSION", "v23.0")

    # Email (SMTP for sending, IMAP for reading)
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    IMAP_HOST = os.getenv("IMAP_HOST", "")
    IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USERNAME = os.getenv("IMAP_USERNAME", "")
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

    # User identity (used when signing drafts/emails)
    USER_NAME = os.getenv("USER_NAME", "")
    USER_EMAIL = os.getenv("USER_EMAIL", "")

    @property
    def has_llm_key(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    @property
    def has_database(self) -> bool:
        return bool(self.DATABASE_URL)


settings = Settings()
