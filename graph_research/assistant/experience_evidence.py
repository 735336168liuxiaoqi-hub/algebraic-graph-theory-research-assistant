"""Derive review candidates from scoped, verified executions; never from answers."""
import math
from pathlib import Path
import re
import sqlite3
from types import SimpleNamespace

from graph_research.runtime.storage import safe_path,read_json
from graph_research.runtime.evidence import file_hash
from .experience import ExperienceStore,fingerprint
from .memory import read_memory_context


def failure_reference(task_directory,error):
    """Retain only a hash-bound host failure receipt under this task root."""
    raw=getattr(error,'execution_directory',None)
    if not raw:return None
    try:
        root=Path(task_directory).resolve();directory=safe_path(raw,root=root)
        if not re.fullmatch('task_[0-9a-f]{32}',directory.name) or directory.parent!=root:return None
        receipt=directory/'execution.json';data,_=read_json(receipt,max_bytes=1024*1024)
        if data.get('status')!='failed':return None
        return {'task_id':directory.name,'directory':str(directory),'receipt_sha256':file_hash(receipt)}
    except (OSError,ValueError):return None


def _failure_evidence(session,item):
    meta=item['failed_execution'];root=session.directory/'tasks';directory=safe_path(meta['directory'],root=root)
    if directory.name!=meta['task_id'] or directory.parent!=root.resolve():raise ValueError('Invalid failure execution location')
    if file_hash(directory/'execution.json')!=meta['receipt_sha256']:raise ValueError('Failure receipt changed')
    receipt,_=read_json(directory/'execution.json',max_bytes=1024*1024)
    if receipt.get('status')!='failed' or not receipt.get('core_manifest_sha256') or not receipt.get('environment'):raise ValueError('Failure receipt lacks execution version')
    if receipt.get('request_sha256')!=file_hash(directory/'request.json'):raise ValueError('Failure request evidence mismatch')
    result_hash=file_hash(directory/'result.json') if (directory/'result.json').is_file() else None
    if receipt.get('result_sha256')!=result_hash:raise ValueError('Failure result evidence mismatch')
    request,_=read_json(directory/'request.json',max_bytes=256*1024)
    if request.get('name')!=item['tool'] or fingerprint(request.get('arguments'))!=fingerprint(item.get('arguments')):raise ValueError('Failure input mismatch')
    return receipt,directory


def verified_call(service,task_id,call_id):
    """Read only this host user's one call, validating data against its receipt."""
    if not re.fullmatch('call-[0-9]{4,6}',call_id):raise ValueError('Invalid call ID')
    record=service.read(task_id);state,_,_=service.snapshot_state(record)
    index=int(call_id[5:])-1;observations=state.get('observations',[])
    if not 0<=index<len(observations):raise FileNotFoundError('Source call unavailable')
    item=observations[index]
    if 'tool' not in item:raise ValueError('Source is not a tool call')
    session=SimpleNamespace(directory=service.task_dir(task_id)/'session')
    if item.get('ok') is True:
        from .results import _execution
        level,receipt,_,_=_execution(session,item,'experience',False,[])
        if level!='verified_execution':raise ValueError('Source evidence not verified')
        directory=safe_path(item['execution']['directory'],root=session.directory/'tasks');meta=item['execution']
    else:
        receipt,directory=_failure_evidence(session,item);meta=item['failed_execution']
    proof={'task_id':task_id,'call_id':call_id,'receipt_sha256':meta['receipt_sha256'],
           'request_sha256':file_hash(directory/'request.json'),
           'result_sha256':file_hash(directory/'result.json') if (directory/'result.json').is_file() else None,
           'core_manifest_sha256':receipt['core_manifest_sha256'],'environment':receipt['environment'],
           'verification':'verified_tool_execution' if item.get('ok') else 'verified_failed_attempt',
           'tool_package_id':(receipt.get('tool_provenance') or {}).get('package_id')}
    return item,proof


