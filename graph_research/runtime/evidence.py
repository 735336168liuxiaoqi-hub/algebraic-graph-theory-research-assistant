"""Host-created execution evidence for portable scientific result snapshots."""
import hashlib
from importlib.metadata import version,PackageNotFoundError
from pathlib import Path
import platform

from .storage import safe_path,io_path,logical_path


def file_hash(path):
    with io_path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def environment_info():
    from graph_research import __version__
    libraries={}
    for name in ('numpy','networkx','sympy','matplotlib','jsonschema','langgraph'):
        try:libraries[name]=version(name)
        except PackageNotFoundError:pass
    return {'package_version':__version__,'python':platform.python_version(),'platform':platform.system(),'libraries':libraries}


def output_inventory(workspace):
    """Only generated scientific outputs, never temp/cache/config or credentials."""
    root=logical_path(workspace);outputs=io_path(root/'outputs');result=[]
    if not outputs.exists():return result
    for path in sorted(outputs.rglob('*')):
        safe_path(path,root=root)
        if path.name.startswith('.gr-'):continue  # Unpublished atomic staging files are never scientific artifacts.
        if path.is_file():
            result.append({'path':logical_path(path).relative_to(root).as_posix(),'bytes':path.stat().st_size,'sha256':file_hash(path)})
    return result
