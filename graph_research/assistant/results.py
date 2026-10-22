"""Portable conversation/turn results: bounded snapshots, provenance and hashes.

Export never executes a tool or model. Only host-recorded scientific outputs
inside this session's task directories may become attachments. The bundle is
data, not an installable extension or an automatic replay program.
"""
import csv
import copy
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
from html import escape
import io
import json
from pathlib import Path,PurePosixPath
import re
from urllib.parse import quote
import uuid
import zipfile

from graph_research.runtime.evidence import file_hash,environment_info
from graph_research.runtime.storage import safe_path,staged_file,atomic_text,io_path
from graph_research.runtime.observability import timed

MAX_BYTES=256*1024*1024
MAX_FILE_BYTES=64*1024*1024
MAX_FILES=4096
PENDING={'batch_partial','batch_failed','running','recovery_required','manual_development_required','awaiting_plan','awaiting_approval','awaiting_assessment','awaiting_clarification','execution_error','cancelled',
         'assessment_failed','extension_failed','budget_exhausted','approval_or_budget_required','extension_rejected'}
LABELS={'batch_complete':'批量工作流已完成','batch_partial':'批量工作流部分成功','batch_failed':'批量工作流失败','recorded':'计算记录已保存','partial':'部分结果或尚未完成','analysis_only':'只有分析记录，没有计算结果',
        'tool_execution_failed':'工具计算失败','task_failed':'任务失败','blocked':'执行被阻止',
        'tool_results_available':'已有工具计算结果','model_analysis_only':'本轮仅有模型分析','extension_ready':'扩展已准备',
        'awaiting_plan':'等待查看任务计划','awaiting_approval':'等待开发确认','awaiting_assessment':'等待需求评估','awaiting_clarification':'等待补充需求',
        'execution_error':'执行中断或错误','cancelled':'已取消','extension_rejected':'已拒绝开发','running':'执行中',
        'budget_exhausted':'达到本轮预算','assessment_failed':'评估未通过','extension_failed':'扩展验收失败',
        'approval_or_budget_required':'需要重新确认范围或预算','success':'成功','failed':'失败',
        'verified_execution':'已与执行回执核对','legacy_record':'旧记录，缺少原始执行回执',
        'incomplete_evidence':'执行证据或附件不完整','failed_call':'失败调用，未计作成功结果'}


def _json(value):
    return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def export_issues(observations):
    """Keep completed calculations distinct from their requested file exports."""
    return [{'call_id':f'call-{index+1:04d}','tool':item['tool'],'export_status':item['result']['export_status']}
            for index,item in enumerate(observations) if item.get('tool')=='graph_batch_study' and item.get('ok') is True
            and isinstance(item.get('result'),dict) and item['result'].get('export_status') in ('partial','failed')]


