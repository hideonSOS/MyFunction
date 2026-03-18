# デスクネッツ フォーム XPath マッピング

調査日: 2026-03-18
調査スクリプト: `ringi_inspect.py`
定数ファイル: `form_xpath.py`

---

## 共通（ログイン・ナビゲーション）

| キー | XPath | 用途 |
|------|-------|------|
| `sel_btn` | `//input[@class="jco-sel-btn"]` | ログイン選択ボタン |
| `tree1` | `(//ins[@class='jstree-icon'])[11]` | ユーザーツリー操作 |
| `tree2` | `(//ins[@class='jstree-icon'])[14]` | ユーザーツリー操作 |
| `user` | `//select[@name='uid']/option[@value='23']` | ユーザーID=23 選択 |
| `pw` | `//input[@class='co-width-100p']` | パスワード入力欄 |
| `login` | `//a[@id='login-btn']` | ログインボタン |
| `status_select` | `(//select)[4]` | 一覧ステータス切替ドロップダウン |
| `copy_btn` | `//input[@value='複写して作成']` | 複写ボタン |
| `draft_btn` | `//input[@value='下書き保存'] \| //button[contains(text(),'下書き')]` | 下書き保存ボタン |
| `iframe` | `//iframe[contains(@src, 'appsuite.cgi?cmd=cdbbrowsedetailframe')]` | フォーム本体 iframe |
| `subject` | `//input[@class="jco-input-subject co-width-long"]` | 件名（iframe外） |

### 接続情報

| 項目 | 値 |
|------|---|
| ログインURL | `https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?` |
| ワークフローURL | `https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex` |
| ユーザーID | 23（option value='23'） |
| パスワード | 156222 |

### ナビゲーション手順

```
1. WORKFLOW_URL に直接遷移
2. (//select)[4] で「作成分（完了）」を選択
3. 目的の書類リンクをクリック → 「複写して作成」ボタン押下
4. iframe に switch_to.frame() してから各フィールドを操作
5. switch_to.default_content() → 下書き保存
```

---

## 契約連絡表

調査時の件名例:
`契約連絡表（経営・企画）34 箕面 03/04~03/09 ボートピア梅田開設19周年記念競走 住之江ゼミナール`

### 件名フォーマット（iframe外）

```
契約連絡表（経営・企画）{開催ID} {主催} {MM/DD}~{MM/DD} {タイトル} {項目}
```

### inputフィールド（iframe内）

| index | キー | フィールド名 | ID（確定） | 調査時の値 |
|-------|------|------------|-----------|-----------|
| [1] | `keiyaku_saki` | 契約先名 | `jcdb-part-item19cfc5e263cde64` | 箕面市ボートレース事業局 |
| [2] | `keiyaku_tanto` | 契約担当 | `jcdb-part-item19cfc5e263d8865` | 箕面・津浦氏 |
| [3] | `genba_tanto` | 現場担当 | `jcdb-part-item19cfc5e263e7670` | （空） |
| [4] | `tel` | TEL | `jcdb-part-item19cfc5e2641e99b` | （空） |
| [5] | `shozaichi` | 所在地 | `jcdb-part-item19cfc5e2642efef` | 大阪市住之江区泉１－１－71　ボートレース住之江 |
| [6] | `gyomu_bi` | 業務日 | `jcdb-part-item19cfc5e2643cbda` | 2026/03/04 ,2026/03/07 , 2026/... |
| [7] | `inp7` | （不明・通常空） | `jcdb-part-item19cfc5e26444b33` | （空） |
| [8] | `zeibiki` | 税抜き | `jcdb-part-item19cfc5e26472e14` | \337,500(税別) |
| [9] | `inp9` | （不明・通常空） | `jcdb-part-item19cfc5e2648509c` | （空） |
| [10] | `sochi_saki` | 送付先 社名 | `jcdb-part-item19cfc5e264a75bb` | 箕面市ボートレース事業局 |
| [11] | `sochi_jusho` | 送付先 住所/宛先 | `jcdb-part-item19cfc5e264b98b7` | （空） |

### textareaフィールド（iframe内）

