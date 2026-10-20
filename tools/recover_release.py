"""Standalone recovery: does not import or execute the damaged package.

Keep this maintenance utility and the printed archive SHA256 with your backup.
Always recover to a new directory, then review/switch runtimes separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import zipfile


def recover(archive,pin,destination):
    original=Path(os.path.abspath(destination))
    if original.exists():raise FileExistsError('Destination already exists; choose a new directory')
    for parent in original.parents:
        if parent.exists() and (parent.is_symlink() or getattr(parent.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Recovery path cannot pass through links or junctions')
    with Path(archive).open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if len(pin)!=64 or actual!=pin.lower():raise ValueError('Archive differs from the trusted SHA256')
    with zipfile.ZipFile(archive) as bundle:
        infos=bundle.infolist();names=[i.filename for i in infos]
        if len(names)!=len({n.casefold() for n in names}) or sum(i.file_size for i in infos)>64*1024*1024:raise ValueError('Duplicate or oversized entries')
        for info in infos:
            path=PurePosixPath(info.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename or not path.parts or path.parts[0]!='graph_research' or (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe archive path')
        contents={name:bundle.read(name) for name in names}
        manifest=json.loads(contents['graph_research/_integrity.json'])
        if manifest.get('format')!='graph-research-integrity-v1':raise ValueError('Unknown manifest')
        expected={'graph_research/'+name:value for name,value in manifest['files'].items()}
        if set(contents)!=set(expected)|{'graph_research/_integrity.json'}:raise ValueError('Inventory mismatch')
        if any(hashlib.sha256(contents[name]).hexdigest()!=value for name,value in expected.items()):raise ValueError('Invalid package content hash')
    original.mkdir(parents=True,exist_ok=False)
    for name,data in contents.items():
        target=original/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(data)
    return {'destination':str(original),'verified':True,'archive_sha256':actual,'files':len(contents)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='不导入损坏包的独立恢复工具；只写入全新目录')
    parser.add_argument('archive');parser.add_argument('--sha256',required=True);parser.add_argument('--destination',required=True)
    args=parser.parse_args()
    print(json.dumps(recover(args.archive,args.sha256,args.destination),ensure_ascii=False,indent=2))
