"""Explicit, previewed result cleanup with same-volume reversible moves.

No model tools call this module. A durable journal and per-session marker block
resumption after a crash; restore never executes calculations or resets usage.
"""
from contextlib import ExitStack
import copy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid

from graph_research.runtime.storage import safe_path,read_json,write_json,exclusive_lock
from graph_research.runtime.evidence import file_hash
from graph_research.runtime.serialization import legacy_json_fingerprint as _json_hash

BUSY={'running','awaiting_plan','awaiting_clarification','awaiting_approval','awaiting_assessment'}


def _inventory(path,root):
    path=safe_path(path,root=root)
    if not path.exists():raise ValueError('预览中的文件已不存在，请刷新后再清理。')
    items=[];paths=[path]
    if path.is_dir():
        for target in path.rglob('*'):
            if len(paths)>=100000:raise ValueError('文件过多，请分批清理。')
            paths.append(target)
    for target in paths:
        target=safe_path(target,root=root);relative='.' if target==path else target.relative_to(path).as_posix()
        if target.is_dir():items.append({'path':relative,'directory':True})
        elif target.is_file():
            before=target.stat();digest=file_hash(target);after=target.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('预览时文件发生变化，请刷新。')
            items.append({'path':relative,'bytes':after.st_size,'sha256':digest})
        else:raise ValueError('不能清理特殊文件。')
    return sorted(items,key=lambda item:item['path'])


