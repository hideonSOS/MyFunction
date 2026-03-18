"""
list_inspect.py  –  作成分（完了）一覧ページのHTML構造を調査する
実行: python list_inspect.py
"""

import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL          = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?'
WORKFLOW_URL = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex'
PASSWORD     = '156222'

xpath_sel_btn = '//input[@class="jco-sel-btn"]'
xpath_tree1   = "(//ins[@class='jstree-icon'])[11]"
xpath_tree2   = "(//ins[@class='jstree-icon'])[14]"
xpath_user    = "//select[@name='uid']/option[@value='23']"
xpath_pw      = "//input[@class='co-width-100p']"
xpath_login   = "//a[@id='login-btn']"

def log(msg):
    print(msg, flush=True)

def wait_click(driver, xpath, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(2)

# ============================================================
# 一覧ページの構造を丸ごと調査するJS
# ============================================================
JS_INSPECT_LIST = """
var result = {};

// 1. ページ内の全リンク (a タグ) を先頭20件
var links = document.querySelectorAll('a');
result.links = [];
links.forEach(function(a, i) {
    if (i >= 30) return;
    result.links.push({
        i: i,
        text: a.innerText.trim().substring(0, 60),
        href: (a.getAttribute('href') || '').substring(0, 80),
        cls:  a.className || '',
        onclick: (a.getAttribute('onclick') || '').substring(0, 80)
    });
});

// 2. ページ内の全 input[type=button] と button
result.buttons = [];
document.querySelectorAll('input[type=button], input[type=submit], button').forEach(function(el, i) {
    if (i >= 20) return;
    result.buttons.push({
        i: i,
        tag:   el.tagName,
        value: (el.value || el.innerText || '').trim().substring(0, 40),
        cls:   el.className || '',
        onclick: (el.getAttribute('onclick') || '').substring(0, 80)
    });
});

// 3. tr 行数（テーブルの件数把握）
result.table_rows = document.querySelectorAll('tr').length;

// 4. ページ番号・ページネーション関連テキスト
// class に page/pager/navi を含む要素
result.page_elements = [];
document.querySelectorAll('[class*="page"],[class*="pager"],[class*="navi"],[class*="next"],[class*="prev"]').forEach(function(el, i) {
    if (i >= 20) return;
    result.page_elements.push({
        tag: el.tagName,
        cls: el.className,
        text: el.innerText.trim().substring(0, 60)
    });
});

// 5. 一覧の最初の数行のHTML（テーブル構造確認）
var rows = document.querySelectorAll('tr');
result.first_rows_html = [];
for (var i = 0; i < Math.min(5, rows.length); i++) {
    result.first_rows_html.push(rows[i].outerHTML.substring(0, 300));
}

// 6. 現在のURL
result.current_url = location.href;

// 7. select 要素一覧
result.selects = [];
document.querySelectorAll('select').forEach(function(s, i) {
    var opts = [];
    s.querySelectorAll('option').forEach(function(o) { opts.push(o.text.trim()); });
    result.selects.push({i: i, name: s.name, opts: opts});
});

return JSON.stringify(result);
"""

def main():
    driver = webdriver.Chrome()
    driver.maximize_window()

    try:
        log("[1] ログイン中...")
        driver.get(URL)
        time.sleep(2)
        wait_click(driver, xpath_sel_btn)
        wait_click(driver, xpath_tree1)
        wait_click(driver, xpath_tree2)
        wait_click(driver, xpath_user)
        driver.find_element(By.XPATH, xpath_pw).send_keys(PASSWORD)
        wait_click(driver, xpath_login)
        time.sleep(3)
        log("[1] ログイン完了")

        log("[2] ワークフロー一覧へ...")
        driver.get(WORKFLOW_URL)
        time.sleep(4)

        log("[3] 作成分（完了）を選択中...")
        all_selects = driver.find_elements(By.TAG_NAME, 'select')
        for s in all_selects:
            opts = s.find_elements(By.TAG_NAME, 'option')
            if any('作成分' in o.text for o in opts):
                for o in opts:
                    if '作成分（完了' in o.text:
                        o.click()
                        log(f"[3] '{o.text}' 選択完了")
                        break
                break
        time.sleep(4)

        log("[4] ページ構造を調査中...")
        raw    = driver.execute_script(JS_INSPECT_LIST)
        result = json.loads(raw)

        # ---- 出力 ----
        log(f"\n現在のURL: {result.get('current_url','')}")
        log(f"テーブル行数: {result.get('table_rows', 0)}")

        log("\n=== SELECT 要素 ===")
        for s in result.get('selects', []):
            log(f"  [{s['i']}] name={s['name']}  opts={s['opts']}")

        log("\n=== リンク (先頭30件) ===")
        for lk in result.get('links', []):
            log(f"  [{lk['i']:2d}] cls='{lk['cls']}'  text='{lk['text']}'  href='{lk['href']}'  onclick='{lk['onclick']}'")

        log("\n=== ボタン ===")
        for b in result.get('buttons', []):
            log(f"  [{b['i']:2d}] {b['tag']}  value='{b['value']}'  cls='{b['cls']}'  onclick='{b['onclick']}'")

        log("\n=== ページネーション関連要素 ===")
        for p in result.get('page_elements', []):
            log(f"  tag={p['tag']}  cls='{p['cls']}'  text='{p['text']}'")

        log("\n=== 最初の5行HTML ===")
        for i, html in enumerate(result.get('first_rows_html', [])):
            log(f"  --- row[{i}] ---")
            log(f"  {html}")

        log("\n[DONE] 調査完了")

    except Exception as e:
        import traceback
        log(f"[ERROR] {e}")
        log(traceback.format_exc())

    finally:
        input("\nEnterでブラウザを閉じます...")
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == '__main__':
    main()
