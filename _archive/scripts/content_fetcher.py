"""
content_fetcher.py  –  デスクネッツ書類の中身を取得して docs_cache.json に追記

【重要】このスクリプトはデスクネッツを「読むだけ」です。
       書き込み・ボタン操作・保存は一切行いません。
       docs_cache.json の fields フィールドを埋めるだけです。

Usage:
    python content_fetcher.py           # fields 未取得の全件処理
    python content_fetcher.py --limit 5 # 最初の5件だけ（動作確認用）
"""

import argparse
import json
import re
import sys
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

# ── ラベル正規化（全角スペース・半角スペース除去） ──
def norm(t):
    return t.replace('\u3000', '').replace('\xa0', '').replace(' ', '').strip()

# 契約連絡表 の既知ラベル → フィールド名
KEIYAKU_LABELS = {
    '契約先名':     '契約先名',
    '契約担当':     '契約担当',
    '現場担当':     '現場担当',
    'ＴＥＬ':      'TEL',
    'TEL':         'TEL',
    '所在地':      '所在地',
    '業務対象':    '業務対象',
    '業務日':      '業務日',
    '業務内容':    '業務内容',
    '社名：':      '送付先_社名',
    '住所：':      '送付先_住所',
    '宛先：':      '送付先_宛先',
}

# 外注費連絡表 の既知ラベル → フィールド名
GAICHUU_LABELS = {
    '外注先名':     '外注先名',
    '契約担当':     '契約担当',
    '業務担当':     '業務担当',
    'ＴＥＬ':      'TEL',
    'TEL':         'TEL',
    '所在地':      '所在地',
    '業務対象':    '業務対象',
    '業務日':      '業務日',
    '業務内容':    '業務内容',
    '担当時間':    '担当時間',
    '銀行名':      '銀行名',
    '支店名':      '支店名',
    '口座番号':    '口座番号',
    '口座名義':    '口座名義',
    '支払方法':    '支払方法',
}


def log(msg):
    print(str(msg).encode('cp932', errors='replace').decode('cp932'), flush=True)


def load_cache():
    with open(CACHE_FILE, encoding='utf-8') as f:
        return json.load(f)


def save_cache(docs):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)


def wait_click(driver, xpath, timeout=15):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    el.click()
    time.sleep(1.5)


def login(driver):
    log('[1] ログイン中...')
    driver.get(URL)
    time.sleep(2)
    wait_click(driver, '//input[@class="jco-sel-btn"]')
    wait_click(driver, "(//ins[@class='jstree-icon'])[11]")
    wait_click(driver, "(//ins[@class='jstree-icon'])[14]")
    wait_click(driver, "//select[@name='uid']/option[@value='23']")
    driver.find_element(By.XPATH, "//input[@class='co-width-100p']").send_keys(PASSWORD)
    wait_click(driver, "//a[@id='login-btn']")
    time.sleep(3)
    log('[1] ログイン完了')


def extract_label_values(texts, label_map):
    """
    テキストリストからラベル→値ペアを抽出
    ラベルの前後両方向を探索（レイアウトによって前後どちらにも値が来るため）
    """
    result = {}
    label_set = set(label_map.keys())

    for i, raw in enumerate(texts):
        n = norm(raw)
        if n not in label_set:
            continue
        field_name = label_map[n]
        if field_name in result:
            continue  # 先勝ち

        # 前方探索（ラベル → 値）
        for j in range(i + 1, min(i + 6, len(texts))):
            val = texts[j].strip()
            if val and norm(val) not in label_set:
                result[field_name] = val
                break

        # 見つからなければ後方探索（値 → ラベル）
        if field_name not in result:
            for j in range(i - 1, max(-1, i - 6), -1):
                val = texts[j].strip()
                if val and norm(val) not in label_set:
                    result[field_name] = val
                    break

    return result


