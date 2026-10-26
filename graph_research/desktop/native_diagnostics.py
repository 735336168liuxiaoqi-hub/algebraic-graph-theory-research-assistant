"""Local native-crash/Qt diagnostics. Never reads environment credentials."""
from datetime import datetime, timezone
import faulthandler
import os
from pathlib import Path
import sys
from threading import RLock
import traceback

_stream = None
_lock = RLock()
_qt_handler = None


def note(message):
    if _stream is None or _stream.closed:
        return
    with _lock:
        try:
            _stream.write(datetime.now(timezone.utc).isoformat() + ' pid='+str(os.getpid())+' ' + message + '\n'); _stream.flush()
        except (OSError,ValueError):pass


def install(path=None):
    global _stream,_qt_handler
    if _stream is not None:
        return
    path = Path(path or Path.home() / '.graph_research/logs/desktop.log')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _stream = path.open('a', encoding='utf-8', buffering=1)
    except (OSError,ValueError):
        import tempfile,os
        try:
            fallback=Path(tempfile.gettempdir())/('graph-research-desktop-'+str(os.getpid())+'.log')
            _stream=fallback.open('a',encoding='utf-8',buffering=1)
        except (OSError,ValueError):return  # Diagnostics must never close a usable window.
    try:
        faulthandler.enable(_stream, all_threads=True)
    except (OSError, RuntimeError):
        pass
    from PySide6.QtCore import qInstallMessageHandler
    def qt_message(kind, context, message):
        note('Qt ' + str(kind) + ': ' + message)
    _qt_handler=qt_message;qInstallMessageHandler(_qt_handler)
    def exception(kind, value, tb):
        with _lock:
            traceback.print_exception(kind, value, tb, file=_stream); _stream.flush()
    sys.excepthook = exception
    note('desktop process started')
