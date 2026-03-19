# Selenium / ChromeDriver をウェブアプリに組み込む際の知見

作成日: 2026-03-20
対象環境: Django + Gunicorn + Nginx / Ubuntu 24.04 (Noble) / Python 3.12

---

## ⚠️ AIが迷走したときに最初に読むこと

このプロジェクトで Selenium が動かないとき、**確認すべき順番**は以下の通り。
手当たり次第に試さず、この順番で原因を特定すること。

1. **Chrome/Chromiumがサーバーにインストールされているか**
   `which google-chrome || which chromium-browser`
   → 何も出なければインストールから始める。これが最も根本的な原因になりうる。

2. **www-dataユーザーでChromeが起動できるか**
   `sudo -u www-data google-chrome --headless --no-sandbox --disable-gpu --dump-dom about:blank 2>&1 | head -20`
   → ここで出るエラーが直接の原因。

3. **Pythonの実行パスが正しいか**
   `views.py` で subprocess を起動する Python は `sys.executable` を使うこと。
   Windows は `venv/Scripts/python.exe`、Linux は `venv/bin/python` と異なるため。

4. **複数ワーカー問題でUIがエラー表示になっていないか**
   Gunicorn は複数ワーカーで動く。`_jobs` dict は各ワーカーに独立して存在するため、
   `/run/` と `/log/` が別ワーカーに振られるとジョブが見つからず誤ってエラー表示になる。
   → `log_view` のフォールバック処理でログファイルの `[DONE]` マーカーを確認すること。

---

## つまずいたこと・原因・解決策

### 1. Pythonの実行パスが Windows 用のまま（最初の500エラー）

**症状:** POST /run/ が500エラー、ログファイルが作成されない
**原因:** `views.py` に `PYTHON = BASE_DIR / 'venv' / 'Scripts' / 'python.exe'` とハードコードされていた
**解決:** `sys.executable` を使う（Windows・Linux両対応）

```python
import sys
PYTHON = sys.executable
```

---

### 2. Chromeがサーバーにインストールされていない

**症状:** `session not created: Chrome instance exited`
**原因:** ローカル（Windows）では Chrome がインストール済みだが、Linux サーバーには存在しない
**解決:** Google Chrome をサーバーにインストール

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
```

> **注意:** Ubuntu 24.04 の `apt install chromium-browser` は Snap 版をインストールする。
> Snap 版は www-data ユーザーからの呼び出しに制限があり、Selenium から使用できない。
> **必ず Google Chrome（非Snap）をインストールすること。**

---

### 3. www-data のホームディレクトリに書き込めない

**症状:** `mkdir: cannot create directory '/var/www/.local': Permission denied`
**原因:** Chrome は起動時にホームディレクトリ配下にプロファイル・キャッシュを作ろうとする。
`www-data` のホームは `/var/www` で書き込み不可。
**解決策①:** Gunicorn の systemd サービスファイルに `Environment=HOME=/tmp` を追加

```ini
[Service]
Environment=HOME=/tmp
```

追加後:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

**解決策②:** Chrome オプションでユーザーデータディレクトリを明示

```python
options.add_argument('--user-data-dir=/tmp/chrome-profile')
```

---

### 4. Selenium Manager のキャッシュディレクトリに書き込めない

**症状:** `Cache folder (/root/.cache/selenium) cannot be created: Permission denied`
**原因:** Selenium Manager が ChromeDriver を `/root/.cache/selenium` にキャッシュしようとする
**解決:** 環境変数でキャッシュパスを変更

```python
os.environ.setdefault('SE_CACHE_PATH', '/tmp/selenium_cache')
```

---

### 5. Gunicorn 複数ワーカー問題（UIが常にエラー表示）

**症状:** 処理は成功し DeskNets に下書きが保存されているが、UIに `✖ ERROR (rc=1)` が表示される
**原因:** Gunicorn は複数ワーカー（デフォルト3）で動く。`_jobs` dict は各ワーカーのメモリ上に独立して存在する。
`/run/` リクエストをワーカーAが処理してジョブを登録しても、
`/log/` ポーリングがワーカーBやCに振られると `job_id not in _jobs` になる。
フォールバック処理でログファイルを読むが、処理が完了する前に `done=True` を返してしまい、
`[DONE]` マーカーがまだ書かれていない状態で `rc=1` が返っていた。

**解決:** フォールバック処理で `[DONE]`/`[ERROR]` マーカーが書かれるまで `done=False` を返す

```python
# views.py log_view のフォールバック部分
if log_path.exists():
    content = log_path.read_text(encoding='utf-8')
    done = '[DONE]' in content or '[ERROR]' in content
    rc   = 0 if '[DONE]' in content else (1 if '[ERROR]' in content else None)
