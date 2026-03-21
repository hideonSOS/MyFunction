"""
docs_fetcher.py  –  デスクネッツ 作成分（完了）一覧を取得 + 各書類の中身を取得
                    → docs_cache.json に保存する（読み取り専用）

1回のブラウザ起動で以下をまとめて実行:
  1. ワークフロー一覧ページから書類リストを取得
  2. fields が未取得の書類を1件ずつ開いてフィールドを読み取り
  3. 1件ごとに docs_cache.json に保存（中断しても進捗保持）
"""

import json
import re
import sys
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

URL          = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/dneo.cgi?'
WORKFLOW_URL = 'https://dn.yamatocorporation.jp/cgi-bin/dneo/zflow.cgi?cmd=flowindex'
PASSWORD     = '156222'
OUT_FILE     = Path('docs_cache.json')
DEBUG_FILE   = Path('debug_raw.json')

xpath_sel_btn = '//input[@class="jco-sel-btn"]'
xpath_tree1   = "(//ins[@class='jstree-icon'])[11]"
xpath_tree2   = "(//ins[@class='jstree-icon'])[14]"
xpath_user    = "//select[@name='uid']/option[@value='23']"
xpath_pw      = "//input[@class='co-width-100p']"
xpath_login   = "//a[@id='login-btn']"

def log(msg):
    text = str(msg).replace('\xa0', ' ')
    print(text, flush=True)

_step = 0
def slog(msg):
    global _step
    _step += 1
    log(f"[{_step}] {msg}")


def wait_click(driver, xpath, timeout=10):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(2)


def classify(title):
    if '契約連絡表' in title:
        return '契約連絡表'
    if '外注費連絡表' in title:
        return '外注費連絡表'
    return '稟議書'


# ── 一覧取得ヘルパー ──────────────────────────────

def find_list_frame(driver):
    driver.switch_to.default_content()
    frames = driver.find_elements(By.TAG_NAME, 'frame')
    log(f"    frame数: {len(frames)}")
    if not frames:
        return None
    for i in range(len(frames)):
        driver.switch_to.default_content()
        driver.switch_to.frame(i)
        rows = driver.find_elements(By.CSS_SELECTOR, 'tr.flow-list-line')
        if rows:
            log(f"    → frame[{i}] にリスト発見")
            return i
    driver.switch_to.default_content()
    return None


def scrape_rows(rows):
    result = []
    for row in rows:
        try:
            links = row.find_elements(By.CSS_SELECTOR, 'a[href*="flowdisp"]')
            a = None
            for lnk in links:
                t = (lnk.get_attribute('title') or '').strip()
                if t:
                    a = lnk
                    break
            if a is None:
                continue
            title = a.get_attribute('title').strip()
            if not title:
                continue
            doc_id = ''
            try:
                chk = row.find_element(By.CSS_SELECTOR, 'input[name="id"]')
                doc_id = chk.get_attribute('value') or ''
            except Exception:
                pass
            date = ''
            tds = row.find_elements(By.TAG_NAME, 'td')
            for td in reversed(tds):
                t = td.text.strip()
                if t and re.search(r'\d{2}/\d{2}', t):
                    date = t
                    break
            kind = classify(title)
            result.append({'title': title, 'date': date, 'doc_id': doc_id, 'kind': kind})
        except Exception as ex:
            log(f"    ROW SKIP: {ex}")
            continue
    return result


def scrape_current_page(driver, frame_idx):
    if frame_idx is not None:
        driver.switch_to.default_content()
        driver.switch_to.frame(frame_idx)
    rows = driver.find_elements(By.CSS_SELECTOR, 'tr.flow-list-line')
    log(f"    行数: {len(rows)}")
    result = scrape_rows(rows)
    for i, r in enumerate(result[:3]):
        log(f"    SAMPLE[{i}] title={r['title'][:60]!r}  doc_id={r['doc_id']}")
    return result


def click_next_page(driver, frame_idx):
    if frame_idx is not None:
        driver.switch_to.default_content()
        driver.switch_to.frame(frame_idx)
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, 'li.co-page-next a.co-page-link')
        next_btn.click()
        log("  → 次ページへ移動")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'tr.flow-list-line'))
        )
        time.sleep(1)
        return True
    except Exception:
        return False


