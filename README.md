# GALLERIA 在庫復活通知

2026-10-16にカフェ予約監視から変更。S-monitor (Raspberry Pi) の
`galleria-stock.service` が60秒ごとにドスパラの商品ページを取得し、
在庫復活時に従来のDiscordチャンネルへ通知します。

- 対象: GALLERIA XMC9A-R5x-GD 動画配信向けモデル（ガンメタル）
- 商品: https://www.dospara.co.jp/TC30/MC21585.html
- 価格も通知に表示します。画像の価格を上限とする条件は設けていません。
- 商品名・SKU・JSON-LD在庫・商品欄の出荷表示を照合。不一致や取得失敗は在庫なしとして扱いません。
- 同じ在庫では連投せず、在庫なしを確認後の復活で再通知します。
- 状態はPiの `shared/data/status.json` に保存し、再起動・再配置で引き継ぎます。
- 3回連続で失敗すると障害をDiscordへ通知（最大1時間に1回）。復旧時にも通知します。
- 通知自体が失敗するとDiscordには届かないため、サービスログでも確認できます。
- 初回の正常確認後に、Piから監視開始兼通知テストを送ります。
- 購入・カート操作は行いません。

## ローカル確認

`.env.example` の設定を `.env` に置きます。WebhookはGitに含めません。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe main.py --once
```

`--once` は在庫取得だけを行い、通知・状態保存はしません。

## Pi運用

ソースはこのフォルダ、実行先はS-monitorです。

```powershell
.\deploy-pi.ps1
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd env galleria-stock "C:\claude-tools\スヌーピーミュージアム カフェ\.env"
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd status galleria-stock
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd logs galleria-stock
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd stop galleria-stock
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd start galleria-stock
```

systemdがPi起動時の自動起動と、クラッシュ時の再起動を担当します。
PCを終了してもPiが稼働しネット接続があれば監視は継続します。

旧カフェ監視の `src/` は履歴用に保持。GitHub Actionsは無効で定期スケジュールも削除済みです。
GitHubの実行枠に依存せず、Pi側で監視します。