```

また、ジョブがメモリにある場合も、プロセス終了コードよりログの `[DONE]` マーカーを優先する:

```python
if '[DONE]' in content:
    rc = 0
elif '[ERROR]' in content:
    rc = 1
elif proc_done:
    rc = info['proc'].returncode
else:
    rc = None
```

---

## 最終的に動作している構成

### Chrome オプション（Linux サーバー用）

```python
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

os.environ.setdefault('SE_CACHE_PATH', '/tmp/selenium_cache')

options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('--user-data-dir=/tmp/chrome-profile')

if os.path.exists('/usr/bin/google-chrome'):
    options.binary_location = '/usr/bin/google-chrome'
elif os.path.exists('/usr/bin/chromium-browser'):
    options.binary_location = '/usr/bin/chromium-browser'

driver = webdriver.Chrome(options=options)
```

### Gunicorn サービス設定（/etc/systemd/system/gunicorn.service）

```ini
[Service]
User=www-data
Environment=HOME=/tmp
ExecStart=/srv/MyFunction/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 MyFunction.wsgi
```

### views.py での subprocess 起動

```python
import sys
PYTHON = sys.executable  # Windows/Linux 両対応
```

### Nginx upstream（TCP接続）

```nginx
upstream django {
    server 127.0.0.1:8000 fail_timeout=0;
}
```

> **注意:** Unix ソケット（`unix:/srv/.../gunicorn.sock`）から TCP に切り替えた場合、
> Nginx の upstream 設定も必ず合わせること。

---

## その他の注意事項

### Windows固有コードの混入に注意

`copy_runner.py` の `finally` ブロックに以下のような Windows 専用コードが残っている:

```python
_sp.call('taskkill /F /IM chromedriver.exe >nul 2>&1', shell=True)
```

Linux では `taskkill` コマンドは存在しないが、`_sp.call` はエラーを無視するため
処理自体は止まらない。ただし `/srv/MyFunction` に `nul` という名前のファイルが生成される場合がある。
将来的には以下のように修正することを推奨:

```python
import sys as _sys
if _sys.platform == 'win32':
    _sp.call('taskkill /F /IM chromedriver.exe >nul 2>&1', shell=True)
```

### Gunicorn.service ファイルの編集時の注意

`gunicorn.service` に Nginx の設定（upstream ブロック等）を誤って混入させないこと。
`[Install]` セクション以降に nginx 設定が入ると `daemon-reload` 時に警告が出て
設定の一部が無視される。

---

## 動作確認コマンド

```bash
# Chromeが www-data で起動できるか
sudo -u www-data google-chrome --headless --no-sandbox --disable-gpu --dump-dom about:blank 2>&1 | head -5

# Gunicorn が 8000番ポートで待ち受けているか
ss -tlnp | grep 8000

# 最新のジョブログを確認
ls -t /srv/MyFunction/logs/job_copy_*.log | head -1 | xargs cat

# Nginx エラーログ
sudo tail -20 /var/log/nginx/myfunction_error.log
```
