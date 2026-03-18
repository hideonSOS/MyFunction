"""
diagnose_fields.py  –  書類1件のフィールドDOM構造を診断する（読み取り専用）

Usage:
    python diagnose_fields.py              # 契約連絡表の最初の1件
    python diagnose_fields.py --kind 外注費連絡表
    python diagnose_fields.py --docid 1234

出力: diagnose_output.txt
"""

import argparse
import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL          = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?'
WORKFLOW_URL = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex'
PASSWORD     = '156222'
BASE_DIR     = Path(__file__).parent
CACHE_FILE   = BASE_DIR / 'docs_cache.json'
OUT_FILE     = BASE_DIR / 'diagnose_output.txt'

XPATH_SEL_BTN = '//input[@class="jco-sel-btn"]'
XPATH_TREE1   = "(//ins[@class='jstree-icon'])[11]"
XPATH_TREE2   = "(//ins[@class='jstree-icon'])[14]"
XPATH_USER    = "//select[@name='uid']/option[@value='23']"
XPATH_PW      = "//input[@class='co-width-100p']"
XPATH_LOGIN   = "//a[@id='login-btn']"


def log(msg):
    text = str(msg).replace('\xa0', ' ')
    print(text.encode('cp932', errors='replace').decode('cp932'), flush=True)


def wait_click(driver, xpath, timeout=15):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(1.5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind',  default='契約連絡表')
    parser.add_argument('--docid', default='')
    args = parser.parse_args()

    # --docid 直接指定の場合はキャッシュ不要
    if args.docid:
        doc = {'title': f'doc_id={args.docid}', 'doc_id': args.docid, 'kind': args.kind}
    else:
        if not CACHE_FILE.exists():
            log(f'[ERROR] {CACHE_FILE} が存在しません。--docid で直接指定してください。')
            return
        with open(CACHE_FILE, encoding='utf-8') as f:
            docs = json.load(f)
        targets = [d for d in docs if d.get('kind') == args.kind and d.get('doc_id')]
        if not targets:
            log(f'対象書類が見つかりません: kind={args.kind}')
            return
        doc = targets[0]

    log(f'対象: {doc["title"][:60]}  doc_id={doc["doc_id"]}')

    driver = webdriver.Chrome()
    driver.maximize_window()

    lines = []
    def w(s=''):
        lines.append(s)
        print(s.encode('cp932', errors='replace').decode('cp932'), flush=True)

    try:
        log('[1] ログイン中...')
        driver.get(URL)
        time.sleep(2)
        wait_click(driver, XPATH_SEL_BTN)
        wait_click(driver, XPATH_TREE1)
        wait_click(driver, XPATH_TREE2)
        wait_click(driver, XPATH_USER)
        driver.find_element(By.XPATH, XPATH_PW).send_keys(PASSWORD)
        wait_click(driver, XPATH_LOGIN)
        time.sleep(3)
        log('[1] ログイン完了')

        log('[2] 書類を開く...')
        driver.get(f"{WORKFLOW_URL}#cmd=flowdisp&id={doc['doc_id']}")
        time.sleep(4)

        iframes = driver.find_elements(By.TAG_NAME, 'iframe')
        if not iframes:
            log('[ERROR] iframe が見つかりません')
            return

        driver.switch_to.frame(iframes[0])
        time.sleep(2)

        parts = driver.find_elements(By.CSS_SELECTOR, 'div.cdb-part.cdb-part-in-detail')
        w(f'=== 書類: {doc["title"][:60]} ===')
        w(f'=== kind: {doc["kind"]} ===')
        w(f'=== cdb-part-in-detail の総数: {len(parts)} ===')
        w()

        for i, part in enumerate(parts):
            text = part.text.strip()
            html = part.get_attribute('outerHTML') or ''
            w(f'--- div[{i}] ---')
            w(f'  .text (repr): {repr(text)}')
            w(f'  .text (raw):')
            for line in text.split('\n'):
                w(f'    | {line}')
            # HTML は長いので先頭300文字だけ
            w(f'  .outerHTML (先頭300文字):')
            w(f'    {html[:300]}')
            w()

        # 参考: 他のセレクターで取れる要素も確認
        w('=== 参考: cdb-part-label クラス ===')
        labels = driver.find_elements(By.CSS_SELECTOR, '[class*="cdb-part-label"], [class*="label"]')
        w(f'  件数: {len(labels)}')
        for el in labels[:5]:
            w(f'  text={repr(el.text[:50])}  class={el.get_attribute("class")}')

        w()
        w('=== 参考: cdb-text-view (値セル候補) ===')
        vals = driver.find_elements(By.CSS_SELECTOR, '[class*="cdb-text-view"], [class*="cdb-view"]')
        w(f'  件数: {len(vals)}')
        for el in vals[:5]:
            w(f'  text={repr(el.text[:50])}  class={el.get_attribute("class")}')

        driver.switch_to.default_content()

        OUT_FILE.write_text('\n'.join(lines), encoding='utf-8')
        log(f'\n[DONE] 出力: {OUT_FILE}')

    except Exception as e:
        import traceback
        log(f'[ERROR] {e}')
        log(traceback.format_exc())
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
