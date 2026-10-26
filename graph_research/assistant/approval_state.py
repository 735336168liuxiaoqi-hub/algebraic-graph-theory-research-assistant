"""Shared native-approval visibility state, without GUI or approval authority.

MCP publishes requests; native windows publish heartbeats. These markers only
route an existing task to a window. They never sign events or start computation.
"""
import importlib.util
import os
from pathlib import Path
import time
import uuid

from graph_research.runtime.storage import read_json, safe_path, write_json
from .task_contract import check_id

REQUEST_FILE = 'approval-ui-request.json'
WINDOW_FILE = 'approval-ui-active.json'
DESKTOP_FILE = 'desktop-active.json'
HEARTBEAT_SECONDS = 12
MARKER_BYTES = 8192


def read_optional(path):
    """Read bounded advisory state; missing or corrupt markers confer no rights."""
    try:
        value = read_json(path, max_bytes=MARKER_BYTES)[0]
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def heartbeat_fresh(marker, *, now=None):
    """Use the same visibility timeout for standalone and main desktop windows."""
    now = time.time() if now is None else now
    heartbeat = marker.get('heartbeat')
    return (not marker.get('closed') and type(heartbeat) in (int, float)
            and 0 <= now - heartbeat < HEARTBEAT_SECONDS)


def write_heartbeat(directory, filename=WINDOW_FILE, *, closed=False):
    """Publish this process's visibility only; no connection or user event."""
    if filename not in (WINDOW_FILE, DESKTOP_FILE):
        raise ValueError('Unknown approval heartbeat file')
    write_json(Path(directory) / filename,
               {'pid': os.getpid(), 'heartbeat': time.time(), 'closed': closed})


def interactive_available():
    return (os.name == 'nt'
            and os.environ.get('QT_QPA_PLATFORM', '').lower() not in ('offscreen', 'minimal')
            and importlib.util.find_spec('PySide6') is not None)


def desktop_directory():
    return safe_path(Path.home() / '.graph_research/desktop-approval-bridge')


def request_window(directory, task_id=None, connection=None):
    """Request navigation to a task, without resuming or approving it."""
    item = {'version': 1, 'request_id': uuid.uuid4().hex,
            'task_id': check_id(task_id) if task_id else None, 'created_at': time.time()}
    if connection is not None:
        item['connection'] = connection
    write_json(Path(directory) / REQUEST_FILE, item)
    return item


def compatible_core(record, core_pin=None):
    """Keep native review and automatic notification on one core-pinning rule."""
    ledger = record.get('study_ledger') or record.get('experiment_ledger') or {}
    pinned = ledger.get('core_sha256')
    if not pinned:
        return True
    if core_pin is None:
        from graph_research.runtime.integrity import CORE, sha256
        core_pin = sha256(CORE / '_integrity.json')
    return pinned == core_pin
