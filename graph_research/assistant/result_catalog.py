"""Local result collections and immutable ZIP versions, indexed by stable IDs.

Only host-published exports enter the catalog. Scientific execution records stay
in their original session; automatic retention never removes that evidence.
"""
from contextlib import contextmanager,ExitStack
import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
import uuid

from graph_research.runtime.storage import safe_path,read_json,write_json,staged_file,exclusive_lock
from graph_research.runtime.evidence import file_hash


def safe_name(value,default='未分类',maximum=32):
    text=re.sub(r'[<>:"/\\|?*\x00-\x1f]',' ',str(value));text=' '.join(text.split()).strip(' .')[:maximum].strip(' .') or default
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?',text):text='_'+text
    return text


def default_results_directory():
    """Use Windows' actual Documents known folder, including redirection."""
    if os.environ.get('RESEARCH_RESULTS_HOME'):return safe_path(Path(os.environ['RESEARCH_RESULTS_HOME']).expanduser())
    documents=Path.home()/'Documents'
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        class GUID(ctypes.Structure):
            _fields_=[('a',wintypes.DWORD),('b',wintypes.WORD),('c',wintypes.WORD),('d',ctypes.c_ubyte*8)]
        identifier=GUID.from_buffer_copy(uuid.UUID('fdd39ad0-238f-46af-adb4-6c85480369c7').bytes_le);pointer=ctypes.c_wchar_p()
        try:
            status=ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(identifier),0,None,ctypes.byref(pointer))
            if status==0:documents=Path(pointer.value)
        finally:
            if pointer:ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(pointer,ctypes.c_void_p))
    return safe_path(documents/'图论科研助手'/'成果')


class ResultPreferences:
    """Public directory preferences; changing location applies to new sessions."""
    def __init__(self,path=None,default_root=None):
        self.path=safe_path(path or Path.home()/'.graph_research'/'results.json')
        self.default_root=safe_path(default_root or default_results_directory())

    def read(self):
        if not self.path.exists():return {'version':1,'active':str(self.default_root),'roots':[str(self.default_root)]}
        value,_=read_json(self.path,max_bytes=32768)
        if not isinstance(value,dict) or set(value)!={'version','active','roots'} or value['version']!=1 or not isinstance(value['roots'],list) or len(value['roots'])>100:
            raise ValueError('成果目录配置无效，原文件已保留。')
        roots=list(dict.fromkeys(str(safe_path(p)) for p in value['roots']));active=str(safe_path(value['active']))
        if active not in roots:raise ValueError('当前成果目录不在已登记目录中。')
        return {'version':1,'active':active,'roots':roots}

    @property
    def active(self):return Path(self.read()['active'])

    def select(self,root):
        root=str(safe_path(root))
        with exclusive_lock(self.path.with_suffix('.lock')):
            value=self.read();value['active']=root
            if root not in value['roots']:value['roots'].append(root)
            if len(value['roots'])>100:raise ValueError('登记目录已达100个，请整理配置后再添加。')
            write_json(self.path,value,backup=self.path.exists())
        return Path(root)

    def remember(self,root):
        root=str(safe_path(root))
        with exclusive_lock(self.path.with_suffix('.lock')):
            value=self.read()
            if root not in value['roots']:
                if len(value['roots'])>=100:raise ValueError('登记目录已达100个，请整理配置后再添加。')
                value['roots'].append(root);write_json(self.path,value,backup=self.path.exists())


