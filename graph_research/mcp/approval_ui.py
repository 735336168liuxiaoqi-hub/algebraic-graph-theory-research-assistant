"""Automatic native approval visibility, with no approval authority."""
import os
from pathlib import Path
import re
import subprocess
import sys

from graph_research.runtime.storage import safe_path, write_json, exclusive_lock
# Re-export the original helper names for existing host integrations.
from graph_research.assistant.approval_state import (
    WINDOW_FILE, DESKTOP_FILE, compatible_core, desktop_directory,
    heartbeat_fresh, interactive_available, read_optional, request_window,
)


class ApprovalNotifier:
    def __init__(self, runtime,*,desktop_bridge=None):
        self.runtime = runtime; self.child = None;self.desktop=Path(desktop_bridge) if desktop_bridge is not None else desktop_directory()

    def notify(self):
        runtime = self.runtime
        if runtime.configuration.approval_ui != 'auto' or not interactive_available():
            return None
        candidates = [row for row in runtime.list_tasks(limit=30)['tasks'] if row['status'] in ('waiting_for_user', 'waiting_for_approval', 'interrupted')]
        if not candidates:
            return None
        row = candidates[0]; record = runtime.service.read(row['task_id']); pending = record.get('pending')
        if not pending:
            return None
        if not compatible_core(record):return None
        directory = runtime.directory
        with exclusive_lock(directory / '.approval-ui.lock'):
            previous = read_optional(directory / 'approval-ui-notified.json')
            active = read_optional(directory / WINDOW_FILE)
            desktop=read_optional(self.desktop/DESKTOP_FILE)
            desktop_fresh=heartbeat_fresh(desktop)
            same=previous.get('interaction_id')==pending['interaction_id']
            fresh=heartbeat_fresh(active)
            if same:
                unexpected=not active.get('closed') and not fresh and previous.get('state') in ('launched','starting','reused')
                stopped=self.child is None or self.child.poll() is not None
                desktop_recovered=desktop_fresh and previous.get('desktop_pid')!=desktop.get('pid')
                if not (desktop_recovered or unexpected and stopped and previous.get('launch_attempts',1)<2):return None
            if row['updated_at'] < previous.get('updated_at', ''):return None
            marker = {'version': 1, 'task_id': row['task_id'], 'interaction_id': pending['interaction_id'], 'updated_at': row['updated_at']}
            marker['launch_attempts']=previous.get('launch_attempts',0)+1 if same else 1
            request_window(directory, row['task_id'])
            if desktop_fresh:
                request_window(self.desktop,row['task_id'],{'root':runtime.configuration.root,'user_id':runtime.configuration.user_id})
                marker.update(state='reused_desktop',desktop_pid=desktop['pid'])
            elif fresh:
                marker['state'] = 'reused'
            elif self.child is not None and self.child.poll() is None:
                marker['state'] = 'starting'
            else:
                executable = Path(sys.executable)
                gui = executable.with_name('pythonw.exe')
                if gui.is_file():executable = gui
                environment = {k: v for k, v in os.environ.items() if not re.search(r'KEY|SECRET|TOKEN|PASSWORD', k, re.I)}
                log = safe_path(directory / 'approval-ui-bootstrap.log', root=directory)
                try:
                    with log.open('ab') as stream:
                        self.child = subprocess.Popen([str(executable), '-I', '-B', '-X', 'utf8', '-m', 'graph_research', 'approvals',
                            '--root', runtime.configuration.root, '--user', runtime.configuration.user_id, '--task', row['task_id']],
                            stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, env=environment,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), close_fds=True)
                    marker.update(state='launched', pid=self.child.pid)
                except OSError as error:
                    marker.update(state='failed', error_type=type(error).__name__)
            write_json(directory / 'approval-ui-notified.json', marker)
            return marker
