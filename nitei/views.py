import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Title, WorkEntry


def index(request):
    return render(request, 'nitei/index.html')


# ── 開催タイトル API ──────────────────────────────

def api_titles(request):
    titles = list(Title.objects.values('id', 'date_from', 'date_to', 'venue', 'title'))
    for t in titles:
        t['date_from'] = t['date_from'].strftime('%Y/%m/%d')
        t['date_to']   = t['date_to'].strftime('%Y/%m/%d')
    return JsonResponse(titles, safe=False)


# ── 勤務記録 API ──────────────────────────────────

def api_schedule(request):
    entries = WorkEntry.objects.all()
    data = {f"w_{e.sheet_index}_{e.section_index}_{e.day_index}": e.status
            for e in entries}
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(['POST'])
def api_schedule_save(request):
    try:
        body = json.loads(request.body)
        key    = body['key']    # e.g. "w_0_0_3"
        status = body['status']
    except (KeyError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    parts = key.split('_')
    if len(parts) != 4 or parts[0] != 'w':
        return JsonResponse({'error': 'bad key'}, status=400)

    _, si, sec, di = parts
    if status == '':
        WorkEntry.objects.filter(
            sheet_index=int(si), section_index=int(sec), day_index=int(di)
        ).delete()
    else:
        WorkEntry.objects.update_or_create(
            sheet_index=int(si), section_index=int(sec), day_index=int(di),
            defaults={'status': status}
        )
    return JsonResponse({'ok': True})


@csrf_exempt
@require_http_methods(['POST'])
def api_schedule_clear(request):
    """シート単位でリセット"""
    try:
        body = json.loads(request.body)
        sheet_index = int(body['sheet_index'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid'}, status=400)

    WorkEntry.objects.filter(sheet_index=sheet_index).delete()
    return JsonResponse({'ok': True})
