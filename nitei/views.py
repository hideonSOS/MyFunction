import json
from functools import wraps
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from datetime import date as date_cls, datetime
from .models import (
    Title, WorkEntry, EventEntry, PERSONS,
    LayoutDay, LayoutRace, LayoutCell, LayoutMember,
    LAYOUT_RACE_COUNT, LAYOUT_COL_COUNT, LAYOUT_DEFAULT_HEADERS, LAYOUT_COLOR_KEYS,
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
        'color_keys':       json.dumps(LAYOUT_COLOR_KEYS),
        'members':          json.dumps(_members_list(), ensure_ascii=False),
    })


@nitei_login_required
def haichi_print(request):
    """配置図の印刷ページ（最大3日分をA3横に並べ、ブラウザ印刷でPDF化）"""
    return render(request, 'nitei/haichi_print.html', {
        'dates_param':      request.GET.get('dates', ''),
        'race_count':       LAYOUT_RACE_COUNT,
        'col_count':        LAYOUT_COL_COUNT,
        'default_headers':  json.dumps(LAYOUT_DEFAULT_HEADERS, ensure_ascii=False),
    })


@nitei_login_required
def overview(request):
    return render(request, 'nitei/overview.html', {
        'persons_json': json.dumps(PERSONS, ensure_ascii=False),
    })


@nitei_login_required
def schedule_print(request):
    """個人の勤務表の印刷ページ（?person=a&sheet=N の勤務表1枚分を横長1枚に。ブラウザ印刷でPDF化）"""
    person = request.GET.get('person', '')
    if person not in PERSONS:
        return redirect('nitei:top')
    return render(request, 'nitei/schedule_print.html', {
        'person':      person,
        'person_name': PERSONS[person],
        'sheet_param': request.GET.get('sheet', ''),
    })


