"""PostgreSQL connection and migration helpers."""
import re
from contextlib import contextmanager
from typing import Iterator

from app.config import BASE_DIR, settings


class DatabaseConfigurationError(RuntimeError):
    pass


class Database:
    def __init__(self, database_url: str = "", schema: str = ""):
        self.database_url = database_url or settings.DATABASE_URL
        self.schema = schema or settings.DATABASE_SCHEMA
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.schema):
            raise DatabaseConfigurationError("DATABASE_SCHEMA is not a valid identifier")

    def _driver(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise DatabaseConfigurationError(
                "psycopg is not installed; run: pip install -r requirements.txt"
            ) from exc
        return psycopg, dict_row

    @contextmanager
    def connect(self) -> Iterator:
        if not self.database_url:
            raise DatabaseConfigurationError("DATABASE_URL is not configured")

        psycopg, dict_row = self._driver()
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            connection.execute(f'SET search_path TO "{self.schema}", public')
            yield connection

    def migrate(self) -> None:
        migration_path = BASE_DIR / "migrations" / "001_market_news.sql"
        sql = migration_path.read_text(encoding="utf-8")
        if self.schema != "market_news":
            sql = re.sub(r"\bmarket_news\b", self.schema, sql)
        with self.connect() as connection:
            connection.execute(sql)
