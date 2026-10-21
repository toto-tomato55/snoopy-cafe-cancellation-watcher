import json
import logging
import os
import re
import signal
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from stock_monitor import products, read_state, send_discord, timestamp, write_state


DOSPARA = "https://www.dospara.co.jp"
OZ = "https://www.ozgaming-pcshop.com"
GRID = DOSPARA + "/on/demandware.store/Sites-dospara-Site/ja_JP/Search-UpdateGrid"


def text(node):
    return node.get_text(" ", strip=True) if node else ""


def gpu_name(value):
    value = unicodedata.normalize("NFKC", value)
    if re.search(r"laptop|ノート", value, re.I):
        return ""
    matches = re.findall(r"\bRTX\s*(\d{4})\s*(TI(?:\s*SUPER)?|SUPER)?\b", value, re.I)
    names = {"RTX " + number + (" " + suffix.upper().replace("TI", "Ti") if suffix else "")
             for number, suffix in matches}
    if len(names) > 1:
        raise ValueError("Multiple GPUs in a base configuration")
    return next(iter(names), "")


def yen(value):
    numbers = re.findall(r"\d[\d,]*", unicodedata.normalize("NFKC", value))
    if len(numbers) != 1:
        raise ValueError("Missing or ambiguous product price")
    result = int(numbers[0].replace(",", ""))
    if result <= 0:
        raise ValueError("Invalid product price")
    return result


def stock_flag(value):
    if any(word in value for word in ("在庫なし", "売り切れ", "販売終了", "販売を終了", "SOLD OUT")):
        return False
    count = re.search(r"在庫\s*(\d+)\s*個", value)
    if count:
        return int(count[1]) > 0
    if re.search(r"在庫あり|出荷|最短", value):
        return True
    return None


def safe_url(base, value, path_pattern=None):
    result = urljoin(base, value)
    parsed = urlparse(result)
    if parsed.scheme != "https" or parsed.netloc != urlparse(base).netloc:
        raise ValueError("Unexpected store URL")
    if path_pattern and not re.fullmatch(path_pattern, parsed.path):
        raise ValueError("Unexpected product path: " + parsed.path[:180])
    return result


@dataclass(frozen=True)
class Offer:
    source: str
    item_id: str
    url: str
    name: str
    cpu: str
    gpu: str
    price: int
    available: bool | None
    specs: str = ""

    @property
    def key(self):
        return self.source + ":" + self.item_id


@dataclass
class Catalog:
    offers: list
    prices: list
    next_url: str | None


@dataclass
class Scan:
    offers: list
    unresolved: set
    errors: list
    pages: int
    listed: int


def parse_dospara_catalog(html, expected_gpu):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".product[data-pid]")
    if not rows:
        raise ValueError("GALLERIA product grid is missing")
    offers, prices = [], []
    for row in rows:
        price = yen(text(row.select_one(".p-products-all-item-product__number")))
        prices.append(price)
        specs = {text(tr.find("th")): text(tr.find("td")) for tr in row.select("table tr")}
        gpu = gpu_name(specs.get("グラフィックス", ""))
        if gpu != expected_gpu:
            raise ValueError("GALLERIA GPU filter no longer matches its results")
        link = row.select_one(".p-products-all-item-product__name__text a[href]")
        name = text(link)
        if not name.startswith("GALLERIA "):
            continue
        # Catalog membership and product identity do not depend on the URL's category.
        url = safe_url(DOSPARA, link["href"], r"/TC\d+/MC\d+\.html")
        item_id = row["data-pid"]
        if urlparse(url).path.rsplit("/", 1)[-1] != item_id + ".html" or not specs.get("CPU"):
            raise ValueError("GALLERIA product identity/specifications changed")
        offers.append(Offer("galleria", item_id, url, name, specs["CPU"], gpu, price,
                            stock_flag(text(row.select_one(".p-products-all-item-product__price"))),
                            " / ".join(specs.get(k, "") for k in ("メモリ", "ストレージ"))))
    more = soup.select_one(".show-more[data-url]")
    return Catalog(offers, prices, more.get("data-url") if more else None)


