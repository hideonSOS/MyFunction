import json
import mimetypes
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime, parseaddr

JST = timezone(timedelta(hours=9))
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from . import gmail_client as gc
from .models import MailMark, MailMarkAssign

APP_DIR    = Path(__file__).resolve().parent
BASE_DIR   = APP_DIR.parent
MAIL_CACHE = APP_DIR / 'mail_cache.json'
CONTACT_CACHE = APP_DIR / 'contact_cache.json'   # アドレス → 連絡先の登録名
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
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(JST).replace(tzinfo=None)
    except Exception:
        return None


def _load_mails():
    global _cache_data, _cache_mtime
    if not MAIL_CACHE.exists():
        return []
    # 連絡先の表が更新されたら表示名も作り直す（どちらかの更新で再構築）
    mtime = (MAIL_CACHE.stat().st_mtime, _contacts_mtime())
    if _cache_data is not None and mtime == _cache_mtime:
        return _cache_data
    try:
        with open(MAIL_CACHE, encoding='utf-8') as f:
            mails = json.load(f)
    except (OSError, ValueError):
        # 更新中などで読めなかった場合は直前の内容を返す（次回アクセスで再読込）
        return _cache_data or []
    mails.sort(key=lambda m: _parse_date(m.get('date', '')) or datetime.min, reverse=True)
    for m in mails:
        dt = _parse_date(m.get('date', ''))
        m['date_fmt']    = dt.strftime('%Y/%m/%d') if dt else ''
        m['date_detail'] = dt.strftime('%Y/%m/%d %H:%M') if dt else ''
        m['from_name']   = _display_name(m.get('from', ''))
    _cache_data  = mails
    _cache_mtime = mtime
    return mails


_contacts_data  = None
_contacts_mtime_cached = None


def _contacts_mtime():
    try:
        return CONTACT_CACHE.stat().st_mtime
    except OSError:
        return None


