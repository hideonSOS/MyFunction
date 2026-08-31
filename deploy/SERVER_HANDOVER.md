# サーバー反映 申し送り

---

# ② LINE予約通知（linenotify）の反映 ※2026-08-31 追加

新アプリ `linenotify` を追加。指定日時にLINEへメッセージを自動送信する
（ブロードキャスト＝友だち全員 / 登録済みグループ・ユーザー宛を選択可）。

## サーバーで必要な作業

### 1. 取得・マイグレーション・静的ファイル
```bash
cd /srv/MyFunction
git pull
./venv/bin/python manage.py migrate
./venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

### 2. LINE認証情報の配置【必須・Git管理外】
`/srv/MyFunction/line_credentials.json` を作成（.gitignore 済み。SCP等で配置）:
```json
{
  "channel_access_token": "＜LINE Developersで発行した長期チャネルアクセストークン＞",
  "channel_secret": "＜チャネルシークレット（Webhook利用時のみ必須）＞",
  "public_base_url": "https://＜外部から到達できるホスト＞"
}
```
※ `public_base_url` は通知への添付画像を送る場合のみ必須。LINEの画像は
「受信者の端末がこのURL配下の /media/ へ取得しに来る」方式のため、
**外部到達可能かつ正規のHTTPS証明書**が必要（自己署名では端末に表示されない）。
未設定の場合、画像付き通知は送信保留となりエラー表示される（テキストのみの通知は影響なし）。
※ 未配置でも画面は動くが送信は失敗する（画面に警告が出る）。

### 3. 予約送信の cron 登録【必須】
毎分、送信時刻を過ぎた予約を送るコマンドを実行する:
```bash
* * * * * cd /srv/MyFunction && ./venv/bin/python manage.py send_line_due >> logs/line_notify.log 2>&1
```

### 4. Webhook（グループ自動登録。任意）
- LINE Developers の Webhook URL: `https://＜サーバー＞/line/webhook/`
- **正規のSSL証明書（信頼されたCA発行）が必須**。自己署名証明書では LINE が接続を拒否する。
  その場合は使わなくてよい（画面からIDを手動登録する運用。webhook.site で groupId を採取）。
- nginx は `location /` で Django に渡っていれば追加設定不要。

### 5. 動作確認
1. `/line/` を開き、警告バナーが消えていること（トークン設定OK）
2. 「接続テスト送信」→ ボットを友だち追加したLINEに届くこと
3. 1〜2分後の時刻で予約 → その時刻に自動送信されること（cron確認）

---

# ① 付箋の添付機能の反映（反映済みなら読み飛ばし可）

このコミットで **付箋（fusen）にファイル添付（画像・PDF）機能** を追加しました。
本番サーバー側で以下の反映作業をお願いします。**特に nginx の項目は必須**（未対応だと 1MB を超えるアップロードが 413 で弾かれます）。

## このコミットの変更概要
- 付箋に画像・PDF を添付・表示・並べ替えできる機能を追加
- 新モデル `fusen.Attachment`（マイグレーション 0005, 0006）
- アップロード先は `MEDIA_ROOT`（= `<BASE_DIR>/media/`）。URL は `/media/`
- アップロード上限 **50MB**（Django: `fusen/views.py` の `MAX_UPLOAD_SIZE` ／ nginx: `client_max_body_size`）
- 静的ファイル（JS/CSS）を更新

## サーバーで必要な作業

### 1. 取得
```bash
cd /srv/MyFunction
git pull
```

### 2. DB マイグレーション（Attachment テーブル作成）
```bash
./venv/bin/python manage.py migrate
```

### 3. 静的ファイル収集（JS/CSS を更新済み。未実施だと旧UIのまま）
```bash
./venv/bin/python manage.py collectstatic --noinput
```

### 4. nginx にアップロード上限を反映【必須】
`deploy/nginx.conf` に `client_max_body_size 50m;` を追加済み。
これを本番の nginx 設定（例: `/etc/nginx/conf.d/myfunction.conf` 等）に反映し、リロード：
```bash
sudo nginx -t && sudo systemctl reload nginx
```
※ 未設定だと nginx 既定の 1MB 制限が効き、Django 側を 50MB にしても大きいファイルは弾かれます。

### 5. media ディレクトリの用意
- アップロード実体は `/srv/MyFunction/media/` に保存されます（**`media/` は .gitignore 対象＝git では配布されません。サーバー上のファイルとして永続します**）。
- ディレクトリが無ければ作成し、gunicorn 実行ユーザーが書き込める権限にしてください：
```bash
mkdir -p /srv/MyFunction/media && chown -R <gunicornユーザー>:<グループ> /srv/MyFunction/media
```
- 配信は nginx の `location /media/ { alias /srv/MyFunction/media/; }` で既に設定済み（`deploy/nginx.conf`）。

### 6. アプリ再起動
```bash
sudo systemctl restart gunicorn
```

## 上限値をあとで変える場合
以下 2 か所を同じ値に揃える（例: 100MB なら `100` と `100m`）：
- `fusen/views.py` … `MAX_UPLOAD_SIZE = 50 * 1024 * 1024`
- `deploy/nginx.conf` … `client_max_body_size 50m;`

## 動作確認
1. 付箋を開いて編集 → 「＋ ファイルを追加」または本文へ Ctrl+V で画像/PDF を添付
2. 画像がフォーム全幅で表示され、ドラッグで並べ替えできる
3. 大きめ（例: 30MB 程度）のファイルがアップロードできる＝ nginx 上限が効いている