def extract_financial(all_text):
    """金額フィールドをパターンマッチで抽出"""
    result = {}

    # 税抜き: ¥XXX,XXX(税別) or 類似
    m = re.search(r'([\\¥￥]\s*[\d,]+\s*[\(（][^）\)]*税別[^）\)]*[\)）])', all_text)
    if m:
        result['税抜き'] = m.group(1).strip()

    # 消費税・総額: ¥XXX(消費税)〜¥XXX（総額）
    m = re.search(
        r'([\\¥￥]\s*[\d,\s]+[\(（][^）\)]*消費税[^）\)]*[\)）]'
        r'.*?'
        r'[\\¥￥]\s*[\d,\s]+[\(（][^）\)]*総額[^）\)]*[\)）])',
        all_text, re.DOTALL
    )
    if m:
        result['消費税・総額'] = m.group(0).strip()

    return result


def extract_fields(driver, kind):
    """
    書類の VIEW モードからフィールドを読み取る（読むだけ）
    """
    fields = {}

    # ── iframe に切替 ──
    iframes = driver.find_elements(By.TAG_NAME, 'iframe')
    if not iframes:
        return fields

    driver.switch_to.frame(iframes[0])
    time.sleep(2)

    # ── 全テキストを収集（cdb-part-in-detail の各 div から） ──
    parts = driver.find_elements(By.CSS_SELECTOR, 'div.cdb-part.cdb-part-in-detail')
    texts = [p.text.strip() for p in parts]

    # 全体テキスト（金額パターン抽出用）
    all_text = '\n'.join(t for t in texts if t)

    # ── ラベル→値 抽出 ──
    label_map = KEIYAKU_LABELS if kind == '契約連絡表' else \
                GAICHUU_LABELS if kind == '外注費連絡表' else {}
    if label_map:
        fields.update(extract_label_values(texts, label_map))

    # ── 金額フィールド（パターンマッチ） ──
    fields.update(extract_financial(all_text))

    # ── 稟議書など：全文を格納 ──
    if not label_map and all_text:
        fields['_full_text'] = all_text[:500]

    driver.switch_to.default_content()
    return fields


def fetch_one(driver, doc):
    doc_id = doc.get('doc_id', '')
    if not doc_id:
        return {'_error': 'doc_id なし'}

    target_url = f"{WORKFLOW_URL}#cmd=flowdisp&id={doc_id}"
    driver.get(target_url)
    time.sleep(4)

    try:
        return extract_fields(driver, doc.get('kind', ''))
    except Exception as e:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return {'_error': str(e)[:120]}


def main():
    parser = argparse.ArgumentParser(
        description='書類中身を取得して docs_cache.json に追記（読み取り専用）'
    )
    parser.add_argument('--limit', type=int, metavar='N',
                        help='最初の N 件だけ処理（動作確認用）')
    args = parser.parse_args()

    docs = load_cache()
    targets = [(i, d) for i, d in enumerate(docs) if d.get('fields') is None]

    if args.limit:
        targets = targets[:args.limit]

    log(f'[設定] 未取得: {len(targets)} 件  (全 {len(docs)} 件中)')

    if not targets:
        log('[INFO] 未取得の書類はありません。')
        return

    driver = webdriver.Chrome()
    driver.maximize_window()

    ok = err = 0
    try:
        login(driver)

        for n, (idx, doc) in enumerate(targets):
            title = doc.get('title', '').replace('\xa0', ' ')
            log(f'[{n+1}/{len(targets)}] {title[:55]}')

            fields = fetch_one(driver, doc)
            docs[idx]['fields'] = fields

            if '_error' in fields:
                log(f'  -> ERROR: {fields["_error"]}')
                err += 1
            else:
                keys = [k for k in fields if not k.startswith('_')]
                log(f'  -> OK  {keys}')
                ok += 1

            # 1件ごとに保存（中断しても進捗保持）
            save_cache(docs)

        log(f'\n[完了] 成功: {ok} 件 / エラー: {err} 件')

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
