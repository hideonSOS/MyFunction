import json
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from datetime import datetime, time as dtime
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.views.decorators.http import require_http_methods

from .models import Note, Task, Attachment, TONE_CHOICES

# アップロード許可（画像全般 と PDF のみ）／サイズ上限
# 注意: 本番は nginx の client_max_body_size も同じ値に揃えること（deploy/nginx.conf）
MAX_UPLOAD_SIZE = 50 * 1024 * 1024   # 50MB


# ── リッチテキスト本文の軽量サニタイズ ─────────────────
# 付箋の中身はリッチテキスト(HTML)を保存する。ログイン必須・本人のみ閲覧の
# 個人メモだが、危険なタグ／属性だけは念のため除去する（完全な sanitizer
# ではない。危険要素の持ち込みを防ぐ最小限の防御）。
_TAG_BLOCKLIST = re.compile(
    r'<\s*/?\s*(script|style|iframe|object|embed|link|meta|form|input|button)\b[^>]*>',
    re.IGNORECASE)
_ON_ATTR = re.compile(r'\son\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', re.IGNORECASE)
_JS_URL = re.compile(r'(href|src)\s*=\s*("|\')\s*javascript:[^"\']*\2', re.IGNORECASE)


def sanitize_html(html):
    if not html:
        return ''
    html = _TAG_BLOCKLIST.sub('', html)
    html = _ON_ATTR.sub('', html)
    html = _JS_URL.sub('', html)
    return html[:20000]


# ── シリアライズ ──────────────────────────────────────

def _dt(value):
    """DateTime → ローカルの ISO 文字列（未設定なら None）"""
    if not value:
        return None
    return timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')


def attachment_dict(a):
    return {
        'id':           a.id,
        'name':         a.name,
        'url':          a.file.url,
        'content_type': a.content_type,
        'size':         a.size,
        'is_image':     a.is_image,
        'is_pdf':       a.is_pdf,
    }


def note_dict(n):
    return {
        'id':       n.id,
        'title':    n.title,
        'body':     n.body,
        'tone':     n.tone,
        'pinned':   n.pinned,
        'date':     n.date.strftime('%Y-%m-%d') if n.date else None,
        'time':     n.time.strftime('%H:%M') if n.time else None,
        'order':    n.order,
        'updated':  _dt(n.updated),
        'attachments': [attachment_dict(a) for a in n.attachments.all()],
    }


def task_dict(t):
    return {
        'id':         t.id,
        'title':      t.title,
        'detail':     t.detail,
        'tone':       t.tone,
        'status':     t.status,
        'priority':   t.priority,
        'due_at':     _dt(t.due_at),
        'all_day':    t.all_day,
        'remind_at':  _dt(t.remind_at),
        'reminded':   t.reminded,
        'is_done':    t.is_done,
        'is_overdue': t.is_overdue,
        'is_due_soon': t.is_due_soon,
        'should_remind': t.should_remind,
    }


def _parse_dt(value):
    """フロントの 'YYYY-MM-DDTHH:MM' を aware datetime に。空なら None"""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_date(value):
    """'YYYY-MM-DD' を date に。空・不正なら None"""
    if not value:
        return None
    return parse_date(value)


def _parse_time(value):
    """'HH:MM' を time に。空・不正なら None"""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%H:%M').time()
    except (TypeError, ValueError):
        return None


def _combine_local(d, t):
    """date と time をローカルタイムの aware datetime にする"""
    naive = datetime.combine(d, t)
    return timezone.make_aware(naive, timezone.get_current_timezone())


# ── ページ ────────────────────────────────────────────

@login_required
def board(request):
    return render(request, 'fusen/board.html', {
        'tones': [{'key': k, 'label': v} for k, v in TONE_CHOICES],
    })


# ── まとめ取得（初期ロード用） ─────────────────────────

@login_required
def api_state(request):
    notes = (Note.objects.filter(user=request.user, archived=False)
             .prefetch_related('attachments'))
    tasks = Task.objects.filter(user=request.user)
    return JsonResponse({
        'notes': [note_dict(n) for n in notes],
        'tasks': [task_dict(t) for t in tasks],
        'now':   _dt(timezone.now()),
    })