class ResultCatalog:
    """A catalog belongs to one local result directory, never to a model tool."""
    def __init__(self,root):
        self.root=safe_path(root);self.management=safe_path(self.root/'.管理',root=self.root);self.database=safe_path(self.management/'index.sqlite3',root=self.root)

    @contextmanager
    def connect(self):
        self.management.mkdir(parents=True,exist_ok=True)
        safe_path(self.database,root=self.root)
        connection=sqlite3.connect(self.database,timeout=10);connection.row_factory=sqlite3.Row
        try:
            if connection.execute('PRAGMA user_version').fetchone()[0] not in (0,1):raise ValueError('成果索引版本不受支持，原文件已保留。')
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, directory TEXT UNIQUE NOT NULL, mode TEXT NOT NULL,
                  title TEXT NOT NULL, project TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, latest TEXT, state TEXT NOT NULL DEFAULT 'ready', updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, source_id TEXT NOT NULL, kind TEXT NOT NULL, path TEXT NOT NULL,
                  sha256 TEXT, bytes INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL, fingerprint TEXT, bundle TEXT, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS aliases(path TEXT NOT NULL, sha256 TEXT NOT NULL, source_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
                  PRIMARY KEY(path,sha256,source_id));
                CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, state TEXT NOT NULL, created REAL NOT NULL, data TEXT NOT NULL);
                PRAGMA user_version=1;
            ''')
            with connection:yield connection
        finally:connection.close()

    def source(self,identifier):
        with self.connect() as db:row=db.execute('SELECT * FROM sources WHERE id=?',(identifier,)).fetchone()
        if row is None:raise ValueError('没有该成果集合。')
        return dict(row)

    def artifact(self,identifier):
        with self.connect() as db:row=db.execute('SELECT * FROM artifacts WHERE id=?',(identifier,)).fetchone()
        if row is None:raise ValueError('没有该成果版本。')
        return dict(row)

    def _bundle(self,row):
        bundle=json.loads(row['bundle']) if row.get('bundle') else {}
        source=self.source(row['source_id'])
        bundle.update(archive=row['path'],artifact_id=row['id'],result_id=row['source_id'],results_root=str(self.root),
            result_name=source['title'],project=source['project'],availability=row['state'],automatic=row['kind']=='auto')
        if row['state']=='ready':bundle['sha256_file']=str(row['path'])+'.sha256' if Path(str(row['path'])+'.sha256').is_file() else None
        return bundle

    def resolve(self,identifier,*,source_directory=None,expected_sha256=None):
        row=self.artifact(identifier);source=self.source(row['source_id'])
        if source_directory is not None and safe_path(source['directory'])!=safe_path(source_directory):raise ValueError('成果不属于该计算会话。')
        if expected_sha256 is not None and row['sha256']!=expected_sha256:raise ValueError('成果索引与原始摘要不一致。')
        target=safe_path(row['path'],root=self.root)
        value=self._bundle(row)
        if row['state']=='ready' and not target.is_file():value['availability']='missing'
        return value

    def find_alias(self,path,sha256,source_directory):
        with self.connect() as db:
            row=db.execute('SELECT a.artifact_id FROM aliases a JOIN sources s ON a.source_id=s.id WHERE a.path=? AND a.sha256=? AND s.directory=?',
                (str(Path(path).resolve()),sha256,str(safe_path(source_directory)))).fetchone()
        return self.resolve(row[0],source_directory=source_directory,expected_sha256=sha256) if row else None

    def reserve(self,session,*,automatic=False):
        identifier=uuid.uuid4().hex;source_id=session.session_id
        if not re.fullmatch(r'[0-9a-f]{32}',source_id):raise ValueError('会话编号无效。')
        mode=getattr(session,'results_mode','api');title=safe_name(session.state.get('question') or '科研成果',default='科研成果',maximum=26)
        if mode=='offline' and session.state.get('observations'):
            from graph_research.rendering.results import TITLES
            first=next((o for o in session.state['observations'] if o.get('tool')),None)
            if first:title=TITLES.get(first['tool'],title)
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO sources(id,directory,mode,title,project,updated) VALUES(?,?,?,?,?,?)',
                (source_id,str(session.directory),mode,title,'未分类',time.time()))
            source=db.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone()
            if source['directory']!=str(session.directory) or source['state']=='cleared':raise ValueError('成果集合已清理或会话位置不一致。')
            folder=safe_path(self.root/safe_name(source['project']),root=self.root)
            marker='自动成果' if automatic else '快照'
            path=safe_path(folder/(datetime.now().strftime('%Y-%m-%d')+'_'+safe_name(source['title'],maximum=26)+'_'+marker+'_'+identifier[:6]+'.zip'),root=self.root)
            if path.exists():raise FileExistsError('成果名称冲突，请重试导出。')
            db.execute('INSERT INTO artifacts(id,source_id,kind,path,state,created) VALUES(?,?,?,?,?,?)',(identifier,source_id,'auto' if automatic else 'snapshot',str(path),'preparing',time.time()))
        return identifier,path

    def publish(self,identifier,bundle,*,fingerprint=None):
        from .results import verify_bundle
        row=self.artifact(identifier);target=safe_path(row['path'],root=self.root)
        if Path(bundle['archive']).resolve()!=target:raise ValueError('成果发布位置与登记位置不一致。')
        verify_bundle(target,bundle['sha256'])
        with self.connect() as db:
            db.execute('UPDATE artifacts SET sha256=?,bytes=?,state=?,fingerprint=?,bundle=? WHERE id=?',
                (bundle['sha256'],target.stat().st_size,'ready',fingerprint,json.dumps(bundle,ensure_ascii=False),identifier))
            db.execute('INSERT OR REPLACE INTO aliases VALUES(?,?,?,?)',(str(target),bundle['sha256'],row['source_id'],identifier))
            db.execute('UPDATE sources SET latest=?,updated=? WHERE id=?',(identifier,time.time(),row['source_id']))
        return self.resolve(identifier)

    def reusable(self,source_id,fingerprint):
        from .results import verify_bundle
        with self.connect() as db:
            row=db.execute("SELECT * FROM artifacts WHERE source_id=? AND kind='auto' AND state='ready' AND fingerprint=? ORDER BY created DESC LIMIT 1",(source_id,fingerprint)).fetchone()
        if row:
            try:
                bundle=self.resolve(row['id']);verify_bundle(bundle['archive'],bundle['sha256']);return bundle
            except (OSError,ValueError):pass
        return None

    def pinned_by_receipt(self,source,sha256):
        task=Path(source['directory']).parent/'task.json'
        if source['mode']!='mcp' or not task.is_file():return False
        record,_=read_json(task,max_bytes=2*1024*1024)
        references=[record.get('response'),*record.get('response_history',[]),*[r for r in record.get('event_receipts',{}).values() if r.get('state')=='complete']]
        for reference in references:
            if not reference or not reference.get('path'):continue
            path=safe_path(task.parent/reference['path'],root=task.parent)
            if file_hash(path)!=reference['sha256']:raise ValueError('宿主回执快照已变化，拒绝自动清理。')
            response,_=read_json(path,max_bytes=2*1024*1024)
            if any(a.get('sha256')==sha256 for a in response.get('artifacts',[])):return True
        return False

    def prune_automatic(self,source_id,keep_id):
        """Only obsolete unreferenced automatic ZIPs; never scientific evidence."""
        source=self.source(source_id)
        if source['pinned']:return []
        with self.connect() as db:rows=[dict(r) for r in db.execute("SELECT * FROM artifacts WHERE source_id=? AND kind='auto' AND state='ready' AND id!=?",(source_id,keep_id))]
        removed=[]
        for row in rows:
            if self.pinned_by_receipt(source,row['sha256']):continue
            target=safe_path(row['path'],root=self.root)
            if not target.exists():continue
            if file_hash(target)!=row['sha256']:continue
            # This is retention of replaceable automatic archives. Explicit
            # user cleanup uses the separate reversible cleanup journal.
            target.unlink();sidecar=safe_path(str(target)+'.sha256',root=self.root)
            if sidecar.exists():
                parts=sidecar.read_text(encoding='utf-8').split()
                if parts and parts[0]==row['sha256']:sidecar.unlink()
            with self.connect() as db:db.execute("UPDATE artifacts SET state='superseded' WHERE id=?",(row['id'],))
            removed.append(row['id'])
        return removed

    def list_sources(self):
        with self.connect() as db:
            rows=[dict(r) for r in db.execute('SELECT s.*,COUNT(a.id) AS versions,COALESCE(SUM(a.bytes),0) AS bytes FROM sources s LEFT JOIN artifacts a ON a.source_id=s.id AND a.state=\'ready\' GROUP BY s.id ORDER BY s.updated DESC')]
        for row in rows:
            row['results_root']=str(self.root)
            row['latest_bundle']=self.resolve(row['latest']) if row['latest'] else None
        return rows

    def list_versions(self,source_id):
        with self.connect() as db:rows=[dict(r) for r in db.execute('SELECT * FROM artifacts WHERE source_id=? ORDER BY created DESC',(source_id,))]
        return [self.resolve(row['id']) for row in rows]

    def pin(self,source_id,pinned):
        if type(pinned) is not bool:raise ValueError('保留标记必须为布尔值。')
        source=self.source(source_id)
        with exclusive_lock(Path(source['directory'])/'.session.lock'):
            with self.connect() as db:db.execute('UPDATE sources SET pinned=? WHERE id=?',(int(pinned),source_id))

    def rename(self,source_id,title,project):
        """Move only registered ZIPs within this result root; hashes stay fixed."""
        source=self.source(source_id);title=safe_name(title,default='科研成果',maximum=26);project=safe_name(project)
        moves=[];sidecars=[]
        with ExitStack() as stack:
            task=Path(source['directory']).parent/'task.json'
            if source['mode']=='mcp' and task.is_file():stack.enter_context(exclusive_lock(task.parent/'.task.lock'))
            stack.enter_context(exclusive_lock(Path(source['directory'])/'.session.lock'))
            try:
                with self.connect() as db:
                    rows=[dict(r) for r in db.execute("SELECT * FROM artifacts WHERE source_id=? AND state='ready'",(source_id,))]
                    for row in rows:
                        old=safe_path(row['path'],root=self.root)
                        if file_hash(old)!=row['sha256']:raise ValueError('成果已被外部修改，未重命名。')
                        marker='自动成果' if row['kind']=='auto' else '快照'
                        target=safe_path(self.root/project/(datetime.fromtimestamp(row['created']).strftime('%Y-%m-%d')+'_'+title+'_'+marker+'_'+row['id'][:6]+'.zip'),root=self.root)
                        if old==target:continue
                        if target.exists():raise FileExistsError('目标成果文件已存在。')
                        target.parent.mkdir(parents=True,exist_ok=True);os.replace(old,target);moves.append((old,target))
                        sidecar=Path(str(old)+'.sha256')
                        if sidecar.is_file():
                            text=sidecar.read_text(encoding='utf-8')
                            if not text.split() or text.split()[0]!=row['sha256']:raise ValueError('成果摘要文件已变化，未重命名。')
                            new_sidecar=safe_path(str(target)+'.sha256',root=self.root);os.replace(sidecar,new_sidecar);moves.append((sidecar,new_sidecar))
                            sidecars.append((new_sidecar,text))
                            with staged_file(new_sidecar,overwrite=True) as temporary:temporary.write_text(row['sha256']+'  '+target.name+'\n',encoding='utf-8')
                        db.execute('UPDATE artifacts SET path=? WHERE id=?',(str(target),row['id']))
                        db.execute('INSERT OR REPLACE INTO aliases VALUES(?,?,?,?)',(str(old),row['sha256'],source_id,row['id']))
                    db.execute('UPDATE sources SET title=?,project=?,updated=? WHERE id=?',(title,project,time.time(),source_id))
            except Exception:
                for path,text in sidecars:
                    if path.exists():
                        with staged_file(path,overwrite=True) as temporary:temporary.write_text(text,encoding='utf-8')
                for old,new in reversed(moves):
                    if new.exists() and not old.exists():os.replace(new,old)
                raise

    def import_legacy(self,session):
        """Copy and verify old ZIPs. Originals remain until explicit cleanup."""
        # Older releases did not persist a result mode. Retain delegated task
        # identity so whole-task cleanup also writes its idempotent tombstone.
        if not session.results_directory:
            task=session.directory.parent/'task.json'
            if re.fullmatch(r'[0-9a-f]{32}',session.directory.parent.name) and task.is_file():
                record,_=read_json(task,max_bytes=2*1024*1024)
                if record.get('task_id')!=session.directory.parent.name or not record.get('owner_key'):raise ValueError('旧委派任务身份不一致，未导入。')
                session.results_mode='mcp'
            elif session.task_context.get('interaction_mode')=='offline_tools':session.results_mode='offline'
        history=list(session.export_history)
        if session.result_bundle and session.result_bundle not in history:history.append(session.result_bundle)
        imported=[]
        from .results import verify_bundle
        for bundle in history:
            if not isinstance(bundle,dict) or not bundle.get('archive') or bundle.get('artifact_id'):continue
            original=safe_path(bundle['archive'],root=session.directory/'exports')
            existing=self.find_alias(original,bundle['sha256'],session.directory)
            if existing:imported.append(existing);continue
            verify_bundle(original,bundle['sha256']);identifier,target=self.reserve(session,automatic=False)
            with staged_file(target) as temporary:
                shutil.copyfile(original,temporary);verify_bundle(temporary,bundle['sha256'])
            published=self.publish(identifier,{**bundle,'archive':str(target),'sha256_file':None})
            with self.connect() as db:db.execute('INSERT OR REPLACE INTO aliases VALUES(?,?,?,?)',(str(original),bundle['sha256'],session.session_id,identifier))
            imported.append(published)
        return imported


def resolve_bundle(bundle,*,source_directory=None,results_root=None):
    """Locate renamed managed results; never substitute a different checksum."""
    if not bundle:return bundle
    value=copy.deepcopy(bundle);root=value.get('results_root') or results_root
    if not root:return value
    catalog=ResultCatalog(root)
    if not catalog.database.is_file():
        if value.get('artifact_id'):value['availability']='missing'
        return value
    if value.get('artifact_id'):
        located=catalog.resolve(value['artifact_id'],source_directory=source_directory,expected_sha256=value.get('sha256'))
    elif source_directory and value.get('archive') and value.get('sha256'):
        located=catalog.find_alias(value['archive'],value['sha256'],source_directory)
    else:located=None
    return located or value
