import json
import mimetypes
import os
import subprocess
import sys
import uuid
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from . import gmail_client as gc

APP_DIR    = Path(__file__).resolve().parent
BASE_DIR   = APP_DIR.parent
MAIL_CACHE = APP_DIR / 'mail_cache.json'
LOG_DIR    = BASE_DIR / 'logs'
FETCHER    = APP_DIR / 'mail_fetcher.py'
PYTHON     = sys.executable

LOG_DIR.mkdir(exist_ok=True)

_jobs: dict = {}

# ── インメモリキャッシュ ───────────────────────────────
_cache_data  = None
_cache_mtime = None


def _parse_date(date_str):
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return None


def _load_mails():
    global _cache_data, _cache_mtime
    if not MAIL_CACHE.exists():
        return []
    mtime = MAIL_CACHE.stat().st_mtime
    if _cache_data is not None and mtime == _cache_mtime:
        return _cache_data
    with open(MAIL_CACHE, encoding='utf-8') as f:
        mails = json.load(f)
    mails.sort(key=lambda m: _parse_date(m.get('date', '')) or datetime.min, reverse=True)
    for m in mails:
        dt = _parse_date(m.get('date', ''))
        m['date_fmt'] = dt.strftime('%Y/%m/%d') if dt else ''
    _cache_data  = mails
    _cache_mtime = mtime
    return mails


INITIAL_LIMIT = 300


# ── メイン画面 ────────────────────────────────────────
@login_required
def index(request):
    mails = _load_mails()
    ctx = {
        'mails':         mails[:INITIAL_LIMIT],
        'total':         len(mails),
        'cache_exists':  MAIL_CACHE.exists(),
        'initial_limit': INITIAL_LIMIT,
        'needs_auth':    gc.needs_auth(),
    }
    return render(request, 'mailfunction/index.html', ctx)


# ── OAuth 認証フロー ──────────────────────────────────
def _build_redirect_uri(request):
    return request.build_absolute_uri('/mailfunction/oauth/callback/')


@login_required
def oauth_start(request):
    """Google 認証ページへリダイレクト。"""
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_secrets_file(
        str(gc.CREDS_FILE),
        scopes=gc.SCOPES,
        redirect_uri=_build_redirect_uri(request),
    )
    auth_url, state = flow.authorization_url(
        prompt='consent',
        access_type='offline',
    )
    request.session['oauth_state'] = state
    return HttpResponseRedirect(auth_url)


@login_required
def oauth_callback(request):
    """Google からのコールバックを受け取り token.json を保存。"""
    from google_auth_oauthlib.flow import Flow
    state = request.session.get('oauth_state', '')
    flow = Flow.from_client_secrets_file(
        str(gc.CREDS_FILE),
        scopes=gc.SCOPES,
        state=state,
        redirect_uri=_build_redirect_uri(request),
    )
    # 本番では HTTPS が前提。ローカル開発時のみ以下を有効化。
    # os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    try:
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        gc.save_credentials(flow.credentials)
    except Exception as e:
        return HttpResponse(f'認証エラー: {e}', status=400)
    return redirect('/mailfunction/')


# ── サーバーサイド検索 ────────────────────────────────
@login_required
def search(request):
    query = request.GET.get('q', '').strip().lower()
    label = request.GET.get('label', '').strip()

    mails = _load_mails()

    if label:
        mails = [m for m in mails if label in m.get('labels', [])]
    if query:
        mails = [m for m in mails if
                 query in m.get('subject', '').lower() or
                 query in m.get('from', '').lower() or
                 query in m.get('snippet', '').lower()]

    result = [{
        'id':       m['id'],
        'subject':  m.get('subject', ''),
        'from':     m.get('from', ''),
        'date_fmt': m.get('date_fmt', ''),
        'snippet':  m.get('snippet', ''),
        'labels':   m.get('labels', []),
    } for m in mails[:500]]

    return JsonResponse({'mails': result, 'matched': len(mails)})


# ── メール詳細（本文 + 添付一覧） ─────────────────────
@login_required
def mail_detail(request, mail_id):
    """
    指定IDのメールを Gmail API で full 取得して返す。
    キャッシュには snippet しかないため都度 API を呼ぶ。
    """
    service = gc.get_service()
    if service is None:
        return JsonResponse({'error': 'auth_required'}, status=401)

    try:
        detail = gc.get_message_detail(service, mail_id)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({
        'body_text':   detail['body_text'],
        'body_html':   detail['body_html'],
        'attachments': detail['attachments'],
    })


# ── 添付ファイルダウンロード ──────────────────────────
@login_required
def attachment_download(request, mail_id, attachment_id):
    """添付ファイルをブラウザにストリーミング配信する。"""
    filename  = request.GET.get('filename', 'attachment')
    mime_type = request.GET.get('mime', 'application/octet-stream')

    service = gc.get_service()
    if service is None:
        return HttpResponse('認証が必要です', status=401)

    try:
        data = gc.get_attachment(service, mail_id, attachment_id)
    except Exception as e:
        return HttpResponse(f'取得エラー: {e}', status=500)

    response = HttpResponse(data, content_type=mime_type)
    # インライン表示（PDF・画像）か強制ダウンロードかを mime で判定
    if mime_type.startswith('image/') or mime_type == 'application/pdf':
        disposition = 'inline'
    else:
        disposition = 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


# ── SYNC ─────────────────────────────────────────────
@login_required
@require_POST
def fetch_mails(request):
    global _cache_data, _cache_mtime
    mode     = request.POST.get('mode', 'update')
    job_id   = 'mail_' + str(uuid.uuid4())[:6]
    log_path = LOG_DIR / f'job_{job_id}.log'

    cmd = [str(PYTHON), str(FETCHER)]
    if mode == 'full':
        cmd.append('--full')

    with open(log_path, 'w', encoding='utf-8') as lf:
        proc = subprocess.Popen(
            cmd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )

    _cache_data  = None
    _cache_mtime = None

    _jobs[job_id] = {'proc': proc, 'log': str(log_path)}
    return JsonResponse({'job_id': job_id, 'mode': mode})


# ── ログポーリング ────────────────────────────────────
@login_required
def log_view(request):
    try:
        job_id = request.GET.get('job_id', '')

        if job_id not in _jobs:
            log_path = LOG_DIR / f'job_{job_id}.log'
            if log_path.exists():
                content = log_path.read_text(encoding='utf-8')
                done = '[DONE]' in content or '[ERROR]' in content
                rc   = 0 if '[DONE]' in content else (1 if '[ERROR]' in content else None)
            else:
                content = '（サーバーが再起動したためジョブ情報が失われました。再度実行してください。）'
                done = True
                rc   = -1
            return JsonResponse({'log': content, 'done': done, 'rc': rc})

        info    = _jobs[job_id]
        content = ''
        try:
            with open(info['log'], encoding='utf-8', errors='replace') as f:
                content = f.read()
        except FileNotFoundError:
            pass

        proc_done = info['proc'].poll() is not None
        log_done  = '[DONE]' in content or '[ERROR]' in content
        done      = proc_done or log_done

        if '[DONE]' in content:
            rc = 0
        elif '[ERROR]' in content:
            rc = 1
        elif proc_done:
            rc = info['proc'].returncode
        else:
            rc = None

        return JsonResponse({'log': content, 'done': done, 'rc': rc})

    except Exception as e:
        return JsonResponse({'log': f'[VIEW ERROR] {e}', 'done': True, 'rc': -1})
