# GALLERIA / OZ Gaming お得PC通知

S-monitor (Raspberry Pi) が2店の商品一覧を60秒ごとに巡回します。
一覧から価格条件に合うPCを抽出し、商品ページでもGPU・CPU・価格・在庫を
確認できた候補だけ、従来のDiscordチャンネルへ通知します。

## 通知条件

本体の税込価格です。送料・オプション・カスタマイズ代は含みません。

| GPU | 上限価格 |
| --- | ---: |
| RTX 5070 Ti | 280,000円 |
| RTX 5080 | 320,000円 |
| RTX 5090 | 280,000円 |

ユーザー指定: 「RTX5080 32万以下 と 5070Ti以上 28万以下」。
対象はデスクトップPC本体です。ノートPC、単体GPU、周辺機器は含めません。
条件は `deal_rules.json` に保存しています。

## 取得範囲

- GALLERIA: ドスパラのTC30一覧をGPU別・価格昇順で取得。各GPUの上限額を
  超えるページまで確認します。ブランド名がGALLERIAの商品だけが対象です。
  商品リンクはTC30固定ではなく、TC917等の通販限定モデルも含め、公式ドメインと
  一覧の商品IDの一致を確認します。通知前の詳細ページ確認も維持します。
- OZ Gaming: 公式の全商品一覧を価格昇順で取得。32万円を超えるページまで確認します。
- 一覧の価格順・GPU絞り込み・ページ送りが崩れた場合はエラーとして扱います。
- 候補は詳細ページを再取得し、一覧から構成が変わっていないことと在庫を確認します。
- 詳細を確認できなかった商品は通知せず、次回に再試行します。
- 初回から条件内で購入可能な商品があれば通知します。
- 同じ商品・価格は連投しません。さらに値下がり、条件外からの再値下げ、
  条件内での再入荷時には再通知します。再起動後も通知履歴を保持します。
- 店舗ごとに独立して処理し、3回連続失敗時はDiscordへ障害を通知します。
  同じ障害の通知は最大1時間に1回です。復旧時も通知します。

各店の一覧を読む方式で、検索APIやAI APIを毎分呼びません。公開ページへの掲載や
キャッシュ更新前の情報は検出できません。ネットワークや店側の制限によって
周期が延びる場合があります。購入操作は行いません。

## ローカル確認

`.env.example` を参考に `.env` を設定します。WebhookをGitに含めないでください。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe main.py --once
```

`--once` は実サイトを一巡し、結果を表示します。Discord送信と状態保存は行いません。
テストは合成データでの価格境界・誤通知・再送・重複防止に加え、旧監視の回帰も含みます。

## Pi運用

サービス名は既存の `galleria-stock.service` を引き継いでいます。
新しい通知履歴は `shared/data/deals-status.json` です。旧単品監視の
`shared/data/status.json` と混ぜません。Pi再起動時の自動起動・障害時の再起動はsystemdが担当します。

```powershell
.\deploy-pi.ps1
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd env galleria-stock "C:\claude-tools\スヌーピーミュージアム カフェ\.env"
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd status galleria-stock
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd logs galleria-stock
C:\claude-tools\raspberrypi-5plus\bin\pi.cmd stop galleria-stock
```

配置はソースだけをステージングし、Piの設定・データを保持します。
設定の転送は `pi env` で別途行います。`MONITOR_MODE=deals` が現在のモードです。
`INTERVAL_SECONDS=60`、`DEAL_STATE_FILE=data/deals-status.json` を使用します。

旧MC21585の単品監視は `MONITOR_MODE=single` でのみ実行できます。
旧カフェ監視の `src/` は履歴用です。カフェのGitHub Actionsは引き続き無効です。
