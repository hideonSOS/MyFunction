# 申し送り: 配置図（1日単位）機能のデプロイ

宛先: サーバー側（`/srv/MyFunction`）で作業する Claude
作成: 2026-07-23 / ローカル側 Claude
対象コミット:
- `bd6806e` — `nitei: 1日単位の配置図ページを追加`
- （後続）`nitei: 配置セルの背景色（付箋の折り目）を追加・印刷ボタン削除`

---

## 1. 現状サマリ

- ローカルで新機能を実装し、`origin/main` に push 済み（`f67bcaa..bd6806e`）。
- **サーバーには未反映**。ユーザーから「本番で配置図のボタンすら出てこない」と報告あり。
- 原因は「サーバーが `git pull` していない」と判断している（リモートには確実に入っている）。
  - 確認済み: `git show origin/main:nitei/templates/nitei/top.html` の24行目に配置図ボタンあり。
  - 確認済み: `haichi.html` / `haichi.css` / `haichi.js` が `origin/main` に存在。
- **サーバーの実状態はローカル側からは一切確認していない。** 下記手順の前に現状把握すること。

---

## 2. この機能の中身

`/nitei/haichi/` に「1日単位の配置図」ページを新設した。
元ネタはユーザー提供の Excel 配置表（リポジトリ直下 `schedule.png`）。

### 画面構成

- 縦軸: 1R〜12R。各レース3段。
  - 1段目 = 発売開始（シアン帯・入力）
  - 2段目 = 発売時間（`締め切り − 発売開始` を `HH:MM` で自動計算・表示のみ。日跨ぎは +24h）
  - 3段目 = 締め切り時間（レッド帯・入力）
- 横軸: 6ポジション列。既定は `ホワイトボード / 映像 / JLC / 音声 / (空欄) / (空欄)`。
  **列名は画面から編集可能で DB 保存される**（右2列はユーザーが「後で決める」とのことで空欄のまま）。
- セルは自由テキスト。入力から 600ms 後に自動保存（全量差し替え方式）。
- **セル右下の「付箋の折り目」（直角三角形）をクリックすると背景色を10色から選べる。**
  文字入力（セル本体のクリック）と操作が競合しないよう分離してある。
  色は透過16%のフラット単色。DB にはキー `c1`〜`c10` だけを保存し、実際の色は
  `haichi.css` の `.tint-c1`〜`.tint-c10`（CSS変数 `--tint` に RGB 生値）で定義。
  色の調整はこの10行だけ直せばセル・折り目・パレットに一括反映される。
- レース番号セルのクリックで着色トグル（元 Excel の 5R〜12R オレンジに相当）。
- 日付ピッカー + 前日/翌日/今日、日単位クリア。
  印刷ボタンはユーザー要望で削除済み（`@media print` のスタイルは残してあるので
  ブラウザの印刷機能からは整形して出力される）。
- 見た目は既存の月間シフト表（`nitei.css`）と同じサイバー調に統一済み。

### ファイル

新規:
- `nitei/templates/nitei/haichi.html`
- `nitei/static/nitei/css/haichi.css`
- `nitei/static/nitei/js/haichi.js`
- `nitei/migrations/0009_layoutday_layoutcell_layoutrace.py`
- `nitei/migrations/0010_layoutcell_color.py`（`LayoutCell.color` 追加）
- `schedule.png`（リポジトリ直下・元ネタ画像）

変更:
- `nitei/models.py` — モデル3種と定数を追加
- `nitei/views.py` — `haichi` ビュー + API 3本
- `nitei/urls.py` — ルート4本
- `nitei/templates/nitei/top.html` — TOP に「配置図」ボタン追加（**これが出ないという報告**）

### モデル（`nitei/models.py`）

```
LayoutDay   date(unique), headers(JSONField: 6列の列名)
LayoutRace  day(FK), race(1-12), start_time(CharField5), close_time(CharField5), highlight(Bool)
            unique_together (day, race)
LayoutCell  day(FK), race(1-12), col(0-5), text(CharField200), color(CharField8: ''|c1〜c10)
            unique_together (day, race, col)
```

定数: `LAYOUT_RACE_COUNT=12`, `LAYOUT_COL_COUNT=6`, `LAYOUT_DEFAULT_HEADERS`,
`LAYOUT_COLOR_KEYS`（保存APIは色キーをこのホワイトリストで検証する）

`LayoutCell` は **テキストが空でも色だけで保存される**（色のみのセルを許容する）。

### URL（`nitei/urls.py`）

