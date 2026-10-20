"""Fixed diagnostics, called only by the trusted host; never a model tool."""
import ctypes
import os
from pathlib import Path
import time


def execute(request):
    operation=request['operation']
    if operation=='echo':
        # Side-effect-free roundtrip: proves the protected bootstrap, guard and
        # integrity checks all work, without touching the tool registry.
        return {'echo':request.get('payload'),'pid':os.getpid()}
    if operation=='guard_write':
        from graph_research.errors import PathBoundaryError
        try:Path(request['path']).write_text('guard diagnostic',encoding='utf-8')
        except PathBoundaryError:return {'write_denied_by_guard':True,'code':'sandbox_violation'}
        return {'write_denied_by_guard':False}
    if operation=='native_write':
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        handle=kernel.CreateFileW(str(Path(request['path'])),0x40000000,0,None,3,0,None)
        denied=handle==ctypes.c_void_p(-1).value
        if not denied:
            kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle(handle)
        return {'write_denied_by_os':denied,'error':ctypes.get_last_error() if denied else 0}
    if operation=='sleep':
        Path('started').write_text('yes');time.sleep(60);return {'completed':True}
    if operation=='memory':
        try:
            data=bytearray(256*1024*1024)
            return {'allocation_denied':False,'bytes':len(data)}
        except MemoryError:return {'allocation_denied':True}
    raise ValueError('Unknown diagnostic')
