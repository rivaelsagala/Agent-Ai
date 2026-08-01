"""Collector for OJK press releases."""
from typing import List

from app.collectors.base import BaseCollector, normalize_text, parse_indonesian_datetime
from app.market_models import CollectedNews


class OJKCollector(BaseCollector):
    def parse(self, html: str) -> List[CollectedNews]:
        soup = self.soup(html)
        items = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/siaran-pers/" not in href.lower():
                continue
            title = normalize_text(link.get_text(" ", strip=True))
            if len(title) < 20:
                continue
            container_text = normalize_text(link.parent.get_text(" ", strip=True))
            published_at = parse_indonesian_datetime(container_text)
            items.append(
                self.make_item(
                    title=title,
                    published_at=published_at,
                    href=href,
                    excerpt=container_text,
                    metadata={"kind": "ojk_press_release"},
                )
            )
        return self.unique(items)
