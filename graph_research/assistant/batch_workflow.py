"""Bounded, declarative case templates and dependency-aware fixed workflows.

No expressions or arbitrary code are evaluated. Each compiled step remains a
normal protected tool attempt with its original limits, receipts and budget.
"""
import copy
import csv
import io
import json

import jsonschema

from .task_contract import TaskProtocolError,canonical,digest


def read_path(value,path,*,copy_value=True):
    """Read JSON keys/indices only; copy bound inputs, borrow values for previews."""
    for part in path:
        if isinstance(value,dict) and isinstance(part,str):value=value[part]
        elif isinstance(value,list) and type(part) is int:value=value[part]
        else:raise KeyError('JSON path type mismatch')
    return copy.deepcopy(value) if copy_value else value


def compile_batch(request):
    """Expand at most100 logical attempts, with a stable topological order."""
    batch=request['execution']['batch'];template=batch['steps'];cases=batch.get('cases',[{'id':'default','inputs':{}}])
    ids=[step['id'] for step in template];case_ids=[case['id'] for case in cases]
    if len(set(ids))!=len(ids) or len(set(case_ids))!=len(case_ids):raise TaskProtocolError('duplicate_batch_id','批量步骤ID和案例ID各自不能重复。')
    if len(template)*len(cases)>100:raise TaskProtocolError('batch_too_large','展开后的批量步骤最多100项；未执行计算。')
    dependencies={}
    for step_index,step in enumerate(template):
        deps=set(step.get('depends_on',[]))
        for name,binding in step.get('bindings',{}).items():
            if name in step['arguments']:raise TaskProtocolError('invalid_batch_binding','步骤 '+step['id']+' 的参数不能同时来自arguments和bindings。',
                field_path=['execution','batch','steps',step_index,'bindings',name],step_id=step['id'])
            if 'step' in binding:deps.add(binding['step'])
        if step['id'] in deps or deps-set(ids):raise TaskProtocolError('invalid_batch_dependency','批量依赖必须引用同一模板中的其他已声明步骤。')
        dependencies[step['id']]=deps
    ordered=[];remaining=template[:];known=set()
    while remaining:
        ready=[step for step in remaining if dependencies[step['id']]<=known]
        if not ready:raise TaskProtocolError('batch_dependency_cycle','批量步骤存在循环依赖。')
        for step in ready:ordered.append(step);known.add(step['id']);remaining.remove(step)
    for binding in batch.get('outputs',{}).values():
        if binding['step'] not in known:raise TaskProtocolError('invalid_batch_output','汇总输出引用了不存在的步骤。')
    expanded=[];expanded_bytes=2
    for case in cases:
        for step in ordered:
            args=copy.deepcopy(step['arguments']);bindings={}
            for name,binding in step.get('bindings',{}).items():
                if 'step' in binding:bindings[name]={'step':case['id']+'::'+binding['step'],'path':binding['path'][:]}
                else:
                    source=case['inputs'] if 'case' in binding else request.get('inputs',{})
                    try:args[name]=read_path(source,binding.get('case',binding.get('input')))
                    except (KeyError,IndexError):raise TaskProtocolError('batch_input_unavailable','案例 '+case['id']+' 的步骤 '+step['id']+' 缺少所绑定的输入字段。') from None
            compiled={'id':case['id']+'::'+step['id'],'tool':step['tool'],'arguments':args,'bindings':bindings,
                             '_case_id':case['id'],'_local_step_id':step['id'],
                             '_dependencies':[case['id']+'::'+dep for dep in ids if dep in dependencies[step['id']]]}
            expanded_bytes+=len(canonical(compiled).encode('utf-8'))+1
            if expanded_bytes>1024*1024:raise TaskProtocolError('batch_too_large','展开后的批量输入超过1MiB；请缩小案例或共享inputs。')
            expanded.append(compiled)
    plan={'steps':expanded,'case_ids':case_ids,'on_error':batch.get('on_error','stop'),'outputs':copy.deepcopy(batch.get('outputs',{}))}
    return {**plan,'plan_sha256':digest(plan)}


def preflight_batch(request,registry,policy):
    """Reject unknown/disallowed tools and malformed known inputs before work."""
    plan=compile_batch(request)
    for step in plan['steps']:
        name=step['tool'];allowed=policy['allowed_tools']
        if allowed is not None and name not in allowed:raise TaskProtocolError('tool_not_permitted','批量步骤使用了宿主未允许的工具：'+name)
        if name not in registry.tools:raise TaskProtocolError('tool_not_found','批量步骤引用了未安装的工具：'+name)
        schema=copy.deepcopy(registry.tools[name].parameters);properties=schema.get('properties',{})
        if set(step['bindings'])-set(properties):raise TaskProtocolError('invalid_batch_arguments','步骤 '+step['id']+' 绑定了未知参数。')
        schema['required']=[name for name in schema.get('required',[]) if name not in step['bindings']]
        try:jsonschema.validate(step['arguments'],schema)
        except jsonschema.ValidationError:raise TaskProtocolError('invalid_batch_arguments','步骤 '+step['id']+' 的已知参数不符合工具契约；请查看该工具Schema。') from None
    return plan