```
/nitei/haichi/              views.haichi           ページ
/nitei/api/layout/          views.api_layout       GET  ?date=YYYY-MM-DD
/nitei/api/layout/save/     views.api_layout_save  POST 1日分を全量差し替え
/nitei/api/layout/clear/    views.api_layout_clear POST その日を削除
```

認証は既存の `nitei_login_required`（Django ログイン済み、またはセッション
`nitei_authed`）。新しい認証は増やしていない。

---

## 3. デプロイ手順

`git pull` だけでは足りない。3点必要。

```
cd /srv/MyFunction
git pull origin main
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
systemctl restart gunicorn
```

各ステップの理由:

1. **`migrate` 必須** — `LayoutDay` / `LayoutRace` / `LayoutCell` の新テーブルが無いと
   `/nitei/haichi/` は 500 になる。`0009_layoutday_layoutcell_layoutrace` と
   `0010_layoutcell_color` の両方が Applying されることを確認。
2. **`collectstatic` 必須** — `deploy/nginx.conf:25` で `/static/` は
   `/srv/MyFunction/staticfiles/` を alias 配信している。`staticfiles/` は **git 管理外**
   （`git ls-files | grep '^staticfiles/'` が 0 件）。実行しないと `haichi.css` /
   `haichi.js` が 404 になり、素の HTML が出るだけになる。
3. **gunicorn 再起動必須** — `urls.py` / `views.py` / `models.py` はプロセスに読み込み済み。
   再起動しないと `/nitei/haichi/` が 404 のまま。
   （`deploy/gunicorn.service`: WorkingDirectory `/srv/MyFunction`、
   `venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 MyFunction.wsgi:application`）

### 確認ポイント

- `git log --oneline -1` が `bd6806e` になっているか
- `/nitei/` を開いて緑枠の「配置図」ボタンが出るか（`top.html` が効いた証拠）
- `/nitei/haichi/` が開けるか。開いたら 12レース×3段＝36行、配置セル72個が描画される
- ブラウザの Network で `haichi.css` / `haichi.js` が 200 か（404 なら collectstatic 漏れ）
- 日付を変えて何か入力 → ステータス表示が「保存しました」になり、再読み込みで残るか

---

## 4. 注意事項・地雷

- **`.pyc` はコミットしない。** `.gitignore` に `__pycache__/` があるのに
  `nitei/__pycache__/*.pyc` が過去から追跡され続けている。既存コミットも `.pyc` を
  含めない運用なので踏襲すること。ローカルでは modified のまま放置している。
- **`.claude/` は未トラッキングのまま。** `.gitignore` への追加はユーザーが選ばなかった。
- `db.sqlite3` は `.gitignore` 済み。サーバーの DB はサーバー側のもの。migrate で作られる。
- `credentials.json` / `token.json` も `.gitignore` 済み。
- リポジトリの `MyFunction/settings.py` は `DEBUG = True`。サーバー側が別設定で
  上書きしているかは未確認。**DEBUG の扱いは勝手に変えないこと**（ユーザー確認が要る）。
- 保存 API は「その日の全量差し替え」方式（既存行を delete → bulk_create）。
  部分更新ではないので、API を直接叩く場合は必ず全量を送ること。

---

## 5. 未確認事項（サーバー側で確認してほしい）

- サーバーの現在のコミット、`git status` の汚れ具合
- サーバーが本当に `main` を追っているか（別ブランチ／detached でないか）
- `staticfiles/` の中身と collectstatic が通るか
- サーバー側 `settings.py` の DEBUG / STATIC 設定がリポジトリ版と同じか
- gunicorn / nginx が正常稼働しているか
- 上記デプロイ後に実際にボタンとページが出るか

ローカル側では localhost:8002 の dev サーバーで動作確認済み
（描画・API往復・DB保存・日付切替・列幅固定）。**本番では何も検証していない。**

---

## 6. ローカル側で直した既知バグ（参考・修正済み）

1. `.hc-race.on` などが `#hc-table td` に詳細度で負けて着色が効いていなかった
   → セレクタを `#hc-table` 修飾に統一。
2. 自動保存のデバウンス中に日付を切り替えると直前の入力が消えていた
   → 切替時に保留分を確定保存（`flushSave`）。連打時の古いレスポンス上書きも
   `loadSeq` で防止。
3. 時刻欄の幅が入力文字数で動いていた
   → `table-layout: fixed` + thead で列幅宣言（時刻96px / レース46px / セル120px）。

いずれも `bd6806e` に含まれている。
