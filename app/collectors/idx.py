"""Collectors for Indonesia Stock Exchange news via IDX Channel RSS feed."""
from typing import List

from app.collectors.base import BaseCollector, normalize_text, parse_indonesian_datetime
from app.market_models import CollectedNews

from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from loguru import logger


class IDXCollector(BaseCollector):
    def collect(self) -> List[CollectedNews]:
        """Fetch news directly from IDX Channel RSS feed (idx.co.id diblokir Cloudflare 403)."""
        url = "https://www.idxchannel.com/rss"
        logger.info(f"IDXCollector fetching RSS feed from: {url}")
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
            res = self.unique(items)
            logger.info(f"Successfully collected {len(res)} items from IDX Channel RSS feed.")
            return res
        except Exception as e:
            logger.error(f"IDXCollector RSS fetch failed: {e}")
            return []
