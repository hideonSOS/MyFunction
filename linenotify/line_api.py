"""LINE Messaging API との通信。

チャネル認証情報は Git 管理外の line_credentials.json（BASE_DIR 直下）に置く。形式:
    {
      "channel_access_token": "＜長期チャネルアクセストークン＞",
      "channel_secret": "＜チャネルシークレット（Webhook利用時のみ必須）＞"
    }

送信方式:
  - ブロードキャスト … 公式アカウントを友だち追加している全員へ
  - プッシュ         … groupId / roomId / userId を指定してその宛先へ
グループIDは Webhook（ボットをグループに招待した時のイベント）で自動登録する。
"""
import base64
import hashlib
import hmac
import json

import requests
from django.conf import settings

API_BASE  = 'https://api.line.me/v2/bot'
CRED_PATH = settings.BASE_DIR / 'line_credentials.json'


def _load_creds():
    try:
        with open(CRED_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def get_token():
    return (_load_creds().get('channel_access_token') or '').strip()


def get_secret():
    return (_load_creds().get('channel_secret') or '').strip()


def is_configured():
    return bool(get_token())


def _headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def _post_messages(url, payload):
    """メッセージ送信の共通処理。成功なら (True, '')、失敗なら (False, 理由)"""
    token = get_token()
    if not token:
        return False, 'line_credentials.json が未設定です'

    try:
        res = requests.post(url, headers=_headers(token), json=payload, timeout=15)
    except requests.RequestException as e:
        return False, f'通信エラー: {e.__class__.__name__}'

    if res.status_code == 200:
        return True, ''
    # LINE のエラー本文から理由を拾う（トークン無効・月間上限超過など）
    try:
        detail = res.json().get('message', '')
    except ValueError:
        detail = ''
    return False, f'HTTP {res.status_code} {detail}'[:200]


def send_broadcast(text):
    """友だち全員へ送る"""
    return _post_messages(API_BASE + '/message/broadcast',
                          {'messages': [{'type': 'text', 'text': text[:5000]}]})


def send_push(to_id, text):
    """指定の宛先（groupId / roomId / userId）へ送る"""
    return _post_messages(API_BASE + '/message/push',
                          {'to': to_id,
                           'messages': [{'type': 'text', 'text': text[:5000]}]})


def send_to(target, text):
    """LineTarget へ送る。運用方針により宛先未指定（ブロードキャスト）は無効。"""
    if target is None:
        return False, 'ブロードキャストは現在無効です（送信先を指定してください）'
    return send_push(target.target_id, text)


def get_group_name(group_id):
    """グループ名を取得（Webhook 自動登録の表示名に使う）。失敗時は空文字"""
    token = get_token()
    if not token:
        return ''
    try:
        res = requests.get(f'{API_BASE}/group/{group_id}/summary',
                           headers=_headers(token), timeout=10)
        if res.status_code == 200:
            return (res.json().get('groupName') or '')[:100]
    except (requests.RequestException, ValueError):
        pass
    return ''


def verify_signature(body_bytes, signature):
    """Webhook の X-Line-Signature を検証する（チャネルシークレット必須）"""
    secret = get_secret()
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode('utf-8'), body_bytes, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode('ascii')
    return hmac.compare_digest(expected, signature)
