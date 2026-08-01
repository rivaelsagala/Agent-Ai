"""Base classes and parsing helpers for official news collectors."""
import hashlib
import re
from datetime import datetime
from typing import Iterable, List, Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from app.config import settings
from app.market_models import CollectedNews

JAKARTA = ZoneInfo("Asia/Jakarta")
MONTHS = {
    "jan": 1,
    "januari": 1,
    "feb": 2,
    "februari": 2,
    "mar": 3,
    "maret": 3,
    "apr": 4,
    "april": 4,
    "mei": 5,
    "may": 5,
    "jun": 6,
    "juni": 6,
    "jul": 7,
    "juli": 7,
    "agu": 8,
    "agt": 8,
    "agustus": 8,
    "aug": 8,
    "sep": 9,
    "september": 9,
    "okt": 10,
    "oktober": 10,
    "oct": 10,
    "nov": 11,
    "november": 11,
    "des": 12,
    "desember": 12,
    "dec": 12,
}
DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})"
    r"(?:\s*[|,]?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
    re.IGNORECASE,
)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_indonesian_datetime(value: str) -> Optional[datetime]:
    match = DATE_PATTERN.search(normalize_text(value))
    if not match:
        return None
    day, month_name, year, hour, minute, second = match.groups()
    month = MONTHS.get(month_name.lower())
    if not month:
        return None
    return datetime(
        int(year),
        month,
        int(day),
        int(hour or 0),
        int(minute or 0),
        int(second or 0),
        tzinfo=JAKARTA,
    )


class BaseCollector:
    def __init__(self, source: dict, session: Optional[requests.Session] = None):
        self.source = source
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.NEWS_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            }
        )

    def fetch_html(self) -> str:
        response = self.session.get(
            self.source["base_url"],
            timeout=settings.NEWS_FETCH_TIMEOUT,
        )
        response.raise_for_status()
        return response.text

    def collect(self) -> List[CollectedNews]:
        return self.parse(self.fetch_html())

    def parse(self, html: str) -> List[CollectedNews]:
        raise NotImplementedError

    def soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def make_item(
        self,
        *,
        title: str,
        published_at: Optional[datetime],
        href: str = "",
        excerpt: str = "",
        metadata: Optional[dict] = None,
    ) -> CollectedNews:
        normalized_title = normalize_text(title)
        normalized_excerpt = normalize_text(excerpt)[:1500]
        identity = "|".join(
            [
                self.source["code"],
                normalized_title.lower(),
                published_at.isoformat() if published_at else "",
            ]
        )
        external_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        canonical_url = (
            urljoin(self.source["base_url"], href)
            if href
            else f'{self.source["base_url"]}#item-{external_id}'
        )
        content_hash = hashlib.sha256(
            f"{normalized_title}|{normalized_excerpt}".encode("utf-8")
        ).hexdigest()
        return CollectedNews(
            external_id=external_id,
            canonical_url=canonical_url,
            title=normalized_title,
            published_at=published_at,
            source_excerpt=normalized_excerpt,
            content_hash=content_hash,
            raw_metadata=metadata or {},
        )

    @staticmethod
    def unique(items: Iterable[CollectedNews]) -> List[CollectedNews]:
        result = []
        seen = set()
        for item in items:
            if item.external_id in seen:
                continue
            seen.add(item.external_id)
            result.append(item)
        return result
