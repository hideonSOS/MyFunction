"""
gmail_client.py  –  Gmail API 共通クライアント

認証フロー:
  - token.json が有効なら自動リフレッシュ
  - 無効 / 存在しない場合は needs_auth() が True を返す
  - 再認証は Django の OAuth views (/mailfunction/oauth/start/) で実施
"""

import base64
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

APP_DIR    = Path(__file__).resolve().parent
BASE_DIR   = APP_DIR.parent
TOKEN_FILE = APP_DIR / 'token.json'
CREDS_FILE = BASE_DIR / 'credentials.json'

# 読み取り + 送信スコープ
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]


# ── 認証 ─────────────────────────────────────────────
def get_credentials():
    """token.json から認証情報を取得・リフレッシュして返す。失敗時は None。"""
    if not TOKEN_FILE.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except Exception:
        return None

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception:
            return None

    return None


def needs_auth():
    """認証が必要な状態かどうか。"""
    return get_credentials() is None


def get_service():
    """認証済み Gmail API サービスを返す。未認証なら None。"""
    creds = get_credentials()
    if not creds:
        return None
    return build('gmail', 'v1', credentials=creds)


def save_credentials(creds):
    """OAuth コールバック後に token.json を保存する。"""
    _save_token(creds)


def _save_token(creds):
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        f.write(creds.to_json())


# ── メール送信 ───────────────────────────────────────
def send_message(service, to, subject, body, thread_id=None, attachments=None):
    """テキストメールを送信する。attachments は {'filename', 'data'} のリスト。"""
    if attachments:
        msg = MIMEMultipart()
        msg['to']      = to
        msg['subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        for att in attachments:
            mime_type, _ = mimetypes.guess_type(att['filename'])
            main_type, sub_type = mime_type.split('/', 1) if mime_type else ('application', 'octet-stream')
            part = MIMEBase(main_type, sub_type)
            part.set_payload(att['data'])
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{att["filename"]}"')
            msg.attach(part)
    else:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['to']      = to
        msg['subject'] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = {'raw': raw}
    if thread_id:
        payload['threadId'] = thread_id
    return service.users().messages().send(userId='me', body=payload).execute()


# ── メッセージ詳細取得 ────────────────────────────────
def get_message_detail(service, msg_id):
    """
    指定IDのメールを full フォーマットで取得。
    戻り値:
        {
          'body_text':   str,
          'body_html':   str,
          'attachments': [{ 'filename', 'mime_type', 'attachment_id', 'size' }, ...]
        }
    """
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()
    payload = msg.get('payload', {})
    body_text, body_html, attachments = _parse_payload(payload)
    return {
        'body_text':   body_text,
        'body_html':   body_html,
        'attachments': attachments,
    }


def get_attachment(service, msg_id, attachment_id):
    """添付ファイルのバイナリデータを返す。"""
    att = service.users().messages().attachments().get(
        userId='me', messageId=msg_id, id=attachment_id
    ).execute()
    data = att.get('data', '')
    return base64.urlsafe_b64decode(data + '==')


# ── MIME パース ───────────────────────────────────────
def _decode_body(data):
    try:
        return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
    except Exception:
        return ''


def _parse_payload(payload):
    body_text   = ''
    body_html   = ''
    attachments = []

    def walk(part):
        nonlocal body_text, body_html
        mime   = part.get('mimeType', '')
        body   = part.get('body', {})
        fname  = part.get('filename', '')

        if fname:
            # 添付ファイル
            attachments.append({
                'filename':      fname,
                'mime_type':     mime,
                'attachment_id': body.get('attachmentId', ''),
                'size':          body.get('size', 0),
            })
        elif mime == 'text/plain' and not body_text:
            body_text = _decode_body(body.get('data', ''))
        elif mime == 'text/html' and not body_html:
            body_html = _decode_body(body.get('data', ''))
        elif mime.startswith('multipart/'):
            for sub in part.get('parts', []):
                walk(sub)

    walk(payload)
    return body_text, body_html, attachments