# ── 付箋 API ─────────────────────────────────────────

@login_required
@require_http_methods(['POST'])
def api_note_save(request):
    """部分更新。payload に含まれるキーだけを反映する
    （ドラッグ移動が {id, date} だけ送っても本文が消えないように）"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    note_id = data.get('id')
    if note_id:
        note = Note.objects.filter(user=request.user, id=note_id).first()
        if not note:
            return JsonResponse({'error': 'not found'}, status=404)
    else:
        note = Note(user=request.user)

    if 'title' in data:
        note.title = str(data.get('title') or '')[:200]
    if 'body' in data:
        note.body = sanitize_html(str(data.get('body') or ''))
    if 'tone' in data and data['tone'] in dict(TONE_CHOICES):
        note.tone = data['tone']
    if 'pinned' in data:
        note.pinned = bool(data['pinned'])
    if 'date' in data:
        note.date = _parse_date(data['date'])
    if 'time' in data:
        note.time = _parse_time(data['time'])
    if 'order' in data:
        try:
            note.order = int(data['order'])
        except (TypeError, ValueError):
            pass

    note.save()
    return JsonResponse(note_dict(note))


@login_required
@require_http_methods(['POST'])
def api_note_delete(request):
    try:
        data = json.loads(request.body)
        note_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    Note.objects.filter(user=request.user, id=note_id).delete()
    return JsonResponse({'ok': True})


# ── 付箋の添付ファイル API ────────────────────────────

@login_required
@require_http_methods(['POST'])
def api_note_upload(request):
    """付箋に画像・PDF を添付する（multipart/form-data）。
    フィールド: note_id, file"""
    note = Note.objects.filter(user=request.user, id=request.POST.get('note_id')).first()
    if not note:
        return JsonResponse({'error': 'not found'}, status=404)

    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'no file'}, status=400)

    ct = (f.content_type or '').lower()
    if not (ct.startswith('image/') or ct == 'application/pdf'):
        return JsonResponse({'error': '画像または PDF のみアップロードできます'}, status=400)
    if f.size > MAX_UPLOAD_SIZE:
        mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        return JsonResponse({'error': f'ファイルが大きすぎます（上限{mb}MB）'}, status=400)

    # 新しい添付は末尾に並べる
    last = note.attachments.order_by('-order').first()
    next_order = (last.order + 1) if last else 0
    att = Attachment(note=note, file=f, name=(f.name or 'file')[:255],
                     content_type=ct, size=f.size, order=next_order)
    att.save()
    return JsonResponse(attachment_dict(att))


@login_required
@require_http_methods(['POST'])
def api_note_attach_delete(request):
    try:
        data = json.loads(request.body)
        att_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    # 本人の付箋の添付だけを削除できる（post_delete で実ファイルも消える）
    att = Attachment.objects.filter(note__user=request.user, id=att_id).first()
    if att:
        att.delete()
    return JsonResponse({'ok': True})


@login_required
@require_http_methods(['POST'])
def api_note_attach_reorder(request):
    """付箋内の添付の並び順を更新する。payload: {note_id, ids: [...]}"""
    try:
        data = json.loads(request.body)
        note_id = int(data['note_id'])
        ids = [int(x) for x in data['ids']]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    note = Note.objects.filter(user=request.user, id=note_id).first()
    if not note:
        return JsonResponse({'error': 'not found'}, status=404)

    # 本人の付箋に属する添付だけを、渡された順で 0,1,2... に振り直す
    owned = {a.id: a for a in note.attachments.all()}
    order = 0
    for aid in ids:
        att = owned.get(aid)
        if att:
            att.order = order
            att.save(update_fields=['order'])
            order += 1
    return JsonResponse({'ok': True})


# ── タスク API ────────────────────────────────────────

@login_required
@require_http_methods(['POST'])
def api_task_save(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    title = str(data.get('title', '')).strip()
    if not title:
        return JsonResponse({'error': 'title required'}, status=400)

    valid_status = dict(Task.STATUS_CHOICES)
    status = data.get('status', Task.STATUS_TODO)
    if status not in valid_status:
        status = Task.STATUS_TODO

    try:
        priority = int(data.get('priority', 1))
    except (TypeError, ValueError):
        priority = 1
    priority = max(0, min(2, priority))

    fields = {
        'title':     title[:200],
        'detail':    sanitize_html(str(data.get('detail', ''))),
        'tone':      data.get('tone', 'blue'),
        'status':    status,
        'priority':  priority,
        'due_at':    _parse_dt(data.get('due_at')),
        'all_day':   bool(data.get('all_day', False)),
        'remind_at': _parse_dt(data.get('remind_at')),
    }
    if fields['tone'] not in dict(TONE_CHOICES):
        fields['tone'] = 'blue'

    task_id = data.get('id')
    if task_id:
        task = Task.objects.filter(user=request.user, id=task_id).first()
        if not task:
            return JsonResponse({'error': 'not found'}, status=404)
    else:
        task = Task(user=request.user)

    # リマインド時刻が未来に動いたら、再びリマインドできるようフラグを戻す
    new_remind = fields['remind_at']
    if new_remind and (task.remind_at != new_remind) and new_remind > timezone.now():
        task.reminded = False

    was_done = task.is_done
    for k, v in fields.items():
        setattr(task, k, v)

    # 完了状態の遷移で done_at を管理
    if task.is_done and not was_done:
        task.done_at = timezone.now()
    elif not task.is_done:
        task.done_at = None

    task.save()
    return JsonResponse(task_dict(task))


@login_required
@require_http_methods(['POST'])
def api_task_move(request):
    """タスクの日付・時刻・終日をまとめて変更（ドラッグ移動用）。
      date 空          → 期限を外す（未分類へ）
      all_day 真       → その日の終日（時刻は 00:00 保持、all_day=True）
      time 指定/既存   → 時間軸に配置（all_day=False）
    """
    try:
        data = json.loads(request.body)
        task_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    task = Task.objects.filter(user=request.user, id=task_id).first()
    if not task:
        return JsonResponse({'error': 'not found'}, status=404)

    new_date = _parse_date(data.get('date'))
    if new_date is None:
        task.due_at = None
        task.all_day = False
    elif data.get('all_day'):
        keep_time = timezone.localtime(task.due_at).time() if task.due_at else dtime(0, 0)
        task.due_at = _combine_local(new_date, keep_time)
        task.all_day = True
    else:
        new_time = _parse_time(data.get('time'))
        if new_time is None:
            new_time = timezone.localtime(task.due_at).time() if task.due_at else dtime(9, 0)
        task.due_at = _combine_local(new_date, new_time)
        task.all_day = False
    task.save()
    return JsonResponse(task_dict(task))


@login_required
@require_http_methods(['POST'])
def api_task_status(request):
    """ステータスだけ手早く更新（チェックボックス等）"""
    try:
        data = json.loads(request.body)
        task_id = int(data['id'])
        status = data['status']
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    if status not in dict(Task.STATUS_CHOICES):
        return JsonResponse({'error': 'bad status'}, status=400)

    task = Task.objects.filter(user=request.user, id=task_id).first()
    if not task:
        return JsonResponse({'error': 'not found'}, status=404)

    was_done = task.is_done
    task.status = status
    if task.is_done and not was_done:
        task.done_at = timezone.now()
    elif not task.is_done:
        task.done_at = None
    task.save()
    return JsonResponse(task_dict(task))


@login_required
@require_http_methods(['POST'])
def api_task_reminded(request):
    """リマインドを確認済みにする（スヌーズ or 既読）"""
    try:
        data = json.loads(request.body)
        task_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    task = Task.objects.filter(user=request.user, id=task_id).first()
    if not task:
        return JsonResponse({'error': 'not found'}, status=404)

    snooze = data.get('snooze_minutes')
    if snooze:
        try:
            minutes = int(snooze)
            task.remind_at = timezone.now() + timezone.timedelta(minutes=minutes)
            task.reminded = False
        except (TypeError, ValueError):
            task.reminded = True
    else:
        task.reminded = True
    task.save()
    return JsonResponse(task_dict(task))


@login_required
@require_http_methods(['POST'])
def api_task_delete(request):
    try:
        data = json.loads(request.body)
        task_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    Task.objects.filter(user=request.user, id=task_id).delete()
    return JsonResponse({'ok': True})
