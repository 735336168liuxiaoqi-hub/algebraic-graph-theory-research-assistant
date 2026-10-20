"""Additional Python-level task path and process/network restrictions.

Windows mandatory integrity and Job limits provide the OS layer. An audit hook
also narrows ordinary Python writes to the task directory, including other low
integrity locations. Audit hooks alone are not an OS security boundary.
"""
import os
from pathlib import Path
import sys
import subprocess

_installed=False


def active():
    return _installed


def install(workspace):
    global _installed
    from .storage import logical_path,io_path
    root=logical_path(io_path(workspace).resolve())
    def writable(path):
        if isinstance(path,int) or path is None:return
        from .storage import safe_path
        safe_path(os.fsdecode(path),root=root)
    def audit(event,args):
        if event=='open':
            path,mode,flags=args
            if (isinstance(mode,str) and any(ch in mode for ch in 'wax+')) or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):writable(path)
        elif event in ('os.remove','os.rmdir','os.mkdir','os.chmod','os.truncate','os.utime','os.chown'):
            writable(args[0])
        elif event in ('os.rename','os.link'):
            writable(args[0]);writable(args[1])
        elif event in ('os.symlink','os.system','os.startfile','os.posix_spawn','os.spawn','os.exec') or event.startswith('socket.'):
            raise PermissionError('Protected calculations cannot create links, access the network or launch arbitrary commands')
        elif event=='subprocess.Popen':
            executable,argv,cwd,env=args
            allowed=('graph_research.tools.elimination_worker','graph_research.tools.extension_worker')
            commands=[[sys.executable,'-m',module] for module in allowed]
            valid_argv=any(argv==command or argv==subprocess.list2cmdline(command) for command in commands)
            if not valid_argv or (executable is not None and Path(executable).resolve()!=Path(sys.executable).resolve()):
                raise PermissionError('Only fixed internal calculation workers may be launched')
    sys.addaudithook(audit)
    _installed=True
