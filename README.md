# スヌーピーミュージアム カフェ キャンセル通知

PEANUTS Cafe SNOOPY MUSEUM TOKYO の ebica 予約ページを確認し、2026-10-03 の 11:00 から 12:00 付近に空きが出たら Discord に通知します。

対象スロットは初期設定で `11:00,11:15,11:30,11:45,12:00` です。

## 現状確認

```bash
npm install
npm run check:dry-run
```

`○` が空き、`×` が満席、`-` が予約時間外です。`DRY_RUN=1` のときは Discord には送らず、送信予定の内容だけ表示します。

## Discord webhook を設定

Discord で通知したいチャンネルの Webhook URL を作り、GitHub のリポジトリで以下を登録します。

1. GitHub リポジトリを開く
2. `Settings` → `Secrets and variables` → `Actions`
3. `New repository secret`
4. Name: `DISCORD_WEBHOOK_URL`
5. Secret: Discord の Webhook URL

## GitHub の新しいアカウントで動かす

1. ブラウザで GitHub に新しいアカウントでログイン
2. `New repository` で新しいリポジトリを作成
3. このフォルダを GitHub に push

HTTPS で push する場合は、途中で GitHub のログインまたは Personal access token の入力を求められます。

```bash
git init
git branch -M main
git add .
git commit -m "Add reservation cancellation watcher"
git remote add origin https://github.com/<your-account>/<your-repo>.git
git push -u origin main
```

push 後、GitHub の `Actions` タブを開いて workflow を有効化してください。`Check reservation availability` は5分ごとに実行され、手動実行もできます。GitHub 側の都合で cron 実行は数分遅れることがあります。

## 設定を変える

GitHub Actions の `.github/workflows/check-reservation.yml` で変更できます。

- `TARGET_DATE`: 監視する日付
- `TARGET_TIMES`: 監視する時間。カンマ区切り
- `EBICA_URL`: 予約ページ URL

同じ空き状況では Discord 通知を重複送信しないよう、`.state` を GitHub Actions cache に保存しています。空きが消えてから再び出た場合は再通知します。