def parse_oz_catalog(html, current_url):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".category-item-list > li.item-list")
    if not rows:
        raise ValueError("OZ product list is missing")
    offers, prices = [], []
    for row in rows:
        price = yen(text(row.select_one(".item-list-price")))
        prices.append(price)
        link = row.select_one(".item-list-name a[href]")
        name = text(link)
        spec_node = row.select_one(".item-spec-source[data-spec]")
        specs = {key.strip(): value.strip() for key, value in (
            part.split(":", 1) for part in spec_node["data-spec"].split(",") if ":" in part
        )} if spec_node else {}
        cpu = specs.get("CPU", "").strip()
        gpu = gpu_name(specs.get("GPU", "") or name)
        if not cpu or not gpu:
            continue
        url = safe_url(OZ, link["href"], r"/view/item/\d+").split("?", 1)[0]
        item_id = urlparse(url).path.rsplit("/", 1)[-1]
        offers.append(Offer("oz", item_id, url, name, cpu, gpu, price,
                            stock_flag(text(row.select_one(".item-list-stock"))),
                            " / ".join(specs.get(k, "") for k in ("メモリ", "SSD"))))
    current_page = int(parse_qs(urlparse(current_url).query).get("page", ["1"])[0])
    next_url = None
    for link in soup.select("a[href]"):
        candidate = urljoin(OZ, link["href"])
        query = parse_qs(urlparse(candidate).query)
        if query.get("page") == [str(current_page + 1)] and query.get("sort") == ["price"]:
            next_url = safe_url(OZ, candidate, r"/view/category/all_items")
            break
    return Catalog(offers, prices, next_url)


def parse_dospara_detail(html, candidate):
    soup = BeautifulSoup(html, "html.parser")
    matches = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            matches.extend(p for p in products(json.loads(script.get_text()))
                           if re.fullmatch(re.escape(candidate.item_id) + r"(?:-SN\d+)?", p.get("sku", "")))
        except (ValueError, TypeError):
            continue
    if len(matches) != 1:
        raise ValueError("GALLERIA detail product identity is missing")
    product = matches[0]
    if not product.get("name", "").startswith("GALLERIA ") or text(soup.find("h1")) != product["name"]:
        raise ValueError("GALLERIA detail heading disagrees with product data")
    specs = BeautifulSoup(product.get("description", ""), "html.parser")
    gpu = gpu_name(text(specs.select_one(".spec-gpu")))
    cpu = text(specs.select_one(".spec-cpu"))
    if gpu != candidate.gpu or not cpu:
        raise ValueError("GALLERIA base configuration no longer matches the listing")
    offer = product.get("offers", {})
    if not isinstance(offer, dict) or offer.get("priceCurrency") != "JPY":
        raise ValueError("GALLERIA detail currency changed")
    price = yen(str(offer.get("price", "")))
    availability = str(offer.get("availability", "")).rsplit("/", 1)[-1]
    delivery = stock_flag(" ".join(text(n) for n in soup.select(".p-product-show-detail__delivery-line")))
    if availability not in ("InStock", "OutOfStock", "SoldOut", "Discontinued") or delivery is None:
        raise ValueError("GALLERIA detail availability is unknown")
    available = availability == "InStock"
    if available != delivery:
        raise ValueError("GALLERIA detail stock signals disagree")
    return replace(candidate, name=product["name"], cpu=cpu, price=price, available=available)


def parse_oz_detail(html, candidate):
    soup = BeautifulSoup(html, "html.parser")
    name = text(soup.select_one("h1.item-name"))
    gpu = gpu_name(name)
    cpu_key = re.sub(r"[^a-z0-9]", "", candidate.cpu.lower())
    name_key = re.sub(r"[^a-z0-9]", "", name.lower())
    if gpu != candidate.gpu or not cpu_key or cpu_key not in name_key:
        raise ValueError("OZ detail base configuration no longer matches the listing")
    price = yen(text(soup.select_one('[data-id="makeshop-item-price:1"]')))
    available = stock_flag(text(soup.select_one("p.item-stock")))
    if available is None:
        raise ValueError("OZ detail stock is unknown")
    if available and not soup.select_one("a.cart-btn.instock.on"):
        raise ValueError("OZ purchase control is unavailable")
    return replace(candidate, name=name, price=price, available=available)


