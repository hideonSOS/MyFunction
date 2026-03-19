"""
copy_runner.py  –  指定した書類を「複写して作成」→ フィールド入力 →「下書き保存」
Usage: python copy_runner.py <doc_id> "<title>" [<fields_json_path>]
"""

import json
import os
import sys
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL          = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?'
WORKFLOW_URL = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex'
PASSWORD     = '156222'

XPATH_SEL_BTN   = '//input[@class="jco-sel-btn"]'
XPATH_TREE1     = "(//ins[@class='jstree-icon'])[11]"
XPATH_TREE2     = "(//ins[@class='jstree-icon'])[14]"
XPATH_USER      = "//select[@name='uid']/option[@value='23']"
XPATH_PW        = "//input[@class='co-width-100p']"
XPATH_LOGIN     = "//a[@id='login-btn']"
XPATH_COPY_BTN  = "//input[@value='複写して作成']"
XPATH_DRAFT_BTN = "//input[@value='下書き保存'] | //button[contains(text(),'下書き')]"
XPATH_SUBJECT   = '//input[@class="jco-input-subject co-width-long"]'
XPATH_IFRAME    = '//iframe[contains(@src, "appsuite.cgi?cmd=cdbbrowsedetailframe")]'

INP = '(//input[@class="cdb-text-input jcdb-style-target"])'
TA  = '(//textarea)'

# 契約連絡表: フィールドキー → XPath
# INP は iframe 内 input.cdb-text-input.jcdb-style-target のみカウント（textbox のみ）
# TA は iframe 内 textarea のみカウント
# インデックスは diagnose_elements_output.txt で確定したDOM順に基づく
KEIYAKU_MAP = {
    '契約先名': f'{INP}[1]',   # INP[7]  in VIEW
    '契約担当': f'{INP}[2]',   # INP[8]
    '現場担当': f'{INP}[3]',   # INP[9]
    'ＴＥＬ':   f'{INP}[4]',   # INP[10]
    '所在地':   f'{INP}[5]',   # INP[11]
    '業務日':   f'{INP}[6]',   # INP[12]
    '業務内容': f'{INP}[7]',   # INP[13]
    '税別':     f'{INP}[8]',   # INP[15] (INP[14]=radio → スキップ)
    '住所：':   f'{INP}[9]',   # INP[16]
    '社名：':   f'{INP}[10]',  # INP[18] (INP[17]=radio → スキップ)
    '宛先：':   f'{INP}[11]',  # INP[19]
    '業務対象': f'{TA}[1]',    # TA[1]
    '総額':     f'{TA}[3]',    # TA[3]  (TA[2]=業務時間人員欄=未使用)
}

# 外注費連絡表: フィールドキー → XPath
GAICHUU_MAP = {
    '外注先名':  f'{INP}[1]',   # INP[9]  in VIEW
    '契約担当':  f'{INP}[2]',   # INP[10]
    '業務担当':  f'{INP}[3]',   # INP[11]
    'ＴＥＬ':    f'{INP}[4]',   # INP[12]
    '所在地':    f'{INP}[5]',   # INP[13]
    '業務日':    f'{INP}[6]',   # INP[14]
    '業務内容':  f'{INP}[7]',   # INP[15]
    '税別':      f'{INP}[8]',   # INP[17] (INP[16]=radio → スキップ)
    '支払方法':  f'{INP}[9]',   # INP[18]
    '銀行名：':  f'{INP}[10]',  # INP[19]
    '支店名：':  f'{INP}[11]',  # INP[20]
    '口座番号：': f'{INP}[12]', # INP[21]
    '口座名義：': f'{INP}[13]', # INP[22]
    '業務対象':  f'{TA}[1]',    # TA[1]
    '担当時間':  f'{TA}[2]',    # TA[2]
    '総額':      f'{TA}[3]',    # TA[3]
}


def log(msg):
    text = str(msg).replace('\xa0', ' ')
    print(text, flush=True)


