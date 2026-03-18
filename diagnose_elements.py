"""
diagnose_elements.py  – フォームの全input/textarea要素をインデックス付きで列挙する
Usage: python diagnose_elements.py
"""

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

XPATH_SEL_BTN = '//input[@class="jco-sel-btn"]'
XPATH_TREE1   = "(//ins[@class='jstree-icon'])[11]"
XPATH_TREE2   = "(//ins[@class='jstree-icon'])[14]"
XPATH_USER    = "//select[@name='uid']/option[@value='23']"
XPATH_PW      = "//input[@class='co-width-100p']"
XPATH_LOGIN   = "//a[@id='login-btn']"

TARGETS = [
    {'kind': '契約連絡表',   'doc_id': '4695'},
    {'kind': '外注費連絡表', 'doc_id': '4565'},
    {'kind': '稟議書',      'doc_id': '4676'},
]

OUT_FILE = Path('diagnose_elements_output.txt')


def wait_click(driver, xpath, timeout=15):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(1.5)


def diagnose(driver, kind, doc_id):
    lines = []
    lines.append(f'\n{"="*60}')
    lines.append(f'【{kind}】  doc_id={doc_id}')
    lines.append(f'{"="*60}')

    driver.get(f'{WORKFLOW_URL}#cmd=flowdisp&id={doc_id}')
    time.sleep(4)
    driver.switch_to.default_content()

    # iframe に切替
    iframes = driver.find_elements(By.TAG_NAME, 'iframe')
    if not iframes:
        lines.append('  [ERROR] iframe が見つかりません')
        return lines
    driver.switch_to.frame(iframes[0])
    time.sleep(2)

    # cdb-part-in-detail の全要素をDOM順で列挙
    parts = driver.find_elements(By.CSS_SELECTOR, 'div.cdb-part.cdb-part-in-detail')
    lines.append(f'\n--- cdb-part-in-detail ({len(parts)}件) ---')
    inp_idx = 0
    ta_idx  = 0
    for i, el in enumerate(parts):
        cls      = el.get_attribute('class') or ''
        data_kind = el.get_attribute('data-kind') or ''
        text     = (el.text or '').strip().replace('\n', ' | ')
        is_value = 'cdb-part-label-none' in cls
        if is_value:
            if data_kind == 'textarea':
                ta_idx += 1
                idx_str = f'TA[{ta_idx}]'
            else:
                inp_idx += 1
                idx_str = f'INP[{inp_idx}]'
            lines.append(f'  {idx_str:10s}  kind={data_kind:15s}  {repr(text[:80])}')
        else:
            lines.append(f'  {"LABEL":10s}  kind={data_kind:15s}  {repr(text[:80])}')

    driver.switch_to.default_content()
    return lines


def main():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=options)

    all_lines = []
    try:
        print('[1] ログイン中...')
        driver.get(URL)
        time.sleep(2)
        wait_click(driver, XPATH_SEL_BTN)
        wait_click(driver, XPATH_TREE1)
        wait_click(driver, XPATH_TREE2)
        wait_click(driver, XPATH_USER)
        driver.find_element(By.XPATH, XPATH_PW).send_keys(PASSWORD)
        wait_click(driver, XPATH_LOGIN)
        time.sleep(3)
        print('[1] ログイン完了')

        for t in TARGETS:
            print(f'[診断] {t["kind"]} (doc_id={t["doc_id"]}) ...')
            lines = diagnose(driver, t['kind'], t['doc_id'])
            all_lines.extend(lines)
            for l in lines:
                print(l)

    finally:
        driver.quit()

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_lines))
    print(f'\n[完了] {OUT_FILE} に出力しました')


if __name__ == '__main__':
    main()
