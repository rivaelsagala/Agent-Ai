"""Collector for Bloomberg market and economics news via RSS feeds."""
from typing import List

from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from loguru import logger

from app.collectors.base import BaseCollector, normalize_text, parse_indonesian_datetime
from app.market_models import CollectedNews

BLOOMBERG_RSS_FEEDS = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://feeds.bloomberg.com/economics/news.rss",
]


class BloombergCollector(BaseCollector):
    def collect(self) -> List[CollectedNews]:
        """Fetch news from Bloomberg RSS feeds (markets + economics)."""
        all_items: List[CollectedNews] = []
        for url in BLOOMBERG_RSS_FEEDS:
            logger.info(f"BloombergCollector fetching RSS from: {url}")
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
                                metadata={"kind": "bloomberg_rss", "feed": url},
                            )
                        )
                logger.info(f"Collected {len(items)} items from: {url}")
                all_items.extend(items)
            except Exception as e:
                logger.error(f"BloombergCollector failed for {url}: {e}")

        res = self.unique(all_items)
        logger.info(f"BloombergCollector total unique items: {len(res)}")
        return res
