import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import LineNotification, LineTarget
from . import line_api
from datetime import datetime


def _target_dict(t):
    return {
        'id':        t.id,
        'name':      t.name,
        'target_id': t.target_id,
        'kind':      t.kind,
        'kind_label': t.get_kind_display(),
    }


def _notif_dict(n):
    return {
        'id':          n.id,
        'date':        n.date.strftime('%Y-%m-%d'),
        'time':        n.time.strftime('%H:%M'),
        'message':     n.message,
        'target':      n.target.id if n.target else None,
        'target_name': n.target.name if n.target else 'ブロードキャスト',
        'sent':        n.sent,
        'sent_at':     timezone.localtime(n.sent_at).strftime('%Y-%m-%d %H:%M') if n.sent_at else None,
        'error':       n.error,
    }


@login_required
def index(request):
    return render(request, 'linenotify/index.html', {
        'configured': line_api.is_configured(),
    })


@login_required
def api_list(request):
    return JsonResponse({
        'items':      [_notif_dict(n) for n in
                       LineNotification.objects.select_related('target')],
        'targets':    [_target_dict(t) for t in LineTarget.objects.all()],
        'configured': line_api.is_configured(),
    })


def _resolve_target(data):
    """payload の target（LineTarget の id / null）を検証して返す。
    戻り値: (target or None, error or None)"""
    target_id = data.get('target')
    if not target_id:
        return None, '送信先を指定してください（ブロードキャストは現在無効です）'
    t = LineTarget.objects.filter(id=target_id).first()
    if not t:
        return None, '送信先が見つかりません（削除された可能性があります）'
    return t, None


@login_required
@require_http_methods(['POST'])
def api_save(request):
    """新規登録 or 編集（id があれば更新）。送信済みは編集不可"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    d = parse_date(str(data.get('date') or ''))
    try:
        t = datetime.strptime(str(data.get('time') or ''), '%H:%M').time()
    except ValueError:
        t = None
    message = str(data.get('message') or '').strip()

    if not d or not t or not message:
        return JsonResponse({'error': '日付・時刻・メッセージをすべて入力してください'}, status=400)

    target, err = _resolve_target(data)
    if err:
        return JsonResponse({'error': err}, status=400)

    notif_id = data.get('id')
    if notif_id:
        n = LineNotification.objects.filter(id=notif_id).first()
        if not n:
            return JsonResponse({'error': 'not found'}, status=404)
        if n.sent:
            return JsonResponse({'error': '送信済みの通知は編集できません'}, status=400)
    else:
        n = LineNotification()

    n.date, n.time, n.message, n.target = d, t, message[:1000], target
    n.error = ''
    n.save()
    return JsonResponse(_notif_dict(n))


@login_required
@require_http_methods(['POST'])
def api_delete(request):
    try:
        data = json.loads(request.body)
        notif_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    LineNotification.objects.filter(id=notif_id).delete()
    return JsonResponse({'ok': True})


@login_required
@require_http_methods(['POST'])
def api_send_now(request):
    """1件を今すぐ送信（予約を待たない）。動作確認にも使う"""
    try:
        data = json.loads(request.body)
        notif_id = int(data['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    n = LineNotification.objects.filter(id=notif_id).select_related('target').first()
    if not n:
        return JsonResponse({'error': 'not found'}, status=404)

    # 二重送信防止: 先に原子的にクレームする（ボタン連打・cronとの同時実行対策）
    claimed = LineNotification.objects.filter(id=n.id, sent=False).update(
        sent=True, sent_at=timezone.now(), error='')
    if not claimed:
        n.refresh_from_db()
        return JsonResponse(_notif_dict(n))   # すでに送信済み

    ok, err = line_api.send_to(n.target, n.message)
    if not ok:
        LineNotification.objects.filter(id=n.id).update(
            sent=False, sent_at=None, error=err)
    n.refresh_from_db()
    return JsonResponse(_notif_dict(n))


@login_required
@require_http_methods(['POST'])
def api_test(request):
    """接続テスト（選択中の宛先へ固定文言を即時送信）"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}
    target, err = _resolve_target(data)
    if err:
        return JsonResponse({'ok': False, 'error': err})
    name = target.name if target else 'ブロードキャスト'
    ok, err = line_api.send_to(target, f'MyFunction LINE通知のテスト送信です。（宛先: {name}）')
    return JsonResponse({'ok': ok, 'error': err})


# ── 送信先の管理 ──────────────────────────────

@login_required
@require_http_methods(['POST'])
def api_target_save(request):
    """送信先の手動登録 or 名前変更（id があれば更新）"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    name = str(data.get('name') or '').strip()[:100]
    tid  = str(data.get('target_id') or '').strip()[:64]

    target_pk = data.get('id')
    if target_pk:
        t = LineTarget.objects.filter(id=target_pk).first()
        if not t:
            return JsonResponse({'error': 'not found'}, status=404)
        if name:
            t.name = name
        t.save()
        return JsonResponse(_target_dict(t))

    if not name or not tid:
        return JsonResponse({'error': '表示名とIDを入力してください'}, status=400)
    if LineTarget.objects.filter(target_id=tid).exists():
        return JsonResponse({'error': 'そのIDは登録済みです'}, status=400)

    kind = 'group' if tid.startswith('C') else 'room' if tid.startswith('R') \
        else 'user' if tid.startswith('U') else 'group'
    t = LineTarget.objects.create(name=name, target_id=tid, kind=kind)
    return JsonResponse(_target_dict(t))


# 注: 送信先の削除APIは誤操作防止のため撤去した。
# 誤登録の修正が必要な場合は Django 管理画面（/admin/）から行う。


# ── LINE Webhook（グループ自動登録） ─────────────
# ボットをグループに招待する／グループ内で発言があると LINE から届く。
# 署名検証には line_credentials.json の channel_secret が必要。

@csrf_exempt
@require_http_methods(['POST'])
def webhook(request):
    signature = request.headers.get('X-Line-Signature', '')
    if not line_api.verify_signature(request.body, signature):
        return HttpResponse(status=403)

    try:
        events = json.loads(request.body).get('events', [])
    except (ValueError, AttributeError):
        events = []

    for ev in events:
        src = ev.get('source') or {}
        gid = src.get('groupId')
        rid = src.get('roomId')
        if gid and not LineTarget.objects.filter(target_id=gid).exists():
            name = line_api.get_group_name(gid) or 'LINEグループ'
            LineTarget.objects.create(name=name, target_id=gid, kind='group')
        elif rid and not LineTarget.objects.filter(target_id=rid).exists():
            LineTarget.objects.create(name='トークルーム', target_id=rid, kind='room')

    return HttpResponse(status=200)
