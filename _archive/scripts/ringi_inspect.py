"""
ringi_inspect.py  –  フォームフィールド調査スクリプト
契約連絡表・外注費連絡表のiframe内 input/textarea を全列挙して
XPathインデックスと現在値を出力する。
"""

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

xpath_sel_btn       = '//input[@class="jco-sel-btn"]'
xpath_tree1         = "(//ins[@class='jstree-icon'])[11]"
xpath_tree2         = "(//ins[@class='jstree-icon'])[14]"
xpath_user          = "//select[@name='uid']/option[@value='23']"
xpath_pw            = "//input[@class='co-width-100p']"
xpath_login         = "//a[@id='login-btn']"
xpath_status_select = "(//select)[4]"
xpath_copy_btn      = "//input[@value='複写して作成']"
target_iframe       = "//iframe[contains(@src, 'appsuite.cgi?cmd=cdbbrowsedetailframe')]"

JS_INSPECT = """
var results = [];

// ---- input 系 ----
var inputs = document.querySelectorAll('input.cdb-text-input');
inputs.forEach(function(el, i) {
    results.push({
        kind:  'input',
        index: i + 1,
        name:  el.name  || '',
        id:    el.id    || '',
        label: (el.closest('tr') || el.closest('div') || {}).innerText || '',
        value: el.value || ''
    });
});

// ---- textarea 系 ----
var tas = document.querySelectorAll('textarea');
tas.forEach(function(el, i) {
    results.push({
        kind:  'textarea',
        index: i + 1,
        name:  el.name  || '',
        id:    el.id    || '',
        label: (el.closest('tr') || el.closest('div') || {}).innerText || '',
        value: el.value || ''
    });
});

return JSON.stringify(results);
"""

# 件名欄（iframe外）の調査用
JS_SUBJECT = """
var el = document.querySelector('input.jco-input-subject');
return el ? JSON.stringify({id: el.id, name: el.name, value: el.value}) : 'NOT FOUND';
"""

def wait_click(driver, xpath, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(2)

def login(driver):
    print("[LOGIN] ログイン中...")
    driver.get(URL)
    time.sleep(2)
    wait_click(driver, xpath_sel_btn)
    wait_click(driver, xpath_tree1)
    wait_click(driver, xpath_tree2)
    wait_click(driver, xpath_user)
    driver.find_element(By.XPATH, xpath_pw).send_keys(PASSWORD)
    wait_click(driver, xpath_login)
    time.sleep(3)
    print("[LOGIN] 完了")

def goto_kanryo_list(driver):
    driver.get(WORKFLOW_URL)
    time.sleep(3)
    sel = driver.find_element(By.XPATH, xpath_status_select)
    for opt in sel.find_elements(By.TAG_NAME, 'option'):
        if '作成分（完了' in opt.text:
            opt.click()
            break
    time.sleep(2)

def open_copy_form(driver, link_text_contains):
    """指定キーワードを含む書類を開いて「複写して作成」"""
    xpath = f"(//a[contains(text(), '{link_text_contains}')])[1]"
    wait_click(driver, xpath)
    time.sleep(3)
    wait_click(driver, xpath_copy_btn)
    time.sleep(4)

def inspect_form(driver, label):
    import json

    print(f"\n{'='*60}")
    print(f"  {label}  フィールド調査")
    print(f"{'='*60}")

    # iframe外: 件名
    try:
        subj = driver.execute_script(JS_SUBJECT)
        print(f"\n[件名欄（iframe外）]\n  {subj}")
    except Exception as e:
        print(f"[件名欄エラー] {e}")

    # iframe切替
    try:
        iframe = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, target_iframe))
        )
        driver.switch_to.frame(iframe)
        time.sleep(2)
    except Exception as e:
        print(f"[iframe切替エラー] {e}")
        return

    # フィールド全列挙
    try:
        raw = driver.execute_script(JS_INSPECT)
        fields = json.loads(raw)
    except Exception as e:
        print(f"[JS実行エラー] {e}")
        driver.switch_to.default_content()
        return

    print(f"\n{'--- input フィールド ---':}")
    inp_fields = [f for f in fields if f['kind'] == 'input']
    for f in inp_fields:
        label_short = f['label'].replace('\n', ' ').strip()[:40]
        print(f"  [{f['index']:2d}] name={f['name']:<30} id={f['id']:<40} val=\"{f['value'][:30]}\"")
        if label_short:
            print(f"        label: {label_short}")

    print(f"\n--- textarea フィールド ---")
    ta_fields = [f for f in fields if f['kind'] == 'textarea']
    for f in ta_fields:
        label_short = f['label'].replace('\n', ' ').strip()[:40]
        val_short   = f['value'].replace('\n', '\\n')[:50]
        print(f"  [{f['index']:2d}] name={f['name']:<30} id={f['id']:<40} val=\"{val_short}\"")
        if label_short:
            print(f"        label: {label_short}")

    # 絶対XPath取得（textarea）
    print(f"\n--- textarea 絶対XPath ---")
    JS_ABS = """
var tas = document.querySelectorAll('textarea');
var out = [];
function getXPath(el) {
    if (el.id) return '//*[@id="' + el.id + '"]';
    var path = '';
    while (el && el.nodeType === 1) {
        var idx = 1;
        var sib = el.previousSibling;
        while (sib) { if (sib.nodeType===1 && sib.tagName===el.tagName) idx++; sib=sib.previousSibling; }
        path = '/' + el.tagName.toLowerCase() + '[' + idx + ']' + path;
        el = el.parentNode;
    }
    return path;
}
tas.forEach(function(el, i) {
    out.push({index: i+1, xpath: getXPath(el), name: el.name, value: el.value.substring(0,30)});
});
return JSON.stringify(out);
"""
    try:
        raw2 = driver.execute_script(JS_ABS)
        abs_list = json.loads(raw2)
        for a in abs_list:
            print(f"  [{a['index']:2d}] {a['xpath']}")
            if a['value']:
                print(f"        val: \"{a['value']}\"")
    except Exception as e:
        print(f"[絶対XPathエラー] {e}")

    driver.switch_to.default_content()
    print(f"\n{'='*60}\n")

def main():
    driver = webdriver.Chrome()
    driver.maximize_window()

    try:
        login(driver)

        # ========================================
        # 1. 契約連絡表 調査
        # ========================================
        print("\n[1/2] 契約連絡表を開きます...")
        goto_kanryo_list(driver)
        open_copy_form(driver, '契約連絡表')
        inspect_form(driver, '契約連絡表')

        input("\n契約連絡表の調査完了。Enterで外注費連絡表へ...")

        # ========================================
        # 2. 外注費連絡表 調査
        # ========================================
        print("\n[2/2] 外注費連絡表を開きます...")
        goto_kanryo_list(driver)
        open_copy_form(driver, '外注費連絡表')
        inspect_form(driver, '外注費連絡表')

        print("\n★ 調査完了 ★")
        print("上記の出力をコピーして共有してください。")

    except Exception as e:
        import traceback
        print(f"\n[ERROR] {e}")
        traceback.print_exc()

    finally:
        input("\nEnterでブラウザを閉じます...")
        driver.quit()

if __name__ == '__main__':
    main()
