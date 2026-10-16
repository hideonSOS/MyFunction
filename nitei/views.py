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
    EventCode, EVENT_CODE_KINDS, EVENT_CODE_COLORS,
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
        'codes_json':   _codes_json(),
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
        'codes_json':  _codes_json(),
    })


@nitei_login_required
def overview_print(request):
    """全員一覧の印刷ページ（?month=YYYY-MM の1か月分をA3横1枚に。ブラウザ印刷でPDF化）"""
    return render(request, 'nitei/overview_print.html', {
        'persons_json': json.dumps(PERSONS, ensure_ascii=False),
        'codes_json':   _codes_json(),
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
        'codes_json':  _codes_json(),
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
# テンプレートは、人やAIが元資料（PDF・別のExcel等）から書き写すことを前提に、
# 入力セル（黄色）・行と列の対応・書式・してはいけないことを「説明」シートに明記する。
# 1シリーズ（最大7日）をまとめて入力できるよう、1日目〜7日目を横に並べる（1日 = 2列）。
# 取り込みは「発売時刻」シートの「日付」の行と「A列にレース番号がある行」だけを読む
EXCEL_MAX_BYTES  = 2 * 1024 * 1024
EXCEL_SHEET      = '発売時刻'
EXCEL_DAYS       = 7
EXCEL_DATE_ROW   = 5          # 各日の日付の行
EXCEL_FIRST_ROW  = 7          # 1R の行（行番号 = レース番号 + 6）
EXCEL_DATE_LABELS = ('日付', '対象日')   # 対象日 = 1日分だった旧テンプレートの見出し


def _excel_day_cols(day):
    """day日目（1始まり）の 発売開始・締め切り の列番号（B,C / D,E / … / N,O）"""
    return 2 * day, 2 * day + 1


EXCEL_GUIDE = [
    ('このファイルの用途',
     '業務ツール「日程 > 配置図」の「📥 時刻Excel読込」で読み込み、各レースの「発売開始」と'
     '「締め切り」の時刻を、最大7日分（1シリーズ）まとめて入力するためのファイルです。'
     '人またはAIが、出走表などの元資料（PDF・Excel・画像など）から時刻を書き写して使います。'),
    ('入力するセル',
     'シート「発売時刻」の黄色のセルだけです。\n'
     '・5行目：各日の日付（1日目は B5、2日目は D5 … 7日目は N5）\n'
     '・7〜18行目：1R〜12R の時刻（1日目は B列=発売開始・C列=締め切り、2日目は D列・E列 …）\n'
     'これ以外のセルには書き込まないでください。'),
    ('列と日の対応',
     '1日 = 2列です。左の列が発売開始、右の列が締め切り。\n'
     '1日目 = B列・C列、2日目 = D列・E列、3日目 = F列・G列、4日目 = H列・I列、'
     '5日目 = J列・K列、6日目 = L列・M列、7日目 = N列・O列。\n'
     '4行目に「1日目」〜「7日目」、6行目に「発売開始」「締め切り」の見出しがあります。'),
    ('行とレースの対応',
     '7行目=1R、8行目=2R、9行目=3R … 18行目=12R（行番号 = レース番号 + 6）。\n'
     'A列にレース番号（1R〜12R）が入っているので、同じ行に書きます。'),
    ('日付（5行目）',
     '1日目の日付（B5）に、シリーズ初日の日付を書きます（例：2026/10/17）。\n'
     '2日目以降（D5・F5 …）は「前の日の翌日」が自動で入る計算式になっています。'
     '開催日が連続していない場合だけ、その日の日付を上書きしてください。\n'
     'B5 が空欄のときは、画面で表示中の日付が1日目になります。'),
    ('日数が7日より少ない場合',
     '使わない日の列は、時刻を空欄のままにしてください（日付は残っていても構いません）。'
     '時刻が1つも入っていない日は取り込まれません。'),
    ('発売開始（各日の左の列）',
     'そのレースの投票券の発売が始まる時刻。\n'
     '元資料での呼び名の例：「発売開始」「発売開始時刻」「発売開始予定」。'),
    ('締め切り（各日の右の列）',
     'そのレースの投票の締め切り時刻。\n'
     '元資料での呼び名の例：「締切」「締切予定時刻」「投票締切」「発売締切」「締切時刻」。\n'
     '「発走時刻」「スタート時刻」「展示時刻」は締め切りとは別の時刻なので入れないでください。'
     '締め切りが資料に無い場合は、推測で埋めず空欄にしてください。'),
    ('時刻の書き方',
     '24時間表記の「時:分」（例：10:30、20:45）。Excelの時刻値でも、文字列 "10:30" でも構いません。\n'
     '秒は不要です。「午前／午後」「AM／PM」は使わないでください。'),
    ('日をまたぐ場合',
     'ナイター等で締め切りが翌日の0時台になる場合も、日付を付けずに 0:15 のように書いてください。'),
    ('分からない・無いレース',
     '空欄のままにしてください（推測で埋めない）。空欄のセルは取り込まれず、画面に入力済みの時刻がそのまま残ります。'
     '12レースより少ない開催日は、残りの行を空欄にします。'),
    ('変更しないもの',
     'シート名「発売時刻」、A列のレース番号、4行目と6行目の見出し、行と列の位置。'
     '行や列の挿入・削除、セルの結合・結合解除はしないでください。'),
    ('保存形式',
     '.xlsx のまま保存してください（CSV・PDF・画像では読み込めません）。ファイル名は自由です。'),
    ('記入例',
     '初日が 2026/10/17 で、1日目の1Rが 発売開始 10:05・締め切り 10:28 なら → B5 に 2026/10/17、B7 に 10:05、C7 に 10:28。\n'
     '2日目の1Rが 発売開始 10:00・締め切り 10:25 なら → D7 に 10:00、E7 に 10:25（D5 は自動で 2026/10/18）。'),
    ('仕上げの確認',
     '① 黄色のセル以外に書き込んでいない\n'
     '② 1日目の日付（B5）を書いた。開催日が連続しない日は、その日の日付を上書きした\n'
     '③ 時刻はすべて「時:分」の形になっている\n'
     '④ 各日の左の列が発売開始、右の列が締め切りになっている（逆にしていない）\n'
     '⑤ レース番号が進むほど時刻も遅くなっている\n'
     '⑥ 資料から読み取れなかった値は空欄のままにした'),
]


@nitei_login_required
def layout_excel_template(request):
    """発売時刻取り込み用の Excel テンプレート（最大7日分の入力シート＋説明シート）"""
    from io import BytesIO
    from urllib.parse import quote
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    thin   = Side(style='thin', color='888888')
    thick  = Side(style='medium', color='333333')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    wrap   = Alignment(wrap_text=True, vertical='top')
    head   = PatternFill('solid', fgColor='DDE6F0')
    entry  = PatternFill('solid', fgColor='FFF2A8')   # 入力セル（黄色）
    auto   = PatternFill('solid', fgColor='FFF9D6')   # 自動入力（上書き可）
    fixed  = PatternFill('solid', fgColor='EEEEEE')   # 変更しないセル
    last_row = EXCEL_FIRST_ROW + LAYOUT_RACE_COUNT - 1
    last_col = get_column_letter(_excel_day_cols(EXCEL_DAYS)[1])

    wb = Workbook()
    ws = wb.active
    ws.title = EXCEL_SHEET

    ws['A1'] = '配置図 発売時刻 取り込みシート（最大7日分）'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = ('入力するのは黄色のセルだけです（5行目の日付と、7〜18行目の時刻）。'
                '1日 = 2列（左=発売開始・右=締め切り）。書き方のルールは「説明」シートを参照してください。')
    ws['A2'].font = Font(color='C00000', bold=True)
    ws['A2'].alignment = Alignment(wrap_text=True, vertical='center')
    ws.merge_cells(f'A2:{last_col}2')
    ws.row_dimensions[2].height = 32

    for label_row, label in ((4, ''), (EXCEL_DATE_ROW, '日付'), (EXCEL_DATE_ROW + 1, 'レース')):
        c = ws.cell(row=label_row, column=1, value=label or None)
        c.font, c.fill, c.alignment, c.border = Font(bold=True), (head if label else fixed), center, border

    dv_time = DataValidation(
        type='time', operator='between', formula1='0', formula2='0.999305555555556',
        allow_blank=True, showErrorMessage=True,
        errorTitle='時刻の形式', error='24時間表記の「時:分」（例 10:30）で入力してください')
    ws.add_data_validation(dv_time)

    for day in range(1, EXCEL_DAYS + 1):
        sc, cc = _excel_day_cols(day)
        sl, cl = get_column_letter(sc), get_column_letter(cc)
        # 4行目: 「n日目」
        ws.cell(row=4, column=sc, value=f'{day}日目')
        ws.merge_cells(start_row=4, start_column=sc, end_row=4, end_column=cc)
        # 5行目: 日付（1日目は入力、2日目以降は前日+1の計算式。上書き可）
        d = ws.cell(row=EXCEL_DATE_ROW, column=sc)
        if day > 1:
            prev = get_column_letter(_excel_day_cols(day - 1)[0])
            d.value = f'=IF({prev}{EXCEL_DATE_ROW}="","",{prev}{EXCEL_DATE_ROW}+1)'
        d.number_format = 'yyyy/mm/dd(aaa)'
        ws.merge_cells(start_row=EXCEL_DATE_ROW, start_column=sc, end_row=EXCEL_DATE_ROW, end_column=cc)
        # 6行目: 見出し
        ws.cell(row=EXCEL_DATE_ROW + 1, column=sc, value='発売開始')
        ws.cell(row=EXCEL_DATE_ROW + 1, column=cc, value='締め切り')
        for col in (sc, cc):
            for row, fill in ((4, head), (EXCEL_DATE_ROW, entry if day == 1 else auto),
                              (EXCEL_DATE_ROW + 1, head)):
                c = ws.cell(row=row, column=col)
                c.fill, c.alignment, c.border = fill, center, border
                if row != EXCEL_DATE_ROW:
                    c.font = Font(bold=True)
            # 時刻の入力セル
            for row in range(EXCEL_FIRST_ROW, last_row + 1):
                c = ws.cell(row=row, column=col)
                c.fill, c.alignment, c.number_format = entry, center, 'hh:mm'
                c.border = Border(left=thick if col == sc else thin, right=thick if col == cc else thin,
                                  top=thin, bottom=thin)
        dv_time.add(f'{sl}{EXCEL_FIRST_ROW}:{cl}{last_row}')
        ws.column_dimensions[sl].width = 9.5
        ws.column_dimensions[cl].width = 9.5

    for r in range(1, LAYOUT_RACE_COUNT + 1):
        a = ws.cell(row=EXCEL_FIRST_ROW + r - 1, column=1, value=f'{r}R')
        a.fill, a.font, a.alignment, a.border = fixed, Font(bold=True), center, border
    ws.column_dimensions['A'].width = 8
    ws.freeze_panes = f'B{EXCEL_FIRST_ROW}'

    guide = wb.create_sheet('説明')
    guide['A1'] = '「発売時刻」シートの書き方（このファイルを編集する人・AI向け）'
    guide['A1'].font = Font(bold=True, size=13)
    for col, title in enumerate(['項目', '内容'], start=1):
        c = guide.cell(row=3, column=col, value=title)
        c.font, c.fill, c.border, c.alignment = Font(bold=True), head, border, center
    for i, (item, text) in enumerate(EXCEL_GUIDE, start=4):
        a = guide.cell(row=i, column=1, value=item)
        a.font, a.border, a.alignment = Font(bold=True), border, wrap
        b = guide.cell(row=i, column=2, value=text)
        b.border, b.alignment = border, wrap
        guide.row_dimensions[i].height = 15 * (text.count('\n') + 1 + len(text) // 55)
    guide.column_dimensions['A'].width = 24
    guide.column_dimensions['B'].width = 95

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


def _excel_date(value):
    """対象日のセルを 'YYYY-MM-DD' に。空欄・読めない場合は ''"""
    import re
    import unicodedata
    from datetime import date as date_only
    if isinstance(value, (datetime, date_only)):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, str):
        m = re.fullmatch(r'(\d{4})[/\-.年](\d{1,2})[/\-.月](\d{1,2})日?',
                         unicodedata.normalize('NFKC', value).strip())
        if m:
            try:
                return date_only(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime('%Y-%m-%d')
            except ValueError:
                return ''
    return ''


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def layout_excel_import(request):
    """Excel から最大7日分の発売開始・締め切りを読み取り、取り込み内容の確認用に返す（保存はしない）。
    日付が空欄の日は「前の日の翌日」、1日目も空欄なら画面で表示中の日付（base_date）を使う"""
    from datetime import timedelta
    from openpyxl import load_workbook

    f = request.FILES.get('file')
    if f is None:
        return JsonResponse({'error': 'ファイルが選ばれていません'}, status=400)
    if f.size > EXCEL_MAX_BYTES:
        return JsonResponse({'error': 'ファイルが大きすぎます（2MBまで）'}, status=400)
    base = _parse_date(request.POST.get('base_date'))
    if base is None:
        return JsonResponse({'error': 'invalid base_date'}, status=400)
    try:
        wb = load_workbook(f, data_only=True, read_only=True)
    except Exception:
        return JsonResponse({'error': 'Excelファイル（.xlsx）として読み込めませんでした'}, status=400)

    max_col = _excel_day_cols(EXCEL_DAYS)[1]
    date_cells = {}                                  # day -> 'YYYY-MM-DD'（書かれていた日だけ）
    found = {d: {} for d in range(1, EXCEL_DAYS + 1)}  # day -> race -> {start, close}
    warnings = []
    n_days = EXCEL_DAYS   # 旧テンプレート（1日分・D列に発売時間の計算式）は1日目だけ読む
    try:
        ws = wb[EXCEL_SHEET] if EXCEL_SHEET in wb.sheetnames else wb.worksheets[0]
        for row in ws.iter_rows(max_col=max_col, values_only=True):
            if not row:
                continue
            cell = lambda col: row[col - 1] if len(row) >= col else None   # noqa: E731
            if isinstance(row[0], str) and row[0].strip() in EXCEL_DATE_LABELS:
                if row[0].strip() == '対象日':
                    n_days = 1
                for day in range(1, n_days + 1):
                    v = _excel_date(cell(_excel_day_cols(day)[0]))
                    if v:
                        date_cells[day] = v
                continue
            race = _excel_race(row[0])
            if race is None:
                continue
            for day in range(1, n_days + 1):
                sc, cc = _excel_day_cols(day)
                times = {}
                for label, key, raw in (('発売開始', 'start', cell(sc)), ('締め切り', 'close', cell(cc))):
                    t = _excel_time(raw)
                    if t is None:
                        warnings.append(f'{day}日目 {race}R {label}「{raw}」')
                    elif t:
                        times[key] = t
                if times:
                    found[day][race] = {'start': times.get('start', ''), 'close': times.get('close', '')}
    finally:
        wb.close()

    # 各日の日付を決める（書かれていればそれ、無ければ前の日の翌日）
    days, prev = [], None
    for day in range(1, EXCEL_DAYS + 1):
        if day in date_cells:
            d = datetime.strptime(date_cells[day], '%Y-%m-%d').date()
        else:
            d = base if prev is None else prev + timedelta(days=1)
        prev = d
        if found[day]:
            days.append({'day': day, 'date': d.strftime('%Y-%m-%d'),
                         'races': {str(r): v for r, v in sorted(found[day].items())}})

    dates = [x['date'] for x in days]
    if len(set(dates)) != len(dates):
        return JsonResponse({'error': '同じ日付が2回以上あります。5行目の日付を確認してください'}, status=400)

    # 上書きになる（入力済みで値が変わる）時刻の数
    overwrite = 0
    existing = {(r.day.date.strftime('%Y-%m-%d'), r.race): r
                for r in LayoutRace.objects.filter(day__date__in=dates).select_related('day')}
    for x in days:
        for race, v in x['races'].items():
            cur = existing.get((x['date'], int(race)))
            if cur is None:
                continue
            overwrite += sum(1 for new, old in ((v['start'], cur.start_time), (v['close'], cur.close_time))
                             if new and old and new != old)

    return JsonResponse({'days': days, 'warnings': warnings, 'overwrite': overwrite})


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def layout_excel_apply(request):
    """確認済みの取り込み内容を保存する。payload: {days: [{date, races: {race: {start, close}}}]}
    空欄の時刻は既存の値を残し、配置（氏名）・列名・レース番号の着色には触れない"""
    try:
        body = json.loads(request.body)
        days = body['days'][:EXCEL_DAYS]
    except (KeyError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    saved = []
    for x in days:
        d = _parse_date(x.get('date') if isinstance(x, dict) else None)
        if d is None:
            continue
        day, _ = LayoutDay.objects.get_or_create(date=d, defaults={'headers': LAYOUT_DEFAULT_HEADERS})
        for race, v in (x.get('races') or {}).items():
            try:
                race = int(race)
            except (TypeError, ValueError):
                continue
            if not 1 <= race <= LAYOUT_RACE_COUNT or not isinstance(v, dict):
                continue
            start, close = _clean_time(v.get('start')), _clean_time(v.get('close'))
            if not start and not close:
                continue
            row, _ = LayoutRace.objects.get_or_create(day=day, race=race)
            if start:
                row.start_time = start
            if close:
                row.close_time = close
            row.save()
        saved.append(d.strftime('%Y-%m-%d'))
    return JsonResponse({'ok': True, 'dates': saved})


# ── 勤務表の区分（公開FM・公休など。クリック順・色・公休数の数え方） ──

def _codes_list():
    return [{'id': c.id, 'name': c.name, 'color': c.color, 'kind': c.kind, 'order': c.order}
            for c in EventCode.objects.all()]


def _codes_json():
    return json.dumps(_codes_list(), ensure_ascii=False)


def _codes_response():
    return JsonResponse({'codes': _codes_list()})


@nitei_login_required
def api_codes(request):
    return _codes_response()


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_code_save(request):
    """区分の追加 or 更新（id あり=更新）。payload: {id?, name?, color?, kind?}
    改名時は、入力済みの勤務表（全員・全期間）の区分名も追従して書き換える"""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    name  = str(body.get('name') or '').strip()
    color = str(body.get('color') or '').strip()
    kind  = str(body.get('kind') or '').strip()
    if len(name) > 10:
        return JsonResponse({'error': '区分名は10文字以内にしてください'}, status=400)

    code_id = body.get('id')
    if code_id:
        c = EventCode.objects.filter(id=code_id).first()
        if not c:
            return JsonResponse({'error': 'not found'}, status=404)
        if name and name != c.name:
            if EventCode.objects.filter(name=name).exclude(id=c.id).exists():
                return JsonResponse({'error': f'「{name}」は登録済みです'}, status=400)
            EventEntry.objects.filter(time_text=c.name).update(time_text=name)
            c.name = name
        if color in EVENT_CODE_COLORS:
            c.color = color
        if kind in EVENT_CODE_KINDS:
            c.kind = kind
        c.save()
        return _codes_response()

    if not name:
        return JsonResponse({'error': '区分名を入力してください'}, status=400)
    if EventCode.objects.filter(name=name).exists():
        return JsonResponse({'error': f'「{name}」は登録済みです'}, status=400)
    last = EventCode.objects.order_by('-order').first()
    EventCode.objects.create(
        name=name,
        color=color if color in EVENT_CODE_COLORS else 'white',
        kind=kind if kind in EVENT_CODE_KINDS else 'work',
        order=(last.order + 1) if last else 0)
    return _codes_response()


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_code_delete(request):
    """区分を削除。入力済みの文字は残す（履歴保全。色・公休数の集計・切り替え候補からは外れる）"""
    try:
        body = json.loads(request.body)
        code_id = int(body['id'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    EventCode.objects.filter(id=code_id).delete()
    return _codes_response()


@nitei_login_required
@csrf_exempt
@require_http_methods(['POST'])
def api_code_reorder(request):
    """区分の並び順（=クリックで切り替わる順序）を更新。payload: {ids: [...]}"""
    try:
        body = json.loads(request.body)
        ids = [int(x) for x in body['ids']]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)
    owned = {c.id: c for c in EventCode.objects.filter(id__in=ids)}
    order = 0
    for cid in ids:
        c = owned.get(cid)
        if c:
            c.order = order
            c.save(update_fields=['order'])
            order += 1
    return _codes_response()


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
