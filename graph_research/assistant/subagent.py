"""Durable local subagent facade plus a separate trusted user-action portal.

No network server or parent-agent framework is assumed. The parent sees only
JSON tasks/results and event IDs. Authenticated user interaction is the host's
responsibility; never expose UserPortal methods as model tools.
"""
import copy
from datetime import datetime,timezone
import hashlib
import json
import sqlite3
from pathlib import Path
import uuid
import time

import jsonschema

from graph_research.runtime.integrity import assert_integrity
from graph_research.runtime.storage import safe_path,write_json,read_json,exclusive_lock
from graph_research.runtime.evidence import file_hash
from .host_events import HostEventStore
from .task_contract import PROTOCOL,RESULT_SCHEMA,TaskProtocolError,canonical,digest,check_id,validate_task,dispatch_schema
from .task_control import SubagentLimits,TaskExecutionControl,TaskControlError

TERMINAL={'completed','partial','analysis_only','failed','blocked','budget_exhausted','rejected','cleared'}


def now():return datetime.now(timezone.utc).isoformat()


class _Service:
    def __init__(self,directory,user_id,*,model_factory=None,limits=None,tool_directory=None,memory_directory=None,pricing=None,event_ttl=3600,results_directory=None):
        from graph_research.tools.change_control import external_directory
        from .memory import _user_key
        self.root=external_directory(directory);self.user_id=user_id;self.owner_key=_user_key(user_id)
        # Keep the storage namespace compact on Windows. Full owner digests
        # remain in records/events and are checked before access.
        self.directory=safe_path(self.root/'users'/self.owner_key[:32])
        self.tool_directory=external_directory(tool_directory or self.directory/'tool_packages')
        self.memory_directory=external_directory(memory_directory or self.root/'memory');self.pricing=pricing;self.model_factory=model_factory
        self.limits=limits or SubagentLimits()
        self.events=HostEventStore(self.root,self.owner_key,event_ttl)
        self.results_directory=external_directory(results_directory) if results_directory else None

    def task_dir(self,task_id):return safe_path(self.directory/'tasks'/check_id(task_id),root=self.directory)
    def record_path(self,task_id):return self.task_dir(task_id)/'task.json'
    def task_lock(self,task_id):return exclusive_lock(self.task_dir(task_id)/'.task.lock')

    def read(self,task_id):
        try:record,_=read_json(self.record_path(task_id),max_bytes=2*1024*1024)
        except (OSError,ValueError):raise TaskProtocolError('task_not_found','当前用户下没有该任务，或任务记录损坏。') from None
        if record.get('owner_key')!=self.owner_key or record.get('task_id')!=task_id:raise TaskProtocolError('task_not_found','当前用户下没有该任务。')
        return record

    def save(self,record,*,bump=True):
        if bump:record['revision']+=1;record['updated_at']=now()
        write_json(self.record_path(record['task_id']),record)

    def _remember_response(self,record):
        reference=record.get('response')
        if reference and reference not in record.setdefault('response_history',[]):record['response_history'].append(copy.deepcopy(reference))

    def check_host_policy(self,record):
        if not self.limits.accepts(record['policy']):raise TaskProtocolError('host_policy_changed','宿主已收紧执行策略；此任务不能沿用旧权限继续，请重新委派。')

    def context(self,record):
        request=record['request']
        result={key:request.get(key) for key in ('request_id','parent_task_id','objective','inputs','definitions','expected_outputs')}
        if request['execution']['mode']=='batch':result['execution']=copy.deepcopy(request['execution'])
        return result

    def session(self,record):
        from .session import ResearchSession
        control=TaskExecutionControl(record,self.save)
        return ResearchSession(self.task_dir(record['task_id'])/'session',self.tool_directory,self.pricing,
                               user_id=self.user_id,memory_directory=self.memory_directory,execution_control=control,task_context=self.context(record),results_directory=self.results_directory,results_mode='mcp')

    def snapshot_state(self,record):
        path=self.task_dir(record['task_id'])/'session/session.json'
        if not path.is_file():return {},None,None
        document,_=read_json(safe_path(path),recover=True)
        exports=document.get('exports',{})
        return document.get('state',{}),exports.get('latest'),exports.get('error')

    def build_result(self,record,session=None):
        if record['status']=='cleared':
            policy=record['policy'];usage=record['usage']
            return {'protocol':PROTOCOL,'task_id':record['task_id'],'request_id':record['request']['request_id'],
                'parent_task_id':record['request'].get('parent_task_id'),'revision':record['revision'],'status':'cleared','terminal':True,
                'answer':'此任务的计算文件已清理；任务编号和累计预算保留。可在成果中心回收区恢复。','results':[],
                'summary':{'successful_calls':0,'failed_calls':0,'verified_calls':0,'execution_complete':False,'mathematical_proof':False,
                    'result_id':record.get('cleared',{}).get('result_id')},'interaction':None,
                'budget':{'limits':policy,'used':dict(usage),'remaining':{k:max(0,policy['max_'+k]-usage[k]) for k in ('model_calls','tool_calls')}},
                'artifacts':[],'error':{'code':'task_cleared','message':'任务已清理，未重新计算。','retryable':False},'warnings':[],
                'next_actions':['get','restore_in_results_center','submit_new_task'],'updated_at':record['updated_at']}
        if session is None:state,bundle,export_error=self.snapshot_state(record)
        else:state,bundle,export_error=session.state,session.result_bundle,session.export_error
        results=[];inline_bytes=0
        for index,item in enumerate(state.get('observations',[])):
            if 'tool' not in item:continue
            entry={'call_id':f'call-{index+1:04d}','step_id':item.get('step_id'),'tool':item['tool'],'arguments':item.get('arguments',{}),
                   'status':'success' if item.get('ok') is True else 'failed','tool_status':item.get('tool_status','unknown')}
            for key in ('case_id','local_step_id'):
                if key in item:entry[key]=item[key]
            if item.get('ok') is True:
                data=item.get('result');size=len(canonical(data).encode('utf-8'));execution=item.get('execution',{})
                if execution.get('directory'):
                    receipt_path=safe_path(Path(execution['directory'])/'execution.json',root=self.task_dir(record['task_id'])/'session/tasks')
                    if file_hash(receipt_path)!=execution.get('receipt_sha256'):raise TaskProtocolError('receipt_changed','执行回执已变化，不能报告其成本或结果。')
                    receipt,_=read_json(receipt_path,max_bytes=1024*1024);entry['measurements']=receipt.get('measurements',{'available':False})
                    if receipt.get('diagnostic_id'):entry['diagnostic_id']=receipt['diagnostic_id']
                    if receipt.get('timings'):entry['timings']=receipt['timings']
                entry['verification']={'level':'host_recorded_execution','receipt_sha256':execution.get('receipt_sha256'),
                                       'meaning':'记录了实际计算；不构成一般数学证明。'}
                if size+inline_bytes<=1024*1024:entry['data']=data;inline_bytes+=size
                elif execution:
                    path=safe_path(Path(execution['directory'])/'result.json',root=self.task_dir(record['task_id'])/'session/tasks')
                    entry['data_ref']={'path':str(path),'sha256':file_hash(path),'json_field':'result'}
                else:entry['data_ref']={'result_bundle':bundle,'reason':'结果超过内联上限，请读取结果包。'}
            else:
                entry['error']=str(item.get('error','Tool call failed'))
                if item.get('error_details'):entry['error_details']=copy.deepcopy(item['error_details'])
            results.append(entry)
        successes=sum(r['status']=='success' for r in results);failures=len(results)-successes
        observations=state.get('observations',[])
        reused=sum(bool(o.get('reused_execution')) for o in observations)
        replays=0
        index=self.directory/'requests'/(hashlib.sha256(record['request']['request_id'].encode()).hexdigest()+'.json')
        try:
            if index.is_file():replays=read_json(index)[0].get('replays',0)
        except (OSError,ValueError):replays=0
        pending=copy.deepcopy(record.get('pending'))
        if pending:pending.update(task_id=record['task_id'],revision=record['revision'])
        usage=record['usage'];policy=record['policy']
        budget={'limits':policy,'used':dict(usage),'remaining':{kind:max(0,policy['max_'+kind]-usage[kind]) for kind in ('model_calls','tool_calls')},
                'accounting':'调用前预扣尝试数，含失败和中断；不是服务商账单token或费用。'}
        warnings=[];artifacts=[]
        from .results import export_issues
        missing_exports=export_issues(observations)
        if missing_exports:warnings.append('批量计算已返回原始数值，但部分文件导出未完成；请查看export_status/export_errors，不自动重新计算。')
        if record['request']['execution']['mode']=='batch':
            from .batch_workflow import compile_batch
            budget['required_tool_attempts']=len(compile_batch(record['request'])['steps'])
        if record['request']['execution']['mode']=='tools':
            from .spectral_scan import execution_steps
            required=len(execution_steps(record['request']))
            budget['required_tool_attempts']=required
            if required>policy['max_tool_calls']:
                warnings.append(f"固定步骤共需{required}次工具尝试，超过预算{policy['max_tool_calls']}；"
                                "将执行到预算用尽为止，超出步骤不会执行。如需整体拒绝，请在constraints中设置fail_fast=true。")
        if bundle:artifacts.append({'kind':'result_bundle','path':bundle['archive'],'sha256':bundle['sha256'],'summary':bundle['summary'],
            **{k:bundle[k] for k in ('artifact_id','result_id','result_name','project','results_root','availability') if k in bundle}})
        if export_error:warnings.append('计算记录已保留，结果包未完成：'+str(export_error))
        extension=state.get('extension_installed')
        if extension:
            path=safe_path(extension['archive'],root=self.tool_directory)
            if path.is_file():artifacts.append({'kind':'experimental_extension','path':str(path),'sha256':file_hash(path),'validation':'仅通过所列验收样例，需独立复核；接收文件不会自动安装。'})
        if any(r['tool_status']=='fixture_tested_experimental' for r in results):warnings.append('包含实验性扩展结果，仅通过登记的验收样例，不代表一般数学正确性。')
        if record.get('inflight_step') is not None and record['status'] in ('interrupted','cancelled'):warnings.append('中断时有一个步骤可能已开始；恢复不会自动发生，需由用户明确选择继续。')
        if record['status'] in ('waiting_for_user','waiting_for_approval'):actions=['get','resume_with_host_event','cancel']
        elif record['status'] in ('interrupted','cancelled'):actions=['get','resume_with_host_event','cancel']
        elif record['status'] in ('queued','running'):actions=['get','cancel','recover_if_host_process_stopped']
        else:actions=['get','submit_new_task']
        response={'protocol':PROTOCOL,'task_id':record['task_id'],'request_id':record['request']['request_id'],
                  'parent_task_id':record['request'].get('parent_task_id'),'revision':record['revision'],'status':record['status'],
                  'terminal':record['status'] in TERMINAL,'answer':state.get('answer',''),'results':results,
                  'summary':{'successful_calls':successes,'failed_calls':failures,'verified_calls':bundle['summary']['verified_calls'] if bundle else 0,
                             'execution_mode':record['request']['execution']['mode'],'fail_fast':record['request'].get('constraints',{}).get('fail_fast',False),
                             'claims':state.get('audited_claims',[]),'reused_calculations':reused,
                             'reuse':{'task_reused':replays,'steps_reused':reused,
                                      'steps_recomputed':sum(1 for o in observations if 'tool' in o and not o.get('reused_execution'))},
                             'execution_complete':record['status'] in ('completed','partial','analysis_only'), 'mathematical_proof':False,
                             'phase':record.get('phase',record['status']),'metrics':record.get('metrics',{}),
                             'experience_collection':record.get('experience_collection'),
                             'output_complete':not missing_exports and failures==0,'export_failures':missing_exports,
                             'main_agent_token_usage':None,'main_agent_usage_status':'not_supplied_by_trusted_host'},
                  'interaction':pending,'budget':budget,'artifacts':artifacts,'error':record.get('error'),
                  'warnings':warnings,'next_actions':actions,'updated_at':record['updated_at']}
        from .spectral_scan import scan_summary
        scan=scan_summary(record['request'],state.get('observations',[]))
        if scan is not None:response['summary']['scan']=scan
        from .batch_workflow import summary as batch_summary
        batch=batch_summary(record['request'],state,record)
        if batch is not None:response['summary']['batch']=batch
        jsonschema.validate(response,RESULT_SCHEMA)
        return self.resolve_artifacts(record,response)

    def resolve_artifacts(self,record,response):
        result=copy.deepcopy(response);session_directory=self.task_dir(record['task_id'])/'session';root=self.results_directory
        manifest=session_directory/'session.json'
        if manifest.is_file():
            document,_=read_json(manifest,max_bytes=16*1024*1024);root=document.get('exports',{}).get('results_root') or root
        if not root:return result
        from .result_catalog import resolve_bundle
        for artifact in result.get('artifacts',[]):
            if artifact.get('kind')!='result_bundle':continue
            located=resolve_bundle({**artifact,'archive':artifact['path']},source_directory=session_directory,results_root=root)
            artifact.update(path=located['archive'],**{k:located[k] for k in ('artifact_id','result_id','result_name','project','results_root','availability') if k in located})
            if located.get('availability','ready')!='ready':
                artifact['path']=None;result['warnings'].append('成果包当前不可用，可在成果中心查看或恢复；未自动重算。')
        return result

    def result(self,record):
        if record['status']=='cleared':return self.build_result(record)
        reference=record.get('response')
        if reference and record['status'] not in ('queued','running'):
            path=safe_path(self.task_dir(record['task_id'])/reference['path'],root=self.task_dir(record['task_id']))
            if file_hash(path)!=reference['sha256']:raise TaskProtocolError('response_corrupted','任务返回快照被修改，拒绝将其当成有效结果。')
            return self.resolve_artifacts(record,read_json(path)[0])
        return self.build_result(record)

    def finish(self,record,session):
        state=session.state;raw=state.get('status','execution_error');observations=state.get('observations',[])
        successful=any(i.get('ok') is True and 'tool' in i for i in observations)
        failed=any(i.get('ok') is False and 'tool' in i for i in observations)
        mapping={'batch_complete':'completed','batch_partial':'partial','batch_failed':'failed','recovery_required':'interrupted','manual_development_required':'blocked','awaiting_plan':'waiting_for_user','awaiting_clarification':'waiting_for_user','awaiting_approval':'waiting_for_approval','execution_error':'interrupted',
                 'cancelled':'cancelled','extension_rejected':'rejected','budget_exhausted':'budget_exhausted','blocked':'blocked','task_failed':'failed',
                 'approval_or_budget_required':'blocked','assessment_failed':'failed','extension_failed':'failed','awaiting_assessment':'blocked'}
        status=mapping.get(raw,'partial' if failed and successful else 'failed' if failed else 'completed' if successful or state.get('extension_installed') else 'analysis_only')
        if session.export_error and successful and status=='completed':status='partial'
        record['status']=status;record['phase']='finished' if status in TERMINAL else status;record['pending']=None
        control_error=state.get('control_error')
        if control_error:record['error']={**control_error,'retryable':False}
        elif status in ('interrupted','failed','blocked','budget_exhausted'):
            record['error']={'code':raw,'message':state.get('answer','未完成计算'),'retryable':status=='interrupted'}
        else:record['error']=None
        if status=='waiting_for_user':
            from .planning import plan_text
            questions=state.get('questions',[]) if raw!='awaiting_plan' else ['请查看以下已有工具计划，回复是否按此目标继续，或说明修改要求：\n'+plan_text(state['plan'])]
            record['pending']={'kind':'clarification','interaction_id':uuid.uuid4().hex,
                               'questions':[{'question_id':f'q{i+1}','text':q} for i,q in enumerate(questions)],
                               'host_actions':['answer'],'message':'请宿主将问题展示给用户；不要将主agent自行推测当作用户回复。'}
        elif status=='waiting_for_approval':
            assessment=state['assessment']
            record['pending']={'kind':'approval','interaction_id':uuid.uuid4().hex,'assessment_id':assessment['id'],
                               'scope_sha256':assessment['scope_sha256'],'assessment':assessment,'host_actions':['approve','reject','revise'],
                               'message':state['answer']}
        elif status in ('interrupted','cancelled'):
            record['pending']={'kind':'resume','interaction_id':uuid.uuid4().hex,'host_actions':['continue'],
                               'message':'该步骤没有可核验的完成回执；继续将确认重新执行未核验步骤，并保留前次预算。请明确展示给用户。' if raw=='recovery_required' else '任务已暂停；请由用户选择是否在原预算内继续。程序先核验执行记录，不确定步骤会另行等待重算确认。'}
            if record['request']['execution']['mode']=='batch':
                record['pending']['message']=('批量步骤 '+record['inflight_step']+' 可能已尝试但尚无可核验完成记录。选择继续将核验前序步骤，并重新执行未核验步骤；前次预算保留，重算另计一次尝试。请明确展示给用户。' if record.get('inflight_step') else
                    '批量任务已暂停。选择继续将复用已核验步骤并执行剩余步骤，前次预算保留；不会自动继续。')
        self.save(record)
        if 'experience_cursor' in record:
            from .experience_evidence import collect_task
            try:collect_task(self,record,session)
            except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                record['experience_cursor']=len(session.state.get('observations',[]))
                record['experience_collection']={'status':'storage_unavailable','created':0}
            self.save(record,bump=False)
        response=self.build_result(record,session)
        path=self.task_dir(record['task_id'])/'responses'/f"r{record['revision']}.json"
        write_json(path,response)
        reference={'path':path.relative_to(self.task_dir(record['task_id'])).as_posix(),'sha256':file_hash(path)}
        self._remember_response(record);record['response']=reference
        active=record.pop('active_event',None)
        if active:record['event_receipts'][active]={'state':'complete',**reference}
        self.save(record,bump=False)
        return response

    def model(self):
        if self.model_factory is not None:actual=self.model_factory()
        else:
            from .model import ConfiguredModel
            actual=ConfiguredModel()  # Machine interfaces never consume stdin for a key.
        class SafeModel:
            def __init__(self):self.actual=actual
            def complete(self,messages,*,max_output_tokens=None):
                import inspect
                options={'max_output_tokens':max_output_tokens} if max_output_tokens is not None and 'max_output_tokens' in inspect.signature(actual.complete).parameters else {}
                try:return actual.complete(messages,**options)
                except TaskControlError:raise
                except Exception as exc:
                    if type(exc).__module__ in ('graph_research.assistant.model','graph_research.assistant.model_config'):raise
                    raise RuntimeError('宿主模型适配器调用失败，原始异常未写入科研记录，以避免泄露凭据。') from None
        return SafeModel()

    def drive(self,record,action='start',payload=None,*,preserve_cancel=False):
        started=time.monotonic()
        self.check_host_policy(record)
        if action!='start' and not preserve_cancel:(self.task_dir(record['task_id'])/'session/.cancel').unlink(missing_ok=True)
        self._remember_response(record)
        record.update(status='running',phase='calculating',pending=None,response=None,error=None)
        self.save(record);session=self.session(record)
        try:
            if (action=='start' or preserve_cancel) and (session.directory/'.cancel').exists():
                if not session.state:
                    session.state={'question':record['request']['objective'],'conversation':[]};session._begin_turn(record['request']['objective'])
                raise InterruptedError('Task cancelled before execution')
            if record['request']['execution']['mode'] in ('tools','scan','batch'):self.run_steps(record,session)
            elif action=='start':session.ask(record['request']['objective'],self.model())
            elif action in ('answer','revise'):session.reply(payload['text'],self.model())
            elif action=='approve':session.approve(payload['assessment_id'],self.model())
            elif action=='reject':session.reject(payload['assessment_id'],payload.get('reason','用户拒绝本次开发'))
            elif action=='continue':
                if session.state.get('status')=='recovery_required':session.retry_uncertain_calculation(self.model())
                else:session.continue_run(self.model())
            else:raise TaskProtocolError('invalid_event','不支持的恢复操作。')
        except TaskControlError as exc:
            session.state.update(status=exc.status,answer=str(exc),control_error={'code':exc.code,'message':str(exc)})
            record['phase']='exporting';self.save(record);session._save();session._finalize_output()
        except (InterruptedError,KeyboardInterrupt):
            session.state.update(status='cancelled',answer='用户取消了该任务；已保存的计算保留。')
            session._save();session._finalize_output()
        except Exception as exc:
            # The built-in API adapter emits redacted errors. Unknown host
            # clients may include credentials in exception text; omit that text.
            from .model_config import ModelConfigurationError
            safe_message=str(exc) if isinstance(exc,(ModelConfigurationError,TaskProtocolError)) else f'{type(exc).__name__}：子任务执行中断，请检查宿主配置或保存的记录。'
            if not session.state:
                session.state={'question':record['request']['objective'],'conversation':[]};session._begin_turn(record['request']['objective'])
            session.state.update(status='task_failed' if isinstance(exc,TaskProtocolError) else 'execution_error',answer=safe_message)
            session._save();session._finalize_output()
        metrics=record.setdefault('metrics',{});metrics['execution_elapsed_seconds']=metrics.get('execution_elapsed_seconds',0)+time.monotonic()-started
        return self.finish(record,session)

    def run_steps(self,record,session):
        from graph_research.runtime.runner import run_tool
        from .results import _execution
        with exclusive_lock(session.directory/'.session.lock'):
            if not session.state:
                session.state={'question':record['request']['objective'],'conversation':[{'role':'user','content':record['request']['objective']}],
                               'observations':[],'delegated_task':self.context(record)}
                session._begin_turn(record['request']['objective'])
            # A queued task can be recovered/cancelled before its first tool
            # ever ran. Such a valid session has turns but no observations yet.
            session.state.setdefault('observations',[])
            session.state.setdefault('delegated_task',self.context(record))
            session._cancel.clear()
            session.state.pop('control_error',None);session.state.update(status='running',answer='正在按固定步骤计算。');session._save()
            if record['request']['execution']['mode']=='batch':
                from .batch_workflow import execute_batch
                execute_batch(record,session,self.save);return
            registry=session._registry();known={}
            from .spectral_scan import execution_steps
            scanning=record['request']['execution']['mode']=='scan'
            for index,step in enumerate(execution_steps(record['request'])):
                args=copy.deepcopy(step['arguments'])
                for parameter,binding in step.get('bindings',{}).items():
                    if 'input' in binding:value=record['request']['inputs'];path=binding['input']
                    else:
                        if binding['step'] not in known:raise TaskProtocolError('binding_unavailable','引用的前序步骤没有有效结果。')
                        value=known[binding['step']];path=binding['path']
                    try:
                        for component in path:
                            if isinstance(value,dict) and isinstance(component,str):value=value[component]
                            elif isinstance(value,list) and type(component) is int:value=value[component]
                            else:raise TaskProtocolError('invalid_binding','绑定路径只能读取JSON对象键或列表索引。')
                    except (KeyError,IndexError):raise TaskProtocolError('binding_unavailable','前序结果中没有所需的参数绑定路径。') from None
                    args[parameter]=copy.deepcopy(value)
                for candidate in step.get('_warm_candidates',[]):
                    if candidate in known and known[candidate].get('perron_vector') is not None:
                        args['initial_vector']=copy.deepcopy(known[candidate]['perron_vector']);break
                failed=next((o for o in session.state['observations'] if o.get('step_id')==step['id'] and o.get('ok') is False),None)
                if scanning and failed:
                    if not record['request']['execution']['scan'].get('continue_on_error',True):break
                    continue
                previous=next((o for o in session.state.get('observations',[]) if o.get('step_id')==step['id'] and o.get('ok') is True),None)
                if previous is not None:
                    if previous['tool']!=step['tool'] or canonical(previous['arguments'])!=canonical(args):raise TaskProtocolError('saved_step_changed','保存的步骤与当前固定任务不一致。')
                    if not previous.get('execution') or _execution(session,previous,'cached',False,[])[0]!='verified_execution':raise TaskProtocolError('saved_step_unverified','保存步骤没有可验证的执行回执。')
                    previous['reused_execution']=True
                    known[step['id']]=previous['result'];record['cursor']=index+1;record.pop('inflight_step',None);self.save(record);continue
                if (session.directory/'.cancel').exists():raise InterruptedError('Task cancelled')
                session.execution_control.before_tool(step['tool'])
                record['inflight_step']=step['id'];self.save(record)
                observation={'step_id':step['id'],'tool':step['tool'],'arguments':args};tool_started=time.monotonic()
                try:
                    value=run_tool(step['tool'],args,self.tool_directory,directory=session.directory/'tasks',limits=session.execution_control.tool_limits,
                                   cancel_file=session.directory/'.cancel',include_receipt=True)
                    observation.update(ok=True,result=value['result'],execution=value['execution'],tool_status=registry.tools[step['tool']].status)
                except InterruptedError:raise
                except Exception as exc:
                    observation.update(ok=False,error=f"{getattr(exc,'error_type',None) or type(exc).__name__}: {exc}")
                    from graph_research.runtime.observability import error_details
                    observation['error_details']=error_details(exc,phase='subagent.tool_execution')
                    from .experience_evidence import failure_reference
                    failed=failure_reference(session.directory/'tasks',exc)
                    if failed:observation['failed_execution']=failed
                finally:
                    elapsed=time.monotonic()-tool_started;observation['attempt_elapsed_seconds']=elapsed
                    metrics=record.setdefault('metrics',{});metrics['tool_attempt_seconds']=metrics.get('tool_attempt_seconds',0)+elapsed
                session.state['observations'].append(observation);session._observe_tools(registry);session._save()
                record.pop('inflight_step',None);self.save(record)
                if not observation['ok']:
                    session.state.update(status='tool_execution_failed',answer='固定步骤执行失败，已保留前序结果；未自动重试。')
                    if scanning and step['id']!='scan-graph' and record['request']['execution']['scan'].get('continue_on_error',True):continue
                    break
                known[step['id']]=observation['result'];record['cursor']=index+1;self.save(record)
            else:session.state.update(status='tool_results_available',answer='固定计算步骤已完成，结果及执行回执已保存。')
            session._save();session._finalize_output()


