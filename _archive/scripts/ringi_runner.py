"""
ringi_runner.py  –  Django UI から subprocess で呼ばれる実行スクリプト
Usage: python ringi_runner.py <業務ID1> <業務ID2> ...
       例: python ringi_runner.py 1 3 5
"""

import sys
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ============================================================
# 設定
# ============================================================
URL          = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?'
WORKFLOW_URL = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex'
PASSWORD     = '156222'
JSON_FILE    = 'kaisai_data.json'

ITEM_FULLNAME = {
    'ゼミナール': '住之江ゼミナール',
}

KAISAI_MASTER = {
    '都市': {'keiyaku_saki': '大阪府都市ボートレース企業団', 'sochi_saki': '大阪府都市ボートレース企業団'},
    '箕面': {'keiyaku_saki': '箕面市ボートレース事業局',   'sochi_saki': '箕面市ボートレース事業局'},
}

# ============================================================
# XPath
# ============================================================
xpath_sel_btn        = '//input[@class="jco-sel-btn"]'
xpath_tree1          = "(//ins[@class='jstree-icon'])[11]"
xpath_tree2          = "(//ins[@class='jstree-icon'])[14]"
xpath_user           = "//select[@name='uid']/option[@value='23']"
xpath_pw             = "//input[@class='co-width-100p']"
xpath_login          = "//a[@id='login-btn']"
xpath_status_select  = "(//select)[4]"
xpath_first_ringi    = "(//a[contains(text(), '契約連絡表')])[1]"
xpath_copy_btn       = "//input[@value='複写して作成']"
xpath_draft          = "//input[@value='下書き保存'] | //button[contains(text(),'下書き')]"
target_iframe        = "//iframe[contains(@src, 'appsuite.cgi?cmd=cdbbrowsedetailframe')]"
xpath_subject        = '//input[@class="jco-input-subject co-width-long"]'
xpath_zei_textarea   = '/html/body/div[2]/div/div/div[1]/div/div/div[1]/div/form/div[43]/div/div/textarea'

# ============================================================
# ヘルパー
# ============================================================
def item_fullname(koumoku):
    return ITEM_FULLNAME.get(koumoku, koumoku)

def log(msg):
    print(msg, flush=True)

def wait_click(driver, xpath, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(2)

def clear_input(driver, xpath, text, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    driver.execute_script("""
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
        arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
    """, el, str(text))
    time.sleep(0.5)

# ============================================================
# データ準備
# ============================================================
def get_form_data(kid):
    with open(JSON_FILE, encoding='utf-8') as f:
        records = json.load(f)
    rows = [r for r in records if r['業務ID'] == kid]
    if not rows:
        raise ValueError(f"業務ID={kid} が見つかりません")

    first  = rows[0]
    shusai = first['主催']
    master = KAISAI_MASTER[shusai]
    mf = first['日程'][5:]
    mt = first['終了日'][5:]

    first_item = item_fullname(rows[0]['項目'])
    subject = (
        f"契約連絡表（経営・企画）{first['開催ID']} {shusai} "
        f"{mf}~{mt} {first['タイトル']} {first_item}"
    )

    items_text = "\n".join(item_fullname(r['項目']) for r in rows)
    gyomu_tai  = items_text + "\n" + first['タイトル']

    zeibiki   = sum(r['税抜き']      for r in rows)
    shouhizei = sum(r['消費税']      for r in rows)
    total     = sum(r['税込み価格'] for r in rows)

    return {
        'subject':      subject,
        'keiyaku_saki': master['keiyaku_saki'],
        'gyomu_tai':    gyomu_tai,
        'date_from':    first['日程'],
        'date_to':      first['終了日'],
        'zeibiki':      f"¥{zeibiki:,}（税抜）",
        'zei_text':     f"¥{shouhizei:,}（消費税）\n¥{total:,}（総 額）",
        'sochi_saki':   master['sochi_saki'],
    }

# ============================================================
# ナビゲーション
# ============================================================
def goto_kanryo_list(driver):
    driver.get(WORKFLOW_URL)
    time.sleep(3)
    sel = driver.find_element(By.XPATH, xpath_status_select)
    for opt in sel.find_elements(By.TAG_NAME, 'option'):
        if '作成分（完了' in opt.text:
            opt.click()
            break
    time.sleep(2)

# ============================================================
# 1件分の入力
# ============================================================
def process_one(driver, fd):
    gyomu_bi = fd['date_from'] + '～' + fd['date_to']

    wait_click(driver, xpath_first_ringi)
    time.sleep(3)
    wait_click(driver, xpath_copy_btn)
    time.sleep(4)

    clear_input(driver, xpath_subject, fd['subject'])

    iframe = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, target_iframe))
    )
    driver.switch_to.frame(iframe)
    time.sleep(2)

    def ci(xpath, val):
        clear_input(driver, xpath, val)

    inp = '(//input[@class="cdb-text-input jcdb-style-target"])'
    ci(f'{inp}[1]',  fd['keiyaku_saki'])
    ci('(//textarea)[1]', fd['gyomu_tai'])
    ci(f'{inp}[6]',  gyomu_bi)
    ci(f'{inp}[8]',  fd['zeibiki'])
    ci(xpath_zei_textarea, fd['zei_text'])
    ci(f'{inp}[10]', fd['sochi_saki'])

    driver.switch_to.default_content()
    time.sleep(1)
    wait_click(driver, xpath_draft)
    time.sleep(3)

# ============================================================
# メイン
# ============================================================
def main():
    if len(sys.argv) < 2:
        log("ERROR: 業務IDを引数で指定してください")
        log("Usage: python ringi_runner.py 1 2 3 ...")
        sys.exit(1)

    target_ids = [int(x) for x in sys.argv[1:]]
    log(f"[START] 対象業務ID: {target_ids}")

    driver = webdriver.Chrome()
    driver.maximize_window()

    try:
        log("[STEP 1] ログイン中...")
        driver.get(URL)
        time.sleep(2)
        wait_click(driver, xpath_sel_btn)
        wait_click(driver, xpath_tree1)
        wait_click(driver, xpath_tree2)
        wait_click(driver, xpath_user)
        driver.find_element(By.XPATH, xpath_pw).send_keys(PASSWORD)
        wait_click(driver, xpath_login)
        time.sleep(3)
        log("[STEP 1] ログイン完了")

        total = len(target_ids)
        for i, kid in enumerate(target_ids):
            log(f"[{i+1}/{total}] 業務ID={kid} 処理中...")
            goto_kanryo_list(driver)
            fd = get_form_data(kid)
            log(f"  件名: {fd['subject']}")
            process_one(driver, fd)
            log(f"[{i+1}/{total}] 業務ID={kid} 下書き保存完了")

        log(f"[DONE] {total}件の処理が完了しました")

    except Exception as e:
        import traceback
        log(f"[ERROR] {e}")
        log(traceback.format_exc())
        sys.exit(1)

    finally:
        driver.quit()

if __name__ == '__main__':
    main()
