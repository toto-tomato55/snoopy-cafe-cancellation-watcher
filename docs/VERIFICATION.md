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