class Store:
    def __init__(self, name, limits):
        self.name = name
        self.limits = limits
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PcDealMonitor/1.0 (personal price alerts)",
                                     "Accept-Language": "ja,en;q=0.5", "Cache-Control": "no-cache"})

    def get(self, url):
        base = DOSPARA if self.name == "galleria" else OZ
        safe_url(base, url)
        response = self.session.get(url, timeout=(5, 18))
        safe_url(base, response.url)
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text

    def scan(self):
        pages, listed, candidates = 0, 0, {}
        groups = list(self.limits) if self.name == "galleria" else [None]
        for gpu in groups:
            url = GRID + "?" + urlencode({"cgid": "TC30", "prefn1": "txGraphicFilter",
                                           "prefv1": "GeForce " + gpu, "srule": "03", "start": 0, "sz": 20}) if gpu else OZ + "/view/category/all_items?sort=price"
            cap = self.limits[gpu] if gpu else max(self.limits.values())
            previous_price, seen_urls = 0, set()
            for _ in range(12):
                if url in seen_urls:
                    raise ValueError("Store pagination repeated a page")
                seen_urls.add(url)
                html = self.get(url)
                page = parse_dospara_catalog(html, gpu) if gpu else parse_oz_catalog(html, url)
                pages += 1
                listed += len(page.prices)
                for price in page.prices:
                    if price < previous_price:
                        raise ValueError("Store price sorting changed; cannot safely stop pagination")
                    previous_price = price
                for item in page.offers:
                    if item.gpu in self.limits and item.price <= self.limits[item.gpu]:
                        candidates[item.key] = item
                if page.prices[-1] > cap or not page.next_url:
                    break
                url = safe_url(DOSPARA if gpu else OZ, page.next_url)
                if gpu:
                    query = parse_qs(urlparse(url).query)
                    if query.get("srule") != ["03"] or query.get("prefv1") != ["GeForce " + gpu]:
                        raise ValueError("GALLERIA pagination lost its filter/sort")
            else:
                raise ValueError("Store catalog exceeded the configured page limit")
        offers, unresolved, errors = [], set(), []
        for item in candidates.values():
            if item.available is False:
                offers.append(item)
                continue
            try:
                html = self.get(item.url)
                offers.append(parse_dospara_detail(html, item) if self.name == "galleria" else parse_oz_detail(html, item))
            except Exception as error:
                unresolved.add(item.key)
                errors.append(item.url + ": " + str(error)[:200])
        return Scan(offers, unresolved, errors, pages, listed)


