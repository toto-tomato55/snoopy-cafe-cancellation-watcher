import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


PRODUCT_URL = "https://www.dospara.co.jp/TC30/MC21585.html"
PRODUCT_MODEL = "XMC9A-R5x-GD"
UNAVAILABLE = {"OutOfStock", "SoldOut", "Discontinued"}
STOCK_SELECTOR = ".p-product-show-detail__delivery-line"


class ProductPageMissing(RuntimeError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"商品ページが見つかりません（HTTP {status_code}）")


def timestamp():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Stock:
    name: str
    sku: str
    price: int
    available: bool
    availability: str
    delivery: str

    @property
    def sale_ended(self):
        return self.availability == "Discontinued" or any(
            word in self.delivery for word in ("販売終了", "販売を終了")
        )


def products(value):
    if isinstance(value, list):
        for item in value:
            yield from products(item)
    elif isinstance(value, dict):
        kinds = value.get("@type", [])
        if kinds == "Product" or isinstance(kinds, list) and "Product" in kinds:
            yield value
        if "@graph" in value:
            yield from products(value["@graph"])


def parse_stock(html):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            candidates.extend(products(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    matching = [p for p in candidates if PRODUCT_MODEL.lower() in p.get("name", "").lower()
                and re.fullmatch(r"MC21585(?:-SN\d+)?", p.get("sku", ""))]
    if len(matching) != 1:
        raise ValueError("Expected product MC21585 was not uniquely identified")
    product = matching[0]
    heading = soup.find("h1")
    if not heading or PRODUCT_MODEL.lower() not in heading.get_text().lower():
        raise ValueError("Product heading is missing or does not match")
    offer = product.get("offers", {})
    if not isinstance(offer, dict) or offer.get("priceCurrency") != "JPY":
        raise ValueError("Expected one JPY product offer")
    price = Decimal(str(offer.get("price", "0")))
    if not price.is_finite() or price <= 0 or price != price.to_integral_value():
        raise ValueError("Product price is invalid")
    availability = str(offer.get("availability", "")).rstrip("/").rsplit("/", 1)[-1]
    if availability not in UNAVAILABLE | {"InStock"}:
        raise ValueError("Unknown or unsupported availability: " + availability[:80])
    delivery = " ".join(node.get_text(" ", strip=True) for node in soup.select(STOCK_SELECTOR))
    if not delivery:
        raise ValueError("Product delivery/stock area is missing")
    unavailable_text = any(word in delivery for word in ("在庫なし", "売り切れ", "販売終了", "販売を終了"))
    available_text = bool(re.search(r"出荷|在庫あり|在庫有", delivery))
    available = availability == "InStock"
    if (available and (unavailable_text or not available_text)) or (not available and (available_text or not unavailable_text)):
        raise ValueError("Structured stock and delivery text disagree")
    return Stock(product["name"], product["sku"], int(price), available, availability, delivery)


def fetch_stock(session, url=PRODUCT_URL):
    response = session.get(url, timeout=(10, 20), headers={
        "User-Agent": "GalleriaStockMonitor/1.0 (personal availability check)",
        "Accept-Language": "ja,en;q=0.5",
        "Cache-Control": "no-cache",
    })
    if urlparse(response.url).hostname != "www.dospara.co.jp":
        raise ValueError("Product redirected to an unexpected host")
    if response.status_code in (404, 410):
        raise ProductPageMissing(response.status_code)
    response.raise_for_status()
    response.encoding = "utf-8"
    return parse_stock(response.text)


def send_discord(session, webhook, content):
    # Do not include requests exception text: it can contain the webhook token.
    try:
        response = session.post(webhook, json={"content": content, "allowed_mentions": {"parse": []}},
                                timeout=(10, 20))
        if response.status_code not in (200, 204):
            raise RuntimeError("Discord returned HTTP " + str(response.status_code))
    except requests.RequestException:
        raise RuntimeError("Discord network request failed") from None


def read_state(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise ValueError("State file must contain an object")
    return value


def write_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    pending.replace(path)


class Monitor:
    def __init__(self, state_path, fetch, notify, url=PRODUCT_URL, interval=60):
        self.state_path = Path(state_path)
        self.fetch = fetch
        self.notify = notify
        self.url = url
        self.interval = interval
        self.state = read_state(state_path)
        if self.state.get("productUrl") != url:
            self.state = {"productUrl": url}

    def save(self):
        write_state(self.state_path, self.state)

    def check_once(self):
        self.state["lastAttemptAt"] = timestamp()
        stock = self.fetch()
        self.state.update(lastSuccessAt=timestamp(), lastStock=asdict(stock),
                          monitorStatus="sale_ended" if stock.sale_ended else "checking_stock")
        self.save()
        logging.info("stock_check sku=%s price=%s availability=%s delivery=%s",
                     stock.sku, stock.price, stock.availability, stock.delivery)
        page_returned = self.state.get("pageMissing", False)
        if page_returned:
            self.notify("【商品ページ再掲載】GALLERIAの商品ページを再び確認できました。\n"
                        + f"現在: {stock.delivery}\n表示価格: {stock.price:,}円（税込）\n" + self.url)
            self.state.update(pageMissing=False, pageMissingNotified=False, errorNotified=False)
            self.save()
        elif self.state.get("errorNotified"):
            self.notify("【監視復旧】GALLERIAの在庫確認が正常に戻りました。\n" + self.url)
            self.state["errorNotified"] = False
            self.save()
        if stock.sale_ended and not self.state.get("saleEndedNotified"):
            if not page_returned:
                self.notify("【販売終了表示】GALLERIAの商品ページが「販売終了」に変わりました。\n"
                            + "現在購入できません。販売再開の確認は1分ごとに継続します。\n" + self.url)
            self.state["saleEndedNotified"] = True
            self.save()
        elif not stock.sale_ended:
            self.state["saleEndedNotified"] = False
        if not stock.available:
            self.state["availabilityNotified"] = False
            self.save()
        if stock.available and not self.state.get("availabilityNotified"):
            self.notify("【在庫あり】" + stock.name + "\n"
                        + f"表示価格: {stock.price:,}円（税込）\n状態: {stock.delivery}\n"
                        + "購入ページ: " + self.url + "\n在庫・価格は購入時に再確認してください。")
            self.state["availabilityNotified"] = True
            self.state["lastAvailabilityNotificationAt"] = timestamp()
            self.save()
        if not self.state.get("startupNotified"):
            self.notify("【監視開始・接続テスト】S-monitorでGALLERIAの在庫監視を開始しました。\n"
                        + stock.name + f"\n間隔: {self.interval}秒\n表示価格: {stock.price:,}円（税込）\n"
                        + "現在: " + stock.delivery + "\n在庫復活時にこのチャンネルへ通知します。\n" + self.url)
            self.state["startupNotified"] = True
            self.save()
        self.state["consecutiveFailures"] = 0
        self.save()
        return stock

    def record_page_missing(self, error):
        self.state.update(pageMissing=True, monitorStatus="page_missing",
                          lastPageMissingAt=timestamp(), lastHttpStatus=error.status_code)
        self.save()
        logging.warning("product_page_missing status=%s; stock is unknown", error.status_code)
        if not self.state.get("pageMissingNotified"):
            previous_delivery = self.state.get("lastStock", {}).get("delivery", "未確認")
            self.notify("【商品ページ掲載なし】GALLERIAの商品ページが見つかりません。\n"
                        + f"HTTP {error.status_code} / 最後に確認した表示: {previous_delivery}\n"
                        + "現在の在庫は確認できません。再掲載を1分ごとに確認し、"
                        + "ページ復活・在庫復活時に通知します。\n" + self.url)
            self.state.update(pageMissingNotified=True, errorNotified=False)
        self.state["consecutiveFailures"] = 0
        self.save()

    def record_failure(self, error):
        failures = self.state.get("consecutiveFailures", 0) + 1
        self.state.update(consecutiveFailures=failures, lastErrorAt=timestamp(), lastError=str(error),
                          monitorStatus="error")
        self.save()
        logging.error("stock_check_failed count=%s error=%s", failures, error)
        if failures >= 3 and time.time() - self.state.get("lastErrorNotificationEpoch", 0) >= 3600:
            try:
                self.notify("【監視エラー】GALLERIAの在庫確認または通知に3回以上失敗しています。\n"
                            + "監視は再試行中です。在庫なしとは判定していません。\n"
                            + str(error)[:300] + "\n" + self.url)
            except Exception:
                logging.error("error_notification_failed")
                return
            self.state.update(errorNotified=True, lastErrorNotificationEpoch=time.time())
            self.save()
