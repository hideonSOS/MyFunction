import json
from functools import wraps
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Title, WorkEntry, EventEntry, PERSONS

NITEI_SESSION_KEY = 'nitei_authed'


# ── nitei 専用認証デコレーター ────────────────────────
# Django ログイン済み（管理者）はそのまま通す
# nitei セッションがあればそのまま通す
# どちらでもなければ nitei ログインページへ

def nitei_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        if request.session.get(NITEI_SESSION_KEY):
            return view_func(request, *args, **kwargs)
        return redirect('nitei:login')
    return wrapper


# ── nitei ログイン / ログアウト ───────────────────────

def nitei_login(request):
    # すでに認証済みならトップへ
    if request.user.is_authenticated or request.session.get(NITEI_SESSION_KEY):
        return redirect('nitei:top')

    error = False
    if request.method == 'POST':
        pw = request.POST.get('password', '')
        if pw == getattr(settings, 'NITEI_PASSWORD', ''):
            request.session[NITEI_SESSION_KEY] = True
            request.session.set_expiry(60 * 60 * 24 * 30)  # 30日間
            return redirect('nitei:top')
        error = True

    return render(request, 'nitei/login.html', {'error': error})


def nitei_logout(request):
    request.session.pop(NITEI_SESSION_KEY, None)
    return redirect('nitei:login')


# ── ページビュー ──────────────────────────────────────

@nitei_login_required
def top(request):
    return render(request, 'nitei/top.html', {'persons': PERSONS})


@nitei_login_required
def schedule(request, person):
    if person not in PERSONS:
        return redirect('nitei:top')
    return render(request, 'nitei/index.html', {
        'person':      person,
        'person_name': PERSONS[person],
        'persons':     PERSONS,
    })


# ── 開催タイトル API ──────────────────────────────────

@nitei_login_required
def api_titles(request):
    titles = list(Title.objects.values('id', 'date_from', 'date_to', 'venue', 'title'))
    for t in titles:
        t['date_from'] = t['date_from'].strftime('%Y/%m/%d')
        t['date_to']   = t['date_to'].strftime('%Y/%m/%d')
    return JsonResponse(titles, safe=False)


# ── 勤務記録 API ──────────────────────────────────────

@nitei_login_required
def api_schedule(request):
    person = request.GET.get('person', 'a')
    if person not in PERSONS:
        return JsonResponse({'error': 'invalid person'}, status=400)
    entries = WorkEntry.objects.filter(person=person)
    data = {f"w_{e.sheet_index}_{e.section_index}_{e.day_index}": e.status
            for e in entries}
    return JsonResponse(data)


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_schedule_save(request):
    try:
        body   = json.loads(request.body)
        key    = body['key']
        status = body['status']
        person = body.get('person', 'a')
    except (KeyError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    if person not in PERSONS:
        return JsonResponse({'error': 'invalid person'}, status=400)

    parts = key.split('_')
    if len(parts) != 4 or parts[0] != 'w':
        return JsonResponse({'error': 'bad key'}, status=400)

    _, si, sec, di = parts
    if status == '':
        WorkEntry.objects.filter(
            person=person,
            sheet_index=int(si), section_index=int(sec), day_index=int(di)
        ).delete()
    else:
        WorkEntry.objects.update_or_create(
            person=person,
            sheet_index=int(si), section_index=int(sec), day_index=int(di),
            defaults={'status': status}
        )
    return JsonResponse({'ok': True})


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_schedule_clear(request):
    try:
        body        = json.loads(request.body)
        person      = body.get('person', 'a')
        sheet_index = int(body['sheet_index'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    if person not in PERSONS:
        return JsonResponse({'error': 'invalid person'}, status=400)

    WorkEntry.objects.filter(person=person, sheet_index=sheet_index).delete()
    return JsonResponse({'ok': True})


# ── 開催行 時間メモ API ────────────────────────────────

@nitei_login_required
def api_events(request):
    person = request.GET.get('person', 'a')
    if person not in PERSONS:
        return JsonResponse({'error': 'invalid person'}, status=400)
    entries = EventEntry.objects.filter(person=person)
    data = {f"e_{e.sheet_index}_{e.section_index}_{e.day_index}": e.time_text
            for e in entries}
    return JsonResponse(data)


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_events_save(request):
    try:
        body      = json.loads(request.body)
        key       = body['key']
        time_text = body['time_text']
        person    = body.get('person', 'a')
    except (KeyError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    if person not in PERSONS:
        return JsonResponse({'error': 'invalid person'}, status=400)

    parts = key.split('_')
    if len(parts) != 4 or parts[0] != 'e':
        return JsonResponse({'error': 'bad key'}, status=400)

    _, si, sec, di = parts
    if time_text == '':
        EventEntry.objects.filter(
            person=person,
            sheet_index=int(si), section_index=int(sec), day_index=int(di)
        ).delete()
    else:
        EventEntry.objects.update_or_create(
            person=person,
            sheet_index=int(si), section_index=int(sec), day_index=int(di),
            defaults={'time_text': time_text}
        )
    return JsonResponse({'ok': True})
