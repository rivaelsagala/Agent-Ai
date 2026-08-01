"""Collectors for Indonesia Stock Exchange public news pages."""
import re
from typing import List

from app.collectors.base import BaseCollector, normalize_text, parse_indonesian_datetime
from app.market_models import CollectedNews

TICKER_PATTERN = re.compile(r"\[([A-Z0-9-]{2,15})\]")
IGNORED_HEADINGS = {
    "keterbukaan informasi",
    "pengumuman",
    "laporan keuangan",
    "berita",
    "siaran pers",
    "loading...",
}


class IDXCollector(BaseCollector):
    def parse(self, html: str) -> List[CollectedNews]:
        if self.source["source_type"] == "idx_disclosure":
            return self._parse_disclosures(html)
        return self._parse_news(html)

    def _parse_disclosures(self, html: str) -> List[CollectedNews]:
        soup = self.soup(html)
        items = []
        for heading in soup.find_all(["h4", "h5", "h6"]):
            title = normalize_text(heading.get_text(" ", strip=True))
            if len(title) < 12 or title.lower() in IGNORED_HEADINGS:
                continue

            container = heading.parent
            container_text = normalize_text(container.get_text(" ", strip=True))
            published_at = parse_indonesian_datetime(container_text)
            if not published_at:
                previous_text = " ".join(
                    normalize_text(node.get_text(" ", strip=True))
                    for node in heading.find_all_previous(limit=3)
                )
                published_at = parse_indonesian_datetime(previous_text)
            if not published_at:
                continue

            link = container.find("a", href=True)
            tickers = TICKER_PATTERN.findall(title)
            items.append(
                self.make_item(
                    title=title,
                    published_at=published_at,
                    href=link["href"] if link else "",
                    excerpt=container_text,
                    metadata={"tickers": tickers, "kind": "disclosure"},
                )
            )
        return self.unique(items)

    def _parse_news(self, html: str) -> List[CollectedNews]:
        soup = self.soup(html)
        items = []
        for row in soup.find_all("tr"):
            text = normalize_text(row.get_text(" ", strip=True))
            published_at = parse_indonesian_datetime(text)
            link = row.find("a", href=True)
            if not published_at or not link:
                continue
            title = normalize_text(link.get_text(" ", strip=True))
            if len(title) < 15 or title.lower() in {"lihat detail", "detail"}:
                cell_texts = [
                    normalize_text(cell.get_text(" ", strip=True))
                    for cell in row.find_all(["td", "th"])
                ]
                candidates = [
                    value
                    for value in cell_texts
                    if len(value) >= 15 and not parse_indonesian_datetime(value)
                ]
                title = max(candidates, key=len, default="")
            if len(title) < 12:
                continue
            items.append(
                self.make_item(
                    title=title,
                    published_at=published_at,
                    href=link["href"],
                    excerpt=text,
                    metadata={"kind": "idx_news"},
                )
            )

        if items:
            return self.unique(items)

        for link in soup.find_all("a", href=True):
            title = normalize_text(link.get_text(" ", strip=True))
            parent_text = normalize_text(link.parent.get_text(" ", strip=True))
            published_at = parse_indonesian_datetime(parent_text)
            if len(title) >= 20 and published_at:
                items.append(
                    self.make_item(
                        title=title,
                        published_at=published_at,
                        href=link["href"],
                        excerpt=parent_text,
                        metadata={"kind": "idx_news"},
                    )
                )
        return self.unique(items)
