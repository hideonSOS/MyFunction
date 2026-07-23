import json
from functools import wraps
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from datetime import date as date_cls, datetime
from .models import (
    Title, WorkEntry, EventEntry, PERSONS,
    LayoutDay, LayoutRace, LayoutCell,
    LAYOUT_RACE_COUNT, LAYOUT_COL_COUNT, LAYOUT_DEFAULT_HEADERS,
)

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
def haichi(request):
    return render(request, 'nitei/haichi.html', {
        'today':            date_cls.today().strftime('%Y-%m-%d'),
        'race_count':       LAYOUT_RACE_COUNT,
        'col_count':        LAYOUT_COL_COUNT,
        'default_headers':  json.dumps(LAYOUT_DEFAULT_HEADERS, ensure_ascii=False),
    })


@nitei_login_required
def overview(request):
    return render(request, 'nitei/overview.html', {
        'persons_json': json.dumps(PERSONS, ensure_ascii=False),
    })


def api_overview(request):
    if not (request.user.is_authenticated or request.session.get(NITEI_SESSION_KEY)):
        return JsonResponse({'error': 'unauthorized'}, status=403)
    sheet_index   = int(request.GET.get('sheet_index', 0))
    section_index = int(request.GET.get('section_index', 0))

    data = {}
    for person in PERSONS:
        pdata = {}
        for e in WorkEntry.objects.filter(
                person=person, sheet_index=sheet_index, section_index=section_index):
            pdata[f"w_{e.day_index}_{e.row_type}"] = e.status
        for e in EventEntry.objects.filter(
                person=person, sheet_index=sheet_index, section_index=section_index):
            pdata[f"e_{e.day_index}"] = e.time_text
        data[person] = pdata

    titles = list(Title.objects.values('id', 'date_from', 'date_to', 'venue', 'title'))
    for t in titles:
        t['date_from'] = t['date_from'].strftime('%Y/%m/%d')
        t['date_to']   = t['date_to'].strftime('%Y/%m/%d')

    return JsonResponse({'data': data, 'titles': titles})


def schedule(request, person):
    if person not in PERSONS:
        return redirect('nitei:top')

    if person == 'a':
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
    else:
        if not request.user.is_authenticated and not request.session.get(NITEI_SESSION_KEY):
            return redirect('nitei:login')

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
    data = {f"w_{e.sheet_index}_{e.section_index}_{e.day_index}_{e.row_type}": e.status
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
    if len(parts) != 5 or parts[0] != 'w':
        return JsonResponse({'error': 'bad key'}, status=400)

    _, si, sec, di, rt = parts
    if status == '':
        WorkEntry.objects.filter(
            person=person,
            sheet_index=int(si), section_index=int(sec), day_index=int(di), row_type=int(rt)
        ).delete()
    else:
        WorkEntry.objects.update_or_create(
            person=person,
            sheet_index=int(si), section_index=int(sec), day_index=int(di), row_type=int(rt),
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


# ── 配置図 API ────────────────────────────────────────

def _parse_date(value):
    """'YYYY-MM-DD' を date に。不正なら None"""
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _clean_time(value):
    """HH:MM 形式だけ通す。それ以外は空文字"""
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if not value:
        return ''
    try:
        datetime.strptime(value, '%H:%M')
    except ValueError:
        return ''
    return value


@nitei_login_required
def api_layout(request):
    day_date = _parse_date(request.GET.get('date'))
    if day_date is None:
        return JsonResponse({'error': 'invalid date'}, status=400)

    day = LayoutDay.objects.filter(date=day_date).first()
    if day is None:
        return JsonResponse({
            'date':    day_date.strftime('%Y-%m-%d'),
            'headers': LAYOUT_DEFAULT_HEADERS,
            'races':   [],
            'cells':   {},
            'exists':  False,
        })

    headers = day.headers or LAYOUT_DEFAULT_HEADERS
    headers = (list(headers) + [''] * LAYOUT_COL_COUNT)[:LAYOUT_COL_COUNT]

    return JsonResponse({
        'date':    day_date.strftime('%Y-%m-%d'),
        'headers': headers,
        'races': [{
            'race':      r.race,
            'start':     r.start_time,
            'close':     r.close_time,
            'highlight': r.highlight,
        } for r in day.races.all()],
        'cells':  {f"{c.race}_{c.col}": c.text for c in day.cells.all()},
        'exists': True,
    })


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_layout_save(request):
    """1日分をまとめて保存（差し替え）"""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    day_date = _parse_date(body.get('date'))
    if day_date is None:
        return JsonResponse({'error': 'invalid date'}, status=400)

    headers = body.get('headers') or []
    if not isinstance(headers, list):
        return JsonResponse({'error': 'invalid headers'}, status=400)
    headers = [str(h)[:50] for h in headers[:LAYOUT_COL_COUNT]]
    headers += [''] * (LAYOUT_COL_COUNT - len(headers))

    day, _ = LayoutDay.objects.update_or_create(
        date=day_date, defaults={'headers': headers})

    # レース時刻
    day.races.all().delete()
    races = []
    for item in (body.get('races') or []):
        try:
            race = int(item.get('race'))
        except (TypeError, ValueError):
            continue
        if not 1 <= race <= LAYOUT_RACE_COUNT:
            continue
        start     = _clean_time(item.get('start'))
        close     = _clean_time(item.get('close'))
        highlight = bool(item.get('highlight'))
        if not start and not close and not highlight:
            continue
        races.append(LayoutRace(day=day, race=race, start_time=start,
                                close_time=close, highlight=highlight))
    LayoutRace.objects.bulk_create(races)

    # 配置セル
    day.cells.all().delete()
    cells = []
    for key, text in (body.get('cells') or {}).items():
        parts = str(key).split('_')
        if len(parts) != 2:
            continue
        try:
            race, col = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if not (1 <= race <= LAYOUT_RACE_COUNT and 0 <= col < LAYOUT_COL_COUNT):
            continue
        text = str(text or '').strip()[:200]
        if not text:
            continue
        cells.append(LayoutCell(day=day, race=race, col=col, text=text))
    LayoutCell.objects.bulk_create(cells)

    return JsonResponse({'ok': True})


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_layout_clear(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    day_date = _parse_date(body.get('date'))
    if day_date is None:
        return JsonResponse({'error': 'invalid date'}, status=400)

    LayoutDay.objects.filter(date=day_date).delete()
    return JsonResponse({'ok': True})
