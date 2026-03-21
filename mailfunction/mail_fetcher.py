"""
mail_fetcher.py  –  Gmail API でメールを全件取得しキャッシュに保存する

モード:
  python mail_fetcher.py          # 差分更新（新着のみ取得）
  python mail_fetcher.py --full   # 全件取得（IDリスト全件を再確認）

キャッシュ: mailfunction/mail_cache.json
  - 1件ごとに保存するため中断しても進捗が保持される
  - 差分更新では既存キャッシュにないIDだけを取得・追記する
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

APP_DIR      = Path(__file__).resolve().parent          # mailfunction/
BASE_DIR     = APP_DIR.parent                           # プロジェクトルート
TOKEN_FILE   = APP_DIR / 'token.json'
CREDS_FILE   = BASE_DIR / 'credentials.json'
OUT_FILE     = APP_DIR / 'mail_cache.json'
DEBUG_FILE   = APP_DIR / 'mail_debug.json'
SCOPES       = ['https://www.googleapis.com/auth/gmail.readonly']


# ── ログ ─────────────────────────────────────────────
def log(msg):
    text = str(msg).replace('\xa0', ' ')
    print(text, flush=True)

_step = 0
def slog(msg):
    global _step
    _step += 1
    log(f"[{_step}] {msg}")


# ── 認証 ─────────────────────────────────────────────
def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError(
                f'token.json が無効です。再認証が必要です。({TOKEN_FILE})'
            )
    return creds


# ── キャッシュ読み込み ────────────────────────────────
def load_cache():
    if not OUT_FILE.exists():
        return []
    with open(OUT_FILE, encoding='utf-8') as f:
        return json.load(f)

def save_cache(mails):
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(mails, f, ensure_ascii=False, indent=2)


# ── ID リスト取得 ─────────────────────────────────────
def fetch_all_ids(service):
    """全メッセージIDをページネーションで取得（最大500件/リクエスト）"""
    ids = []
    page_token = None
    while True:
        kwargs = {'userId': 'me', 'maxResults': 500}
        if page_token:
            kwargs['pageToken'] = page_token
        resp = service.users().messages().list(**kwargs).execute()
        batch = resp.get('messages', [])
        ids.extend(m['id'] for m in batch)
        page_token = resp.get('nextPageToken')
        slog(f"ID取得中... {len(ids)} 件")
        if not page_token:
            break
    return ids


def fetch_new_ids(service, existing_ids: set):
    """新着IDのみ取得（既存IDが現れたらページネーション停止）"""
    new_ids = []
    page_token = None
    while True:
        kwargs = {'userId': 'me', 'maxResults': 500}
        if page_token:
            kwargs['pageToken'] = page_token
        resp = service.users().messages().list(**kwargs).execute()
        batch = resp.get('messages', [])
        found_existing = False
        for m in batch:
            if m['id'] in existing_ids:
                found_existing = True
                break
            new_ids.append(m['id'])
        page_token = resp.get('nextPageToken')
        if found_existing or not page_token:
            break
        slog(f"新着ID取得中... {len(new_ids)} 件")
    return new_ids


# ── メール詳細取得 ────────────────────────────────────
def get_header(headers, name):
    return next((h['value'] for h in headers if h['name'].lower() == name.lower()), '')

def fetch_detail(service, msg_id):
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='metadata',
        metadataHeaders=['Subject', 'From', 'Date']
    ).execute()
    headers = msg.get('payload', {}).get('headers', [])
    return {
        'id':        msg_id,
        'thread_id': msg.get('threadId', ''),
        'subject':   get_header(headers, 'Subject') or '（件名なし）',
        'from':      get_header(headers, 'From'),
        'date':      get_header(headers, 'Date'),
        'snippet':   msg.get('snippet', ''),
        'labels':    msg.get('labelIds', []),
        'fetched_at': datetime.now(timezone.utc).isoformat(),
    }


# ── メイン ───────────────────────────────────────────
def main():
    mode = 'full' if '--full' in sys.argv else 'update'
    slog(f"開始（モード: {mode}）")

    slog("認証中...")
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)
    slog("認証完了")

    # 既存キャッシュを読み込み
    existing = load_cache()
    existing_map = {m['id']: m for m in existing}
    existing_ids = set(existing_map.keys())
    slog(f"既存キャッシュ: {len(existing)} 件")

    # 取得対象IDを決定
    if mode == 'full':
        slog("全件IDリストを取得中...")
        all_ids = fetch_all_ids(service)
        slog(f"全件ID取得完了: {len(all_ids)} 件")
        # キャッシュにないIDだけを対象にする
        target_ids = [i for i in all_ids if i not in existing_ids]
        slog(f"未取得: {len(target_ids)} 件")
    else:
        slog("新着IDを確認中...")
        target_ids = fetch_new_ids(service, existing_ids)
        slog(f"新着: {len(target_ids)} 件")

    if not target_ids:
        slog("新着メールはありません")
        log('[DONE] 完了（追加なし）')
        return

    # 詳細取得・1件ごとにキャッシュ保存
    slog(f"詳細取得開始: {len(target_ids)} 件")
    ok = err = 0
    new_mails = []

    for n, msg_id in enumerate(target_ids):
        try:
            detail = fetch_detail(service, msg_id)
            new_mails.append(detail)
            ok += 1
        except Exception as e:
            new_mails.append({
                'id': msg_id, 'subject': '[取得エラー]',
                'from': '', 'date': '', 'snippet': str(e)[:120],
                'labels': [], 'fetched_at': datetime.now(timezone.utc).isoformat(),
            })
            err += 1

        # 50件ごとに保存（中断しても進捗保持）
        if (n + 1) % 50 == 0:
            merged = list(existing_map.values()) + new_mails
            save_cache(merged)
            slog(f"[{n+1}/{len(target_ids)}] 保存中... 成功 {ok} / エラー {err}")

    # 最終保存（新着を先頭に追加）
    merged = new_mails + list(existing_map.values())
    save_cache(merged)

    slog(f"詳細取得完了: 成功 {ok} 件 / エラー {err} 件")
    slog(f"キャッシュ合計: {len(merged)} 件")
    log(f'[DONE] 完了（総計 {len(merged)} 件）')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        log(f'[ERROR] {e}')
        log(traceback.format_exc())
        sys.exit(1)