def initial_state(plan):
    """Initialize the durable ledger without claiming a tool has executed."""
    return {'plan_sha256':plan['plan_sha256'],'steps':{step['id']:{'status':'pending','attempted':False} for step in plan['steps']}}


def summary(request,state,record=None,*,plan=None):
    """Build bounded scalar/reference rows, keeping skips separate from attempts."""
    if request['execution']['mode']!='batch':return None
    if plan is None:plan=compile_batch(request)
    ledger=state.get('batch_workflow',{}).get('steps',{})
    paused=state.get('status') in ('cancelled','execution_error','recovery_required','budget_exhausted')
    observations=state.get('observations',[]);calls={o.get('step_id'):(i,o) for i,o in enumerate(observations) if 'tool' in o}
    rows=[];details=[]
    for step in plan['steps']:
        entry=ledger.get(step['id'],{});call=calls.get(step['id']);status=entry.get('status','pending')
        if call:status='success' if call[1].get('ok') else 'failed'
        elif paused and status=='running':status='interrupted'
        details.append({'step_id':step['id'],'case_id':step['_case_id'],'local_step_id':step['_local_step_id'],'tool':step['tool'],
                        'status':status,'depends_on':step['_dependencies'],
                        'attempted':call is not None or entry.get('attempted',False),
                        **({'call_id':f'call-{call[0]+1:04d}','elapsed_seconds':call[1].get('attempt_elapsed_seconds',0),
                            'reused':bool(call[1].get('reused_execution'))} if call else {}),
                        **({'reason':entry['reason']} if entry.get('reason') else {})})
    for case_id in plan['case_ids']:
        steps=[step for step in details if step['case_id']==case_id];statuses=[step['status'] for step in steps]
        case_status='success' if all(s=='success' for s in statuses) else 'pending' if all(s=='pending' for s in statuses) else 'paused' if paused and any(s in ('pending','running','interrupted') for s in statuses) else 'running' if any(s in ('pending','running') for s in statuses) else 'partial' if 'success' in statuses else 'failed'
        outputs={}
        for alias,binding in plan['outputs'].items():
            step_id=case_id+'::'+binding['step'];call=calls.get(step_id)
            if call is None or not call[1].get('ok'):
                outputs[alias]={'status':'unavailable','reason':'source_step_not_successful'};continue
            call_id=f'call-{call[0]+1:04d}'
            try:value=read_path(call[1]['result'],binding['path'],copy_value=False)
            except (KeyError,IndexError):
                outputs[alias]={'status':'unavailable','call_id':call_id,'reason':'output_path_unavailable'};continue
            output={'status':'available','call_id':call_id}
            if isinstance(value,(dict,list)) or len(canonical(value).encode('utf-8'))>128:output['value_location']='research_inspect_result or result bundle'
            else:output['value']=value
            outputs[alias]=output
        if case_status=='success' and any(o['status']=='unavailable' for o in outputs.values()):case_status='partial'
        rows.append({'case_id':case_id,'status':case_status,'outputs':outputs})
    counts={name:sum(step['status']==name for step in details) for name in ('pending','running','success','failed','skipped','interrupted')}
    return {'format':'graph-research-batch/1','plan_sha256':plan['plan_sha256'],'on_error':plan['on_error'],'output_definitions':plan['outputs'],
            'total_steps':len(details),'finished_steps':counts['success']+counts['failed']+counts['skipped'],
            'counts':counts,'attempted_steps':sum(step['attempted'] for step in details),
            'total_cases':len(rows),'successful_cases':sum(row['status']=='success' for row in rows),
            'rows':rows,'steps':details,'required_tool_attempts':len(details),
            'all_outputs_available':all(o['status']=='available' for row in rows for o in row['outputs'].values()),
            'accounting':'每个展开步骤分别计一次工具尝试；依赖跳过和预检失败不计计算，恢复不重置预算。'}


def summary_csv(batch):
    """Export scalar rows plus result locations, escaping spreadsheet formulas."""
    stream=io.StringIO(newline='');writer=csv.writer(stream)
    writer.writerow(['case_id','case_status','output','output_status','value','step_id','call_id','json_path','reason'])
    def cell(value):
        if type(value) in (int,float):return value
        if value is None:return 'null'
        if type(value) is bool:return 'true' if value else 'false'
        text=str(value)
        return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
    for row in batch['rows']:
        for alias,output in (row['outputs'] or {'':{}}).items():
            value=output.get('value',output.get('value_location',''))
            definition=batch['output_definitions'].get(alias,{})
            writer.writerow([cell(v) for v in (row['case_id'],row['status'],alias,output.get('status',''),value,
                row['case_id']+'::'+definition['step'] if definition else '',output.get('call_id',''),json.dumps(definition.get('path',[]),ensure_ascii=False),output.get('reason',''))])
    return b'\xef\xbb\xbf'+stream.getvalue().encode('utf-8')


