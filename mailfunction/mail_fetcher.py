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
import os
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
LABEL_FILE   = APP_DIR / 'label_cache.json'   # ラベルID → 名前 の対応表
CONTACT_FILE = APP_DIR / 'contact_cache.json' # メールアドレス → 連絡先の登録名
CONTACTS_SCOPE = 'https://www.googleapis.com/auth/contacts.readonly'
PROFILE_SCOPE  = 'https://www.googleapis.com/auth/userinfo.profile'
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
        # 付与済みの権限のまま読む。SCOPES を渡すと更新時に token.json の権限が
        # gmail.readonly だけに上書きされ、送信・連絡先の権限情報が失われる
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))

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
    # 一時ファイルに書き切ってから置き換える。画面側が書き込み途中の
    # 不完全なJSONを読んでエラーになるのを防ぐ（定期更新で頻度が上がるため）
    tmp = OUT_FILE.with_name(OUT_FILE.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(mails, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_FILE)


def save_label_cache(service):
    """Gmail のラベル一覧（ID・名前・種別）を保存する。
    キャッシュのメールはラベルを内部ID（Label_123…）で持つため、画面表示に名前が要る"""
    labels = service.users().labels().list(userId='me').execute().get('labels', [])
    data = [{'id': l['id'], 'name': l.get('name', l['id']), 'type': l.get('type', '')}
            for l in labels]
    tmp = LABEL_FILE.with_name(LABEL_FILE.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LABEL_FILE)
    return data


# 取り込み済みメールでも後から変わりうるラベル（マイラベルに加えて同期する）
SYNC_SYSTEM_LABELS = ['INBOX', 'UNREAD', 'STARRED']


def _ids_with_label(service, label_id):
    """指定ラベルが付いているメールIDの集合（IDだけ取るので軽い）"""
    ids, token = set(), None
    while True:
        res = service.users().messages().list(
            userId='me', labelIds=[label_id], maxResults=500, pageToken=token,
            fields='messages/id,nextPageToken').execute()
        ids.update(m['id'] for m in res.get('messages', []))
        token = res.get('nextPageToken')
        if not token:
            return ids


def sync_labels(service, mails, user_label_ids):
    """取り込み済みメールのラベルをGmailの現状に合わせる。
    新着取得時にしかラベルを記録しないため、後から付けた／外したラベル、
    既読化・スターの付け外しが反映されない問題への対処。変更件数を返す"""
    targets = list(user_label_ids) + SYNC_SYSTEM_LABELS
    members = {lid: _ids_with_label(service, lid) for lid in targets}
    changed = 0
    for m in mails:
        labels = list(m.get('labels') or [])
        now = set(labels)
        for lid in targets:
            if m['id'] in members[lid]:
                now.add(lid)
            else:
                now.discard(lid)
        if now != set(labels):
            # 元の並びを保ちつつ、追加分を末尾へ
            m['labels'] = [l for l in labels if l in now] + sorted(now - set(labels))
            changed += 1
    return changed


def _own_names(creds, gmail_service):
    """ホストアカウント自身のアドレス（送信元エイリアス含む）→ 現在の名前。
    Gmailの「送信者名」が設定されていればそれを、空ならGoogleアカウント名を使う。
    過去の送信メールはヘッダーに送信当時の名前が残っているため、ここで上書きして統一する"""
    account_name = ''
    if PROFILE_SCOPE in (creds.scopes or []):
        try:
            me = build('people', 'v1', credentials=creds).people().get(
                resourceName='people/me', personFields='names').execute()
            names = me.get('names') or []
            account_name = (names[0].get('displayName') or '').strip() if names else ''
        except Exception as e:
            log(f"[WARN] アカウント名の取得に失敗: {str(e)[:200]}")
    own = {}
    send_as = gmail_service.users().settings().sendAs().list(userId='me').execute()
    for s in send_as.get('sendAs', []):
        addr = (s.get('sendAsEmail') or '').strip().lower()
        name = (s.get('displayName') or '').strip() or account_name
        if addr and name:
            own[addr] = name
    return own


def save_contact_cache(creds, gmail_service=None):
    """Googleの連絡先から「メールアドレス → 登録名」の対応表を保存する。
    差出人ヘッダーに名前が無いメール（Gmailは画面上だけ連絡先名で補って表示している）
    を、MyFunction でも同じ名前で表示するため。自分自身のアドレスは現在の
    アカウント名で上書きする。権限が未付与なら None を返してスキップ"""
    if CONTACTS_SCOPE not in (creds.scopes or []):
        return None
    people = build('people', 'v1', credentials=creds)
    table, token = {}, None
    while True:
        res = people.people().connections().list(
            resourceName='people/me', personFields='names,emailAddresses',
            pageSize=1000, pageToken=token).execute()
        for p in res.get('connections', []):
            names = p.get('names') or []
            name = (names[0].get('displayName') or '').strip() if names else ''
            if not name:
                continue
            for e in p.get('emailAddresses') or []:
                addr = (e.get('value') or '').strip().lower()
                if addr:
                    table[addr] = name
        token = res.get('nextPageToken')
        if not token:
            break
    if gmail_service is not None:
        try:
            table.update(_own_names(creds, gmail_service))
        except Exception as e:
            log(f"[WARN] 自分の名前の取得に失敗: {str(e)[:200]}")
    tmp = CONTACT_FILE.with_name(CONTACT_FILE.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(table, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONTACT_FILE)
    return len(table)


# ── 同時実行の防止（定期更新cronと画面のSYNCボタンが重ならないように） ──
# /tmp は sticky + protected_regular により、他ユーザー作成のファイルを
# O_CREAT で開けない（root でも不可）。アプリの logs/ に置く
LOCK_FILE = BASE_DIR / 'logs' / 'mail_fetcher.lock'

def acquire_run_lock():
    """取得できたらロック用fdを返す（プロセス終了まで保持）。
    他で実行中なら None。POSIX 以外（ローカルWindows開発機）はロックしない"""
    if os.name != 'posix':
        return True
    import fcntl
    LOCK_FILE.parent.mkdir(exist_ok=True)
    # root(画面SYNC) と www-data(cron) の双方が開けるよう読み取り専用で作成・取得
    fd = os.open(str(LOCK_FILE), os.O_RDONLY | os.O_CREAT, 0o666)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


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
        metadataHeaders=['Subject', 'From', 'To', 'Date']
    ).execute()
    headers = msg.get('payload', {}).get('headers', [])
    return {
        'id':        msg_id,
        'thread_id': msg.get('threadId', ''),
        'subject':   get_header(headers, 'Subject') or '（件名なし）',
        'from':      get_header(headers, 'From'),
        'to':        get_header(headers, 'To'),
        'date':      get_header(headers, 'Date'),
        'snippet':   msg.get('snippet', ''),
        'labels':    msg.get('labelIds', []),
        'fetched_at': datetime.now(timezone.utc).isoformat(),
    }


# ── メイン ───────────────────────────────────────────
def main():
    mode = 'full' if '--full' in sys.argv else 'update'

    lock = acquire_run_lock()
    if lock is None:
        log('[SKIP] 別のメール更新が実行中のため今回はスキップしました')
        log('[DONE] 完了（スキップ）')
        return

    slog(f"開始（モード: {mode}）")

    slog("認証中...")
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)
    slog("認証完了")

    # ラベル名・連絡先名の対応表を更新（失敗してもメール取得は続行）
    user_label_ids = None
    try:
        label_data = save_label_cache(service)
        user_label_ids = [l['id'] for l in label_data if l['type'] == 'user']
        log(f"ラベル一覧を更新: {len(label_data)} 件")
    except Exception as e:
        log(f"[WARN] ラベル一覧の取得に失敗: {e}")
    try:
        n = save_contact_cache(creds, service)
        if n is None:
            log("連絡先: 権限が未付与のためスキップ（メール画面から再認証すると有効）")
        else:
            log(f"連絡先を更新: {n} アドレス")
    except Exception as e:
        log(f"[WARN] 連絡先の取得に失敗: {str(e)[:300]}")

    # 既存キャッシュを読み込み
    existing = load_cache()
    existing_map = {m['id']: m for m in existing}
    existing_ids = set(existing_map.keys())
    slog(f"既存キャッシュ: {len(existing)} 件")

    # 取り込み済みメールのラベル（マイラベル・受信トレイ・未読・スター）をGmailの現状へ
    if user_label_ids is not None and existing:
        try:
            changed = sync_labels(service, existing, user_label_ids)
            if changed:
                save_cache(existing)
            log(f"ラベルの付け外しを反映: {changed} 件")
        except Exception as e:
            log(f"[WARN] ラベルの同期に失敗: {str(e)[:200]}")

    # 取得対象IDを決定
    if mode == 'full':
        slog("全件IDリストを取得中...")
        all_ids = fetch_all_ids(service)
        slog(f"全件ID取得完了: {len(all_ids)} 件")

        # Gmailで削除・ゴミ箱・迷惑メールへ移動したメールをキャッシュから除く
        # （全件IDの一覧は通常の一覧のみで、ゴミ箱・迷惑メールは含まれない）
        live = set(all_ids)
        gone = [i for i in existing_ids if i not in live]
        # 安全装置: 一度に1割超が消える場合はGmail側の応答異常を疑い、除外しない
        if gone and len(gone) > max(100, len(existing) // 10):
            log(f"[WARN] 削除候補が多すぎるため除外を見送り: {len(gone)} 件")
        elif all_ids and gone:
            for i in gone:
                existing_map.pop(i, None)
            existing = [m for m in existing if m['id'] in live]
            existing_ids = set(existing_map.keys())
            save_cache(existing)
            log(f"Gmailで削除済みのメールを除外: {len(gone)} 件")
        else:
            log("Gmailで削除済みのメールを除外: 0 件")

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