def _finite(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except OverflowError:return False


def derive_candidate(item,proof):
    """Keep a small allowlist of input conditions and observed scalar facts."""
    args=item.get('arguments',{});raw_result=item.get('result',{});result=raw_result if isinstance(raw_result,dict) else {}
    outcome='success' if item.get('ok') is True else 'failure';facts={};conditions={};tags=[]
    for name in ('alpha','tolerance','max_iterations','seed','n','m','k'):
        if _finite(args.get(name)):conditions[name]=args[name]
    for name in ('kind','matrix','method'):
        value=args.get(name)
        if isinstance(value,str) and re.fullmatch('[A-Za-z0-9_.:-]{1,80}',value):conditions[name]=value
    edges=args.get('edges')
    if isinstance(edges,list) and edges and all(isinstance(edge,list) for edge in edges):
        try:
            conditions.update(vertex_count=len(set(v for edge in edges for v in edge)),edge_count=len(edges),uniform=len({len(e) for e in edges})==1)
            if conditions['uniform']:conditions['rank']=len(edges[0])
        except TypeError:pass
    if item['tool'].startswith('graph_') or item['tool']=='weighted_graph_spectrum':conditions.setdefault('rank',2)
    if 'weights' in args:conditions['weighted']=True
    if 'vertex_degrees' in args:conditions['custom_degree_diagonal']=True
    if 'initial_vector' in args:conditions['initial_vector_supplied']=True
    matrix=args.get('matrix')
    if isinstance(matrix,list) and matrix and all(isinstance(row,list) for row in matrix):conditions.update(matrix_rows=len(matrix),matrix_columns=len(matrix[0]))
    for name in ('rho','relative_residual','achieved_tolerance','iterations','order','size','rank','degree','diameter','connected','bipartite','components'):
        value=result.get(name)
        if type(value) is bool or _finite(value):facts[name]=value
    if item['tool']=='generate_hypergraph' and type(facts.get('rank')) is int:conditions.setdefault('rank',facts['rank'])
    method=result.get('method')
    if isinstance(method,str) and re.fullmatch('[A-Za-z0-9_.:-]{1,80}',method):facts['method']=method
    initialization=result.get('initialization')
    if isinstance(initialization,str) and re.fullmatch('[A-Za-z0-9_.:-]{1,80}',initialization):facts['initialization']=initialization
    if isinstance(result.get('verification'),dict):
        passed=result['verification'].get('passed')
        if type(passed) is bool:facts['independent_verification_passed']=passed
    if outcome=='failure':
        text=str(item.get('error',''))
        facts['reported_failure']='solver_unresolved' if any(s in text for s in ('Perron solver did not converge','Newton-Noda solver unresolved')) else 'tool_execution_failed'
        if facts['reported_failure']=='solver_unresolved':tags.append('未收敛')
    if item.get('tool_status')=='fixture_tested_experimental':
        if type(raw_result) is bool or _finite(raw_result):facts['extension_value']=raw_result
        for name,value in list(result.items())[:64]:
            if len([key for key in facts if key.startswith('extension_')])>=16:break
            if isinstance(name,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,48}',name) and (type(value) is bool or _finite(value)):facts['extension_'+name]=value
    if outcome=='success' and not facts:return None
    if _finite(conditions.get('alpha')) and conditions['alpha']>=.9:tags.append('高α')
    title=item['tool']+('成功计算案例' if outcome=='success' else '失败尝试案例')
    if item.get('tool_status')=='fixture_tested_experimental':tags.append('实验工具')
    return {'format':'graph-research-experience/1','title':title,'tool':item['tool'],'tool_status':item.get('tool_status','unknown'),'outcome':outcome,
            'conditions':conditions,'facts':facts,'tags':tags,'evidence':proof,
            'scope_note':'仅为该次输入的执行事实；未记录完整对象，条件匹配不证明可迁移或一般结论。'}


def capture_call(service,task_id,call_id):
    """Trusted capture after evidence validation; no model-supplied summaries."""
    item,proof=verified_call(service,task_id,call_id);payload=derive_candidate(item,proof)
    if payload is None:return {'created':False,'status':'no_supported_facts'}
    return ExperienceStore(service.memory_directory).capture(service.user_id,payload,task_id+':'+call_id+':'+proof['receipt_sha256'])


def collect_task(service,record,session):
    """Advance a durable cursor so clearing memory never mines old calls again."""
    observations=session.state.get('observations',[]);cursor=record.get('experience_cursor',len(observations))
    if not session.memory_enabled or not read_memory_context(service.memory_directory,service.user_id)['enabled']:
        record['experience_cursor']=len(observations);record['experience_collection']={'status':'disabled','created':0};return
    created=0;skipped=0
    for index in range(cursor,len(observations)):
        try:
            result=capture_call(service,record['task_id'],f'call-{index+1:04d}')
            created+=int(result.get('created',False));skipped+=int(result.get('status')=='no_supported_facts')
        except (OSError,ValueError,KeyError,TypeError):skipped+=1
        except sqlite3.Error:
            record['experience_cursor']=len(observations)
            record['experience_collection']={'status':'storage_unavailable','created':created};return
        record['experience_cursor']=index+1
    record['experience_collection']={'status':'candidates_only','created':created,'skipped':skipped}


def check_source(service,entry):
    """Flag archived origins; reject changed sources rather than silently trust."""
    proof=entry['content']['evidence']
    try:
        _,current=verified_call(service,proof['task_id'],proof['call_id'])
        fields=('receipt_sha256','request_sha256','result_sha256','core_manifest_sha256')
        status='verified' if all(current[key]==proof[key] for key in fields) else 'changed'
    except FileNotFoundError:status='unavailable'
    except OSError:status='unavailable'
    except ValueError as error:
        status='unavailable' if getattr(error,'code',None)=='task_not_found' else 'changed'
    except (KeyError,TypeError):status='changed'
    from graph_research.runtime.integrity import CORE,MANIFEST
    entry['source_state']=status
    entry['current_core_matches']=file_hash(CORE/MANIFEST)==proof['core_manifest_sha256']
    if proof.get('tool_package_id'):
        from graph_research.tools.library import active_identity
        active=active_identity(service.tool_directory,entry['content']['tool'])
        entry['current_tool_package_matches']=bool(active and active['package_id']==proof['tool_package_id'])
    entry['scope_warning']='历史案例供参考，当前问题仍须重新计算/验证；原始记录不可访问时仅保留历史证据快照。'
    return entry