class GraphResearchSubagent:
    """Parent-facing API. It cannot mint user answers or development approvals."""
    def __init__(self,service):self._service=service

    def submit(self,task,*,defer=False):
        """Register idempotently; defer=True leaves execution to a trusted worker."""
        service=self._service;request=validate_task(task);policy=service.limits.resolve(request)
        request_hash=digest(request);index=service.directory/'requests'/(hashlib.sha256(request['request_id'].encode()).hexdigest()+'.json')
        with exclusive_lock(service.directory/'.requests.lock'):
            if index.exists():
                previous,_=read_json(index)
                if previous['request_sha256']!=request_hash:raise TaskProtocolError('request_id_conflict','同一request_id不能对应不同输入、定义、步骤或预算。')
                # Replays are counted in the request index (not the frozen task
                # record) so revision/updated_at still prove nothing recomputed.
                previous['replays']=previous.get('replays',0)+1
                write_json(index,previous)
                response=self.get(previous['task_id'])
                # The frozen snapshot still proves the original artifacts; only
                # the replay counter is refreshed on top of it.
                summary=response.get('summary',{})
                if isinstance(summary,dict):
                    reuse=dict(summary.get('reuse',{}));reuse['task_reused']=previous['replays']
                    summary['reuse']=reuse;response['summary']=summary
                return response
            assert_integrity()
            if request['execution']['mode']=='batch':
                from graph_research.tools import ToolRegistry
                from graph_research.tools.extensions import ToolStore
                from .batch_workflow import preflight_batch
                registry=ToolRegistry();ToolStore(service.tool_directory).load_into(registry)
                preflight_batch(request,registry,policy)
            task_id=uuid.uuid4().hex
            record={'version':1,'owner_key':service.owner_key,'task_id':task_id,'request':request,'request_sha256':request_hash,
                    'policy':policy,'usage':{'model_calls':0,'tool_calls':0},'approved_tools':[],'revision':1,
                    'status':'queued','pending':None,'created_at':now(),'updated_at':now(),'event_receipts':{},'cursor':0,'experience_cursor':0}
            write_json(service.record_path(task_id),record);write_json(index,{'task_id':task_id,'request_sha256':request_hash})
        if defer:return service.result(record)
        return self.start_queued(task_id)

    def start_queued(self,task_id):
        """Trusted scheduler entry; only starts a newly registered queued task."""
        service=self._service;task_id=check_id(task_id)
        with service.task_lock(task_id):
            # A host may cancel/recover the queued task before this lock is
            # acquired. Never run the stale in-memory queued record afterward.
            record=service.read(task_id)
            if record['status']!='queued':return service.result(record)
            return service.drive(record)

    def get(self,task_id):return self._service.result(self._service.read(check_id(task_id)))

    def resume(self,task_id,event_id,*,preserve_cancel=False):
        service=self._service;task_id=check_id(task_id);event_id=check_id(event_id)
        with service.task_lock(task_id):
            record=service.read(task_id)
            if record['status']=='cleared':raise TaskProtocolError('task_cleared','任务已清理，请在成果中心恢复，不能自动继续。')
            if (service.task_dir(task_id)/'session/.results-cleanup.json').exists():raise TaskProtocolError('cleanup_in_progress','任务正在清理或需要恢复清理记录。')
            replay=record['event_receipts'].get(event_id)
            if replay:
                if replay['state']!='complete':return service.result(record)
                path=safe_path(service.task_dir(task_id)/replay['path'],root=service.task_dir(task_id))
                if file_hash(path)!=replay['sha256']:raise TaskProtocolError('response_corrupted','事件对应的返回快照已损坏。')
                return service.resolve_artifacts(record,read_json(path)[0])
            service.check_host_policy(record)
            event=service.events.read(event_id)
            pending=record.get('pending')
            if event['task_id']!=task_id or event['request_sha256']!=record['request_sha256']:raise TaskProtocolError('event_scope_mismatch','用户操作属于另一个任务或另一份输入。')
            if not pending or event['revision']!=record['revision'] or event['interaction_id']!=pending['interaction_id']:
                raise TaskProtocolError('stale_interaction','任务已变化，旧回复或旧批准不能继续使用；请重新获取当前交互。')
            kind=event['kind'];payload=event['payload']
            if kind not in pending['host_actions']:raise TaskProtocolError('event_not_allowed','当前状态不能使用这类用户操作。')
            if kind in ('approve','reject'):
                if payload.get('assessment_id')!=pending['assessment_id'] or payload.get('scope_sha256')!=pending['scope_sha256']:
                    raise TaskProtocolError('approval_scope_mismatch','批准范围或评估ID不一致。')
            if kind=='approve':
                if record['usage']['model_calls']>=record['policy']['max_model_calls']:raise TaskProtocolError('task_budget_exhausted','任务模型预算已用尽，批准不能增加预算；请重新委派。')
                record['approved_tools'].append(pending['assessment']['request']['name'])
            record['event_receipts'][event_id]={'state':'in_progress'};record['active_event']=event_id
            return service.drive(record,kind,payload,preserve_cancel=preserve_cancel)

    def cancel(self,task_id):
        service=self._service;record=service.read(check_id(task_id))
        if record['status'] in TERMINAL or record['status']=='cancelled':return service.result(record)
        session_path=service.task_dir(task_id)/'session'
        from graph_research.runtime.storage import atomic_text
        atomic_text(session_path/'.cancel','cancel',overwrite=True)
        if record['status']=='running':
            response=service.build_result(record);response['warnings'].append('已请求取消；远程模型请求可能需等待返回或网络超时。');return response
        try:
            with service.task_lock(task_id):
                record=service.read(task_id)
                # The worker may have finished while cancellation waited for
                # the task lock. Never overwrite or re-export its final state.
                if record['status'] in TERMINAL or record['status']=='cancelled':return service.result(record)
                session=service.session(record)
                if not session.state:
                    session.state={'question':record['request']['objective'],'conversation':[]};session._begin_turn(record['request']['objective'])
                session.state.update(status='cancelled',answer='任务已取消，未自动继续模型或开发。')
                session._save();session._finalize_output()
                return service.finish(record,session)
        except RuntimeError:
            response=service.build_result(service.read(task_id));response['warnings'].append('取消请求已记录，正在等待当前执行停下。');return response

    def recover(self,task_id):
        """Mark an orphaned run interrupted; never rerun a model or calculation."""
        service=self._service;task_id=check_id(task_id)
        with service.task_lock(task_id):
            record=service.read(task_id)
            if record['status'] not in ('queued','running'):return service.result(record)
            session=service.session(record)
            if not session.state:
                session.state={'question':record['request']['objective'],'conversation':[]};session._begin_turn(record['request']['objective'])
            session.state.update(status='execution_error',answer='宿主进程中断，已恢复持久化记录；需由用户明确选择继续，未自动重算。')
            session._save();session._finalize_output()
            return service.finish(record,session)

    def dispatch(self,message):
        """JSON adapter for parent frameworks; the schema has no approval action."""
        try:
            if len(canonical(message).encode('utf-8'))>256*1024:raise ValueError()
            jsonschema.validate(message,dispatch_schema())
            operation=message['operation']
            if operation=='submit':return self.submit(message['task'])
            if operation=='resume':return self.resume(message['task_id'],message['event_id'])
            return getattr(self,operation)(message['task_id'])
        except (jsonschema.ValidationError,ValueError,TypeError,RecursionError) as exc:
            error=exc if isinstance(exc,TaskProtocolError) else TaskProtocolError('invalid_message','父agent消息格式无效；不能直接传入批准、用户角色或任意执行命令。')
            return {'protocol':PROTOCOL,'status':'protocol_error','error':{'code':error.code,'message':str(error)}}
        except (RuntimeError,OSError):
            return {'protocol':PROTOCOL,'status':'protocol_error','error':{'code':'task_busy_or_host_io_error','message':'任务正在执行或宿主存储暂不可用；请先查询状态，不要换request_id重复提交。'}}


