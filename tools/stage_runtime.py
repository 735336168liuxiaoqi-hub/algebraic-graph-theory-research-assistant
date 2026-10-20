"""Stage a checksum-pinned wheel in a NEW runtime; never edit host MCP settings."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat
import sys
import zipfile


LAUNCHER='''"""Pinned runtime bootstrap. No source checkout or model keys are loaded."""
from pathlib import Path
import hashlib,json,sys

root=Path(__file__).resolve().parent
receipt=json.loads((root/'runtime.json').read_text(encoding='utf-8'))
package=root/'package'
actual={}
for path in package.rglob('*'):
    if '__pycache__' in path.parts or path.suffix=='.pyc':continue
    if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:raise RuntimeError('Runtime links are not permitted')
    if path.is_file():actual[path.relative_to(package).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
if actual!=receipt['files']:raise RuntimeError('Pinned runtime changed; restore a verified release. No automatic resealing or execution.')
sys.path.insert(0,str(package))
import graph_research
from graph_research.runtime.integrity import assert_integrity
checked=assert_integrity()
if graph_research.__version__!=receipt['version']:raise RuntimeError('Runtime version mismatch')
if sys.argv[1:]==['--check']:
    from importlib.util import find_spec
    required=('numpy','networkx','sympy','jsonschema','mcp')
    missing=[name for name in required if find_spec(name) is None]
    print(json.dumps({'version':graph_research.__version__,'core_verified':checked['ok'],'files_checked':checked['files_checked'],
        'package_file':str(Path(graph_research.__file__).resolve()),'python':sys.executable,'missing_dependencies':missing,
        'model_calls':0,'state_created':False}))
    raise SystemExit(bool(missing))
from graph_research.mcp.cli import main
raise SystemExit(main(sys.argv[1:]))
'''


def regular_path(path):
    path=Path(os.path.abspath(path))
    for part in (path,*path.parents):
        if part.is_symlink() or part.exists() and getattr(part.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Runtime paths cannot pass through links/junctions')
    return path.resolve()


def valid_release_version(value):
    """A numeric release, optionally with a PEP 440 alpha/beta/rc suffix."""
    return isinstance(value,str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?',value) is not None


def stage(wheel,expected_sha256,destination,python=None):
    wheel=regular_path(wheel);destination=regular_path(destination)
    if not re.fullmatch('[0-9a-fA-F]{64}',expected_sha256):raise ValueError('Supply the SHA256 from the verified release receipt')
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!=expected_sha256.lower():raise ValueError('Wheel SHA256 does not match; no runtime created')
    if destination.exists():raise FileExistsError('Use a NEW runtime directory; an existing version is never updated in place')
    executable=regular_path(python or sys.executable)
    if not executable.is_file():raise ValueError('Choose an existing Python interpreter with the required dependencies installed')
    with zipfile.ZipFile(wheel) as archive:
        infos=archive.infolist();names=[info.filename for info in infos if not info.is_dir()]
        if len(infos)>4096 or sum(info.file_size for info in infos)>64*1024*1024:raise ValueError('Wheel exceeds runtime size limits')
        for info in infos:
            name=info.filename.rstrip('/')
            if not name or '\\' in name or ':' in name or PurePosixPath(name).is_absolute() or any(part in ('','..','.') or part.endswith((' ','.')) for part in name.split('/')) or stat.S_ISLNK(info.external_attr>>16):raise ValueError('Unsafe wheel member')
            reserved={'CON','PRN','AUX','NUL',*('COM'+str(i) for i in range(1,10)),*('LPT'+str(i) for i in range(1,10))}
            if any(ord(ch)<32 for ch in name) or any(part.split('.')[0].upper() in reserved for part in name.split('/')):raise ValueError('Reserved wheel member name')
        if len({name.casefold() for name in names})!=len(names):raise ValueError('Duplicate wheel members')
        manifest=json.loads(archive.read('graph_research/_integrity.json'))
        if manifest.get('format')!='graph-research-integrity-v1':raise ValueError('Unsupported core manifest')
        core={name[len('graph_research/'):]:hashlib.sha256(archive.read(name)).hexdigest() for name in names if name.startswith('graph_research/') and name!='graph_research/_integrity.json'}
        if core!=manifest['files']:raise ValueError('Wheel core differs from its reviewed integrity manifest')
        tree=ast.parse(archive.read('graph_research/_version.py').decode('utf-8'))
        version=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets))
        if not valid_release_version(version):raise ValueError('Invalid release version')
        destination.mkdir(parents=True,exist_ok=False);package=destination/'package';files={}
        # The receipt/launcher is written only after the complete verified copy.
        for name in names:
            target=package/PurePosixPath(name);target.parent.mkdir(parents=True,exist_ok=True)
            raw=archive.read(name)
            with target.open('xb') as stream:stream.write(raw)
            files[name]=hashlib.sha256(raw).hexdigest()
    receipt={'format':'graph-research-pinned-runtime/1','version':version,'wheel_sha256':expected_sha256.lower(),'files':files,
             'python':str(executable),'dependency_environment':'explicitly selected existing interpreter; not installed or changed by staging'}
    (destination/'runtime.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    launcher=destination/'mcp.py';launcher.write_text(LAUNCHER,encoding='utf-8')
    config={'command':str(executable),'args':['-I','-B','-X','utf8',str(launcher)]}
    (destination/'connection-template.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'version':version,'directory':str(destination),'core_files':len(core),'connection_template':config,
            'next':'Append the existing --root, --user and other MCP arguments unchanged; review before switching the host. Run mcp.py --check first.',
            'host_configuration_modified':False,'dependencies_installed':False,'service_restarted':False}


def main():
    parser=argparse.ArgumentParser(description='将已验证wheel封存为独立MCP核心；不安装依赖、不修改配置、不重启服务')
    parser.add_argument('--wheel',required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--destination',required=True)
    parser.add_argument('--python',help='运行环境的Python，需已安装相应依赖；可选专用环境')
    options=parser.parse_args();print(json.dumps(stage(options.wheel,options.sha256,options.destination,options.python),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
