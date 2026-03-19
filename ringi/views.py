import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

BASE_DIR     = Path(__file__).resolve().parent.parent
DOCS_CACHE   = BASE_DIR / 'docs_cache.json'
LOG_DIR      = BASE_DIR / 'logs'
FETCHER      = BASE_DIR / 'docs_fetcher.py'
RUNNER       = BASE_DIR / 'copy_runner.py'
PYTHON       = sys.executable

LOG_DIR.mkdir(exist_ok=True)

_jobs: dict = {}


def _load_docs():
    if not DOCS_CACHE.exists():
        return []
    with open(DOCS_CACHE, encoding='utf-8') as f:
        return json.load(f)


@login_required
def index(request):
    docs = _load_docs()

    kind_filter  = request.GET.get('kind', '')
    query_filter = request.GET.get('q', '')

    filtered = docs
    if kind_filter:
        filtered = [d for d in filtered if d['kind'] == kind_filter]
    if query_filter:
        filtered = [d for d in filtered if query_filter in d['title']]

    # fields を JSON 文字列としてテンプレートに渡す
    import json as _json
    for d in filtered:
        d['fields_json'] = _json.dumps({'__title__': d.get('title', ''), **(d.get('fields') or {})}, ensure_ascii=False)

    ctx = {
        'docs':         filtered,
        'kind_filter':  kind_filter,
        'query':        query_filter,
        'total':        len(docs),
        'cache_exists': DOCS_CACHE.exists(),
    }
    return render(request, 'ringi/index.html', ctx)


@login_required
@require_POST
def fetch_docs(request):
    mode     = request.POST.get('mode', 'update')   # 'update' or 'full'
    job_id   = 'fetch_' + str(uuid.uuid4())[:6]
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

    _jobs[job_id] = {'proc': proc, 'log': str(log_path)}
    return JsonResponse({'job_id': job_id, 'mode': mode})


@login_required
@require_POST
def run_copy(request):
    doc_id     = request.POST.get('doc_id', '').strip()
    title      = request.POST.get('title', '').strip()
    kind       = request.POST.get('kind', '').strip()
    fields_raw = request.POST.get('fields', '')

    if not doc_id:
        return JsonResponse({'error': 'doc_id が指定されていません'}, status=400)

    job_id   = 'copy_' + str(uuid.uuid4())[:6]
    log_path = LOG_DIR / f'job_{job_id}.log'

    cmd = [str(PYTHON), str(RUNNER), doc_id, title]

    # フィールドデータがあれば一時 JSON に書き出して渡す
    if fields_raw:
        try:
            fields_dict = json.loads(fields_raw)
            json_path   = LOG_DIR / f'fields_{job_id}.json'
            with open(json_path, 'w', encoding='utf-8') as jf:
                json.dump({'kind': kind, 'fields': fields_dict}, jf, ensure_ascii=False)
            cmd.append(str(json_path))
        except Exception:
            pass  # パース失敗時はフィールドなしで続行

    with open(log_path, 'w', encoding='utf-8') as lf:
        proc = subprocess.Popen(
            cmd,
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )

    _jobs[job_id] = {'proc': proc, 'log': str(log_path)}
    return JsonResponse({'job_id': job_id})


@login_required
def kaisai_data_view(request):
    """kaisai_data.json を 開催ID キーの dict で返す"""
    data_file = BASE_DIR / 'kaisai_data.json'
    if not data_file.exists():
        return JsonResponse({})
    with open(data_file, encoding='utf-8') as f:
        records = json.load(f)
    grouped = {}
    for r in records:
        kid = str(r['開催ID'])
        if kid not in grouped:
            grouped[kid] = {
                '主催':   r['主催'],
                'タイトル': r['タイトル'],
                '日程':   r['日程'],
                '終了日':  r['終了日'],
                'items': [],
                '合計_税抜き': 0,
                '合計_消費税': 0,
                '合計_税込み': 0,
            }
        try:
            zeibiki   = round(float(r.get('税抜き', 0)))
            shouhizei = round(float(r.get('消費税', 0)))
            total     = round(float(r.get('税込み価格', 0)))
        except (TypeError, ValueError):
            zeibiki = shouhizei = total = 0
        grouped[kid]['items'].append({
            '項目':   r['項目'],
            '税抜き':  zeibiki,
            '消費税':  shouhizei,
            '税込み':  total,
        })
        grouped[kid]['合計_税抜き'] += zeibiki
        grouped[kid]['合計_消費税'] += shouhizei
        grouped[kid]['合計_税込み'] += total
    return JsonResponse(grouped)


@login_required
def log_view(request):
    """常に JSON を返す。サーバー再起動でジョブが消えた場合もエラーにしない。"""
    try:
        job_id = request.GET.get('job_id', '')

        # ジョブがメモリ上にない場合 → ログファイルを直接参照
        if job_id not in _jobs:
            log_path = LOG_DIR / f'job_{job_id}.log'
            if log_path.exists():
                content = log_path.read_text(encoding='utf-8')
                # ファイルがあれば完了扱い（プロセスは消えているが内容は残る）
                done = True
                rc   = 0 if '[DONE]' in content else 1
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

        # プロセス終了 or ログに完了マーカーがあれば done 扱い
        proc_done = info['proc'].poll() is not None
        log_done  = '[DONE]' in content or '[ERROR]' in content
        done      = proc_done or log_done

        if proc_done:
            rc = info['proc'].returncode
        elif log_done:
            rc = 0 if '[DONE]' in content else 1
        else:
            rc = None

        return JsonResponse({'log': content, 'done': done, 'rc': rc})

    except Exception as e:
        return JsonResponse({'log': f'[VIEW ERROR] {e}', 'done': True, 'rc': -1})