def wait_click(driver, xpath, timeout=15):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(1.5)


def js_set(driver, xpath, value, timeout=15):
    el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    driver.execute_script(
        """
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input',  {bubbles: true}));
        arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
        """,
        el, str(value),
    )
    time.sleep(0.3)


def fill_fields(driver, kind, data):
    """複写後の EDIT モードでフィールドを入力する"""

    # ── 件名（iframe外） ── キーは __title__
    subj = data.get('__title__', data.get('件名', '')).strip()
    if subj:
        log(f"  [入力] 件名")
        js_set(driver, XPATH_SUBJECT, subj)

    # ── iframe内へ切替 ──
    iframe = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, XPATH_IFRAME))
    )
    driver.switch_to.frame(iframe)
    time.sleep(2)

    field_map = KEIYAKU_MAP if kind == '契約連絡表' else \
                GAICHUU_MAP if kind == '外注費連絡表' else {}

    filled = []
    for key, xpath in field_map.items():
        val = data.get(key, '').strip()
        if not val:
            continue
        try:
            js_set(driver, xpath, val, timeout=5)
            filled.append(key)
        except Exception as e:
            log(f"  [WARN] {key} 入力失敗: {e}")

    log(f"  [入力完了] {filled}")
    driver.switch_to.default_content()


def main():
    if len(sys.argv) < 2:
        log("ERROR: doc_id を引数で指定してください")
        sys.exit(1)

    doc_id     = sys.argv[1]
    title      = sys.argv[2] if len(sys.argv) > 2 else f'ID={doc_id}'
    json_path  = sys.argv[3] if len(sys.argv) > 3 else None

    kind = ''
    field_data = {}
    if json_path and Path(json_path).exists():
        with open(json_path, encoding='utf-8') as f:
            d = json.load(f)
        kind       = d.get('kind', '')
        field_data = d.get('fields', {})
        log(f"[設定] kind={kind}  入力フィールド数={len(field_data)}")
    else:
        log("[設定] フィールドデータなし → 複写のみ実行")

    log(f"[START] doc_id={doc_id}  title={title[:60]}")

    os.environ.setdefault('SE_CACHE_PATH', '/tmp/selenium_cache')

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=options)

    try:
        log("[1] ログイン中...")
        driver.get(URL)
        time.sleep(2)
        wait_click(driver, XPATH_SEL_BTN)
        wait_click(driver, XPATH_TREE1)
        wait_click(driver, XPATH_TREE2)
        wait_click(driver, XPATH_USER)
        driver.find_element(By.XPATH, XPATH_PW).send_keys(PASSWORD)
        wait_click(driver, XPATH_LOGIN)
        time.sleep(3)
        log("[1] ログイン完了")

        log("[2] 対象書類を開く...")
        driver.get(f"{WORKFLOW_URL}#cmd=flowdisp&id={doc_id}")
        time.sleep(4)
        log(f"[2] 書類を開きました（id={doc_id}）")

        log("[3] 複写して作成...")
        wait_click(driver, XPATH_COPY_BTN)
        time.sleep(5)
        log("[3] 複写完了")

        if field_data and kind in ('契約連絡表', '外注費連絡表'):
            log("[4] フィールド入力中...")
            fill_fields(driver, kind, field_data)
            log("[4] 入力完了")
        else:
            log("[4] 入力データなし → スキップ")

        log("[5] 下書き保存中...")
        wait_click(driver, XPATH_DRAFT_BTN)
        time.sleep(3)
        log("[5] 下書き保存完了")

        log("[DONE] 処理完了")

    except Exception as e:
        import traceback
        log(f"[ERROR] {e}")
        log(traceback.format_exc())
        sys.exit(1)

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        import subprocess as _sp
        _sp.call('taskkill /F /IM chromedriver.exe >nul 2>&1', shell=True)
        # 一時JSONを削除
        if json_path:
            try:
                Path(json_path).unlink(missing_ok=True)
            except Exception:
                pass


if __name__ == '__main__':
    main()