| index | キー | フィールド名 | ID（確定） | 調査時の値 |
|-------|------|------------|-----------|-----------|
| [T1] | `gyomu_tai` | 業務対象 | `jcdb-part-item19cfc5e263f6ee0` | 住之江ゼミナール\nボートピア梅田開設19周年記念競走 |
| [T2] | `gyomu_naiyo` | 業務内容 | `jcdb-part-item19cfc5e2644575d` | （空） |
| [T3] | `zei_text` | 消費税・総額 | `jcdb-part-item19cfc5e2647e74c` | ¥33,750(消費税)\n¥371,250（総額） |
| [T4] | `sonota` | その他 | `jcdb-part-item19cfc5e264bb737` | （空） |

### ringi_test1.py で自動入力している項目

| フィールド | 入力値の生成元 |
|-----------|--------------|
| 件名 | `kaisai_data.json` の 開催ID・主催・日程・タイトル・項目 |
| 契約先名 | `KAISAI_MASTER[主催]['keiyaku_saki']` |
| 業務対象 | 全項目を改行結合 + タイトル |
| 業務日 | `日程 ～ 終了日` |
| 税抜き | `¥{合計税抜き:,}（税抜）` |
| 消費税・総額 | `¥{消費税:,}（消費税）\n¥{税込み:,}（総 額）` |
| 送付先 社名 | `KAISAI_MASTER[主催]['sochi_saki']` |

---

## 外注費連絡表

調査時の件名例:
`外注費連絡表（メディア）栗原・GⅠ第69回近畿地区選手権競走期間(2/4_2/9)式典`

### inputフィールド（iframe内）

| index | キー | フィールド名 | ID（確定） | 調査時の値 |
|-------|------|------------|-----------|-----------|
| [1] | `gaichuu_saki` | 外注先名 | `jcdb-part-item19cfc60075de68d` | ケイプランニング |
| [2] | `keiyaku_tanto` | 契約担当 | `jcdb-part-item19cfc60075e4966` | 栗原　圭 |
| [3] | `gyomu_tanto` | 業務担当 | `jcdb-part-item19cfc60075f800a` | （空） |
| [4] | `tel` | TEL | `jcdb-part-item19cfc6007625f5a` | 072-265-1446 |
| [5] | `shozaichi` | 所在地 | `jcdb-part-item19cfc600763dc27` | 高石市西取石7-8-17-305 |
| [6] | `gyomu_bi` | 業務日 | `jcdb-part-item19cfc600764582b` | 2026/2/3~2026/2/9 |
| [7] | `gyomu_naiyo` | 業務内容（1行） | `jcdb-part-item19cfc6007656dbf` | 式典における音響照明の手配（ベースオントップ等）及びスタッフ |
| [8] | `zeibiki` | 税抜き | `jcdb-part-item19cfc60076a167f` | 2,100,000(税抜) |
| [9] | `shiharai_hoho` | 支払方法 | `jcdb-part-item19cfc60076de456` | （空） |
| [10] | `ginko_mei` | 銀行名 | `jcdb-part-item19cfc60076fde2a` | 三井住友銀行 |
| [11] | `shiten_mei` | 支店名 | `jcdb-part-item19cfc6007704ee2` | 鳳支店 |
| [12] | `koza_bango` | 口座番号 | `jcdb-part-item19cfc6007715fd0` | 普通　１７１１１３７ |
| [13] | `koza_meigi` | 口座名義 | `jcdb-part-item19cfc600772f581` | ケイ　プランニング　栗原　圭 |

### textareaフィールド（iframe内）

| index | キー | フィールド名 | ID（確定） | 調査時の値 |
|-------|------|------------|-----------|-----------|
| [T1] | `gyomu_tai` | 業務対象 | `jcdb-part-item19cfc6007607283` | GⅠ第69回 近畿地区選手権競走期間 式典一式\n音響照明一式・制作費 |
| [T2] | `tanto_jikan` | 担当時間 | `jcdb-part-item19cfc600766ce8d` | 2/3 9:00 ~ 17:00 前検日における設営リハーサル... |
| [T3] | `zei_text` | 消費税・総額 | `jcdb-part-item19cfc60076b8daa` | ¥210,000(消費税)\n¥2,310,000(総額) |
| [T4] | `sonota` | その他 | `jcdb-part-item19cfc60077295e0` | （空） |

