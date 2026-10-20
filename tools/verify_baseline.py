"""Verify a frozen development baseline using only the Python standard library."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath


def verify_baseline(directory=None):
    root=Path(directory or Path(__file__).resolve().parents[1]).resolve()
    document=json.loads((root/'BASELINE.json').read_text(encoding='utf-8'))
    if document.get('format')!='graph-research-baseline-v1':raise ValueError('Unknown baseline format')
    expected=document['files']
    if not isinstance(expected,dict) or not expected:raise ValueError('Empty baseline inventory')
    for name,pin in expected.items():
        relative=PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:raise ValueError('Unsafe inventory path')
        target=root.joinpath(*relative.parts)
        for item in (target,*target.parents):
            if item==root:break
            if item.is_symlink() or (item.exists() and getattr(item.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Links in baseline')
        with target.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=pin:raise ValueError('Changed or corrupted baseline file: '+name)
    return {'ok':True,'version':document['version'],'files_checked':len(expected),'directory':str(root)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='校验封存包内的发布文件，不联网、不执行科研计算')
    parser.add_argument('directory',nargs='?');options=parser.parse_args()
    print(json.dumps(verify_baseline(options.directory),ensure_ascii=False,indent=2))
