import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from deals import (Catalog, DealMonitor, Offer, Scan, gpu_name, load_limits,
                   parse_dospara_catalog, parse_dospara_detail, parse_oz_catalog,
                   parse_oz_detail, stock_flag)


LIMITS = {"RTX 5070 Ti": 280000, "RTX 5080": 320000, "RTX 5090": 280000}


def offer(source="galleria", gpu="RTX 5080", price=320000, available=True):
    return Offer(source, "MC100" if source == "galleria" else "00001",
                 "https://www.dospara.co.jp/TC30/MC100.html" if source == "galleria"
                 else "https://www.ozgaming-pcshop.com/view/item/00001",
                 "GALLERIA Test" if source == "galleria" else "Ryzen 7 9700X RTX5080",
                 "Ryzen 7 9700X", gpu, price, available)


def dospara_detail(gpu="RTX 5080", price="320000", stock="InStock", delivery="翌日出荷"):
    data = {"@type": "Product", "sku": "MC100-SN10", "name": "GALLERIA Test",
            "description": '<li class="spec-cpu">Ryzen 7 9700X</li><li class="spec-gpu">' + gpu + '</li>',
            "offers": {"priceCurrency": "JPY", "price": price,
                       "availability": "https://schema.org/" + stock}}
    return ('<h1>GALLERIA Test</h1><script type="application/ld+json">'
            + json.dumps(data) + '</script><div class="p-product-show-detail__delivery-line">'
            + delivery + '</div>')


