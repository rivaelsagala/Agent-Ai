"""Collectors for Indonesia Stock Exchange public news pages."""
import re
from typing import List

from app.collectors.base import BaseCollector, normalize_text, parse_indonesian_datetime
from app.market_models import CollectedNews

from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime

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
    def collect(self) -> List[CollectedNews]:
        try:
            resp = self.session.get(self.source["base_url"], timeout=5)
            resp.raise_for_status()
            items = self.parse(resp.text)
            if items:
                return items
            return self._fetch_fallback_rss()
        except Exception:
            return self._fetch_fallback_rss()

    def _fetch_fallback_rss(self) -> List[CollectedNews]:
        """Fallback to official IDX Channel RSS feed if idx.co.id is blocked by Cloudflare (403)."""
        url = "https://www.idxchannel.com/rss"
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "xml")
            items = []
            for node in soup.find_all("item"):
                title_node = node.find("title")
                link_node = node.find("link")
                pub_node = node.find("pubDate")
                desc_node = node.find("description")

                title = normalize_text(title_node.get_text()) if title_node else ""
                href = link_node.get_text(strip=True) if link_node else ""
                pub_str = pub_node.get_text(strip=True) if pub_node else ""
                excerpt = normalize_text(desc_node.get_text()) if desc_node else title

                published_at = None
                if pub_str:
                    try:
                        published_at = parsedate_to_datetime(pub_str)
                    except Exception:
                        published_at = parse_indonesian_datetime(pub_str)

                if title and href and len(title) > 10:
                    items.append(
                        self.make_item(
                            title=title,
                            published_at=published_at,
                            href=href,
                            excerpt=excerpt,
                            metadata={"kind": "idx_channel_rss"},
                        )
                    )
            return self.unique(items)
        except Exception:
            return []

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
