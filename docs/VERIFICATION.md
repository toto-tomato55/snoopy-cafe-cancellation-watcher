# Verification: 2026-10-16

## Target

- Source: this repository; main.py and stock_monitor.py.
- Deployment: S-monitor, galleria-stock.service.
- Release: /home/s-ras-01/apps/galleria-stock/releases/20261016T012022-92fda25b.
- Product: https://www.dospara.co.jp/TC30/MC21585.html
- Name: GALLERIA XMC9A-R5x-GD 動画配信向けモデル.
- Config: 60 seconds, prior Discord channel, shared/data/status.json.

## Evidence

- SSH verified by pi doctor. Existing unrelated services preserved.
- Local unittest: 6 tests passed (parser, disagreement/unknown handling,
  restock notification, persistence/deduplication, retry after failed Discord,
  throttled errors and recovery).
- Live product retrieval on Windows: 314,980 JPY, OutOfStock, 在庫なし.
- Pi systemd: active/running, enabled for boot, Restart=always.
- Pi live check completed at 10:21:17 and 10:22:18 JST.
- Check attempts started at 10:21:08.572 and 10:22:08.648 JST,
  demonstrating the configured 60-second start interval.
- Both Pi checks: SKU MC21585-SN4438, price 314980, OutOfStock, 在庫なし.
- Pi state: startupNotified=true and consecutiveFailures=0. This flag is
  saved only after the real Discord webhook returns HTTP 200 or 204.
- Pi configuration permission: 600. Source staging excludes .env, attachments,
  node_modules and local state.
- Cafe GitHub Actions disabled; no in-progress or queued runs.

## Limits

Actual restocking has not occurred during verification; the restock transition
was tested with synthetic product data. The live Pi sent the startup/test message.
Network/site restrictions can prevent a check. Three consecutive failures trigger
an error notification when Discord is reachable; recovery is also notified.

## 2026-10-16: product listing disappeared

Pi logs confirm OutOfStock/在庫なし through 13:52 JST, then 販売終了 from
13:53 through 14:03. HTTP 404 started at 14:04. Both the base product URL and
the previously observed SKU URL MC21585-SN4438.html return HTTP 404 from Windows.
This is a listing change, not a Pi service crash. Active/enabled was verified.

The updated monitor treats 404/410 as page_missing, preserves the last confirmed
stock and its timestamp, and checks for relisting every 60 seconds. It sends one
listing-missing notice per episode, persists that flag across restarts, and sends
a separate notice on relisting. Relisting is not treated as restocking. Other
network/parser failures still use the existing error notification policy.

Local unittest: 11 tests passed, including HTTP classification, sales-ended status,
notification retry, state persistence, and preventing false restock on relisting.
The live page is missing, so successful live stock parsing cannot currently be
verified; synthetic fixtures verify the recovery and restock transitions.

Updated Pi release: 20261016T051619-4887935f. At 14:17:35 JST the live service
recorded HTTP 404 with monitorStatus=page_missing and pageMissingNotified=true.
The latter is saved only after Discord accepts the specialized notice. Historical
lastSuccessAt (14:03:31 JST, 販売終了) was preserved rather than set to the 404 time.