class ResultCleanup:
    def __init__(self,catalog):self.catalog=catalog

    def _task(self,source):
        root=Path(source['directory']);path=root.parent/'task.json'
        if source['mode']!='mcp' or not re.fullmatch(r'[0-9a-f]{32}',root.parent.name) or not path.is_file():return None,None
        record,_=read_json(safe_path(path),max_bytes=2*1024*1024)
        if record.get('task_id')!=root.parent.name or not record.get('owner_key'):raise ValueError('委派任务元数据不一致。')
        return path,record

    def _source_state(self,source):
        root=safe_path(source['directory']);manifest=safe_path(root/'session.json',root=root)
        document,_=read_json(manifest,max_bytes=16*1024*1024)
        if document.get('session_id')!=source['id'] or document.get('cleared'):raise ValueError('会话已清理或身份不一致。')
        if (root/'.results-cleanup.json').exists():raise ValueError('该会话有未完成的清理，请先在回收区恢复。')
        if document.get('state',{}).get('status') in BUSY:raise ValueError('任务正在运行或等待用户回复/审批，暂不清理。')
        if source['pinned']:raise ValueError('成果已标记保留，请先取消保留标记。')
        task_path,task=self._task(source)
        if task and task['status'] in ('queued','running','waiting_for_user','waiting_for_approval'):raise ValueError('委派任务仍在运行或等待用户，暂不清理。')
        return document,task_path,task

    def _targets(self,source,document,mode):
        root=safe_path(source['directory']);targets=[];artifact_ids=[]
        if mode=='temporary':
            for worker in (root/'tasks').glob('task_*'):
                if not re.fullmatch(r'task_[0-9a-f]{32}',worker.name):continue
                for name in ('temp','cache','home','config'):
                    if (worker/name).exists():targets.append((worker/name,root))
        elif mode in ('old_auto','task'):
            with self.catalog.connect() as db:
                rows=[dict(r) for r in db.execute("SELECT * FROM artifacts WHERE source_id=? AND state IN ('ready','preparing')",(source['id'],))]
            for row in rows:
                if mode=='old_auto' and (row['kind']!='auto' or row['id']==source['latest'] or self.catalog.pinned_by_receipt(source,row['sha256'])):continue
                target=safe_path(row['path'],root=self.catalog.root)
                if not target.exists():continue
                if row['sha256'] and file_hash(target)!=row['sha256']:raise ValueError('成果包已被外部修改，请先处理该文件。')
                targets.append((target,self.catalog.root));artifact_ids.append(row['id'])
                sidecar=Path(str(target)+'.sha256')
                if sidecar.exists():targets.append((sidecar,self.catalog.root))
            if mode=='task':
                for worker in (root/'tasks').glob('task_*'):
                    if re.fullmatch(r'task_[0-9a-f]{32}',worker.name):targets.append((worker,root))
                for name in ('session.json','session.json.previous','answer.md','workflow-journal.json','workflow-journal.json.previous','.cancel'):
                    if (root/name).exists():targets.append((root/name,root))
                # Exports/views are host-managed subdirectories; files outside
                # these directories (for example a user's notes) stay in place.
                for name in ('exports','views','changes'):
                    if (root/name).exists():targets.append((root/name,root))
                task_path,task=self._task(source)
                if task and (task_path.parent/'responses').exists():targets.append((task_path.parent/'responses',task_path.parent))
        else:raise ValueError('请选择临时文件、旧自动包或整个任务。')
        seen=set();unique=[]
        for path,anchor in targets:
            path=safe_path(path,root=anchor)
            if str(path) not in seen:seen.add(str(path));unique.append((path,safe_path(anchor)))
        return unique,artifact_ids

    def preview(self,source_ids,mode):
        """Persist exact scopes, checksums and source revisions before approval."""
        with self.catalog.connect() as db:db.execute("DELETE FROM operations WHERE state='prepared' AND created<?",(time.time()-900,))
        plans=[];blocked=[]
        for identifier in dict.fromkeys(source_ids):
            source=self.catalog.source(identifier)
            try:
                document,task_path,task=self._source_state(source);targets,artifact_ids=self._targets(source,document,mode)
                operation_id=uuid.uuid4().hex;moves=[]
                for index,(target,anchor) in enumerate(targets):
                    inventory=_inventory(target,anchor)
                    # Every payload stays on its source volume. Undo requires
                    # only atomic renames, including with a custom result drive.
                    trash=safe_path(anchor/'.成果回收'/operation_id/str(index),root=anchor)
                    moves.append({'source':str(target),'trash':str(trash),'anchor':str(anchor),'inventory':inventory})
                if not moves:blocked.append({'id':identifier,'title':source['title'],'reason':'没有可清理内容。'});continue
                data={'version':1,'id':operation_id,'source':source,'mode':mode,'source_sha256':file_hash(Path(source['directory'])/'session.json'),
                      'task_path':str(task_path) if task_path else None,'task_before':task,'artifact_ids':artifact_ids,
                      'artifact_states':{key:self.catalog.artifact(key)['state'] for key in artifact_ids},'moves':moves,
                      'bytes':sum(item.get('bytes',0) for move in moves for item in move['inventory']),
                      'files':sum(not item.get('directory',False) for move in moves for item in move['inventory']),'created':time.time()}
                with self.catalog.connect() as db:db.execute('INSERT INTO operations VALUES(?,?,?,?)',(operation_id,'prepared',data['created'],json.dumps(data,ensure_ascii=False)))
                plans.append(data)
            except (OSError,ValueError,RuntimeError) as error:blocked.append({'id':identifier,'title':source['title'],'reason':str(error)})
        return {'plans':plans,'blocked':blocked,'bytes':sum(p['bytes'] for p in plans),'files':sum(p['files'] for p in plans)}

    def _operation(self,identifier):
        with self.catalog.connect() as db:row=db.execute('SELECT * FROM operations WHERE id=?',(identifier,)).fetchone()
        if row is None:raise ValueError('没有该清理记录。')
        return row['state'],json.loads(row['data'])

    def _store(self,data,state):
        with self.catalog.connect() as db:db.execute('UPDATE operations SET state=?,data=? WHERE id=?',(state,json.dumps(data,ensure_ascii=False),data['id']))

    def _locks(self,stack,source,task_path):
        if task_path:stack.enter_context(exclusive_lock(Path(task_path).parent/'.task.lock'))
        stack.enter_context(exclusive_lock(Path(source['directory'])/'.session.lock'))

    def _validate_move(self,move,data):
        source=Path(move['source']);root=Path(data['source']['directory']);anchor=Path(move['anchor'])
        allowed={root,self.catalog.root}
        if data['task_path']:allowed.add(Path(data['task_path']).parent)
        if anchor not in allowed:raise ValueError('回收范围不属于已登记成果。')
        source=safe_path(source,root=anchor);trash=safe_path(move['trash'],root=anchor/'.成果回收'/data['id'])
        if source==anchor or source.is_relative_to(anchor/'.成果回收'):raise ValueError('清理目标不合法。')
        return source,trash,anchor

    def apply(self,identifier):
        state,data=self._operation(identifier)
        if state=='applied':return data
        if state!='prepared' or time.time()-data['created']>900:raise ValueError('清理预览已失效，请重新预览。')
        source=self.catalog.source(data['source']['id']);root=Path(source['directory']);marker=root/'.results-cleanup.json'
        with ExitStack() as stack:
            self._locks(stack,source,data['task_path']);current,_=self._operation(identifier)
            if current=='applied':return data
            if current!='prepared':raise ValueError('清理记录已变化，请重新预览。')
            source=self.catalog.source(source['id']);document,_,task=self._source_state(source)
            if file_hash(root/'session.json')!=data['source_sha256'] or _json_hash(task)!=_json_hash(data['task_before']):raise ValueError('预览后任务已变化，请重新预览。')
            for move in data['moves']:
                path,trash,anchor=self._validate_move(move,data)
                if trash.exists() or _inventory(path,anchor)!=move['inventory']:raise ValueError('预览后文件已变化，请重新预览。')
            write_json(marker,{'operation_id':identifier,'mode':data['mode']});self._store(data,'moving')
            try:
                for move in data['moves']:
                    path,trash,anchor=self._validate_move(move,data);trash.parent.mkdir(parents=True,exist_ok=True);os.replace(path,trash)
                if data['mode']=='task':
                    stub={'version':3,'session_id':source['id'],'cleared':{'operation_id':identifier,'at':time.time()},
                          'state':{'question':source['title'],'status':'cleared'},'exports':{'results_root':str(self.catalog.root),'mode':source['mode']}}
                    write_json(root/'session.json',stub);data['stub_sha256']=file_hash(root/'session.json')
                    if task:
                        tombstone=copy.deepcopy(task);tombstone.update(status='cleared',pending=None,response=None,revision=task['revision']+1,
                            updated_at=datetime.now(timezone.utc).isoformat(),cleared={'operation_id':identifier,'at':time.time(),'result_id':source['id']})
                        tombstone['request']={key:task['request'][key] for key in ('version','request_id','parent_task_id','objective') if key in task['request']}
                        write_json(data['task_path'],tombstone)
                with self.catalog.connect() as db:
                    for artifact_id in data['artifact_ids']:db.execute("UPDATE artifacts SET state='trashed' WHERE id=?",(artifact_id,))
                    if data['mode']=='task':db.execute("UPDATE sources SET state='cleared',updated=? WHERE id=?",(time.time(),source['id']))
                self._store(data,'applied');marker.unlink(missing_ok=True)
            except Exception:
                self._store(data,'moving')
                # Preserve the journal and marker if interruption prevents a
                # complete rollback. No caller can silently resume that session.
                try:self._restore_files(data);self._store(data,'restored');marker.unlink(missing_ok=True)
                except Exception:pass
                raise
        return data

    def _restore_files(self,data):
        root=Path(data['source']['directory']);manifest=root/'session.json'
        if data['task_before'] and data['mode']=='task':
            current,_=read_json(data['task_path'],max_bytes=2*1024*1024)
            if any(current.get(key)!=data['task_before'].get(key) for key in ('task_id','owner_key','request_sha256','usage','policy')):
                raise ValueError('任务身份或预算已变化，不能覆盖恢复或回退用量。')
            if current.get('cleared',{}).get('operation_id') not in (None,data['id']):raise ValueError('任务清理状态已变化。')
        if data['mode']=='task' and manifest.exists():
            current_document,_=read_json(manifest,max_bytes=16*1024*1024)
            if current_document.get('cleared',{}).get('operation_id')==data['id']:
                if data.get('stub_sha256') and file_hash(manifest)!=data['stub_sha256']:raise ValueError('已清理会话被修改，不能覆盖恢复。')
                manifest.unlink()
        for move in reversed(data['moves']):
            target,trash,anchor=self._validate_move(move,data)
            if not trash.exists():continue
            if target.exists():raise FileExistsError('原位置已存在新文件，恢复未覆盖它。')
            if _inventory(trash,anchor)!=move['inventory']:raise ValueError('回收内容已变化，拒绝覆盖恢复。')
            target.parent.mkdir(parents=True,exist_ok=True);os.replace(trash,target)
        if data['task_before'] and data['mode']=='task':
            original=copy.deepcopy(data['task_before']);current,_=read_json(data['task_path'],max_bytes=2*1024*1024)
            if current.get('cleared',{}).get('operation_id') not in (None,data['id']):raise ValueError('任务清理状态已变化。')
            original.pop('cleared',None);original['revision']=max(original['revision'],current['revision'])+1;original['response']=None
            original['updated_at']=datetime.now(timezone.utc).isoformat()
            if original['status'] in ('cancelled','interrupted','budget_exhausted'):
                original['status']='interrupted';original.pop('active_event',None)
                original['pending']={'kind':'resume','interaction_id':uuid.uuid4().hex,'host_actions':['continue'],'message':'清理已撤销，请重新确认是否继续；原预算保留。'}
            write_json(data['task_path'],original)
        with self.catalog.connect() as db:
            for identifier in data['artifact_ids']:db.execute('UPDATE artifacts SET state=? WHERE id=?',(data.get('artifact_states',{}).get(identifier,'ready'),identifier))
            db.execute("UPDATE sources SET state='ready',updated=? WHERE id=?",(time.time(),data['source']['id']))

    def restore(self,identifier):
        state,data=self._operation(identifier)
        if state=='restored':return data
        if state not in ('applied','moving'):raise ValueError('该清理记录不能恢复。')
        root=Path(data['source']['directory']);marker=root/'.results-cleanup.json'
        with ExitStack() as stack:
            self._locks(stack,data['source'],data['task_path']);current,_=self._operation(identifier)
            if current=='restored':return data
            if current not in ('applied','moving'):raise ValueError('清理记录已变化，不能恢复。')
            write_json(marker,{'operation_id':identifier,'mode':'restore'})
            self._store(data,'moving')
            self._restore_files(data);self._store(data,'restored');marker.unlink(missing_ok=True)
        return data

    def discard_previews(self,identifiers):
        with self.catalog.connect() as db:
            for identifier in identifiers:db.execute("DELETE FROM operations WHERE id=? AND state='prepared'",(identifier,))

    def list_operations(self):
        with self.catalog.connect() as db:rows=[dict(row) for row in db.execute("SELECT * FROM operations WHERE state IN ('applied','moving') ORDER BY created DESC")]
        return [{'id':row['id'],'state':row['state'],**json.loads(row['data'])} for row in rows]

    def purge_preview(self,identifier):
        state,data=self._operation(identifier)
        if state!='applied':raise ValueError('只有已完成的回收操作可以永久清理。')
        for move in data['moves']:
            _,trash,anchor=self._validate_move(move,data)
            if trash.exists() and _inventory(trash,anchor)!=move['inventory']:raise ValueError('回收内容已变化，请先检查。')
        return {'id':identifier,'title':data['source']['title'],'bytes':data['bytes'],'files':data['files'],'age_days':max(0,(time.time()-data['created'])/86400)}

    def purge(self,identifier):
        """Explicit irreversible action, only after the host previews its scope."""
        self.purge_preview(identifier);state,data=self._operation(identifier)
        with ExitStack() as stack:
            self._locks(stack,data['source'],data['task_path'])
            self.purge_preview(identifier)
            for move in data['moves']:
                _,trash,anchor=self._validate_move(move,data)
                if not trash.exists():continue
                if _inventory(trash,anchor)!=move['inventory']:raise ValueError('回收内容已变化。')
                # Both the resolved target and every descendant were checked;
                # never delete the live session or a computed parent directory.
                if trash.is_dir():shutil.rmtree(trash)
                else:trash.unlink()
            with self.catalog.connect() as db:
                for artifact_id in data['artifact_ids']:db.execute("UPDATE artifacts SET state='cleared' WHERE id=? AND state='trashed'",(artifact_id,))
            data.pop('task_before',None);data['moves']=[];self._store(data,'purged')
        return data
