"""Safe paths, no-clobber exports, atomic state writes and crash recovery."""
from contextlib import contextmanager
import errno
import json
import os
import re
from pathlib import Path
import stat
import tempfile
import time
from graph_research.errors import PathBoundaryError,PathLengthError,SessionBusyError
from .observability import error_details

CORE=Path(__file__).resolve().parents[1]


def logical_path(path):
    """One absolute spelling for guards/records; Windows device aliases rejected."""
    text=os.fsdecode(os.fspath(path))
    if os.name=='nt':
        text=text.replace('/','\\')
        if text.upper().startswith('\\\\?\\UNC\\'):text='\\\\'+text[8:]
        elif text.startswith('\\\\?\\'):
            if not re.match(r'^[A-Za-z]:\\',text[4:]):raise PathBoundaryError('Only drive and UNC file paths are supported')
            text=text[4:]
        elif text.startswith(('\\\\.\\','\\??\\')):raise PathBoundaryError('Windows device namespaces are not file export paths')
    return Path(os.path.abspath(text))


def io_path(path):
    """Native I/O spelling, not an authorization. Validate writes with safe_path."""
    path=logical_path(path)
    if os.name!='nt':return path
    text=str(path)
    if len(text.encode('utf-16-le'))//2>=32760:raise PathLengthError('Windows extended path limit exceeded')
    return Path('\\\\?\\UNC\\'+text[2:] if text.startswith('\\\\') else '\\\\?\\'+text)


def storage_error(error,phase):
    """Small stable diagnostics; no arbitrary host paths or credentials."""
    number=getattr(error,'winerror',None)
    if isinstance(error,PathLengthError) or number==206 or getattr(error,'errno',None)==errno.ENAMETOOLONG:code='path_too_long';retry=False
    elif isinstance(error,PathBoundaryError):code='sandbox_violation';retry=False
    elif isinstance(error,SessionBusyError):code='host_busy';retry=True
    elif isinstance(error,FileExistsError):code='output_exists';retry=False
    elif isinstance(error,PermissionError) and number not in (32,33):code='io_permission_denied';retry=False
    elif number in (32,33):code='io_temporarily_unavailable';retry=True
    elif isinstance(error,FileNotFoundError):code='io_path_missing';retry=False
    else:code='io_error';retry=False
    return {'code':code,'retryable':retry,'type':type(error).__name__,**error_details(error,phase=phase)}


def _sharing_retry(operation):
    """Retry an identical IO operation only, never a producer or calculation.

    Windows can report access denied (5), sharing (32), or lock (33) violations
    while a reader/antivirus briefly holds a destination. Persistent denial
    still fails; no permissions are changed and no-clobber is preserved.
    """
    for attempt in range(10):
        try:return operation()
        except OSError as error:
            if os.name!='nt' or getattr(error,'winerror',None) not in (5,32,33) or attempt==9:raise
            time.sleep(min(.01*(attempt+1),.05))


class StateRecoveryError(ValueError):
    """The original state is unreadable and no valid backup can be recovered."""
    def __init__(self,path,primary_error,backup_error):
        self.path=Path(path);self.primary_error=type(primary_error).__name__;self.backup_error=type(backup_error).__name__
        super().__init__(f'状态文件损坏或无法读取，且没有可用备份：{self.path}。原文件已保留，请检查文件或选择其他会话。')


def safe_path(path,*,root=None):
    """Reject package writes, links/junctions and optional task-root escapes."""
    original=logical_path(path)
    for part in (original,*original.parents):
        try:info=io_path(part).lstat()
        except (FileNotFoundError,NotADirectoryError):continue
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):
            raise PathBoundaryError('Writes through symbolic links or junctions are not allowed')
    resolved=logical_path(io_path(original).resolve())
    core=logical_path(io_path(CORE).resolve())
    if resolved==core or resolved.is_relative_to(core):raise PathBoundaryError('The base package is protected from writes')
    if root is not None and not resolved.is_relative_to(logical_path(io_path(root).resolve())):raise PathBoundaryError('Write path escaped its task directory')
    return resolved


@contextmanager
def staged_file(path,*,overwrite=False,root=None):
    """Publish only a complete file. Existing outputs need explicit overwrite."""
    target=safe_path(path,root=root)
    native=io_path(target)
    if native.exists() and not overwrite:raise FileExistsError('Output exists; choose a new path or explicitly enable overwrite')
    io_path(target.parent).mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.gr-',suffix=target.suffix,dir=io_path(target.parent))
    os.close(fd);temporary=Path(name)
    try:
        yield temporary
        with temporary.open('r+b') as stream:os.fsync(stream.fileno())
        def publish():
            safe_path(target,root=root);safe_path(temporary,root=target.parent)
            if overwrite:os.replace(temporary,native)
            else:
                # Exclusive link retains no-clobber semantics on every attempt.
                os.link(temporary,native)
        _sharing_retry(publish)
    finally:
        # Best-effort cleanup: an antivirus hold must not mask the real
        # outcome; the runner sweeps leftover staged temps after the worker.
        try:_sharing_retry(lambda:temporary.unlink(missing_ok=True))
        except OSError:pass


def atomic_text(path,text,*,overwrite=False,root=None):
    # Retry only when an already-created temporary vanished while its directory
    # remains. A creation failure/missing parent is not evidence of antivirus.
    for attempt in range(6):
        created=None
        try:
            with staged_file(path,overwrite=overwrite,root=root) as temporary:
                created=temporary
                temporary.write_text(text,encoding='utf-8')
            return safe_path(path,root=root)
        except FileNotFoundError:
            if attempt==5 or created is None or not io_path(created.parent).is_dir() or io_path(created).exists():raise
            time.sleep(min(.05*(attempt+1),.25))


def write_json(path,value,*,backup=False):
    text=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
    target=safe_path(path)
    if backup and io_path(target).is_file():
        try:
            previous=io_path(target).read_text(encoding='utf-8');json.loads(previous)
        except (ValueError,OSError):pass
        else:atomic_text(target.with_name(target.name+'.previous'),previous,overwrite=True)
    atomic_text(target,text,overwrite=True)


def read_json(path,*,recover=False,max_bytes=16*1024*1024):
    """Recover ordinary session state only; authorization must always fail closed."""
    path=logical_path(path)
    def read(candidate):
        candidate=io_path(candidate)
        if candidate.stat().st_size>max_bytes:raise ValueError('State file exceeds size limit')
        return json.loads(candidate.read_text(encoding='utf-8'))
    try:return read(path),False
    except (ValueError,OSError) as primary_error:
        if not recover:raise
        try:return read(path.with_name(path.name+'.previous')),True
        except (ValueError,OSError) as backup_error:
            raise StateRecoveryError(path,primary_error,backup_error) from primary_error


@contextmanager
def exclusive_lock(path):
    """Nonblocking cross-process lock; OS releases it after a process crash."""
    path=safe_path(path);io_path(path.parent).mkdir(parents=True,exist_ok=True)
    with io_path(path).open('a+b') as stream:
        if stream.tell()==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:raise SessionBusyError('This session or approval is in use; retry after it finishes') from exc
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)
