"""Release inventories and checksum-pinned recovery into a NEW directory."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import zipfile

MANIFEST='_integrity.json'
CORE=Path(__file__).resolve().parents[1]


class IntegrityError(RuntimeError):
    """Stop task/model execution when the installed core cannot be trusted."""


def sha256(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def inventory(root):
    root=Path(root).resolve();result={}
    for path in sorted(root.rglob('*')):
        if '__pycache__' in path.parts or path.suffix=='.pyc' or path==root/MANIFEST:continue
        if path.is_symlink() or (getattr(path.lstat(),'st_file_attributes',0)&0x400):raise PermissionError('Links/junctions are not allowed in a trusted package')
        if path.is_file():result[path.relative_to(root).as_posix()]=sha256(path)
    return result


def verify(root=None):
    root=Path(root) if root is not None else CORE
    manifest=json.loads((root/MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('format')!='graph-research-integrity-v1':raise ValueError('Unknown core integrity manifest')
    expected=manifest['files'];actual=inventory(root)
    missing=sorted(set(expected)-set(actual));extra=sorted(set(actual)-set(expected))
    changed=sorted(key for key in set(expected)&set(actual) if expected[key]!=actual[key])
    return {'ok':not (missing or extra or changed),'missing':missing,'extra':extra,'changed':changed,
            'manifest_sha256':sha256(root/MANIFEST),'files_checked':len(expected),'core':str(root.resolve())}


def assert_integrity():
    try:report=verify()
    except (OSError,ValueError,TypeError,KeyError) as exc:raise IntegrityError('Core integrity check unavailable; use a verified release or maintenance recovery') from exc
    if not report['ok']:raise IntegrityError('Core integrity check failed; stop calculation and recover a verified release: '+str({k:report[k] for k in ('missing','extra','changed')}))
    return report


def backup(output,root=None):
    """Create an independent recovery archive; never overwrite an existing one."""
    from .storage import staged_file
    root=Path(root) if root is not None else CORE
    report=verify(root)
    if not report['ok']:raise RuntimeError('Cannot back up a core that failed integrity verification')
    with staged_file(output) as temporary:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            for name in [MANIFEST,*inventory(root)]:archive.write(root/name,'graph_research/'+name)
    return {'archive':str(Path(output).resolve()),'sha256':sha256(output),'manifest_sha256':report['manifest_sha256']}


def restore(archive,expected_sha256,destination):
    """Verify a user-pinned archive completely BEFORE extracting a new copy.

    Does not import recovered code, execute installers, replace a live package,
    or alter sessions, user memory, research data or extensions.
    """
    from .storage import safe_path
    destination=safe_path(destination)
    if destination.exists():raise FileExistsError('Recovery requires a new destination; existing data will not be replaced')
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64 or sha256(archive)!=expected_sha256.lower():raise ValueError('Recovery archive checksum does not match the trusted pin')
    with zipfile.ZipFile(archive) as bundle:
        infos=bundle.infolist();names=[item.filename for item in infos]
        if len(names)!=len(set(name.casefold() for name in names)) or sum(i.file_size for i in infos)>64*1024*1024:raise ValueError('Duplicate entries or oversized recovery archive')
        for item in infos:
            name=PurePosixPath(item.filename)
            if '\\' in item.filename or ':' in item.filename or name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0]!='graph_research' or (item.external_attr>>16)&0o170000==0o120000:
                raise ValueError('Unsafe recovery archive entry')
        manifest=json.loads(bundle.read('graph_research/'+MANIFEST))
        if manifest.get('format')!='graph-research-integrity-v1':raise ValueError('Unknown recovery manifest')
        expected={'graph_research/'+key:value for key,value in manifest['files'].items()}
        if set(names)!=set(expected)|{'graph_research/'+MANIFEST}:raise ValueError('Recovery inventory mismatch')
        contents={name:bundle.read(name) for name in names}
        if any(hashlib.sha256(contents[name]).hexdigest()!=value for name,value in expected.items()):raise ValueError('Recovery content failed integrity verification')
    destination.mkdir(parents=True,exist_ok=False)
    for name,value in contents.items():
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
    report=verify(destination/'graph_research')
    return {'destination':str(destination),'verified':report['ok'],'files_checked':report['files_checked']}