def _load_contacts():
    """連絡先の「アドレス(小文字) → 登録名」表。無ければ空"""
    global _contacts_data, _contacts_mtime_cached
    mtime = _contacts_mtime()
    if _contacts_data is not None and mtime == _contacts_mtime_cached:
        return _contacts_data
    try:
        with open(CONTACT_CACHE, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = _contacts_data or {}
    _contacts_data, _contacts_mtime_cached = data, mtime
    return data


def _display_name(raw):
    """表示名の優先順: 連絡先の登録名 → 差出人ヘッダーの名前 → アドレス。
    Gmailの画面と同じく、連絡先に登録済みの相手はヘッダーの名前
    （例: 会社名「ケイプランニング」）より登録名を優先する"""
    name, addr = parseaddr(raw or '')
    contact = _load_contacts().get(addr.lower(), '')
    if contact:
        return contact
    name = name.strip().strip('"\\').strip()
    return name or addr or (raw or '')


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
        'needs_contacts_auth': gc.needs_contacts_auth(),
        # Google は IPアドレスのサイトへの認証戻りを禁止しているため、
        # 認証（許可）は localhost で開いたときだけ実行できる
        'oauth_available': request.get_host().split(':')[0] == 'localhost',
        # 詳細画面の送信元・送信先の名前補完用（アドレス → 連絡先の登録名）
        'contact_names': _load_contacts(),
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
    if hasattr(flow, 'code_verifier') and flow.code_verifier:
        request.session['oauth_code_verifier'] = flow.code_verifier
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
    # ローカル開発時のみ有効（本番デプロイ前に再コメントアウト）
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    # 付与済み権限の併合などで返却スコープが要求と順序・内容が異なっても受け付ける
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
    code_verifier = request.session.get('oauth_code_verifier')
    if code_verifier:
        flow.code_verifier = code_verifier
    try:
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        gc.save_credentials(flow.credentials)
    except Exception as e:
        return HttpResponse(f'認証エラー: {e}', status=400)
    return redirect('/mailfunction/')


# ── サーバーサイド検索 ────────────────────────────────
# Gmail は送信と転送を区別しない（どちらも SENT）ため、件名の先頭で見分ける。
# 件名から「Fwd:」を消して転送したものは送信扱いになる
_FORWARD_SUBJECT = re.compile(r'^\s*(fwd?|fw|転送)\s*[:：]', re.IGNORECASE)


def _is_forward(m):
    return bool(_FORWARD_SUBJECT.match(m.get('subject') or ''))


def _thread_key(m):
    return m.get('thread_id') or m['id']


def _thread_user_labels(mails, user_labels):
    """会話（スレッド）→ その会話のどれかのメールに付いているマイラベルID。
    Gmailのラベルは相手から届いたメールにしか付かないことが多いため、
    ラベルの絞り込みはGmailの画面と同じく会話単位で行う（自分の返信も表示される）。
    Gmail側で削除済みのラベルIDは含めない"""
    table = {}
    for m in mails:
        s = table.setdefault(_thread_key(m), set())
        s.update(l for l in m.get('labels', []) if l in user_labels)
    return table


def _has_label(m, label, thread_labels):
    """画面の絞り込み条件。SENT は転送を除く送信（返信を含む）、FWD は転送だけ。
    マイラベルと NOLABEL（マイラベルの付いていない会話）は会話単位で判定し、
    それ以外（INBOX・未読・スター等）は1通ずつ判定する"""
    labels = m.get('labels', [])
    if label == 'SENT':
        return 'SENT' in labels and not _is_forward(m)
    if label == 'FWD':
        return 'SENT' in labels and _is_forward(m)
    if label == 'NOLABEL':
        return not thread_labels.get(_thread_key(m))
    if label.startswith('Label_'):
        return label in thread_labels.get(_thread_key(m), ())
    return label in labels


@login_required
def search(request):
    query  = request.GET.get('q', '').strip().lower()
    label  = request.GET.get('label', '').strip()
    sender = request.GET.get('sender', '').strip().lower()   # 差出人アドレスで絞り込み
    unread = request.GET.get('unread', '') == '1'            # 未読のみ
    try:
        days = int(request.GET.get('days') or 0)             # 直近N日
    except ValueError:
        days = 0
    mark = request.GET.get('mark', '').strip()               # 独自マークのID

    mails = _load_mails()

    if mark.isdigit():
        marked = set(MailMarkAssign.objects.filter(mark_id=int(mark))
                     .values_list('mail_id', flat=True))
        mails = [m for m in mails if m['id'] in marked]
    if label:
        # カンマ区切りで複数指定可。すべての条件に当てはまるメールだけ（AND）
        # 例: label=INBOX,Label_123 → 受信トレイ かつ そのラベル
        required = [l for l in label.split(',') if l]
        thread_labels = _thread_user_labels(mails, _user_label_names())
        mails = [m for m in mails
                 if all(_has_label(m, l, thread_labels) for l in required)]
    if sender:
        mails = [m for m in mails if sender in m.get('from', '').lower()]
    if unread:
        mails = [m for m in mails if 'UNREAD' in m.get('labels', [])]
    if days > 0:
        # _parse_date は JST の naive datetime を返すので、それに合わせて比較する
        cutoff = datetime.now(JST).replace(tzinfo=None) - timedelta(days=days)
        mails = [m for m in mails
                 if (d := _parse_date(m.get('date', ''))) and d >= cutoff]
    if query:
        mails = [m for m in mails if
                 query in m.get('subject', '').lower() or
                 query in m.get('from', '').lower() or
                 query in m.get('snippet', '').lower()]

    result = [{
        'id':          m['id'],
        'subject':     m.get('subject', ''),
        'from':        m.get('from', ''),
        'from_name':   m.get('from_name', ''),
        'to':          m.get('to', ''),
        'date_fmt':    m.get('date_fmt', ''),
        'date_detail': m.get('date_detail', ''),
        'snippet':     m.get('snippet', ''),
        'labels':      m.get('labels', []),
    } for m in mails[:500]]

    return JsonResponse({'mails': result, 'matched': len(mails)})


# ── ラベル一覧（ラベル選択での絞り込み用） ───────────────
LABEL_CACHE = APP_DIR / 'label_cache.json'

# Gmail のシステムラベルの表示名と並び順（ここに無いシステムラベルは出さない）
# INBOX / SENT は画面上部のフォルダボタンで選ぶため、ラベルの候補には含めない
SYSTEM_LABELS = [
    ('UNREAD', '未読'), ('STARRED', 'スター付き'),
    ('IMPORTANT', '重要'), ('DRAFT', '下書き'),
    ('CATEGORY_PERSONAL', 'メイン'), ('CATEGORY_UPDATES', '新着'),
    ('CATEGORY_PROMOTIONS', 'プロモーション'), ('CATEGORY_SOCIAL', 'ソーシャル'),
    ('CATEGORY_FORUMS', 'フォーラム'),
]


@login_required
def labels(request):
    """キャッシュ中のメールに付いているラベルを件数付きで返す。
    ユーザー作成ラベル（名前順）→ システムラベル（Gmailの並び）の順"""
    from collections import Counter

    mails  = _load_mails()
    counts = Counter(l for m in mails for l in m.get('labels', []))
    names  = _user_label_names()   # 対応表が未作成でも、システムラベルだけは出せる
    # マイラベルの件数は絞り込みと同じく会話単位（会話内の返信なども数える）
    thread_labels = _thread_user_labels(mails, names)
    for m in mails:
        for l in thread_labels.get(_thread_key(m), ()):
            if l not in m.get('labels', []):
                counts[l] += 1

    # マイラベルは件数0でも出す（作ったばかりのラベルも見えるように）。
    # Gmail側で削除済みのラベル（対応表に無い Label_*）は出さない
    # 並びは名前の逆順（都市 → 箕面市 → 代理店・関係 → …）。ユーザー指定の優先順
    user = sorted(({'id': i, 'name': n, 'count': counts[i], 'system': False}
                   for i, n in names.items()),
                  key=lambda x: x['name'], reverse=True)
    system = [{'id': i, 'name': n, 'count': counts[i], 'system': True}
              for i, n in SYSTEM_LABELS if counts[i]]
    return JsonResponse({'labels': user + system, 'addr_labels': _addr_labels(),
                         'own_addrs': _own_addrs(),
                         'total': len(mails),
                         'nolabel_count': sum(_has_label(m, 'NOLABEL', thread_labels)
                                              for m in mails)})


def _user_label_names():
    """マイラベルの「ID → 名前」表（label_cache.json）。無ければ空"""
    names = {}
    try:
        with open(LABEL_CACHE, encoding='utf-8') as f:
            for l in json.load(f):
                if l.get('type') == 'user':
                    names[l['id']] = l['name']
    except (OSError, ValueError):
        pass
    return names


def _own_addrs():
    """自分（ホストアカウント）のアドレス。送信済みメールの差出人から求める。
    CC・BCCで届いたメール（宛先に自分がいない）の判定に使う"""
    own = {parseaddr(m.get('from', ''))[1].lower()
           for m in _load_mails() if 'SENT' in m.get('labels', [])}
    own.discard('')
    return sorted(own)


def _addr_labels():
    """差出人アドレス → その人から届いたメールに付いているマイラベルID。
    送信・転送したメール（自分がFrom）は宛先の人のラベル、CC・BCCで届いた
    ラベル無しのメールは送信元の人のラベルで色分けするために使う"""
    table = {}
    for m in _load_mails():
        labels = m.get('labels', [])
        if 'SENT' in labels:
            continue
        mine = [l for l in labels if l.startswith('Label_')]
        if not mine:
            continue
        addr = parseaddr(m.get('from', ''))[1].lower()
        if addr:
            table.setdefault(addr, set()).update(mine)
    return {a: sorted(ls) for a, ls in table.items()}


# ── 独自マーク（★重要 など。このサイト内だけの印でGmailには反映しない） ──
# 色は画面側のCSS（.mark-c-xxx）と対応するキーだけを受け付ける
MARK_COLORS = ['yellow', 'orange', 'pink', 'red', 'green', 'cyan', 'purple', 'white']


def _marks_payload():
    live = {m['id'] for m in _load_mails()}   # Gmailで削除済みのメールは数えない
    assigned = {}
    for mail_id, mark_id in MailMarkAssign.objects.values_list('mail_id', 'mark_id'):
        if mail_id in live:
            assigned.setdefault(mail_id, []).append(mark_id)
    counts = {}
    for ids in assigned.values():
        for i in ids:
            counts[i] = counts.get(i, 0) + 1
    marks = [{'id': k.id, 'name': k.name, 'symbol': k.symbol, 'color': k.color,
              'count': counts.get(k.id, 0)} for k in MailMark.objects.all()]
    return {'marks': marks, 'assigned': assigned, 'colors': MARK_COLORS}


@login_required
def marks(request):
    """マーク一覧と、メールID → 付いているマークID の表"""
    return JsonResponse(_marks_payload())


@login_required
@require_POST
def mark_toggle(request):
    """メールのマークを付け外しする"""
    mail_id = request.POST.get('mail_id', '').strip()
    mark = MailMark.objects.filter(pk=request.POST.get('mark_id') or 0).first()
    if not mail_id or mark is None:
        return JsonResponse({'error': 'bad_request'}, status=400)
    deleted, _ = MailMarkAssign.objects.filter(mail_id=mail_id, mark=mark).delete()
    if not deleted:
        MailMarkAssign.objects.get_or_create(mail_id=mail_id, mark=mark)
    return JsonResponse({'on': not deleted, **_marks_payload()})


@login_required
@require_POST
def mark_save(request):
    """マークの追加（id なし）・変更（id あり）"""
    name   = request.POST.get('name', '').strip()[:30]
    symbol = request.POST.get('symbol', '').strip()[:4] or '★'
    color  = request.POST.get('color', '')
    if not name:
        return JsonResponse({'error': '名前を入力してください'}, status=400)
    if color not in MARK_COLORS:
        color = MARK_COLORS[0]
    pk = request.POST.get('id')
    if pk:
        mark = MailMark.objects.filter(pk=pk).first()
        if mark is None:
            return JsonResponse({'error': 'not_found'}, status=404)
    else:
        last = MailMark.objects.order_by('-sort_order').first()
        mark = MailMark(sort_order=(last.sort_order + 1) if last else 0)
    mark.name, mark.symbol, mark.color = name, symbol, color
    mark.save()
    return JsonResponse(_marks_payload())


@login_required
@require_POST
def mark_delete(request):
    """マークを削除（そのマークの付け外し記録もまとめて消える）"""
    MailMark.objects.filter(pk=request.POST.get('id') or 0).delete()
    return JsonResponse(_marks_payload())


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


# ── コンタクト一覧 ────────────────────────────────────
@login_required
def contacts(request):
    """過去のメールから送信先候補（From / To）を抽出して返す。"""
    import re
    mails = _load_mails()
    seen, result = set(), []

    def _extract(field_val):
        """'名前 <addr>' または 'addr' 形式からアドレスを抽出。"""
        for addr in re.split(r',\s*', field_val or ''):
            addr = addr.strip()
            if not addr:
                continue
            m = re.search(r'<([^>]+)>', addr)
            email = m.group(1) if m else addr
            if '@' in email and email not in seen:
                seen.add(email)
                result.append({'label': addr, 'email': email})

    for mail in mails:
        _extract(mail.get('from', ''))
        _extract(mail.get('to', ''))

    return JsonResponse({'contacts': result[:500]})


# ── メール送信 ────────────────────────────────────────
@login_required
@require_POST
def send_mail(request):
    to        = request.POST.get('to', '').strip()
    subject   = request.POST.get('subject', '').strip()
    body      = request.POST.get('body', '').strip()
    thread_id = request.POST.get('thread_id', '').strip() or None

    if not to or not subject:
        return JsonResponse({'error': '宛先と件名は必須です'}, status=400)

    service = gc.get_service()
    if service is None:
        return JsonResponse({'error': 'auth_required'}, status=401)

    attachments = [
        {'filename': f.name, 'data': f.read()}
        for f in request.FILES.getlist('attachments')
    ]

    try:
        result = gc.send_message(service, to, subject, body, thread_id, attachments or None)
        return JsonResponse({'ok': True, 'id': result.get('id', '')})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