def merge_cache(new_docs, existing_docs):
    """既存 fields を保持しながらマージ"""
    existing_map = {d['doc_id']: d for d in existing_docs if d.get('doc_id')}
    result = []
    for d in new_docs:
        existing = existing_map.get(d['doc_id'])
        d['fields'] = existing.get('fields') if existing else None
        result.append(d)
    new_ids = {d['doc_id'] for d in new_docs if d['doc_id']}
    old_unique = [d for d in existing_docs if d.get('doc_id') not in new_ids]
    return result + old_unique


# ── 書類別フィールドマップ ──────────────────────────
# (書類種別, 'inp'|'ta', 1始まりインデックス) → フィールド名
# diagnose_elements_output.txt で確定したDOM順インデックスを直書き

FIELD_MAP = {
    # 契約連絡表
    ('契約連絡表', 'inp',  7): '契約先名',
    ('契約連絡表', 'inp',  8): '契約担当',
    ('契約連絡表', 'inp',  9): '現場担当',
    ('契約連絡表', 'inp', 10): 'ＴＥＬ',
    ('契約連絡表', 'inp', 11): '所在地',
    ('契約連絡表', 'inp', 12): '業務日',
    ('契約連絡表', 'inp', 13): '業務内容',
    ('契約連絡表', 'inp', 15): '税別',
    ('契約連絡表', 'inp', 16): '住所：',
    ('契約連絡表', 'inp', 18): '社名：',
    ('契約連絡表', 'inp', 19): '宛先：',
    ('契約連絡表', 'ta',   1): '業務対象',
    ('契約連絡表', 'ta',   3): '総額',
    # 外注費連絡表
    ('外注費連絡表', 'inp',  9): '外注先名',
    ('外注費連絡表', 'inp', 10): '契約担当',
    ('外注費連絡表', 'inp', 11): '業務担当',
    ('外注費連絡表', 'inp', 12): 'ＴＥＬ',
    ('外注費連絡表', 'inp', 13): '所在地',
    ('外注費連絡表', 'inp', 14): '業務日',
    ('外注費連絡表', 'inp', 15): '業務内容',
    ('外注費連絡表', 'inp', 17): '税別',
    ('外注費連絡表', 'inp', 18): '支払方法',
    ('外注費連絡表', 'inp', 19): '銀行名：',
    ('外注費連絡表', 'inp', 20): '支店名：',
    ('外注費連絡表', 'inp', 21): '口座番号：',
    ('外注費連絡表', 'inp', 22): '口座名義：',
    ('外注費連絡表', 'ta',   1): '業務対象',
    ('外注費連絡表', 'ta',   2): '担当時間',
    ('外注費連絡表', 'ta',   3): '総額',
    # 稟議書
    ('稟議書', 'inp', 6): '件名',
    ('稟議書', 'ta',  1): '内容',
}


def extract_fields(driver, kind):
    """
    DOM要素のINP/TAインデックスで直接フィールドを取得する。
    FIELD_MAP に登録されたインデックスのみを保存し、それ以外は無視する。
    """
    fields = {}
    iframes = driver.find_elements(By.TAG_NAME, 'iframe')
    if not iframes:
        return fields
    driver.switch_to.frame(iframes[0])
    time.sleep(2)

    parts = driver.find_elements(By.CSS_SELECTOR, 'div.cdb-part.cdb-part-in-detail')
    inp_idx = 0
    ta_idx  = 0
    for el in parts:
        cls = el.get_attribute('class') or ''
        if 'cdb-part-label-none' not in cls:
            continue
        data_kind = el.get_attribute('data-kind') or ''
        if data_kind == 'textarea':
            ta_idx += 1
            field_name = FIELD_MAP.get((kind, 'ta', ta_idx))
        else:
            inp_idx += 1
            field_name = FIELD_MAP.get((kind, 'inp', inp_idx))
        if field_name is None:
            continue
        fields[field_name] = (el.text or '').strip()

    driver.switch_to.default_content()
    return fields


