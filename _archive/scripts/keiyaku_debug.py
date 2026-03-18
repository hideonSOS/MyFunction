"""
keiyaku_debug.py  –  複写後のフォーム構造を調査する（1件だけ）
iframe の src / 入れ子 iframe / フィールドID を確認する
"""

import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR     = Path(__file__).parent
URL          = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?'
WORKFLOW_URL = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex'
PASSWORD     = '156222'
CACHE_FILE   = BASE_DIR / 'docs_cache.json'

XPATH_SEL_BTN  = '//input[@class="jco-sel-btn"]'
XPATH_TREE1    = "(//ins[@class='jstree-icon'])[11]"
XPATH_TREE2    = "(//ins[@class='jstree-icon'])[14]"
XPATH_USER     = "//select[@name='uid']/option[@value='23']"
XPATH_PW       = "//input[@class='co-width-100p']"
XPATH_LOGIN    = "//a[@id='login-btn']"
XPATH_COPY_BTN = "//input[@value='複写して作成']"
XPATH_IFRAME   = "//iframe[contains(@src, 'appsuite.cgi?cmd=cdbbrowsedetailframe')]"


def p(msg):
    print(str(msg).replace('\xa0', ' '), flush=True)


def wait_click(driver, xpath, timeout=15):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
    el.click()
    time.sleep(2)


def get_template_doc_id():
    with open(CACHE_FILE, encoding='utf-8') as f:
        docs = json.load(f)
    candidates = [d for d in docs if d.get('kind') == '契約連絡表' and d.get('doc_id')]
    doc = candidates[0]
    p(f"[TEMPLATE] doc_id={doc['doc_id']}  title={doc['title'][:60]}")
    return doc['doc_id']


driver = webdriver.Chrome()
driver.maximize_window()

try:
    # ---- ログイン ----
    p("[1] ログイン中...")
    driver.get(URL)
    time.sleep(2)
    wait_click(driver, XPATH_SEL_BTN)
    wait_click(driver, XPATH_TREE1)
    wait_click(driver, XPATH_TREE2)
    wait_click(driver, XPATH_USER)
    driver.find_element(By.XPATH, XPATH_PW).send_keys(PASSWORD)
    wait_click(driver, XPATH_LOGIN)
    time.sleep(3)
    p("[1] ログイン完了")

    # ---- テンプレート書類へ直接遷移 ----
    template_doc_id = get_template_doc_id()
    target_url = f"{WORKFLOW_URL}#cmd=flowdisp&id={template_doc_id}"
    p(f"[2] 書類を開く: {target_url}")
    driver.get(target_url)
    time.sleep(5)

    # ---- 複写 ----
    p("[3] 複写して作成ボタンを押す...")
    wait_click(driver, XPATH_COPY_BTN)
    time.sleep(6)
    p("[3] 複写完了 → フォーム構造を調査...")

    # ---- 現在の iframe 一覧（ネスト前） ----
    driver.switch_to.default_content()
    iframes = driver.find_elements(By.TAG_NAME, 'iframe')
    p(f"\n[INFO] default_content の iframe 数: {len(iframes)}")
    for i, ifr in enumerate(iframes):
        src = ifr.get_attribute('src') or ''
        p(f"  iframe[{i}] src={src[:100]}")

    # ---- 対象 iframe に切替 ----
    p(f"\n[4] iframe を切替: {XPATH_IFRAME}")
    try:
        iframe_el = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, XPATH_IFRAME))
        )
        p(f"  → iframe 発見  src={iframe_el.get_attribute('src')[:100]}")
        driver.switch_to.frame(iframe_el)
        time.sleep(3)
        p("  → switch_to.frame 完了")
    except Exception as e:
        p(f"  [ERROR] iframe 切替失敗: {e}")
        raise

    # ---- iframe 内の input / textarea 一覧 ----
    inputs = driver.find_elements(By.TAG_NAME, 'input')
    textareas = driver.find_elements(By.TAG_NAME, 'textarea')
    p(f"\n[INFO] iframe 内 input 数: {len(inputs)}  textarea 数: {len(textareas)}")

    p("\n--- input (id, class, value 先頭60) ---")
    for i, el in enumerate(inputs[:20]):
        eid   = el.get_attribute('id') or ''
        ecls  = el.get_attribute('class') or ''
        eval_ = (el.get_attribute('value') or '')[:60]
        p(f"  [{i}] id={eid}  class={ecls}  val={eval_!r}")

    p("\n--- textarea (id, value 先頭60) ---")
    for i, el in enumerate(textareas[:10]):
        eid   = el.get_attribute('id') or ''
        eval_ = (el.get_attribute('value') or el.text or '')[:60]
        p(f"  [{i}] id={eid}  val={eval_!r}")

    # ---- iframe 内にさらに iframe があるか確認 ----
    nested = driver.find_elements(By.TAG_NAME, 'iframe')
    p(f"\n[INFO] iframe 内の入れ子 iframe 数: {len(nested)}")
    for i, ifr in enumerate(nested):
        p(f"  nested_iframe[{i}] src={ifr.get_attribute('src') or ''}")

    p("\n[DONE] 調査完了。ブラウザを手動で閉じてください。")
    time.sleep(60)

finally:
    try:
        driver.quit()
    except Exception:
        pass
