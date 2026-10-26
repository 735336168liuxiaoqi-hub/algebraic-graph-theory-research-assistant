"""Reuse a normal user-session desktop without detaching from host jobs."""
import os
from PySide6.QtCore import QObject,QTimer,Slot
from graph_research.assistant.approval_state import (
    DESKTOP_FILE, REQUEST_FILE, desktop_directory, heartbeat_fresh,
    interactive_available, read_optional, write_heartbeat,
)


class DesktopApprovalBridge(QObject):
    def __init__(self,window,*,directory=None):
        super().__init__(window);self.window=window;self.directory=directory or desktop_directory()
        self.seen=read_optional(self.directory/REQUEST_FILE).get('request_id');self.registered=False
        self.timer=QTimer(self);self.timer.setInterval(1500);self.timer.timeout.connect(self.poll)
        self.timer.start();self.poll()

    @Slot()
    def poll(self):
        if not interactive_available() or not self.window.isVisible():return
        try:
            active=read_optional(self.directory/DESKTOP_FILE)
            if active.get('pid')!=os.getpid() and heartbeat_fresh(active):
                self.registered=False;return
            write_heartbeat(self.directory, DESKTOP_FILE)
            self.registered=True
            request=read_optional(self.directory/REQUEST_FILE)
            if request.get('request_id') and request['request_id']!=self.seen:
                connection=request.get('connection') or {}
                if self.window.open_approval_request(connection.get('root'),connection.get('user_id'),request.get('task_id')):
                    self.seen=request['request_id']
        except (OSError,RuntimeError,ValueError,TypeError):pass

    def shutdown(self):
        self.timer.stop()
        if not self.registered:return
        try:
            if read_optional(self.directory/DESKTOP_FILE).get('pid')==os.getpid():
                write_heartbeat(self.directory, DESKTOP_FILE, closed=True)
        except (OSError,RuntimeError,ValueError):pass