@nitei_login_required
def overview_print(request):
    """全員一覧の印刷ページ（?month=YYYY-MM の1か月分をA3横1枚に。ブラウザ印刷でPDF化）"""
    return render(request, 'nitei/overview_print.html', {
        'persons_json': json.dumps(PERSONS, ensure_ascii=False),
        'month_param':  request.GET.get('month', ''),
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
            'colors':  {},
            'exists':  False,
        })

    headers = day.headers or LAYOUT_DEFAULT_HEADERS
    headers = (list(headers) + [''] * LAYOUT_COL_COUNT)[:LAYOUT_COL_COUNT]

    cells  = {}
    colors = {}
    for c in day.cells.all():
        key = f"{c.race}_{c.col}"
        if c.text:
            cells[key] = c.text
        if c.color:
            colors[key] = c.color

    return JsonResponse({
        'date':    day_date.strftime('%Y-%m-%d'),
        'headers': headers,
        'races': [{
            'race':      r.race,
            'start':     r.start_time,
            'close':     r.close_time,
            'highlight': r.highlight,
        } for r in day.races.all()],
        'cells':  cells,
        'colors': colors,
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

    # 配置セル（テキストと背景色。どちらか一方だけでも保存する）
    def parse_key(key):
        parts = str(key).split('_')
        if len(parts) != 2:
            return None
        try:
            race, col = int(parts[0]), int(parts[1])
        except ValueError:
            return None
        if not (1 <= race <= LAYOUT_RACE_COUNT and 0 <= col < LAYOUT_COL_COUNT):
            return None
        return (race, col)

    merged = {}
    for key, text in (body.get('cells') or {}).items():
        rc = parse_key(key)
        if rc is None:
            continue
        text = str(text or '').strip()[:200]
        if text:
            merged.setdefault(rc, {'text': '', 'color': ''})['text'] = text

    for key, color in (body.get('colors') or {}).items():
        rc = parse_key(key)
        if rc is None:
            continue
        color = str(color or '').strip()
        if color in LAYOUT_COLOR_KEYS:
            merged.setdefault(rc, {'text': '', 'color': ''})['color'] = color

    day.cells.all().delete()
    LayoutCell.objects.bulk_create([
        LayoutCell(day=day, race=rc[0], col=rc[1], text=v['text'], color=v['color'])
        for rc, v in merged.items()
    ])

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


# ── 配置図: 発売時刻の Excel 取り込み ─────────────────
# テンプレートは A列=レース（1R〜12R）/ B列=発売開始 / C列=締め切り。
# 取り込みは「レース番号が書かれた行」だけを読むので、見出し行や説明行があってもよい
EXCEL_MAX_BYTES = 2 * 1024 * 1024


@nitei_login_required
def layout_excel_template(request):
    """発売時刻取り込み用の Excel テンプレート（空欄）をダウンロード"""
    from io import BytesIO
    from urllib.parse import quote
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = '発売時刻'
    ws['A1'] = '配置図 発売時刻（時刻は 10:30 のように入力。空欄のセルは取り込みません）'
    ws['A1'].font = Font(bold=True, size=12)

    thin   = Side(style='thin', color='888888')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center')

    for col, title in enumerate(['レース', '発売開始', '締め切り'], start=1):
        c = ws.cell(row=3, column=col, value=title)
        c.font = Font(bold=True)
        c.fill = PatternFill('solid', fgColor='DDE6F0')
        c.alignment = center
        c.border = border
    for r in range(1, LAYOUT_RACE_COUNT + 1):
        row = 3 + r
        ws.cell(row=row, column=1, value=f'{r}R').alignment = center
        for col in (1, 2, 3):
            c = ws.cell(row=row, column=col)
            c.border = border
            c.alignment = center
            if col > 1:
                c.number_format = 'hh:mm'
    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 14
    ws.freeze_panes = 'A4'

    buf = BytesIO()
    wb.save(buf)
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = '配置図_発売時刻テンプレート.xlsx'
    resp['Content-Disposition'] = (
        f"attachment; filename=\"haichi_times_template.xlsx\"; filename*=UTF-8''{quote(filename)}")
    return resp


def _excel_race(value):
    """A列の値をレース番号（1〜12）に。'1R' / '１Ｒ' / 1 などを許容。該当しなければ None"""
    import re
    import unicodedata
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        n = int(value) if float(value).is_integer() else None
    else:
        m = re.fullmatch(r'(\d{1,2})\s*R?', unicodedata.normalize('NFKC', str(value)).strip(), re.I)
        n = int(m.group(1)) if m else None
    return n if n is not None and 1 <= n <= LAYOUT_RACE_COUNT else None


def _excel_time(value):
    """セルの値を 'HH:MM' に。空欄は ''、時刻として読めなければ None"""
    import re
    import unicodedata
    from datetime import time as time_cls, timedelta

    def fmt(h, m):
        return f'{h:02d}:{m:02d}' if 0 <= h <= 23 and 0 <= m <= 59 else None

    def from_clock(t):
        # Excel の時刻は浮動小数なので 10:29:59.99 のようになる。分に四捨五入する
        mins = round((t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6) / 60)
        return fmt(mins // 60, mins % 60) if mins < 24 * 60 else None

    if value is None or (isinstance(value, str) and not value.strip()):
        return ''
    if isinstance(value, datetime):
        # 時刻書式のセルに 1135 のように数字だけ入れると「1135日後の0:00」になる。
        # その場合は元の数字を HHMM として読む
        serial = (value - datetime(1899, 12, 30)).days
        if serial >= 1 and value.hour == value.minute == value.second == 0:
            return fmt(serial // 100, serial % 100)
        return from_clock(value)
    if isinstance(value, time_cls):
        return from_clock(value)
    if isinstance(value, timedelta):
        mins = round(value.total_seconds() / 60)
        return fmt(mins // 60, mins % 60)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 0 <= value < 1:                       # Excel の時刻（1日=1.0）
            mins = round(value * 24 * 60)
            return fmt(mins // 60, mins % 60) if mins < 24 * 60 else None
        if float(value).is_integer():            # 1030 → 10:30
            n = int(value)
            return fmt(n // 100, n % 100)
        return None
    s = unicodedata.normalize('NFKC', str(value)).strip()
    m = (re.fullmatch(r'(\d{1,2}):(\d{1,2})(?::\d{1,2})?', s)
         or re.fullmatch(r'(\d{1,2})時(\d{1,2})分?', s)
         or re.fullmatch(r'(\d{1,2})(\d{2})', s))
    return fmt(int(m.group(1)), int(m.group(2))) if m else None


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def layout_excel_import(request):
    """Excel から発売開始・締め切りを読み取って返す（保存は画面側が通常の保存で行う）"""
    from openpyxl import load_workbook

    f = request.FILES.get('file')
    if f is None:
        return JsonResponse({'error': 'ファイルが選ばれていません'}, status=400)
    if f.size > EXCEL_MAX_BYTES:
        return JsonResponse({'error': 'ファイルが大きすぎます（2MBまで）'}, status=400)
    try:
        wb = load_workbook(f, data_only=True, read_only=True)
    except Exception:
        return JsonResponse({'error': 'Excelファイル（.xlsx）として読み込めませんでした'}, status=400)

    races, warnings = {}, []
    try:
        for row in wb.worksheets[0].iter_rows(max_col=3, values_only=True):
            race = _excel_race(row[0] if row else None)
            if race is None:
                continue
            times = {}
            for label, key, raw in (('発売開始', 'start', row[1] if len(row) > 1 else None),
                                    ('締め切り', 'close', row[2] if len(row) > 2 else None)):
                t = _excel_time(raw)
                if t is None:
                    warnings.append(f'{race}R {label}「{raw}」')
                elif t:
                    times[key] = t
            if times:
                races[race] = {'start': times.get('start', ''), 'close': times.get('close', '')}
    finally:
        wb.close()

    return JsonResponse({'races': races, 'warnings': warnings})


# ── 配置図の名簿（クリック循環の順序・自動着色の色） ────

def _members_list():
    return [{'id': m.id, 'name': m.name, 'color': m.color, 'order': m.order}
            for m in LayoutMember.objects.all()]


def _members_response():
    return JsonResponse({'members': _members_list()})


@nitei_login_required
def api_members(request):
    return _members_response()


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_member_save(request):
    """名簿の追加 or 更新（id あり=更新）。payload: {id?, name?, color?}
    改名時は、配置済みセル（全日付）の氏名・色も追従して書き換える"""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    name  = str(body.get('name') or '').strip()[:20]
    color = str(body.get('color') or '').strip()

    member_id = body.get('id')
    if member_id:
        m = LayoutMember.objects.filter(id=member_id).first()
        if not m:
            return JsonResponse({'error': 'not found'}, status=404)
        if name and name != m.name:
            if LayoutMember.objects.filter(name=name).exclude(id=m.id).exists():
                return JsonResponse({'error': f'「{name}」は登録済みです'}, status=400)
            old = m.name
            m.name = name
            # 改名を配置済みセルへ反映（過去日も含む。同一人物の表記修正を想定）
            LayoutCell.objects.filter(text=old).update(text=name)
        if color in LAYOUT_COLOR_KEYS:
            m.color = color
            # 色変更も配置済みセルへ反映
            LayoutCell.objects.filter(text=m.name).update(color=color)
        m.save()
        return _members_response()

    # 新規追加
    if not name:
        return JsonResponse({'error': '氏名を入力してください'}, status=400)
    if LayoutMember.objects.filter(name=name).exists():
        return JsonResponse({'error': f'「{name}」は登録済みです'}, status=400)
    if color not in LAYOUT_COLOR_KEYS:
        # 未指定なら、使用数が最も少ない色を自動で割り当てる
        used = {c: 0 for c in LAYOUT_COLOR_KEYS}
        for m in LayoutMember.objects.all():
            if m.color in used:
                used[m.color] += 1
        color = min(LAYOUT_COLOR_KEYS, key=lambda c: used[c])
    last = LayoutMember.objects.order_by('-order').first()
    LayoutMember.objects.create(
        name=name, color=color, order=(last.order + 1) if last else 0)
    return _members_response()


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_member_delete(request):
    """名簿から削除。配置済みセルの文字は残す（履歴保全。色と循環からは外れる）"""
    try:
        body = json.loads(request.body)
        member_id = int(body['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    LayoutMember.objects.filter(id=member_id).delete()
    return _members_response()


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_member_reorder(request):
    """名簿の並び順（=クリック循環の順序）を更新。payload: {ids: [...]}"""
    try:
        body = json.loads(request.body)
        ids = [int(x) for x in body['ids']]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    owned = {m.id: m for m in LayoutMember.objects.filter(id__in=ids)}
    order = 0
    for mid in ids:
        m = owned.get(mid)
        if m:
            m.order = order
            m.save(update_fields=['order'])
            order += 1
    return _members_response()
