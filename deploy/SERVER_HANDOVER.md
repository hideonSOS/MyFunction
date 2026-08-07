# サーバー反映 申し送り（付箋の添付機能）

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