def execute_batch(record,session,save):
    """Run a fixed plan under the caller's session lock; never execute Python text."""
    import time
    from graph_research.runtime.runner import run_tool
    from .results import _execution
    request=record['request'];registry=session._registry();plan=preflight_batch(request,registry,record['policy'])
    ledger=session.state.setdefault('batch_workflow',initial_state(plan))
    if ledger.get('plan_sha256')!=plan['plan_sha256']:raise TaskProtocolError('saved_batch_changed','已保存批量计划与当前任务不一致。')
    known={};states=ledger['steps'];stopping=False;record['phase']='batch_calculating';save(record)
    def persist():session._save();save(record)
    for index,step in enumerate(plan['steps']):
        if (session.directory/'.cancel').exists():raise InterruptedError('Task cancelled')
        step_id=step['id'];entry=states[step_id]
        previous=next((o for o in session.state['observations'] if o.get('step_id')==step_id),None)
        if previous and not previous.get('ok'):
            entry.update(status='failed',attempted=True)
            if plan['on_error']=='stop':stopping=True
            continue
        if entry['status'] in ('failed','skipped') and previous is None:
            if entry['status']=='failed' and plan['on_error']=='stop':stopping=True
            continue
        blocked=[dep for dep in step['_dependencies'] if states[dep]['status']!='success']
        if stopping or blocked:
            entry.update(status='skipped',attempted=False,reason='stopped_on_error' if stopping else 'dependency_not_successful: '+','.join(blocked))
            persist();continue
        args=copy.deepcopy(step['arguments'])
        try:
            for parameter,binding in step['bindings'].items():args[parameter]=read_path(known[binding['step']],binding['path'])
        except (KeyError,IndexError):
            if previous:raise TaskProtocolError('saved_step_changed','已完成步骤的绑定无法恢复，停止而不重算。') from None
            entry.update(status='failed',attempted=False,reason='binding_path_unavailable');persist()
            if plan['on_error']=='stop':stopping=True
            continue
        if previous:
            if previous['tool']!=step['tool'] or canonical(previous['arguments'])!=canonical(args):raise TaskProtocolError('saved_step_changed','已完成步骤输入发生变化。')
            if not previous.get('execution') or _execution(session,previous,'cached',False,[])[0]!='verified_execution':raise TaskProtocolError('saved_step_unverified','已完成批量步骤的执行回执无法核验，未重算。')
            previous['reused_execution']=True;entry.update(status='success',attempted=True);known[step_id]=previous['result'];persist();continue
        try:jsonschema.validate(args,registry.tools[step['tool']].parameters)
        except jsonschema.ValidationError:
            entry.update(status='failed',attempted=False,reason='bound_arguments_invalid');persist()
            if plan['on_error']=='stop':stopping=True
            continue
        session.execution_control.before_tool(step['tool'])
        entry.update(status='running',attempted=True);record['inflight_step']=step_id;persist()
        observation={'step_id':step_id,'case_id':step['_case_id'],'local_step_id':step['_local_step_id'],
                     'tool':step['tool'],'arguments':args};started=time.monotonic()
        try:
            result=run_tool(step['tool'],args,session.store.directory,directory=session.directory/'tasks',
                limits=session.execution_control.tool_limits,cancel_file=session.directory/'.cancel',include_receipt=True)
            observation.update(ok=True,result=result['result'],execution=result['execution'],tool_status=registry.tools[step['tool']].status)
        except InterruptedError:raise
        except Exception as exc:
            observation.update(ok=False,error=f"{getattr(exc,'error_type',None) or type(exc).__name__}: {exc}")
            from graph_research.runtime.observability import error_details
            observation['error_details']=error_details(exc,phase='batch.tool_execution')
            from .experience_evidence import failure_reference
            failed=failure_reference(session.directory/'tasks',exc)
            if failed:observation['failed_execution']=failed
        finally:
            elapsed=time.monotonic()-started;observation['attempt_elapsed_seconds']=elapsed
            metrics=record.setdefault('metrics',{});metrics['tool_attempt_seconds']=metrics.get('tool_attempt_seconds',0)+elapsed
        session.state['observations'].append(observation)
        entry.update(status='success' if observation['ok'] else 'failed',attempted=True)
        if not observation['ok']:entry['reason']='tool_execution_failed'
        session._observe_tools(registry);record.pop('inflight_step',None);record['cursor']=index+1;persist()
        if observation['ok']:known[step_id]=observation['result']
        elif plan['on_error']=='stop':stopping=True
    final=summary(request,session.state,record)
    complete=final['successful_cases']==final['total_cases']
    status='batch_complete' if complete else 'batch_partial' if final['counts']['success'] else 'batch_failed'
    session.state.update(status=status,answer=f"批量工作流已结束：{final['counts']['success']}步成功、{final['counts']['failed']}步失败、{final['counts']['skipped']}步跳过；未自动重试失败步骤。")
    session._save();session._finalize_output()
