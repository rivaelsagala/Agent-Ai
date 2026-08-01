import unittest
from unittest.mock import patch

from app.collectors.bi import BICollector
from app.collectors.idx import IDXCollector
from app.collectors.ojk import OJKCollector
from app.config import settings
from app.market_models import SendResult
from app.services.news_processor import NewsProcessor
from app.services.notification_service import NotificationService


def source(code, source_type, url="https://example.com/news"):
    return {
        "code": code,
        "source_type": source_type,
        "base_url": url,
    }


class CollectorTestCase(unittest.TestCase):
    def test_idx_disclosure_parser(self):
        html = """
        <div class="item">
          <span>24 Juli 2026 09:09:31</span>
          <h6>Perolehan Kontrak Penting [PTRO]</h6>
          <a href="/files/ptro.pdf">Lampiran</a>
        </div>
        """
        collector = IDXCollector(source("IDX", "idx_disclosure"))
        items = collector.parse(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].raw_metadata["tickers"], ["PTRO"])
        self.assertEqual(items[0].published_at.year, 2026)

    def test_idx_press_release_parser(self):
        html = """
        <table><tr>
          <td>17 Jul 2026</td>
          <td>BEI Perkuat Transparansi Pasar Modal Indonesia</td>
          <td><a href="/detail/123">Lihat Detail</a></td>
        </tr></table>
        """
        collector = IDXCollector(source("IDX_NEWS", "idx_news"))
        items = collector.parse(html)
        self.assertEqual(len(items), 1)
        self.assertIn("Transparansi", items[0].title)

    def test_ojk_and_bi_parsers(self):
        ojk_html = """
        <div>14 April 2026
          <a href="/id/berita-dan-kegiatan/siaran-pers/Pages/test.aspx">
            OJK Menerbitkan Kebijakan Pasar Modal Baru
          </a>
        </div>
        """
        bi_html = """
        <div>22 Juli 2026
          <a href="/id/publikasi/ruang-media/news-release/Pages/test.aspx">
            BI Rate Tetap untuk Menjaga Stabilitas
          </a>
        </div>
        """
        self.assertEqual(
            len(OJKCollector(source("OJK", "ojk")).parse(ojk_html)),
            1,
        )
        self.assertEqual(
            len(BICollector(source("BI", "bank_indonesia")).parse(bi_html)),
            1,
        )


class ProcessorTestCase(unittest.TestCase):
    def test_local_fallback_detects_ticker_and_high_impact(self):
        news = {
            "title": "Suspensi perdagangan saham PTRO",
            "source_excerpt": "Bursa menghentikan sementara perdagangan.",
            "source_name": "BEI",
            "raw_metadata": {"tickers": ["PTRO"]},
        }
        with patch.object(settings, "OPENROUTER_API_KEY", ""):
            result = NewsProcessor().analyze(news, ["PTRO", "BBCA"])
        self.assertEqual(result.category, "market_event")
        self.assertEqual(result.impact_level, 5)
        self.assertEqual(result.tickers, ["PTRO"])


class FakeSender:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def send(self, destination, message, config):
        if self.should_fail:
            raise RuntimeError("provider unavailable")
        return SendResult(provider_message_id="message-1")


class FakeRepository:
    def __init__(self):
        self.sent = []
        self.failed = []

    def claim_pending_deliveries(self, limit):
        return [
            {
                "id": "delivery-1",
                "channel_type": "telegram",
                "destination": "123",
                "message_text": "Market alert",
                "channel_config": {},
                "attempts": 1,
            }
        ]

    def mark_delivery_sent(self, delivery_id, provider_message_id):
        self.sent.append((delivery_id, provider_message_id))

    def mark_delivery_failed(self, delivery_id, error, attempts):
        self.failed.append((delivery_id, error, attempts))


class NotificationTestCase(unittest.TestCase):
    def test_dispatch_marks_delivery_sent(self):
        repository = FakeRepository()
        service = NotificationService(
            repository,
            senders={"telegram": FakeSender()},
        )
        result = service.dispatch_pending()
        self.assertEqual(result["sent"], 1)
        self.assertEqual(repository.sent, [("delivery-1", "message-1")])

    def test_dispatch_marks_provider_failure(self):
        repository = FakeRepository()
        service = NotificationService(
            repository,
            senders={"telegram": FakeSender(should_fail=True)},
        )
        result = service.dispatch_pending()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(repository.failed[0][0], "delivery-1")

    def test_scheduler_build(self):
        from app.scheduler.jobs import build_scheduler
        scheduler = build_scheduler()
        self.assertIsNotNone(scheduler)


if __name__ == "__main__":
    unittest.main()