### 契約連絡表との主な差異

| 項目 | 契約連絡表 | 外注費連絡表 |
|------|-----------|------------|
| 主体フィールド名 | 契約先名 | 外注先名 |
| 担当者② | 現場担当 | 業務担当 |
| 業務内容 | textarea[T2] | **input[7]**（1行） |
| 振込先情報 | なし | input[10〜13]（銀行・支店・口座番号・名義） |
| textarea[T2] | 業務内容 | 担当時間（スケジュール詳細） |

---

## 実装ファイル一覧

| ファイル | 役割 | 状態 |
|---------|------|------|
| `ringi_inspect.py` | フォームフィールド調査スクリプト | 完成 |
| `form_xpath.py` | XPath定数（両フォーム） | 完成 |
| `ringi_test1.py` | 契約連絡表 Selenium自動化（72件対応） | 完成・動作確認済 |
| `ringi_runner.py` | Django用 subprocess runner | 完成 |
| `kaisai_data.json` | 契約連絡表用データ（72件） | 完成 |
| `ringi/views.py` | Django ビュー | 完成 |
| `start_ui.bat` | Django開発サーバー起動（`--noreload` 必須） | 完成 |
| `docs_fetcher.py` | 作成分（完了）一覧を全取得→docs_cache.json保存 | 完成・動作確認済 |
| `copy_runner.py` | 指定書類を複写して下書き保存 | 完成 |
| `docs_cache.json` | 書類一覧キャッシュ（全214件、稟議書含む） | 運用中 |
| `debug_raw.json` | スクレイプ生データ先頭30件（デバッグ用） | 自動生成 |
| `ringi/templates/ringi/index.html` | Django UI（サイバー風テーマ） | 完成・動作確認済 |

---

---

## 作成分（完了）一覧ページ構造（list_inspect.py 調査結果 2026-03-18確定）

### URL
```
https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex#fid=2&stsid=1&row=0&fldsort=entrydate&order=-1&num=100&cmd=flowindex
```
- 1ページあたり100件、全214件・3ページ構成

### ステータス選択ドロップダウン
- `select[3]`（0始まり）、`name` 属性なし
- options: `未承認・差戻し / 承認済み（申請中）/ 承認予定 / 承認済み（完了）/ 作成分（申請中）/ 作成分（完了）/ 否認・取消し / 下書き`
- 特定方法: `any('作成分' in o.text for o in select.options)` で該当selectを特定

### 書類行の構造（2026-03-18 outerHTML実測で確定）

```html
<tr class="flow-list-line">
  <td class="co-chk"><input type="checkbox" name="id" value="4695"></td>
  <td class="co-thd-1em flow-importance"></td>
  <td class="co-thd-1em flow-file"></td>
  <td class="flow-td-status" title="完了">完了</td>
  <td>
    <span class="flow-no"><a href="#cmd=flowdisp&id=4695" title=""></a></span>  ← title空・使用不可
    <a href="#cmd=flowdisp&id=4695" title="契約連絡表（経営・企画）34...">契約連絡表...</a>  ← こちらが正
  </td>
  ...（日付td）
</tr>
```

| 情報 | 取得方法 |
|------|---------|
| 書類タイトル | `span.flow-no` の外の `<a>` の `title` 属性（`span.flow-no a` は空なので注意） |
| doc_id | `input[name="id"]` の `value` |
| 日付 | 末尾tdから `MM/DD HH:MM` パターンを検索 |
| 書類リンク | `href="#cmd=flowdisp&id={doc_id}"` |

### ⚠ 重要な落とし穴

1. **JavaScriptでスクレイプ不可**: ページは `frameset` 構造ではないが `document.querySelectorAll('tr.flow-list-line')` が0件を返す。原因不明だが **Selenium Python APIで直接取得する**こと。
2. **`span.flow-no a` の title は空**: `span.flow-no` 内の `<a>` は `title=""` で空。隣の `<a>` が正しいリンク。取得方法: `a[href*="flowdisp"]` を全列挙して `title` が空でないものを選ぶ。
3. **Select切り替えには `Select` API を使う**: `option.click()` では change イベントが発火しない場合がある。`Select(element).select_by_visible_text('作成分（完了）')` を使用。
4. **ページ切り替え後は `WebDriverWait` で待機**: `time.sleep` のみでは間に合わないことがある。

