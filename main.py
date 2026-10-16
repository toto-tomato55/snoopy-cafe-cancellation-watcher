import argparse
import logging
import os
import signal
import threading
import time

import requests
from dotenv import load_dotenv

from stock_monitor import Monitor, PRODUCT_URL, ProductPageMissing, fetch_stock, send_discord


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Check once without sending or saving")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    interval = int(os.getenv("INTERVAL_SECONDS", "60"))
    if interval < 60:
        raise ValueError("INTERVAL_SECONDS must be at least 60")
    url = os.getenv("PRODUCT_URL", PRODUCT_URL)
    if url != PRODUCT_URL:
        raise ValueError("This monitor is configured for MC21585 only")
    session = requests.Session()
    if args.once:
        try:
            stock = fetch_stock(session, url)
            print(f"{stock.name}\n{stock.price:,} JPY | {stock.availability} | {stock.delivery}")
        except ProductPageMissing as error:
            print(f"{error}\n在庫は確認不能。常駐監視は再掲載を1分ごとに確認します。")
        finally:
            session.close()
        return
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not webhook.startswith("https://discord.com/api/webhooks/"):
        raise ValueError("Set DISCORD_WEBHOOK_URL before starting the monitor")
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    monitor = Monitor(os.getenv("STATE_FILE", "data/status.json"),
                      lambda: fetch_stock(session, url),
                      lambda message: send_discord(session, webhook, message), url, interval)
    logging.info("monitor_started interval_seconds=%s product=%s", interval, url)
    try:
        while not stop.is_set():
            started = time.monotonic()
            try:
                monitor.check_once()
            except ProductPageMissing as error:
                try:
                    monitor.record_page_missing(error)
                except Exception as notification_error:
                    monitor.record_failure(notification_error)
            except Exception as error:
                monitor.record_failure(error)
            stop.wait(max(0, interval - (time.monotonic() - started)))
    finally:
        session.close()
        logging.info("monitor_stopped")


if __name__ == "__main__":
    main()
