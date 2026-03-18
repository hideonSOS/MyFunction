"""
keiyaku_runner.py  –  契約連絡表 自動下書き作成（安定版）

ringi_test1.py の改良版:
  - form_xpath.py の確定ID XPath を使用（インデックス指定なし）
  - TEMPLATE_DOC_ID を固定 → 毎回同じ書類を複写（リスト先頭クリックに依存しない）
  - 開催ID単位でループ（35件）
  - 1件エラーでも次の件に続行
  - --test / --ids オプションで部分実行可能

Usage:
    python keiyaku_runner.py            # 全開催ID（35件）
    python keiyaku_runner.py --test 1   # 最初の1件だけ（動作確認用）
    python keiyaku_runner.py --ids 1 3  # 開催ID 1, 3 だけ
"""

import argparse
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from form_xpath import COMMON

# ============================================================
# 設定
# ============================================================
BASE_DIR     = Path(__file__).parent
URL          = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?'
WORKFLOW_URL = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex'
PASSWORD     = '156222'
JSON_FILE    = BASE_DIR / 'kaisai_data.json'
CACHE_FILE   = BASE_DIR / 'docs_cache.json'

KAISAI_MASTER = {
    '都市': {
        'keiyaku_saki': '大阪府都市ボートレース企業団',
        'sochi_saki':   '大阪府都市ボートレース企業団',
    },
    '箕面': {
        'keiyaku_saki': '箕面市ボートレース事業局',
        'sochi_saki':   '箕面市ボートレース事業局',
    },
}

ITEM_FULLNAME = {
    'ゼミナール': '住之江ゼミナール',
}

# ============================================================
# ヘルパー
# ============================================================
def log(msg):
    text = str(msg).replace('\xa0', ' ')
    print(text.encode('cp932', errors='replace').decode('cp932'), flush=True)


def wait_click(driver, xpath, timeout=15):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(1.5)


def js_set(driver, xpath, value, timeout=15):
    """JS でフィールドに値をセット（send_keys の改行誤動作・Enterキー誤発火を回避）"""
    el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    driver.execute_script(
        """
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input',  {bubbles: true}));
        arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
        """,
        el,
        str(value),
    )
    time.sleep(0.3)


def item_fullname(s):
    return ITEM_FULLNAME.get(s, s)


# ============================================================
# テンプレート doc_id を docs_cache.json から取得
# ============================================================
def get_template_doc_id():
    """
    docs_cache.json の契約連絡表リストから最新(先頭)の doc_id を返す。
    毎回同じ書類を複写することで「リスト先頭クリック」の不安定さを排除する。
    """
    if not CACHE_FILE.exists():
        raise FileNotFoundError(
            f"{CACHE_FILE} が見つかりません。先に docs_fetcher.py を実行してください。"
        )
    with open(CACHE_FILE, encoding='utf-8') as f:
        docs = json.load(f)

    candidates = [d for d in docs if d.get('kind') == '契約連絡表' and d.get('doc_id')]
    if not candidates:
        raise ValueError("docs_cache.json に契約連絡表が見つかりません")

    template = candidates[0]
    log(f"[TEMPLATE] doc_id={template['doc_id']}  title={template['title'][:60]}")
    return template['doc_id']


# ============================================================
# kaisai_data.json から開催ID単位でデータを集約
# ============================================================
def load_kaisai_grouped():
    """開催IDをキー、業務行リストを値とした dict を返す"""
    with open(JSON_FILE, encoding='utf-8') as f:
        records = json.load(f)
    grouped: dict[int, list] = {}
    for r in records:
        grouped.setdefault(r['開催ID'], []).append(r)
    return grouped


def build_form_data(rows: list) -> dict:
    """業務行リスト → フォーム入力値 dict を生成"""
    first  = rows[0]
    shusai = first['主催']
    master = KAISAI_MASTER[shusai]

    # 日付フォーマット: "2026/04/03" → "04/03"
    mf = first['日程'][5:]
    mt = first['終了日'][5:]

    first_item = item_fullname(rows[0]['項目'])
    subject = (
        f"契約連絡表（経営・企画）"
        f"{first['開催ID']} {shusai} {mf}~{mt} {first['タイトル']} {first_item}"
    )

    # 業務対象: 全項目（改行区切り）+ タイトル
    items_text = "\n".join(item_fullname(r['項目']) for r in rows)
    gyomu_tai  = items_text + "\n" + first['タイトル']
    gyomu_bi   = first['日程'] + '～' + first['終了日']

    zeibiki   = sum(r['税抜き']      for r in rows)
    shouhizei = sum(r['消費税']      for r in rows)
    total     = sum(r['税込み価格'] for r in rows)

    return {
        'subject':      subject,
        'keiyaku_saki': master['keiyaku_saki'],
        'gyomu_tai':    gyomu_tai,
        'gyomu_bi':     gyomu_bi,
        'zeibiki':      f"¥{zeibiki:,}（税抜）",
        'zei_text':     f"¥{shouhizei:,}（消費税）\n¥{total:,}（総 額）",
        'sochi_saki':   master['sochi_saki'],
    }


