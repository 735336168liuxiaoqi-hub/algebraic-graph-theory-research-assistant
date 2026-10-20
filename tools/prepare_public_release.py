"""Export a clean, local source candidate without private history or user state."""
import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import re
import zipfile

PROJECT_NAME='algebraic-graph-theory-research-assistant'
ROOT_FILES={'.gitattributes','.gitignore','pyproject.toml','requirements.txt','requirements-lock.txt','requirements-dev.txt',
            'assistant.py','test_workflow.py','run-demo.ps1','check.cmd','start-assistant.cmd','start-desktop.cmd',
            'start-offline.cmd','algebraic graph theory research assistant.exe'}
ROOT_DOCS={'README.md','使用指南.md','CONTRIBUTING.md','NOTICE.md','LICENSE','LICENSE-STATUS.md'}
FOLDERS=('graph_research','tests','tools','docs','examples','.github','.githooks')
PRIVATE_COMPONENTS={'.git','.venv','__pycache__','outputs','tmp','dist','tool_packages','user_memory','legacy_sage'}
EXTERNAL_TEMPLATES={'tasks.json','report-template.json','assistant-prompt.md','baseline-prompt.md'}


def selected_files(root):
    root=Path(root).resolve();result={}
    for name in sorted(ROOT_FILES|ROOT_DOCS):
        path=root/name
        if path.is_file():result[name]=path
    for folder in FOLDERS:
        for path in (root/folder).rglob('*'):
            relative=path.relative_to(root)
            if any(p in PRIVATE_COMPONENTS for p in relative.parts) or path.suffix in ('.pyc','.pyo'):continue
            # Personal study scripts are not application distribution tools.
            if folder=='tools' and (path.name.startswith('refactor_') or path.name in {'prepare_native_workflow.py','power_check_paired.py'}):continue
            if folder=='examples' and len(relative.parts)>1 and relative.parts[1]=='external_v0351':
                if len(relative.parts)!=3 or path.name not in EXTERNAL_TEMPLATES:continue
            if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:
                raise ValueError('Source export refuses links: '+str(relative))
            if path.is_file():result[relative.as_posix()]=path
    for name,path in result.items():
        if not path.resolve().is_relative_to(root):raise ValueError('File escaped source root: '+name)
        for ancestor in (path,*path.parents):
            if ancestor==root:break
            if ancestor.is_symlink() or getattr(ancestor.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Linked source ancestor: '+name)
    return result


def _markdown(data,name,selected):
    text=data.decode('utf-8-sig')
    # Internal progress links are not useful in a self-contained public source.
    def link(match):
        label,target=match.groups();bare=target.split('#',1)[0]
        if not bare or re.match(r'^[a-z]+:',bare,re.I) or bare.startswith(('/', '#')):return match.group(0)
        resolved=posixpath.normpath((Path(name).parent/bare).as_posix())
        if bare.endswith('.md') and resolved not in selected:return label+'（历史开发记录）'
        return match.group(0)
    text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,text)
    text=re.sub(r'[A-Z]:[/\\]Users[/\\][^/\\\r\n`"<>]+(?:[/\\][^\s`"<>]*)?', '<LOCAL_PATH>', text, flags=re.I)
    return text.encode('utf-8')


def prepare(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    if output.exists():raise FileExistsError('Choose a new candidate directory: '+str(output))
    if output==root or output.is_relative_to(root/'graph_research'):raise ValueError('Candidate cannot replace source')
    output.mkdir(parents=True)
    version_file=(root/'graph_research/_version.py').read_text(encoding='utf-8')
    version=re.search(r'__version__\s*=\s*["\']([^"\']+)',version_file).group(1)
    source=output/(PROJECT_NAME+'-'+version);source.mkdir()
    selected=selected_files(root);hashes={}
    for name,path in sorted(selected.items()):
        data=path.read_bytes()
        if path.suffix=='.md' and not name.startswith('graph_research/'):
            data=_markdown(data,name,selected)
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    rights=json.loads((source/'docs/provenance/rights-status.json').read_text(encoding='utf-8'))
    manifest={'format':'algebraic-graph-theory-source/1','version':version,'project':PROJECT_NAME,
              'publication_status':rights['status'],'private_history_included':False,'files':hashes}
    (source/'SOURCE_MANIFEST.json').write_bytes(json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    archive=output/(PROJECT_NAME+'-'+version+'-source-candidate.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(source.rglob('*')):
            if path.is_file():bundle.write(path,(source.name+'/'+path.relative_to(source).as_posix()))
    with zipfile.ZipFile(archive) as bundle:
        for name,digest in hashes.items():
            if hashlib.sha256(bundle.read(source.name+'/'+name)).hexdigest()!=digest:raise ValueError('Archive verification failed: '+name)
    result={'source_directory':str(source),'source_archive':str(archive),'version':version,'files_verified':len(hashes),
            'source_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'publication_status':rights['status'],'public_upload_performed':False}
    (output/'candidate.json').write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8'))
    return result


def main(arguments=None):
    parser=argparse.ArgumentParser(description='Create a local source candidate; never publishes or copies private Git history')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--root',default=Path(__file__).resolve().parents[1],type=Path)
    args=parser.parse_args(arguments);print(json.dumps(prepare(args.root,args.output),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
