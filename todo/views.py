import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

# リッチテキストのサニタイズとアップロード上限は付箋（fusen）と共通
from fusen.views import sanitize_html, MAX_UPLOAD_SIZE

from .models import TodoItem, TodoAttachment


def _attachment_dict(a):
    return {
        'id':           a.id,
        'name':         a.name,
        'url':          a.file.url,
        'content_type': a.content_type,
        'size':         a.size,
        'is_image':     a.is_image,
        'is_pdf':       a.is_pdf,
    }


def _item_dict(t):
    return {
        'id':          t.id,
        'title':       t.title,
        'memo':        t.memo,
        'importance':  t.importance,
        'progress':    t.progress,
        'done':        t.done,
        'updated':     timezone.localtime(t.updated).strftime('%m/%d %H:%M'),
        'attachments': [_attachment_dict(a) for a in t.attachments.all()],
    }


@login_required
def index(request):
    return render(request, 'todo/index.html')


@login_required
def api_list(request):
    items = TodoItem.objects.filter(user=request.user).prefetch_related('attachments')
    return JsonResponse({'items': [_item_dict(t) for t in items]})


@login_required
@require_http_methods(['POST'])
def api_save(request):
    """部分更新。payload に含まれるキーだけ反映（id なしは新規作成）"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    item_id = data.get('id')
    if item_id:
        item = TodoItem.objects.filter(user=request.user, id=item_id).first()
        if not item:
            return JsonResponse({'error': 'not found'}, status=404)
    else:
        title = str(data.get('title') or '').strip()
        if not title:
            return JsonResponse({'error': 'タイトルを入力してください'}, status=400)
        item = TodoItem(user=request.user)

    if 'title' in data:
        v = str(data['title'] or '').strip()
        if v:
            item.title = v[:200]
    if 'memo' in data:
        item.memo = sanitize_html(str(data['memo'] or ''))
    if 'importance' in data:
        try:
            item.importance = max(1, min(5, int(data['importance'])))
        except (TypeError, ValueError):
            pass
    if 'progress' in data:
        try:
            item.progress = max(0, min(100, int(data['progress'])))
        except (TypeError, ValueError):
            pass
    if 'done' in data:
        item.done = bool(data['done'])
        # 完了にしたら進捗も100%に揃える（戻したら進捗はそのまま）
        if item.done:
            item.progress = 100

    item.save()
    return JsonResponse(_item_dict(item))


@login_required
@require_http_methods(['POST'])
def api_delete(request):
    try:
        data = json.loads(request.body)
        item_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    TodoItem.objects.filter(user=request.user, id=item_id).delete()
    return JsonResponse({'ok': True})


# ── 添付ファイル API（付箋と同方式） ─────────────────

@login_required
@require_http_methods(['POST'])
def api_upload(request):
    """ToDoに画像・PDF を添付する（multipart/form-data）。フィールド: item_id, file"""
    item = TodoItem.objects.filter(user=request.user, id=request.POST.get('item_id')).first()
    if not item:
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

    last = item.attachments.order_by('-order').first()
    att = TodoAttachment(item=item, file=f, name=(f.name or 'file')[:255],
                         content_type=ct, size=f.size,
                         order=(last.order + 1) if last else 0)
    att.save()
    return JsonResponse(_attachment_dict(att))


@login_required
@require_http_methods(['POST'])
def api_attach_delete(request):
    try:
        data = json.loads(request.body)
        att_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    att = TodoAttachment.objects.filter(item__user=request.user, id=att_id).first()
    if att:
        att.delete()   # post_delete で実ファイルも消える
    return JsonResponse({'ok': True})


@login_required
@require_http_methods(['POST'])
def api_attach_reorder(request):
    """添付の並び順を更新。payload: {item_id, ids: [...]}"""
    try:
        data = json.loads(request.body)
        item_id = int(data['item_id'])
        ids = [int(x) for x in data['ids']]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    item = TodoItem.objects.filter(user=request.user, id=item_id).first()
    if not item:
        return JsonResponse({'error': 'not found'}, status=404)

    owned = {a.id: a for a in item.attachments.all()}
    order = 0
    for aid in ids:
        att = owned.get(aid)
        if att:
            att.order = order
            att.save(update_fields=['order'])
            order += 1
    return JsonResponse({'ok': True})