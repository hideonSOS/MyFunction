import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from .models import Note, Task, TONE_CHOICES


# ── シリアライズ ──────────────────────────────────────

def _dt(value):
    """DateTime → ローカルの ISO 文字列（未設定なら None）"""
    if not value:
        return None
    return timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')


def note_dict(n):
    return {
        'id':       n.id,
        'body':     n.body,
        'tone':     n.tone,
        'pinned':   n.pinned,
        'order':    n.order,
        'updated':  _dt(n.updated),
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


# ── ページ ────────────────────────────────────────────

@login_required
def board(request):
    return render(request, 'fusen/board.html', {
        'tones': [{'key': k, 'label': v} for k, v in TONE_CHOICES],
    })


# ── まとめ取得（初期ロード用） ─────────────────────────

@login_required
def api_state(request):
    notes = Note.objects.filter(user=request.user, archived=False)
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
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    note_id = data.get('id')
    fields = {
        'body':   str(data.get('body', ''))[:5000],
        'tone':   data.get('tone', 'yellow'),
        'pinned': bool(data.get('pinned', False)),
    }
    if fields['tone'] not in dict(TONE_CHOICES):
        fields['tone'] = 'yellow'
    if 'order' in data:
        try:
            fields['order'] = int(data['order'])
        except (TypeError, ValueError):
            pass

    if note_id:
        note = Note.objects.filter(user=request.user, id=note_id).first()
        if not note:
            return JsonResponse({'error': 'not found'}, status=404)
        for k, v in fields.items():
            setattr(note, k, v)
        note.save()
    else:
        note = Note.objects.create(user=request.user, **fields)

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
        'detail':    str(data.get('detail', ''))[:5000],
        'tone':      data.get('tone', 'blue'),
        'status':    status,
        'priority':  priority,
        'due_at':    _parse_dt(data.get('due_at')),
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