class SubagentUserPortal:
    """TRUSTED HOST ONLY. Call after receiving an authenticated human UI action.

    A method call is the local trust boundary, not proof of a human by itself.
    Never give this object or its methods to the parent model's tool registry.
    """
    def __init__(self,service):self._service=service

    def _issue(self,task_id,interaction_id,expected_revision,kind,payload,event_id):
        service=self._service;task_id=check_id(task_id);check_id(interaction_id)
        with service.task_lock(task_id):
            record=service.read(task_id);pending=record.get('pending')
            if not pending or type(expected_revision) is not int or record['revision']!=expected_revision or pending['interaction_id']!=interaction_id:
                raise TaskProtocolError('stale_interaction','用户看到的交互已失效，请先刷新任务再操作。')
            if kind not in pending['host_actions']:raise TaskProtocolError('event_not_allowed','当前没有等待这类用户操作。')
            if kind in ('approve','reject') and (payload.get('assessment_id')!=pending['assessment_id'] or payload.get('scope_sha256')!=pending['scope_sha256']):
                raise TaskProtocolError('approval_scope_mismatch','必须确认当前评估ID及其准确范围。')
            return service.events.issue(record,kind,payload,event_id=event_id)

    def answer(self,task_id,interaction_id,expected_revision,text,*,event_id=None):
        if not isinstance(text,str) or not text.strip() or len(text)>20000:raise TaskProtocolError('invalid_answer','用户补充需为非空文本，最多20000字符。')
        record=self._service.read(check_id(task_id))
        kind='revise' if (record.get('pending') or {}).get('kind')=='approval' else 'answer'
        return self._issue(task_id,interaction_id,expected_revision,kind,{'text':text},event_id)

    def approve(self,task_id,interaction_id,expected_revision,assessment_id,scope_sha256,*,event_id=None):
        return self._issue(task_id,interaction_id,expected_revision,'approve',{'assessment_id':assessment_id,'scope_sha256':scope_sha256},event_id)

    def reject(self,task_id,interaction_id,expected_revision,assessment_id,scope_sha256,reason='用户拒绝本次开发',*,event_id=None):
        if not isinstance(reason,str) or len(reason)>2000:raise TaskProtocolError('invalid_reason','拒绝理由最多2000字符。')
        return self._issue(task_id,interaction_id,expected_revision,'reject',{'assessment_id':assessment_id,'scope_sha256':scope_sha256,'reason':reason},event_id)

    def continue_task(self,task_id,interaction_id,expected_revision,*,event_id=None):
        return self._issue(task_id,interaction_id,expected_revision,'continue',{},event_id)


def create_subagent(directory,*,user_id,model_factory=None,limits=None,tool_directory=None,memory_directory=None,pricing=None,event_ttl=3600,results_directory=None):
    """Return (parent_facade, trusted_user_portal); keep the portal out of tools."""
    service=_Service(directory,user_id,model_factory=model_factory,limits=limits,tool_directory=tool_directory,
                     memory_directory=memory_directory,pricing=pricing,event_ttl=event_ttl,results_directory=results_directory)
    return GraphResearchSubagent(service),SubagentUserPortal(service)
