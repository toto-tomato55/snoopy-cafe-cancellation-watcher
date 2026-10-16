import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from stock_monitor import Monitor, PRODUCT_URL, ProductPageMissing, Stock, fetch_stock, parse_stock, read_state


def page(availability="OutOfStock", delivery="在庫なし", sku="MC21585-SN4438"):
    product = {"@type": "Product", "name": "GALLERIA XMC9A-R5x-GD 動画配信向けモデル", "sku": sku,
               "offers": {"priceCurrency": "JPY", "price": "314980", "availability": "https://schema.org/" + availability}}
    return ('<h1>GALLERIA XMC9A-R5x-GD 動画配信向けモデル</h1>'
            + '<script type="application/ld+json">' + json.dumps(product) + '</script>'
            + '<div class="p-product-show-detail__delivery-line">' + delivery + '</div>')


class ParserTests(unittest.TestCase):
    def test_sold_out(self):
        result = parse_stock(page())
        self.assertFalse(result.available)
        self.assertEqual(result.price, 314980)

    def test_in_stock(self):
        self.assertTrue(parse_stock(page("InStock", "翌日出荷")).available)

    def test_sales_ended_is_separate_from_sold_out(self):
        result = parse_stock(page("OutOfStock", "販売終了"))
        self.assertTrue(result.sale_ended)
        self.assertFalse(result.available)
        self.assertFalse(parse_stock(page()).sale_ended)

    def test_http_missing_is_not_stock_and_server_errors_remain_errors(self):
        for status in (404, 410):
            session = Mock()
            session.get.return_value.status_code = status
            session.get.return_value.url = PRODUCT_URL
            with self.subTest(status=status), self.assertRaises(ProductPageMissing):
                fetch_stock(session)
            session.get.return_value.raise_for_status.assert_not_called()
        session = Mock()
        session.get.return_value.status_code = 500
        session.get.return_value.url = PRODUCT_URL
        session.get.return_value.raise_for_status.side_effect = requests.HTTPError("HTTP 500")
        with self.assertRaises(requests.HTTPError):
            fetch_stock(session)

    def test_disagreement_unknown_wrong_product_and_block_page_fail(self):
        for html in (page("InStock", "在庫なし"), page("OutOfStock", "翌日出荷"),
                     page("PreOrder", "予約受付"), page(sku="MC99999"),
                     page(delivery=""), "<html>Access denied</html>"):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_stock(html)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "status.json"
        self.stock = Stock("GALLERIA XMC9A-R5x-GD", "MC21585-SN4438", 314980, False, "OutOfStock", "在庫なし")
        self.messages = []
        self.monitor = Monitor(self.path, lambda: self.stock, self.messages.append)

    def make_available(self):
        self.stock = Stock(self.stock.name, self.stock.sku, self.stock.price, True, "InStock", "翌日出荷")

    def test_restock_notifies_once_and_state_survives_restart(self):
        self.monitor.check_once()
        self.make_available()
        self.monitor.check_once()
        self.monitor.check_once()
        Monitor(self.path, lambda: self.stock, self.messages.append).check_once()
        self.assertEqual(len(self.messages), 2)
        self.assertIn("【在庫あり】", self.messages[1])

    def test_notification_failure_remains_retryable_and_alerts(self):
        self.monitor.check_once()
        self.make_available()
        def fail(_):
            raise RuntimeError("Discord returned HTTP 500")
        self.monitor.notify = fail
        for _ in range(3):
            with self.assertRaises(RuntimeError) as caught:
                self.monitor.check_once()
            self.monitor.record_failure(caught.exception)
        self.assertFalse(read_state(self.path)["availabilityNotified"])
        self.assertEqual(read_state(self.path)["consecutiveFailures"], 3)
        self.monitor.notify = self.messages.append
        self.monitor.check_once()
        self.assertTrue(read_state(self.path)["availabilityNotified"])

    def test_unknown_does_not_rearm_notification_and_error_is_throttled(self):
        self.make_available()
        self.monitor.check_once()
        for _ in range(5):
            self.monitor.record_failure(ValueError("Unknown stock"))
        self.assertTrue(read_state(self.path)["availabilityNotified"])
        self.assertEqual(sum("【監視エラー】" in message for message in self.messages), 1)
        self.monitor.check_once()
        self.assertIn("【監視復旧】", self.messages[-1])
        self.assertEqual(sum("【在庫あり】" in message for message in self.messages), 1)

    def test_missing_preserves_last_stock_and_notifies_once_across_restart(self):
        self.make_available()
        self.monitor.check_once()
        last_success = read_state(self.path)["lastSuccessAt"]
        self.monitor.record_page_missing(ProductPageMissing(404))
        self.monitor.record_page_missing(ProductPageMissing(404))
        restored = Monitor(self.path, lambda: self.stock, self.messages.append)
        restored.record_page_missing(ProductPageMissing(410))
        saved = read_state(self.path)
        self.assertEqual(saved["lastSuccessAt"], last_success)
        self.assertTrue(saved["availabilityNotified"])
        self.assertEqual(saved["monitorStatus"], "page_missing")
        self.assertEqual(sum("【商品ページ掲載なし】" in m for m in self.messages), 1)
        restored.check_once()
        restored.check_once()
        self.assertEqual(sum("【商品ページ再掲載】" in m for m in self.messages), 1)
        self.assertEqual(sum("【在庫あり】" in m for m in self.messages), 1)

    def test_missing_notification_is_retried_after_discord_failure(self):
        self.monitor.check_once()
        def fail(_):
            raise RuntimeError("Discord returned HTTP 500")
        self.monitor.notify = fail
        with self.assertRaises(RuntimeError):
            self.monitor.record_page_missing(ProductPageMissing(404))
        self.assertFalse(read_state(self.path).get("pageMissingNotified", False))
        self.monitor.notify = self.messages.append
        self.monitor.record_page_missing(ProductPageMissing(404))
        self.assertTrue(read_state(self.path)["pageMissingNotified"])

    def test_sales_ended_notifies_on_change_and_returned_page_is_not_stock(self):
        self.monitor.check_once()
        self.stock = Stock(self.stock.name, self.stock.sku, self.stock.price, False, "OutOfStock", "販売終了")
        self.monitor.check_once()
        self.monitor.check_once()
        self.assertEqual(sum("【販売終了表示】" in m for m in self.messages), 1)
        self.monitor.record_page_missing(ProductPageMissing(404))
        self.monitor.check_once()
        self.assertIn("現在: 販売終了", self.messages[-1])
        self.assertEqual(sum("【在庫あり】" in m for m in self.messages), 0)


if __name__ == "__main__":
    unittest.main()