def fetch_contents(driver, all_docs):
    """fields が未取得の書類を1件ずつ開いて取得・保存"""
    targets = [(i, d) for i, d in enumerate(all_docs) if d.get('fields') is None]
    slog(f"書類内容取得: {len(targets)} 件（未取得分）")
    if not targets:
        slog("全件取得済み。スキップ。")
        return

    ok = err = 0
    for n, (idx, doc) in enumerate(targets):
        doc_id = doc.get('doc_id', '')
        title  = doc.get('title', '').replace('\xa0', ' ')
        slog(f"[{n+1}/{len(targets)}] {title[:55]}")

        if not doc_id:
            all_docs[idx]['fields'] = {'_error': 'doc_id なし'}
            err += 1
            continue

        target_url = f"{WORKFLOW_URL}#cmd=flowdisp&id={doc_id}"
        driver.get(target_url)
        time.sleep(4)

        try:
            driver.switch_to.default_content()
            fields = extract_fields(driver, doc.get('kind', ''))
        except Exception as e:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            fields = {'_error': str(e)[:120]}

        # フィールド値のバックスラッシュを円マークに置換
        for k in list(fields.keys()):
            if isinstance(fields[k], str):
                fields[k] = fields[k].replace('\\', '¥')

        all_docs[idx]['fields'] = fields

        if '_error' in fields:
            log(f"    -> ERROR: {fields['_error']}")
            err += 1
        else:
            keys = [k for k in fields if not k.startswith('_')]
            log(f"    -> OK  {keys}")
            ok += 1

        # 1件ごとに保存（中断しても進捗保持）
        with open(OUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_docs, f, ensure_ascii=False, indent=2)

    slog(f"内容取得完了: 成功 {ok} 件 / エラー {err} 件")


# ── メイン ───────────────────────────────────────

def main():
    mode = 'update'
    if '--full' in sys.argv:
        mode = 'full'
    elif not OUT_FILE.exists():
        log("[INFO] docs_cache.json が存在しないため full モードで実行します")
        mode = 'full'

    log(f"[MODE] {'全ページ取得 (FULL)' if mode == 'full' else '最新ページ更新 (UPDATE)'}")

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=options)

    try:
        slog("ログイン中...")
        driver.get(URL)
        time.sleep(2)
        wait_click(driver, xpath_sel_btn)
        wait_click(driver, xpath_tree1)
        wait_click(driver, xpath_tree2)
        wait_click(driver, xpath_user)
        driver.find_element(By.XPATH, xpath_pw).send_keys(PASSWORD)
        wait_click(driver, xpath_login)
        time.sleep(3)
        slog("ログイン完了")

        slog("ワークフロー画面へ...")
        driver.get(WORKFLOW_URL)
        time.sleep(4)

        slog("作成分（完了）を選択中...")
        driver.switch_to.default_content()
        target_select = None
        for s in driver.find_elements(By.TAG_NAME, 'select'):
            opts = s.find_elements(By.TAG_NAME, 'option')
            if any('作成分' in o.text for o in opts):
                target_select = s
                break
        if target_select is None:
            raise Exception("ステータス選択ドロップダウンが見つかりません")
        sel = Select(target_select)
        sel.select_by_visible_text('作成分（完了）')
        slog("'作成分（完了）' 選択完了 → リスト更新待ち...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'tr.flow-list-line'))
        )
        time.sleep(2)

        frame_idx = find_list_frame(driver)
        all_raw = []

        if mode == 'full':
            page = 1
            while True:
                slog(f"ページ {page} を取得中...")
                docs = scrape_current_page(driver, frame_idx)
                log(f"    → {len(docs)} 件")
                all_raw.extend(docs)
                if not click_next_page(driver, frame_idx):
                    slog(f"全 {page} ページ完了")
                    break
                time.sleep(3)
                page += 1
        else:
            slog("最新ページを取得中...")
            all_raw = scrape_current_page(driver, frame_idx)
            log(f"    → {len(all_raw)} 件")

        with open(DEBUG_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_raw[:30], f, ensure_ascii=False, indent=2)

        slog(f"一覧: 全 {len(all_raw)} 件")

        existing = []
        if OUT_FILE.exists():
            with open(OUT_FILE, encoding='utf-8') as f:
                existing = json.load(f)
            log(f"    既存キャッシュ: {len(existing)} 件")

        if mode == 'full':
            # full: 既存 fields を引き継ぎつつ全件置換
            existing_map = {d['doc_id']: d for d in existing if d.get('doc_id')}
            all_docs = []
            for d in all_raw:
                ex = existing_map.get(d['doc_id'])
                d['fields'] = ex.get('fields') if ex else None
                all_docs.append(d)
        else:
            all_docs = merge_cache(all_raw, existing)
            log(f"    マージ後合計: {len(all_docs)} 件")

        with open(OUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_docs, f, ensure_ascii=False, indent=2)
        slog(f"一覧保存完了（{len(all_docs)} 件）")

        # ── 書類内容を取得（同じブラウザセッションで） ──
        fetch_contents(driver, all_docs)

        log(f"\n[DONE] 完了（総計 {len(all_docs)} 件）")

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


if __name__ == '__main__':
    main()
