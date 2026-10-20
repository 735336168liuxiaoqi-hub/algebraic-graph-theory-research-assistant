"""One declared module selection and hash-bound list of actual unittest IDs."""
import ast
import hashlib
import json
from pathlib import Path
import platform
import sys
import unittest


def module_sets(root):
    root=Path(root)
    gates=json.loads((root/'tests/gates.json').read_text(encoding='utf-8'))
    fast=list(gates['fast']);full=list(gates['full']);top=list(gates.get('root',[]))
    discovered=sorted('.'.join(p.relative_to(root/'tests').with_suffix('').parts) for p in (root/'tests').rglob('test_*.py') if '__pycache__' not in p.parts)
    if sorted(set(fast)|set(full))!=discovered or not set(fast)<=set(full):
        raise ValueError('tests/gates.json与tests/模块不一致；新增模块必须登记，不能漏测')
    if sorted(top)!=sorted(p.stem for p in root.glob('test_*.py')):
        raise ValueError('tests/gates.json的root清单与根目录测试不一致')
    for group in (fast,full,top):
        if len(group)!=len(set(group)):raise ValueError('测试模块清单包含重复项')
    return fast,full,top


def source_files(root):
    root=Path(root);files=set()
    for folder in ('graph_research','tests','tools'):
        for path in (root/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pyo'):files.add(path)
    files.update(root.glob('*.py'))
    files.update(p for name in ('pyproject.toml','requirements-lock.txt','requirements-dev.txt','.github/workflows/checks.yml') if (p:=root/name).is_file())
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()


def collect(root,profile='full'):
    root=Path(root).resolve();fast,full,top=module_sets(root)
    if profile not in ('fast','full'):raise ValueError('Unknown test profile')
    modules=['tests.'+name for name in (full if profile=='full' else fast)]+top
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    before=source_files(root);loader=unittest.TestLoader();suite=loader.loadTestsFromNames(modules)
    if loader.errors:raise ValueError('测试收集失败：\n'+'\n'.join(loader.errors))
    for name in modules:
        expected=root.joinpath(*name.split('.')).with_suffix('.py').resolve()
        actual=Path(sys.modules[name].__file__).resolve()
        if actual!=expected:raise ValueError('测试模块从其他项目加载：'+name)
    pending=[suite];ids=[];counts={}
    while pending:
        item=pending.pop()
        if isinstance(item,unittest.TestSuite):pending.extend(reversed(list(item)))
        else:
            ids.append(item.id());name=item.__class__.__module__;counts[name]=counts.get(name,0)+1
    if len(ids)!=len(set(ids)):raise ValueError('重复的测试ID，拒绝按重复次数报告通过数量')
    after=source_files(root)
    if before!=after:raise ValueError('测试收集期间源码变化，不能生成稳定验收清单')
    version=None;version_file=root/'graph_research/_version.py'
    if version_file.is_file():
        for node in ast.parse(version_file.read_text(encoding='utf-8')).body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets):version=ast.literal_eval(node.value)
    core=root/'graph_research/_integrity.json'
    document={'format':'graph-research-test-inventory/1','profile':profile,'version':version,
              'python':sys.executable,'python_version':platform.python_version(),'platform':sys.platform,
              'modules':modules,'module_counts':dict(sorted(counts.items())),'test_ids':ids,'collected_tests':len(ids),
              'tests_directory_count':sum(v for k,v in counts.items() if k.startswith('tests.')),
              'root_count':sum(v for k,v in counts.items() if not k.startswith('tests.')),
              'test_ids_sha256':fingerprint(ids),'source_files':after,'source_sha256':fingerprint(after),
              'core_manifest_sha256':hashlib.sha256(core.read_bytes()).hexdigest() if core.is_file() else None}
    return suite,document