class DealMonitor:
    def __init__(self, state_file, limits, notify):
        self.path = Path(state_file)
        self.limits = limits
        self.notify = notify
        self.state = read_state(self.path)
        self.state.setdefault("offers", {})
        self.state.setdefault("sources", {})

    def save(self):
        write_state(self.path, self.state)

    def failure(self, source, error):
        status = self.state["sources"].setdefault(source, {})
        status.update(lastAttemptAt=timestamp(), lastError=str(error)[:500], status="error")
        status["failures"] = status.get("failures", 0) + 1
        self.save()
        logging.error("deal_scan_failed source=%s failures=%s error=%s", source, status["failures"], error)
        if status["failures"] >= 3 and time.time() - status.get("lastErrorNotice", 0) >= 3600:
            try:
                self.notify(f"【お得PC監視エラー】{source}の確認に3回以上失敗しています。\n"
                            + "再試行を継続します。他店の確認は独立して継続します。\n" + str(error)[:400])
            except Exception:
                logging.error("deal_error_notification_failed source=%s", source)
                return
            status.update(lastErrorNotice=time.time(), errorNotified=True)
            self.save()

    def accept(self, source, scan):
        status = self.state["sources"].setdefault(source, {})
        observed = {item.key for item in scan.offers} | scan.unresolved
        for key, saved in self.state["offers"].items():
            if saved.get("source") == source and key not in observed:
                saved.update(armed=True, eligible=False)
        matches = 0
        for item in scan.offers:
            saved = self.state["offers"].setdefault(item.key, {"armed": True})
            eligible = item.available is True and item.gpu in self.limits and item.price <= self.limits[item.gpu]
            saved.update(asdict(item), eligible=eligible, lastSeenAt=timestamp())
            if not eligible:
                saved["armed"] = True
                continue
            matches += 1
            if saved.get("armed", True) or item.price < saved.get("lastNotifiedPrice", float("inf")):
                self.save()
                self.notify("【お得PC・条件一致】" + ("GALLERIA" if source == "galleria" else "OZ Gaming")
                            + "\n" + item.name[:180] + f"\n本体価格: {item.price:,}円（税込）"
                            + f"\nCPU: {item.cpu}\nGPU: {item.gpu}\n" + item.specs[:160]
                            + "\n" + item.url + "\n在庫・送料・構成は購入時に確認してください。")
                saved.update(armed=False, lastNotifiedPrice=item.price, lastNotifiedAt=timestamp())
                self.save()
        status.update(lastAttemptAt=timestamp(), lastPages=scan.pages, lastListed=scan.listed,
                      lastMatches=matches, lastUnresolved=len(scan.unresolved))
        self.save()
        if scan.errors:
            self.failure(source, RuntimeError(" / ".join(scan.errors)[:450]))
            return
        if status.get("errorNotified"):
            self.notify(f"【お得PC監視復旧】{source}の価格・在庫確認が正常に戻りました。")
        status.update(lastSuccessAt=timestamp(), failures=0, errorNotified=False, status="ok")
        self.save()
        logging.info("deal_scan_ok source=%s pages=%s listed=%s matches=%s", source, scan.pages, scan.listed, matches)

    def announce(self):
        if not self.state.get("startupNotified") and all(
            self.state["sources"].get(source, {}).get("status") == "ok" for source in ("galleria", "oz")
        ):
            self.notify("【お得PC監視開始・接続テスト】S-monitorでGALLERIAとOZ Gamingを1分ごとに確認します。\n"
                        + "RTX 5080搭載: 本体税込32万円以下\nRTX 5070 Ti以上: 本体税込28万円以下\n"
                        + "一覧で候補を探し、商品ページの価格・在庫を確認してから通知します。\n"
                        + "同じ商品の同じ価格は連投せず、値下がり・条件内での再入荷時に再通知します。")
            self.state["startupNotified"] = True
            self.save()


def load_limits(path="deal_rules.json"):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not value or any(gpu_name(k) != k or not isinstance(v, int) or isinstance(v, bool) or v <= 0
                        for k, v in value.items()):
        raise ValueError("Invalid GPU price rules")
    return value


def run_deals(once, interval):
    limits = load_limits(Path(__file__).with_name("deal_rules.json"))
    stores = {name: Store(name, limits) for name in ("galleria", "oz")}
    discord = requests.Session()
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not once and not webhook.startswith("https://discord.com/api/webhooks/"):
        raise ValueError("Set DISCORD_WEBHOOK_URL before starting the monitor")
    monitor = None if once else DealMonitor(os.getenv("DEAL_STATE_FILE", "data/deals-status.json"), limits,
                                          lambda message: send_discord(discord, webhook, message))
    logging.info("deal_monitor_started interval_seconds=%s limits=%s dry_run=%s", interval, limits, once)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            while not stop.is_set():
                started = time.monotonic()
                failed = False
                futures = {pool.submit(store.scan): name for name, store in stores.items()}
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        scan = future.result()
                        if once:
                            matches = [asdict(item) for item in scan.offers if item.available is True
                                       and item.price <= limits.get(item.gpu, 0)]
                            print(json.dumps({"source": name, "pages": scan.pages, "listed": scan.listed,
                                              "matches": matches, "unresolved": list(scan.unresolved),
                                              "errors": scan.errors}, ensure_ascii=False))
                            failed = failed or bool(scan.errors)
                        else:
                            monitor.accept(name, scan)
                    except Exception as error:
                        if once:
                            logging.error("dry_run_failed source=%s error=%s", name, error)
                            failed = True
                        else:
                            monitor.failure(name, error)
                if once:
                    if failed:
                        raise SystemExit(1)
                    return
                try:
                    monitor.announce()
                except Exception as error:
                    monitor.failure("discord", error)
                elapsed = time.monotonic() - started
                logging.info("deal_cycle_done elapsed_seconds=%.2f interval_seconds=%s", elapsed, interval)
                stop.wait(max(0, interval - elapsed))
    finally:
        for store in stores.values():
            store.session.close()
        discord.close()
        logging.info("deal_monitor_stopped")
