"""Map database source types to collector implementations."""
from app.collectors.bi import BICollector
from app.collectors.bloomberg import BloombergCollector
from app.collectors.idx import IDXCollector
from app.collectors.ojk import OJKCollector


class CollectorRegistry:
    COLLECTORS = {
        "idx_disclosure": IDXCollector,
        "idx_news": IDXCollector,
        "ojk": OJKCollector,
        "bank_indonesia": BICollector,
        "bloomberg": BloombergCollector,
    }

    def create(self, source: dict):
        collector_class = self.COLLECTORS.get(source["source_type"])
        if not collector_class:
            raise ValueError(f"Unsupported source type: {source['source_type']}")
        return collector_class(source)