def _member(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or any(ord(ch)<32 for ch in name):raise ValueError('Unsafe result-bundle member name')
    path=PurePosixPath(name)
    if path.is_absolute() or any(part in ('','..','.') or part.endswith((' ','.')) for part in name.split('/')):raise ValueError('Unsafe result-bundle path')
    return path.as_posix()


def _read(path,limit=MAX_FILE_BYTES):
    with io_path(path).open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Result evidence file exceeds size limit')
    return data


@dataclass
class Attachment:
    path:Path
    sha256:str
    size:int


def _checked(path,expected,limit):
    data=_read(path,limit)
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Execution evidence checksum changed: '+Path(path).name)
    return data


def _execution(session,item,identifier,allow_incomplete,warnings):
    """Validate recorded execution and its outputs; never follow arbitrary paths."""
    task_root=session.directory/'tasks';meta=item.get('execution')
    attachments={};mapping={}
    def add(path,relative,expected=None,size=None):
        path=safe_path(path,root=task_root)
        data=_read(path)
        digest=hashlib.sha256(data).hexdigest()
        if expected is not None and (digest!=expected or len(data)!=size):raise ValueError('Scientific output was changed or truncated: '+relative)
        member=_member('artifacts/'+identifier+'/'+relative)
        attachments[member]=Attachment(path,digest,len(data));mapping[str(path)]=member
    if not meta:
        warnings.append(identifier+'：旧记录缺少计算时的校验回执，不能确认原始执行版本。')
        result=item.get('result',{})
        paths=list(result.get('files',{}).values()) if isinstance(result,dict) and isinstance(result.get('files'),dict) else []
        if isinstance(result,dict) and isinstance(result.get('editor'),str):paths.append(result['editor'])
        for raw in paths:
            try:
                path=safe_path(raw,root=task_root);relative=path.relative_to(task_root)
                if len(relative.parts)<3 or relative.parts[1]!='outputs':raise PermissionError('Legacy attachment is outside a task output directory')
                receipt=json.loads(_read(task_root/relative.parts[0]/'execution.json',1024*1024))
                if receipt.get('status')!='complete':raise ValueError('Legacy attachment has no completed execution')
                add(path,PurePosixPath(*relative.parts[1:]).as_posix())
            except (OSError,ValueError,KeyError,TypeError) as exc:
                if not allow_incomplete:raise
                warnings.append(identifier+'：附件未收录：'+str(exc))
        return 'legacy_record',{},attachments,mapping
    try:
        task_id=meta['task_id']
        if not isinstance(task_id,str) or not re.fullmatch(r'task_[0-9a-f]{32}',task_id):raise ValueError('Invalid execution task ID')
        directory=safe_path(meta['directory'],root=task_root)
        if directory!=task_root.resolve()/task_id:raise ValueError('Execution directory does not match its task ID')
        raw=_checked(safe_path(directory/'execution.json',root=task_root),meta['receipt_sha256'],1024*1024)
        receipt=json.loads(raw)
        if receipt.get('status')!='complete' or receipt.get('kind')!='tool':raise ValueError('Calculation has no completed tool execution receipt')
        request=json.loads(_checked(safe_path(directory/'request.json',root=task_root),receipt['request_sha256'],256*1024))
        result=json.loads(_checked(safe_path(directory/'result.json',root=task_root),receipt['result_sha256'],4*1024*1024))
        if request.get('name')!=item['tool'] or _canonical(request.get('arguments'))!=_canonical(item.get('arguments')) or result.get('ok') is not True or _canonical(result.get('result'))!=_canonical(item.get('result')):
            raise ValueError('Calculation record differs from its execution evidence')
        if _canonical(request.get('graph_inputs'))!=_canonical(item.get('graph_inputs')):raise ValueError('Graph input source differs from its execution evidence')
        if _canonical(request.get('research_refs'))!=_canonical(item.get('research_refs')):raise ValueError('Research object source differs from its execution evidence')
        artifacts=receipt.get('artifacts',[])
        if not isinstance(artifacts,list) or len(artifacts)>512:raise ValueError('Invalid execution artifact inventory')
        incomplete=False
        for record in artifacts:
            try:
                relative=_member(record['path'])
                if not relative.startswith('outputs/'):raise PermissionError('Only scientific output artifacts can be packaged')
                add(directory/relative,relative,record['sha256'],record['bytes'])
            except (OSError,ValueError,KeyError,TypeError) as exc:
                if not allow_incomplete:raise
                incomplete=True;warnings.append(identifier+'：附件未收录：'+str(exc))
        return 'incomplete_evidence' if incomplete else 'verified_execution',receipt,attachments,mapping
    except (OSError,ValueError,KeyError,TypeError) as exc:
        if not allow_incomplete:raise
        warnings.append(identifier+'：执行证据未通过验证，未收录附件：'+str(exc))
        return 'incomplete_evidence',{}, {},{}


def _rewrite(value,mapping):
    if isinstance(value,str):
        for source,target in sorted(mapping.items(),key=lambda kv:len(kv[0]),reverse=True):value=value.replace(source,target)
        return value
    if isinstance(value,list):return [_rewrite(item,mapping) for item in value]
    if isinstance(value,dict):return {key:_rewrite(item,mapping) for key,item in value.items()}
    return value


def _fence(text):
    text=str(text)
    runs=re.findall(r'~+',text)
    marker='~'*max(3,max((len(value)+1 for value in runs),default=3))
    return marker+'\n'+text+'\n'+marker


def _report(data,html=False):
    summary=data['summary'];title='科研对话结果' if data['scope']=='conversation' else f"第{data['turns'][0]['number']}轮科研结果"
    intro=f"计算成功 {summary['successful_calls']} 次；失败 {summary['failed_calls']} 次；附件 {summary['artifact_count']} 个。记录状态：{LABELS.get(summary['record_status'],summary['record_status'])}。"
    note='文件校验与执行回执用于复核记录完整性，不代表一般数学证明。模型回答与实际工具结果分别保留。'
    if not html:
        lines=['# '+title,'',intro,'',note,'','解压后打开 report.html 阅读；results.json保留完整精度数据，reproduce.json列出可人工复核的重算参数。']
        if data.get('batch_workflow'):lines.extend(['','批量汇总见batch-results.csv，逐步状态与字段定位见batch-summary.json，输入和依赖计划见batch-plan.json。'])
        for warning in data['warnings']:lines.extend(['','提示：'+escape(warning)])
        for turn in data['turns']:
            lines.extend(['',f"## 第{turn['number']}轮 · {LABELS.get(turn['status'],turn['status'])}",'','用户请求：',_fence(turn['user_request']),'','本轮回答：',_fence(turn['answer'])])
            if turn.get('legacy_conversation'):lines.extend(['','旧版历史问答：',_fence(_json(turn['legacy_conversation']).decode())])
            for call in [c for c in data['calculations'] if c['turn']==turn['number']]:
                lines.extend(['',f"### {call['id']} · {escape(call['tool'])} · {LABELS[call['status']]}",'',f"证据状态：{LABELS[call['evidence_status']]}",'',_fence(_json(call).decode())])
        return '\n'.join(lines)+'\n'
    from graph_research.rendering.results import render_result_report
    return render_result_report(data,LABELS)


@timed('bundle_export')
def export_session(session,output=None,*,turn=None,allow_incomplete=False,bundle_id=None):
    """Export a locked host session; use ResearchSession.export_results normally."""
    if not session.state or not session.turns:raise ValueError('No conversation results to export')
    if turn is not None and (type(turn) is not int or turn<1):raise ValueError('turn must be a positive request number')
    selected=[t for t in session.turns if turn is None or t['number']==turn]
    if not selected:raise ValueError('Requested turn does not exist')
    bundle_id=bundle_id or uuid.uuid4().hex
    if not re.fullmatch(r'[0-9a-f]{32}',bundle_id):raise ValueError('Invalid result bundle ID')
    output=safe_path(output or session.directory/'exports'/f'results_{len(session.turns):04d}_{bundle_id[:12]}.zip')
    if output.suffix.lower()!='.zip':raise ValueError('Result bundle must use the .zip extension')
    observations=session.state.get('observations',[]);warnings=[];calculations=[];files={};mapping={};used=set()
    for t in selected:
        start,end=t['observation_start'],t['observation_end']
        if type(start) is not int or type(end) is not int or not 0<=start<=end<=len(observations):raise ValueError('Invalid saved turn boundary')
        if t.get('origin')=='legacy_unsegmented':warnings.append('旧版历史未记录轮次边界；作为一个历史分组保留，不推断各次请求归属。')
        for index in range(start,end):
            if index in used:raise ValueError('Overlapping turn boundaries would duplicate calculations')
            used.add(index);item=observations[index]
            if 'tool' not in item:continue
            if len(calculations)>=1000:raise ValueError('Conversation exceeds1000 calculations; export smaller turn scopes')
            identifier=f'calc-{index+1:04d}';ok=item.get('ok') is True
            call={'id':identifier,'observation_index':index,'turn':t['number'],'tool':str(item.get('tool','unknown')),
                  'arguments':item.get('arguments',{}),'status':'success' if ok else 'failed','tool_status':item.get('tool_status','unknown'),
                  'evidence_status':'failed_call','artifacts':[]}
            if item.get('graph_inputs'):call['graph_inputs']=copy.deepcopy(item['graph_inputs'])
            for key in ('research_refs','output_graph_ref','plan_id','plan_step','operation_id','reused_execution','decision_id'):
                if key in item:call[key]=copy.deepcopy(item[key])
            if ok:
                evidence,receipt,attachments,paths=_execution(session,item,identifier,allow_incomplete,warnings)
                call.update(result=item.get('result'),evidence_status=evidence,artifacts=list(attachments))
                if receipt:
                    files['calls/'+identifier+'/execution.json']=_json(receipt)
                    call['execution']={key:receipt.get(key) for key in ('core_manifest_sha256','environment','started_at','finished_at','tool_provenance','measurements','diagnostic_id','timings')}
                files.update(attachments);mapping.update(paths)
            else:
                call['error']=str(item.get('error','Calculation failed'))
                if item.get('error_details'):call['error_details']=copy.deepcopy(item['error_details'])
            calculations.append(call)
    calculations=_rewrite(calculations,mapping)
    turns=[{key:t.get(key,'') for key in ('number','id','user_request','answer','status','started_at','updated_at','attempts','origin')} for t in selected]
    for copied,original in zip(turns,selected):
        if original.get('plan'):copied['plan']=copy.deepcopy(original['plan'])
        for key in ('claims','workflow_usage','workflow_task_id','development_brief'):
            if key in original:copied[key]=copy.deepcopy(original[key])
        if original.get('origin')=='legacy_unsegmented':copied['legacy_conversation']=original.get('legacy_conversation',session.state.get('conversation',[]))
    turns=_rewrite(turns,mapping)
    for turn_item in turns:
        if turn_item.get('development_brief'):files['development-briefs/turn-'+str(turn_item['number'])+'.json']=_json(turn_item['development_brief'])
    failed=sum(c['status']=='failed' for c in calculations)
    missing_exports=export_issues([{'tool':c['tool'],'ok':c['status']=='success','result':c.get('result')} for c in calculations])
    if missing_exports:warnings.append('部分计算已完成，但请求的文件导出不完整；原始数值保留在results.json，不自动重算。')
    status='partial' if failed or missing_exports or any(t['status'] in PENDING for t in turns) or any(c['evidence_status']=='incomplete_evidence' for c in calculations) else 'recorded' if calculations else 'analysis_only'
    data={'format':'graph-research-results','version':1,'bundle_id':bundle_id,'session_id':session.session_id,
          'scope':'conversation' if turn is None else 'turn','exported_at':datetime.now(timezone.utc).isoformat(),
          'export_environment':environment_info(),'turns':turns,'calculations':calculations,'warnings':warnings,
          'summary':{'record_status':status,'turn_count':len(turns),'successful_calls':len(calculations)-failed,'failed_calls':failed,
                     'verified_calls':sum(c['evidence_status']=='verified_execution' for c in calculations),'artifact_count':sum(isinstance(v,Attachment) for v in files.values())}}
    if getattr(session,'task_context',None):data['delegated_task']=session.task_context
    context=getattr(session,'task_context',{})
    if context.get('execution',{}).get('mode')=='batch':
        from .batch_workflow import summary as batch_summary,summary_csv
        batch=batch_summary(context,session.state)
        data['batch_workflow']=batch
        files['batch-summary.json']=_json(batch);files['batch-plan.json']=_json(context)
        files['batch-results.csv']=summary_csv(batch)
    if hasattr(session,'workflow') and session.workflow.data['tasks']:
        data['workflow_usage']=session.workflow.summary()
        files['workflow-usage.json']=_json({'summary':data['workflow_usage'],'tasks':{key:{
            'policy':task['policy'],'model_requests':task['model_requests'],'active_seconds':task['active_seconds'],
            'tool_intents':{call:{k:value[k] for k in ('status','operation_id','signature')} for call,value in task['tool_calls'].items()}}
            for key,task in session.workflow.data['tasks'].items()}})
    if getattr(session,'research_objects',{}).get('versions'):
        from .research_objects import validate_objects
        data['research_objects']=validate_objects(session.research_objects)
        files['research-objects.json']=_json(data['research_objects'])
    from .counterexample import summary as counterexample_summary
    search=counterexample_summary(session.state)
    if search is not None:
        data['counterexample_search']=search
        files['counterexample-summary.json']=_json(search)
    files['results.json']=_json(data)
    recipe={'format':'graph-research-reproduction-inputs','note':'Review tool availability, assumptions and versions before manually rerunning. No code is executed by this file.',
            'calculations':[{'id':c['id'],'turn':c['turn'],'tool':c['tool'],'arguments':c['arguments'],'evidence_status':c['evidence_status'],
                             'execution':c.get('execution')} for c in calculations if c['status']=='success']}
    files['reproduce.json']=_json(recipe)
    for call in calculations:
        prefix='calls/'+call['id']+'/'
        files[prefix+'arguments.json']=_json(call['arguments'])
        if call.get('graph_inputs'):files[prefix+'graph-inputs.json']=_json(call['graph_inputs'])
        for number,source in enumerate(call.get('graph_inputs',[]),1):files[prefix+f'input-graph-{number}.json']=_json(source['document'])
        raw=call.get('result') if call['status']=='success' else {'error':call.get('error'),**({'error_details':call['error_details']} if call.get('error_details') else {})}
        files[prefix+('result.json' if call['status']=='success' else 'error.json')]=_json(raw)
    table=io.StringIO(newline='');writer=csv.writer(table)
    writer.writerow(['calculation_id','turn','tool','status','evidence_status','arguments_file','result_or_error_file'])
    for call in calculations:
        row=[call['id'],str(call['turn']),call['tool'],call['status'],call['evidence_status'],'calls/'+call['id']+'/arguments.json',
             'calls/'+call['id']+('/result.json' if call['status']=='success' else '/error.json')]
        writer.writerow(["'"+v if v.lstrip().startswith(('=','+','-','@')) else v for v in row])
    files['calculations.csv']=b'\xef\xbb\xbf'+table.getvalue().encode('utf-8')
    files['report.md']=_report(data).encode('utf-8');files['report.html']=_report(data,html=True).encode('utf-8')
    files['README.txt']=('请先完整解压到一个新目录，再打开report.html。\nresults.json保留各轮参数和原始结果；CSV是索引，不对数学结果作舍入。\n'
                         'manifest.json记录各文件SHA256；请保留ZIP旁的.sha256或对外记录的可信哈希。\n'
                         '本包不包含用户记忆、密钥、宿主配置、扩展源码或可自动生效的审批。不会自动重算或安装程序。\n').encode('utf-8')
    if len(files)>MAX_FILES or any((v.size if isinstance(v,Attachment) else len(v))>MAX_FILE_BYTES for v in files.values()) or sum(v.size if isinstance(v,Attachment) else len(v) for v in files.values())>MAX_BYTES:raise ValueError('Result bundle exceeds bounded export size; select a smaller turn scope')
    manifest={'format':'graph-research-results-manifest','version':1,'bundle_id':bundle_id,'files':{}}
    with staged_file(output) as temporary:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as bundle:
            for name,value in sorted(files.items()):
                _member(name)
                if isinstance(value,Attachment):
                    raw=_read(safe_path(value.path,root=session.directory/'tasks'))
                    if len(raw)!=value.size or hashlib.sha256(raw).hexdigest()!=value.sha256:raise ValueError('Artifact changed during export; no bundle was published')
                else:raw=value
                bundle.writestr(name,raw)
                manifest['files'][name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
            bundle.writestr('manifest.json',_json(manifest))
        verify_bundle(temporary)
    digest=file_hash(output)
    # ZIP publication is already atomic and independently verified. A sidecar
    # error must be visible but cannot erase a complete published archive.
    sidecar=str(output)+'.sha256'
    try:atomic_text(sidecar,digest+'  '+output.name+'\n')
    except OSError:sidecar=None
    return {'archive':str(output),'sha256':digest,'sha256_file':sidecar,'scope':data['scope'],
            'turn':turn,'summary':data['summary'],'warnings':warnings,'bundle_id':bundle_id}


@timed('bundle_verification')
def verify_bundle(archive,expected_sha256=None):
    """Read-only, bounded checksum verification. Never extracts or executes code."""
    digest=file_hash(archive)
    if expected_sha256 is not None and digest!=expected_sha256.lower():raise ValueError('Result ZIP differs from its trusted SHA256')
    with zipfile.ZipFile(io_path(archive)) as bundle:
        infos=bundle.infolist();names=[_member(info.filename) for info in infos]
        if len(names)>MAX_FILES+1 or len(names)!=len({name.casefold() for name in names}) or sum(i.file_size for i in infos)>MAX_BYTES+1024*1024:
            raise ValueError('Duplicate, oversized or excessive result-bundle entries')
        if any((i.external_attr>>16)&0o170000==0o120000 for i in infos):raise ValueError('Result bundle contains a symbolic link')
        if bundle.getinfo('manifest.json').file_size>1024*1024:raise ValueError('Result-bundle manifest too large')
        manifest=json.loads(bundle.read('manifest.json'))
        if manifest.get('format')!='graph-research-results-manifest' or manifest.get('version')!=1:raise ValueError('Unsupported results manifest')
        expected=manifest['files']
        if set(names)!=set(expected)|{'manifest.json'}:raise ValueError('Result-bundle inventory mismatch')
        required={'results.json','report.md','report.html','reproduce.json','calculations.csv','README.txt'}
        if not required<=set(expected):raise ValueError('Result bundle lacks required output files')
        for name,record in expected.items():
            if bundle.getinfo(name).file_size>MAX_FILE_BYTES:raise ValueError('Result-bundle file too large')
            raw=bundle.read(name)
            if len(raw)!=record['bytes'] or hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Result-bundle file checksum mismatch: '+name)
        data=json.loads(bundle.read('results.json'))
        if data.get('format')!='graph-research-results' or data.get('bundle_id')!=manifest['bundle_id']:raise ValueError('Results snapshot does not match its manifest')
        for call in data['calculations']:
            if any(name not in expected for name in call['artifacts']):raise ValueError('Results reference a missing artifact')
    return {'ok':True,'sha256':digest,'files_checked':len(expected),'summary':data['summary'],'bundle_id':manifest['bundle_id']}


def publish_result_view(archive,expected_sha256,directory):
    """Verify a pinned snapshot, then publish a fresh local read-only view.

    Re-render HTML from JSON with the current trusted template. Do not run
    archived HTML, import an extension, or recompute scientific results.
    The original ZIP is preserved; preview metadata identifies its source.
    """
    if not isinstance(expected_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',expected_sha256):raise ValueError('Viewing results requires a trusted result-bundle SHA256')
    checked=verify_bundle(archive,expected_sha256)
    destination=safe_path(Path(directory)/('view_'+uuid.uuid4().hex[:10]));destination.mkdir(parents=True,exist_ok=False)
    hashes={}
    with zipfile.ZipFile(archive) as bundle:
        manifest=json.loads(bundle.read('manifest.json'))
        if manifest['bundle_id']!=checked['bundle_id']:raise ValueError('Bundle changed during view publication')
        for info in bundle.infolist():
            name=_member(info.filename)
            if name in ('report.html','manifest.json'):continue
            raw=bundle.read(info);record=manifest['files'][name]
            if len(raw)!=record['bytes'] or hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Bundle changed during view publication')
            target=safe_path(destination/name,root=destination)
            with staged_file(target,root=destination) as temporary:temporary.write_bytes(raw)
            hashes[name]=record['sha256']
        data=json.loads(bundle.read('results.json'))
    if file_hash(archive)!=expected_sha256:raise ValueError('Bundle changed during view publication')
    html=_report(data,html=True)
    report=destination/'report.html';atomic_text(report,html)
    hashes['report.html']=hashlib.sha256(html.encode('utf-8')).hexdigest()
    metadata={'source_bundle_sha256':expected_sha256,'bundle_id':checked['bundle_id'],'report_regenerated_from_recorded_json':True,
              'model_calls':0,'calculations_reexecuted':0,'files_sha256':hashes}
    atomic_text(destination/'view.json',_json(metadata).decode('utf-8'))
    return {'html':str(report),'directory':str(destination),'source_bundle_sha256':expected_sha256,'bundle_id':checked['bundle_id']}
