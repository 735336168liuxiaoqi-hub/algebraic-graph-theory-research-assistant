"""Persistent multi-generation kernels with streamed, receipt-pinned evidence."""
import copy
import hashlib
import json
from pathlib import Path

from .execution_contract import digest
from .search_engine import run_round, verify_round
from graph_research.runtime.resources import MAX_SEGMENT_EVALUATIONS
from graph_research.runtime.storage import safe_path, io_path,write_json

RELATIVE = 'outputs/search-rounds.jsonl'
MAX_BYTES = 64 * 1024 * 1024


def _base(arguments):
    value = dict(arguments); count = value.pop('round_count')
    if type(count) is not int or not 1 <= count <= 128 or count * value['limit'] > MAX_SEGMENT_EVALUATIONS:
        raise ValueError('Invalid persistent search segment size')
    return value, count


def _compact(rounds, preview, first, count, evaluated, feasible, rescored):
    result = copy.deepcopy(rounds)
    result.update(rows=preview, rows_complete=False, round_start=first,
                  rounds_completed=count, evaluations_completed=evaluated,
                  cached_elites_rescored=rescored)
    result['diagnostics']['feasible'] = feasible
    result['diagnostics']['labelled_diversity'] = None
    return result


def run_segment(arguments, *, directory=None):
    a, count = _base(arguments)
    directory = Path(directory or Path.cwd())
    path = safe_path(directory / RELATIVE, root=directory)
    io_path(path.parent).mkdir(parents=True, exist_ok=True)
    policy = None
    if a['run']['method'] == 'cem':
        from .neural_search import Policy
        policy = Policy(a['run']['space'], a['run']['seed'], (a['checkpoint'] or {}).get('neural'),
                        cpu_threads=a['settings'].get('cpu_threads', 1))
    preview = []; evaluated = feasible = rescored = completed = 0
    first = a['round']; last = None
    with io_path(path).open('x', encoding='utf-8',newline='\n') as stream:
        for offset in range(count):
            current = {**a, 'round': first + offset,
                       'checkpoint': last['checkpoint'] if last else a['checkpoint']}
            last = run_round(current, policy=policy)
            raw = json.dumps(last, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'
            if stream.tell() + len(raw.encode('utf-8')) > MAX_BYTES:
                raise ValueError('Search evidence exceeds64MiB; reduce worker_rounds or batch_size')
            stream.write(raw); stream.flush()
            evaluated += len(last['rows']); feasible += last['diagnostics']['feasible']
            rescored += last['cached_elites_rescored']; completed += 1
            write_json(directory/'outputs/search-progress.json',{'round':current['round'],'rounds_in_segment':completed,
                'evaluations_in_segment':evaluated,'verified':False})
            preview.extend({'round': current['round'], **r} for r in last['rows'])
            preview.sort(key=lambda r: r['training_score'], reverse=True); del preview[8:]
            if last['enumeration']['complete']:
                break
    result = _compact(last, preview, first, completed, evaluated, feasible, rescored)
    with io_path(path).open('rb') as stream:
        fingerprint = hashlib.file_digest(stream, 'sha256').hexdigest()
    result['rows_archive'] = {'path': RELATIVE, 'bytes': io_path(path).stat().st_size, 'sha256': fingerprint}
    return result


def round_records(result, directory):
    archive = result['rows_archive']
    if archive['path'] != RELATIVE or type(archive['bytes']) is not int or not 0 < archive['bytes'] <= MAX_BYTES:
        raise ValueError('Invalid search archive reference')
    path = safe_path(Path(directory) / RELATIVE, root=directory)
    if io_path(path).stat().st_size != archive['bytes']:
        raise ValueError('Search archive size changed')
    with io_path(path).open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != archive['sha256']:
            raise ValueError('Search archive checksum changed')
    with io_path(path).open('r', encoding='utf-8') as stream:
        for line in stream:
            if len(line.encode('utf-8')) > MAX_BYTES:
                raise ValueError('Search round record too large')
            yield json.loads(line)


def verify_segment(arguments, result, directory):
    a, count = _base(arguments)
    previous = a['checkpoint']; preview = []; evaluated = feasible = rescored = completed = 0
    last = None
    for offset, item in enumerate(round_records(result, directory)):
        if offset >= count or last and last['enumeration']['complete']:
            raise ValueError('Search segment exceeded approved generations')
        current = {**a, 'round': a['round'] + offset, 'checkpoint': previous}
        verify_round(current, item)
        previous = item['checkpoint']; last = item; completed += 1
        evaluated += len(item['rows']); feasible += item['diagnostics']['feasible']; rescored += item['cached_elites_rescored']
        preview.extend({'round': current['round'], **r} for r in item['rows'])
        preview.sort(key=lambda r: r['training_score'], reverse=True); del preview[8:]
    if completed != count and not (last and last['enumeration']['complete']):
        raise ValueError('Incomplete persistent search segment')
    expected = _compact(last, preview, a['round'], completed, evaluated, feasible, rescored)
    if digest({k: v for k, v in result.items() if k != 'rows_archive'}) != digest(expected):
        raise ValueError('Search segment summary does not match complete streamed evidence')
    return True
