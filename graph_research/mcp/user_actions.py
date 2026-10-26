"""Trusted desktop outbox delivery inside the original MCP host process.

No event issuance lives here. A signed human action may resume only its pinned
task; a polling model cannot approve a task by creating an outbox JSON file.
"""
import hashlib
import os
import time

from graph_research.assistant.task_contract import canonical, check_id, TaskProtocolError
from graph_research.runtime.storage import safe_path, read_json, write_json, exclusive_lock, io_path


def configuration_hash(configuration):
    return hashlib.sha256(canonical(configuration.public()).encode('utf-8')).hexdigest()


def action_path(runtime, event_id, *, processed=False):
    folder = 'processed' if processed else 'pending'
    return safe_path(runtime.directory / 'user-actions' / folder / (check_id(event_id) + '.json'), root=runtime.directory)


def queued_action(runtime, task_id):
    """Read the most recent UI delivery status without issuing/consuming events."""
    task_id = check_id(task_id)
    pointer = safe_path(runtime.service.task_dir(task_id) / 'ui-action.json', root=runtime.service.directory)
    if not io_path(pointer).is_file():
        return None
    event_id = read_json(pointer, max_bytes=4096)[0]['event_id']
    for processed in (True, False):
        path = action_path(runtime, event_id, processed=processed)
        if io_path(path).is_file():
            item = read_json(path, max_bytes=8192)[0]
            if item['task_id'] != task_id:
                raise ValueError('User-action pointer is outside its task scope')
            return item
    return {'state': 'delivery_unknown', 'task_id': task_id}


def enqueue(runtime, event):
    """Called only after a native user click has issued the signed event."""
    item = {'version': 1, 'event_id': event['event_id'], 'task_id': event['task_id'],
            'configuration_sha256': configuration_hash(runtime.configuration),
            'state': 'queued', 'created_at': time.time()}
    write_json(action_path(runtime, event['event_id']), item)
    write_json(runtime.service.task_dir(event['task_id']) / 'ui-action.json', {'event_id': event['event_id']})
    return item


def _archive(runtime, path, item):
    write_json(path, item)
    target = action_path(runtime, item['event_id'], processed=True)
    io_path(target.parent).mkdir(parents=True, exist_ok=True)
    os.replace(io_path(path), io_path(target))


def _validate(runtime, item):
    task_id = check_id(item['task_id']); event_id = check_id(item['event_id'])
    record = runtime.service.read(task_id)
    event = runtime.service.events.read(event_id)
    if event['task_id'] != task_id or event['request_sha256'] != record['request_sha256']:
        raise TaskProtocolError('event_scope_mismatch', '用户操作与当前任务范围不一致。')
    if event_id in record['event_receipts']:
        return True
    pending = record.get('pending')
    if not pending or event['revision'] != record['revision'] or event['interaction_id'] != pending['interaction_id']:
        raise TaskProtocolError('stale_interaction', '任务已变化，请刷新后重新确认。')
    if event['kind'] not in pending['host_actions']:
        raise TaskProtocolError('event_not_allowed', '当前交互不接受这项用户操作。')
    runtime.service.check_host_policy(record)
    return False


def dispatch_user_actions(runtime, limit=16):
    """A fixed STDIO-host loop delivers signed UI actions, never retries work.

    A crash after launch is recovered by recognizing the SAME event/job. No
    failed or uncertain calculation is retried by this delivery loop.
    """
    pending = runtime.directory / 'user-actions' / 'pending'
    if not io_path(pending).is_dir():
        return 0
    delivered = 0
    try:
        paths = sorted(pending.glob('*.json'))
    except (OSError, RuntimeError, ValueError):
        return 0
    for path in paths:
        if delivered >= limit:
            break
        try:
            path = safe_path(path, root=runtime.directory)
            with exclusive_lock(runtime.directory / '.dispatch.lock'):
                item = read_json(path, max_bytes=8192)[0]
                if item.get('version') != 1 or check_id(item['event_id']) != path.stem:
                    raise ValueError('Invalid user-action envelope')
                if item.get('configuration_sha256') != configuration_hash(runtime.configuration):
                    continue  # Another configured host owns this connection.
                entry = runtime._current_job(check_id(item['task_id']))
                replay = entry and entry[1]['operation'] == 'resume' and entry[1].get('event_id') == item['event_id']
                try:
                    consumed = _validate(runtime, item)
                    if not replay and not consumed:
                        runtime._ensure_idle()
                        result = runtime._launch(item['task_id'], 'resume', item['event_id'])
                        if (result.get('operation') or {}).get('status') == 'failed':
                            raise TaskProtocolError('ui_delivery_failed', '后台未能启动；已保留记录，未自动重试。')
                    item.update(state='delivered', delivered_at=time.time())
                except TaskProtocolError as error:
                    if error.code == 'mcp_busy':
                        continue
                    item.update(state='rejected', error={'code': error.code, 'message': str(error)})
                _archive(runtime, path, item)
                delivered += 1
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            # Read/delivery trouble leaves the signed action and evidence intact.
            # A malformed file never becomes authority to start a calculation.
            continue
    return delivered