### ページネーション
```html
<div class="co-page top jco-pager">
  全214件
  <li class="co-page-meta"><a class="co-page-link co-drop-down-button">1/3</a></li>
  <li class="co-page-first"><span class="co-page-link nolink">最初</span></li>
  <li class="co-page-prev"><span class="co-page-link nolink">前</span></li>
  <li class="co-page-next"><a class="co-page-link">次</a></li>  ← クリック対象
  <li class="co-page-last"><a class="co-page-link">最後</a></li>
</div>
```

- **次ページ**: `document.querySelector('li.co-page-next a.co-page-link').click()`
- 最初のページでは「最初」「前」が `nolink`（クリック不可）
- 最後のページでは「次」「最後」が `nolink`

### 直接書類へ遷移する方法
```python
# doc_id が分かっている場合、直接遷移可能
target_url = f"https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex#cmd=flowdisp&id={doc_id}"
driver.get(target_url)
```

### Selenium Python スニペット（確定版）

```python
# ステータス選択（Select APIを使うこと）
from selenium.webdriver.support.ui import Select
for s in driver.find_elements(By.TAG_NAME, 'select'):
    if any('作成分' in o.text for o in s.find_elements(By.TAG_NAME, 'option')):
        Select(s).select_by_visible_text('作成分（完了）')
        break

# tr.flow-list-line が現れるまで待機
WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, 'tr.flow-list-line'))
)

# 書類一覧スクレイプ（JavaScriptではなくSelenium APIを使う）
rows = driver.find_elements(By.CSS_SELECTOR, 'tr.flow-list-line')
for row in rows:
    links = row.find_elements(By.CSS_SELECTOR, 'a[href*="flowdisp"]')
    a = next((lnk for lnk in links if (lnk.get_attribute('title') or '').strip()), None)
    title  = a.get_attribute('title').strip()
    doc_id = row.find_element(By.CSS_SELECTOR, 'input[name="id"]').get_attribute('value')

# 次ページ（Selenium APIを使う）
try:
    next_btn = driver.find_element(By.CSS_SELECTOR, 'li.co-page-next a.co-page-link')
    next_btn.click()
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'tr.flow-list-line'))
    )
except Exception:
    pass  # 最後のページ
```

---

## Django UI 仕様（2026-03-18 確定）

### 起動方法
```
start_ui.bat を実行（--noreload 必須。なければ _jobs dict がリセットされる）
http://127.0.0.1:8000/ をブラウザで開く
```

### 機能一覧
| 機能 | 操作 |
|------|------|
| 書類一覧表示 | 起動時に docs_cache.json を読み込み表示 |
| 絞り込み | 種別ドロップダウン + タイトル検索（クライアント側フィルタ） |
| UPDATE | 最新ページのみ取得してキャッシュにマージ |
| FULL SYNC | 全3ページ取得（約3〜5分） |
| 複写実行 | 書類を選択して「EXECUTE」→ 複写して下書き保存 |

### 書類種別と表示色
| 種別 | 色 |
|------|----|
| 契約連絡表 | シアン |
| 外注費連絡表 | グリーン |
| 稟議書（その他） | オレンジ |

### ボタンが反応しない場合
前回実行でボタンが無効化されたまま残ることがある。ページリロード（Ctrl+Shift+R）で自動リセットされる。
または Console で `fetchDocs('full')` を直接実行。

### ログ確認
UIのログボックスは完了後消える。ログは `logs/job_*.log` に保存されており直接参照可能。

---

## 今後の作業

- [ ] 複写実行（copy_runner.py）の動作確認
- [ ] 外注費連絡表用データソースの確定（Excel別シート？別ファイル？）
- [ ] 外注費連絡表用 runner スクリプト作成
- [ ] デプロイ先の検討（ローカル → サーバー）