# ============================================================
# ログイン
# ============================================================
def login(driver):
    log("[STEP 1] ログイン中...")
    driver.get(URL)
    time.sleep(2)
    wait_click(driver, COMMON['sel_btn'])
    wait_click(driver, COMMON['tree1'])
    wait_click(driver, COMMON['tree2'])
    wait_click(driver, COMMON['user'])
    driver.find_element(By.XPATH, COMMON['pw']).send_keys(PASSWORD)
    wait_click(driver, COMMON['login'])
    time.sleep(3)
    log("[STEP 1] ログイン完了")


# ============================================================
# 1件分: テンプレート複写 → フィールド入力 → 下書き保存
# ============================================================
def process_one(driver, template_doc_id: str, fd: dict, label: str = ''):
    log(f"  [{label}] 件名: {fd['subject'][:70]}")

    # ① テンプレート書類へ直接遷移
    target_url = f"{WORKFLOW_URL}#cmd=flowdisp&id={template_doc_id}"
    driver.get(target_url)
    time.sleep(4)

    # ② 複写して作成
    wait_click(driver, COMMON['copy_btn'])
    time.sleep(5)
    log(f"  [{label}] 複写完了 → 入力開始")

    # ③ 件名（iframe 外）
    js_set(driver, COMMON['subject'], fd['subject'])

    # ④ iframe 内に切替
    iframe = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, COMMON['iframe']))
    )
    driver.switch_to.frame(iframe)
    time.sleep(2)

    # ⑤ 各フィールドを入力
    # ※ 複写後のドキュメントはフィールドIDが毎回変わるため
    #    class="cdb-text-input jcdb-style-target" の順番(安定)で指定する
    INP = '(//input[@class="cdb-text-input jcdb-style-target"])'
    js_set(driver, f'{INP}[1]',    fd['keiyaku_saki'])  # 契約先名
    js_set(driver, '(//textarea)[1]', fd['gyomu_tai'])  # 業務対象
    js_set(driver, f'{INP}[6]',    fd['gyomu_bi'])      # 業務日
    js_set(driver, f'{INP}[8]',    fd['zeibiki'])       # 税抜き
    js_set(driver, '(//textarea)[3]', fd['zei_text'])   # 消費税・総額
    js_set(driver, f'{INP}[10]',   fd['sochi_saki'])    # 送付先 社名

    # ⑥ iframe 解除 → 下書き保存
    driver.switch_to.default_content()
    time.sleep(1)
    wait_click(driver, COMMON['draft_btn'])
    time.sleep(3)
    log(f"  [{label}] 下書き保存完了 ✓")


# ============================================================
# メイン
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='契約連絡表 自動下書き作成')
    parser.add_argument('--test', type=int, metavar='N',
                        help='最初の N 件だけ実行（動作確認用）')
    parser.add_argument('--ids', type=int, nargs='+', metavar='ID',
                        help='指定した開催ID のみ実行')
    args = parser.parse_args()

    grouped  = load_kaisai_grouped()
    all_kids = sorted(grouped.keys())

    if args.ids:
        targets = [k for k in args.ids if k in grouped]
        missing = [k for k in args.ids if k not in grouped]
        if missing:
            log(f"[WARN] 開催ID {missing} はデータに存在しません")
    elif args.test:
        targets = all_kids[: args.test]
    else:
        targets = all_kids

    if not targets:
        log("[ERROR] 処理対象がありません")
        sys.exit(1)

    log(f"[設定] 処理対象: {len(targets)} 開催ID  {targets[:6]}{'...' if len(targets) > 6 else ''}")

    template_doc_id = get_template_doc_id()

    driver = webdriver.Chrome()
    driver.maximize_window()

    ok_count  = 0
    err_count = 0

    try:
        login(driver)

        for i, kid in enumerate(targets):
            rows  = grouped[kid]
            fd    = build_form_data(rows)
            label = f"{i + 1}/{len(targets)} 開催ID={kid}"
            try:
                process_one(driver, template_doc_id, fd, label)
                ok_count += 1
            except Exception as e:
                import traceback
                log(f"  [{label}] [ERROR] {e}")
                log(traceback.format_exc())
                err_count += 1
                log(f"  [{label}] → スキップして次へ")
                continue

        log(f"\n★ 完了: {ok_count} 件成功 / {err_count} 件エラー ★")

    finally:
        try:
            input("\nEnterキーでブラウザを閉じます...")
        except EOFError:
            time.sleep(5)
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