class AdapterTests(unittest.TestCase):
    def test_gpu_names_and_laptop_exclusion(self):
        for raw, expected in (("GeForce RTX5070Ti 16G", "RTX 5070 Ti"),
                              ("NVIDIA RTX 5080 16GB", "RTX 5080"),
                              ("RTX 5080 Laptop GPU", ""), ("RX 9070XT", "")):
            self.assertEqual(gpu_name(raw), expected)
        with self.assertRaises(ValueError):
            gpu_name("RTX5070 / RTX5080")

    def test_stock_count_is_not_confused_with_out_of_stock(self):
        for raw, expected in (("在庫5個", True), ("在庫0個", False), ("在庫なし", False),
                              ("販売終了", False), ("不明", None)):
            self.assertIs(stock_flag(raw), expected)

    def test_dospara_listing_requires_identity_and_gpu_filter(self):
        html = '''<div class="product" data-pid="MC100">
          <p class="p-products-all-item-product__name__text"><a href="/TC30/MC100.html">GALLERIA Test</a></p>
          <div class="p-products-all-item-product__number">320,000</div>
          <table><tr><th>CPU</th><td>Ryzen 7 9700X</td></tr>
          <tr><th>グラフィックス</th><td>RTX 5080 16GB</td></tr></table></div>'''
        result = parse_dospara_catalog(html, "RTX 5080")
        self.assertEqual(result.offers[0].price, 320000)
        limited = parse_dospara_catalog(html.replace("/TC30/", "/TC917/"), "RTX 5080")
        self.assertEqual(limited.offers[0].item_id, "MC100")
        self.assertEqual(limited.offers[0].url, "https://www.dospara.co.jp/TC917/MC100.html")
        self.assertTrue(parse_dospara_detail(dospara_detail(), limited.offers[0]).available)
        with self.assertRaises(ValueError):
            parse_dospara_catalog(html, "RTX 5070 Ti")
        with self.assertRaises(ValueError):
            parse_dospara_catalog("<html>Access denied</html>", "RTX 5080")

    def test_dospara_listing_rejects_wrong_identity_and_untrusted_routes(self):
        template = '''<div class="product" data-pid="MC24683">
          <p class="p-products-all-item-product__name__text"><a href="{url}">GALLERIA Test</a></p>
          <div class="p-products-all-item-product__number">280,000</div>
          <table><tr><th>CPU</th><td>Core i7</td></tr>
          <tr><th>グラフィックス</th><td>RTX 5070 Ti</td></tr></table></div>'''
        for url in ("/TC917/MC99999.html", "https://example.com/TC917/MC24683.html",
                    "http://www.dospara.co.jp/TC917/MC24683.html",
                    "/TC917/not-a-product.html", "/other/MC24683.html",
                    "/TC917/MC24683-SN123.html"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_dospara_catalog(template.format(url=url), "RTX 5070 Ti")
        with self.assertRaisesRegex(ValueError, "Unexpected product path: /other/"):
            parse_dospara_catalog(template.format(url="/other/MC24683.html"), "RTX 5070 Ti")

    def test_oz_listing_parses_specs_and_retains_sorted_pagination(self):
        html = '''<ul class="category-item-list"><li class="item-list">
          <p class="item-list-name"><a href="/view/item/00001?category_page_id=all_items">Ryzen7 9700X RTX5080</a></p>
          <p class="item-list-price">￥320,000(税込)</p><p class="item-list-stock">在庫2個</p>
          <div class="item-spec-source" data-spec="CPU:Ryzen 7 9700X, GPU:RTX5080, メモリ:32GB"></div>
          </li></ul><a href="/view/category/all_items?page=2&amp;sort=price">2</a>'''
        result = parse_oz_catalog(html, "https://www.ozgaming-pcshop.com/view/category/all_items?sort=price")
        self.assertEqual(result.offers[0].gpu, "RTX 5080")
        self.assertEqual(result.offers[0].specs, "32GB / ")
        self.assertTrue(result.offers[0].available)
        self.assertEqual(result.next_url, "https://www.ozgaming-pcshop.com/view/category/all_items?page=2&sort=price")

    def test_dospara_detail_rechecks_price_gpu_and_stock(self):
        result = parse_dospara_detail(dospara_detail(price="330000"), offer())
        self.assertEqual(result.price, 330000)
        self.assertFalse(parse_dospara_detail(dospara_detail(stock="OutOfStock", delivery="在庫なし"), offer()).available)
        for html in (dospara_detail(gpu="RTX 5070"), dospara_detail(delivery="在庫なし"), "<html>404</html>"):
            with self.assertRaises(ValueError):
                parse_dospara_detail(html, offer())

    def test_oz_detail_rechecks_price_and_purchase_control(self):
        html = '''<h1 class="item-name">Ryzen7 9700X RTX5080</h1>
          <span data-id="makeshop-item-price:1">320,000</span><p class="item-stock">在庫あり</p>
          <a class="cart-btn instock on">カートに入れる</a>'''
        self.assertTrue(parse_oz_detail(html, offer("oz")).available)
        self.assertEqual(parse_oz_detail(html.replace("320,000", "330,000"), offer("oz")).price, 330000)
        with self.assertRaises(ValueError):
            parse_oz_detail(html.replace("instock on", "disabled"), offer("oz"))
        with self.assertRaises(ValueError):
            parse_oz_detail(html.replace("RTX5080", "RTX5070"), offer("oz"))


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.messages = []
        self.monitor = DealMonitor(self.path, LIMITS, self.messages.append)

    def accept(self, *offers, unresolved=None, errors=None):
        self.monitor.accept("galleria", Scan(list(offers), unresolved or set(), errors or [], 1, 20))

    def test_exact_user_price_limits(self):
        for gpu, maximum in LIMITS.items():
            for price, expected in ((maximum, 1), (maximum + 1, 0)):
                with self.subTest(gpu=gpu, price=price):
                    self.monitor.state["offers"] = {}
                    self.messages.clear()
                    self.accept(offer(gpu=gpu, price=price))
                    self.assertEqual(len(self.messages), expected)
        self.messages.clear()
        self.accept(offer(gpu="RTX 5070", price=100000))
        self.assertEqual(self.messages, [])

    def test_dedup_persists_and_only_further_price_drop_notifies(self):
        self.accept(offer())
        self.monitor = DealMonitor(self.path, LIMITS, self.messages.append)
        self.accept(offer())
        self.accept(offer(price=319000))
        self.accept(offer(price=319500))
        self.assertEqual(len(self.messages), 2)

    def test_stock_return_and_return_below_threshold_rearm(self):
        self.accept(offer())
        self.accept(offer(available=False))
        self.accept(offer())
        self.accept(offer(price=320001))
        self.accept(offer())
        self.assertEqual(len(self.messages), 3)

    def test_missing_listing_rearms_but_failed_detail_does_not(self):
        self.accept(offer())
        self.accept(unresolved={offer().key}, errors=["temporary HTTP 500"])
        self.accept(offer())
        self.assertEqual(len(self.messages), 1)
        self.accept()
        self.accept(offer())
        self.assertEqual(len(self.messages), 2)

    def test_discord_failure_retries_even_after_same_price_restock(self):
        self.accept(offer())
        self.accept(offer(available=False))
        def fail(_):
            raise RuntimeError("Discord returned HTTP 500")
        self.monitor.notify = fail
        with self.assertRaises(RuntimeError):
            self.accept(offer())
        self.monitor = DealMonitor(self.path, LIMITS, self.messages.append)
        self.accept(offer())
        self.assertEqual(len(self.messages), 2)

    def test_source_failure_does_not_clear_notified_matches(self):
        self.accept(offer())
        self.monitor.failure("oz", RuntimeError("HTTP 503"))
        self.accept(offer())
        self.assertEqual(len(self.messages), 1)
        self.assertEqual(self.monitor.state["sources"]["oz"]["status"], "error")

    def test_recovery_is_recorded_only_after_discord_accepts(self):
        self.monitor.state["sources"]["galleria"] = {
            "status": "error", "failures": 3, "errorNotified": True}
        def fail(_):
            raise RuntimeError("Discord returned HTTP 500")
        self.monitor.notify = fail
        with self.assertRaises(RuntimeError):
            self.accept()
        status = self.monitor.state["sources"]["galleria"]
        self.assertEqual(status["status"], "error")
        self.assertTrue(status["errorNotified"])
        self.monitor.notify = self.messages.append
        self.accept()
        self.assertEqual(len(self.messages), 1)
        self.assertIn("監視復旧", self.messages[0])
        self.assertEqual(status["status"], "ok")
        self.assertFalse(status["errorNotified"])
        self.assertEqual(status["failures"], 0)
        self.accept()
        self.assertEqual(len(self.messages), 1)


if __name__ == "__main__":
    unittest.main()
