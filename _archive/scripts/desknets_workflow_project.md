# デスクネッツ ワークフロー自動入力プロジェクト 引き継ぎメモ

作成日: 2026-03-17

---

## 目的

`2R8開催タイトル関係.xlsx` のデータを読み込み、デスクネッツのワークフロー「下書き」として自動保存するSeleniumアプリを作成する。

---

## ファイル構成

```
C:/Users/matsuyama/Desktop/study/改良日程作成/
├── 2R8開催タイトル関係.xlsx   ← 元データ
├── kinmuhyo.json              ← 勤務表用フォームデータ（参考）
├── kinmuhyo_2026-03-16.json   ← 同上
├── 日程入力.html              ← 勤務表入力UI（参考）
├── titles.js                  ← タイトル一覧（参考）
└── desknets_workflow_project.md  ← 本ファイル
```

---

## Excelデータ構造（R８年度 (税) シート）

| 列名 | 内容 | 例 |
|------|------|----|
| 開催ID | 開催単位ID | 1, 2, 3... |
| 業務ID | 業務単位ID | 1, 2, 3... |
| 日程 | 開始日 | 2026-04-03 |
| 終了日 | 終了日 | 2026-04-08 |
| month | 月 | 4 |
| 列1 | 日数 | 6 |
| 主催 | 都市 / 箕面 | 都市 |
| 項目 | アクア / ゼミナール / 式典一式 / 表彰式 | アクア |
| タイトル | 開催タイトル | GⅠ太閤賞競走開設70周年記念 |
| 日数 | 日数 | 6 |
| 種別 | 種別コード | 10 |
| 消費税 | 消費税額 | 321002.0 |
| 税抜き | 税抜き価格 | 3210020.0 |
| 税込み価格 | 税込み価格 | 3531022.0 |

**開催ID=1 の例（複数業務がある）:**
- 業務1: アクア → 税込み 3,531,022円
- 業務2: 式典一式 → 税込み 3,000,000円

---

## 既存Seleniumコード（ログイン〜フォーム入力）

```python
URL = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?'
PASSWORD = '156222'

# XPath一覧
xpath1  = '//input[@class="jco-sel-btn"]'           # ログイン選択ボタン
xpath2  = "(//ins[@class='jstree-icon'])[11]"        # ユーザーツリー操作
xpath3  = "(//ins[@class='jstree-icon'])[14]"        # ユーザーツリー操作
xpath5  = "//select[@name='uid']/option[@value='23']" # ユーザーID=23を選択
xpath6  = "//input[@class='co-width-100p']"          # パスワード入力欄
xpath7  = "//a[@id='login-btn']"                     # ログインボタン
xpath8  = '(//img[@class="portal-menu-icon"])[2]'    # ワークフローメニュー（2番目アイコン）
xpath9  = '//input[@class="jco-list-add-page"]'      # 新規作成ボタン
xpath10 = '//input[@class="co-format-chooser-button"]' # フォーム選択ボタン
xpath11 = '(//div[@class="co-format-chooser-format-name"])[10]' # 稟議書（10番目）
xpath12 = '//input[@class="jco-input-subject co-width-long"]'   # 件名入力
xpath13 = '(//div[@class="cdb-part-item"])[4]'
xpath14 = '//input[@class="cdb-text-input jcdb-style-target"]'  # テキスト入力（iframe内）
target_iframe = "//iframe[contains(@src, 'appsuite.cgi?cmd=cdbbrowsedetailframe')]"
txtarea = '//textarea'
title   = '//input[@id="jcdb-part-item195c85db025dad6"]'
xpath15 = '//a[@data-id="157"]/div'                  # 契約連絡票
xpath16 = '(//span[@class="app-text-icon drop-down"])[2]'
xpath17 = '((//ul[@class="jcdb-choice-root"])[2]/li)[4]'

# フロー
# 1. ログイン: xpath1 → xpath2 → xpath3 → xpath5 → xpath6(PW入力) → xpath7
# 2. ワークフロー: xpath8 → xpath9 → xpath10 → xpath15(契約連絡票)
# 3. iframe切替: target_iframe
# 4. 入力: xpath16 → xpath17 → xpath14(名前) → txtarea(本文テキスト)
```

---

## 未確定事項（次回確認が必要）

- [ ] **請求用フォームの種類** - 稟議書？契約連絡票？別のフォーム？（data-idを確認）
- [ ] **フォームのフィールド構成** - 件名・本文・金額欄など何があるか
- [ ] **1申請の単位** - 開催ID単位（1開催=1下書き）か？
- [ ] **下書き保存ボタンのXPath** - 画面で確認が必要
- [ ] **「開催別請求額」JSON** - Excelから生成するのか、既存ファイルがあるのか

---

## 作成済みスクリプト

| ファイル | 役割 |
|---------|------|
| `excel_to_json.py` | Excel→JSON変換（実行済み・動作確認済み） |
| `kaikai_data.json` | 変換済みデータ（72行・35開催ID） |
| `ringi_auto.py` | Seleniumメインスクリプト（要実機調整） |

### ringi_auto.py の要調整箇所

フォーム入力部分のXPath（複写後のフォーム内）は実機確認が必要：
- `xpath_keiyaku`（契約先名）〜`xpath_sochi_saki`（送付先）の索引番号
- `xpath_draft_save`（下書き保存ボタン）
- iframeの有無（複写フォームでもiframeが使われるか）

### 確定済み情報

- 主催=都市 → 契約先名/送付先: 大阪府都市ボートレース企業団
- 主催=箕面 → 契約先名/送付先: 箕面市ボートレース事業局
- 1申請 = 1開催ID（業務IDは使わない）
- 表題フォーマット: `契約連絡表（経営・企画）{開催ID} {主催} {MM/DD}~{MM/DD} {タイトル} 住之江`
- 「複写して作成」ボタン: 申請詳細画面の左上

## 次回の作業手順（予定）

1. フォーム構成・XPathの確認（スクリーンショットまたは実機確認）
2. Excelデータ → JSON変換スクリプトの作成（必要な場合）
3. Seleniumスクリプト本体の作成
   - ログイン（既存コード流用）
   - フォーム選択（請求用フォームのdata-id確定後）
   - 開催IDごとにループして入力
   - 下書き保存
4. テスト実行・デバッグ

---

## デスクネッツ接続情報

- URL: `https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?`
- ユーザーID: 23（option value='23'）
- パスワード: 156222
- ワークフロー下書きURL: `https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex#fid=3&stsid=-1&row=0&fldsort=entrydate&order=-1&num=100&cmd=flowindex`
