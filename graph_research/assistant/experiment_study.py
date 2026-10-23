"""Reviewed adaptive study execution; all search/training lives in protected jobs."""
import copy
import json
import math
import re
import uuid

from graph_research.errors import TaskProtocolError
from graph_research.runtime.storage import exclusive_lock,safe_path,read_json
from graph_research.runtime.evidence import file_hash
from graph_research.runtime.integrity import assert_integrity
from graph_research.runtime.runner import TaskLimits,run_worker
from graph_research.experiments.search_contract import compile_study,OPERATION
from graph_research.experiments.execution_contract import digest
from graph_research.experiments.search_engine import verify_round
from graph_research.experiments.controller import eligible,latest,propose,model_action,checked_action,feedback
from graph_research.experiments.interpretation import analyze
from .experiment_execution import _charges,_settle
from .task_control import TaskControlError


def _settings(spec):return {key:spec[key] for key in ('max_edges','max_actions','edge_sizes') if key in spec}


def arguments_for(compiled,decision,results):
    run=next((r for r in compiled['runs'] if r['id']==decision['run_id']),None)
    if run is None:raise TaskProtocolError('study_scope_changed','检查点包含未授权实例。')
    previous=latest(results,run['id']);round_number=previous['round']+1 if previous else 1
    if decision['round']!=round_number or round_number>compiled['spec']['rounds']:raise TaskProtocolError('study_checkpoint_changed','搜索轮数缺失、重复或超范围。')
    checked_action({'action':'run','run_id':run['id'],'knobs':decision['knobs'],'reason':decision['reason']},compiled,results)
    return {'problem':compiled['spec']['problem'],'run':run,'settings':_settings(compiled['spec']),'knobs':decision['knobs'],
            'round':round_number,'checkpoint':previous['checkpoint'] if previous else None,'limit':compiled['spec']['batch_size']}


def receipt(session,attempt,arguments):
    if not attempt.get('receipt_sha256'):return None
    directory=safe_path(session.directory/'tasks'/('task_'+attempt['id']),root=session.directory/'tasks')
    if file_hash(directory/'execution.json')!=attempt['receipt_sha256']:raise TaskProtocolError('study_receipt_changed','搜索回执已变化。')
    value,_=read_json(directory/'execution.json',max_bytes=1024*1024)
    if value.get('kind')!='experiment' or value.get('status')!='complete' or value.get('core_manifest_sha256')!=attempt['core_sha256']:raise TaskProtocolError('study_receipt_changed','搜索回执版本或状态无效。')
    for name in ('request','result'):
        if file_hash(directory/(name+'.json'))!=value[name+'_sha256']:raise TaskProtocolError('study_evidence_changed','原始搜索输入或结果变化。')
    request,_=read_json(directory/'request.json',max_bytes=256*1024);payload,_=read_json(directory/'result.json',max_bytes=4*1024*1024)
    if request.get('name')!=OPERATION or digest(request.get('arguments'))!=digest(arguments) or payload.get('ok') is not True:raise TaskProtocolError('study_evidence_changed','搜索证据不属于固定输入。')
    verify_round(arguments,payload['result'])
    return {'result':payload['result'],'execution':{'directory':str(directory),'task_id':directory.name,'receipt_sha256':attempt['receipt_sha256']}},value


def history(compiled,ledger,session):
    from .results import _execution
    results=[];observations={}
    for item in session.state.get('observations',[]):
        if item.get('tool')!=OPERATION or not item.get('ok'):continue
        key=item.get('experiment_job_id')
        if key in observations:raise TaskProtocolError('study_checkpoint_changed','重复的搜索成功记录。')
        observations[key]=item
    gap=False
    if len(ledger['decisions'])>len(observations)+1:raise TaskProtocolError('study_checkpoint_changed','搜索历史包含多个未完成决策。')
    for decision in ledger['decisions']:
        item=observations.get(decision['id'])
        if item is None:gap=True;continue
        if gap:raise TaskProtocolError('study_checkpoint_changed','搜索历史中有缺段。')
        arguments=arguments_for(compiled,decision,results)
        if digest(arguments)!=digest(item['arguments']):raise TaskProtocolError('study_checkpoint_changed','搜索历史与批准范围不一致。')
        if _execution(session,item,'study',False,[])[0]!='verified_execution':raise TaskProtocolError('study_checkpoint_changed','搜索历史缺少有效证据。')
        matches=[a for a in ledger['attempts'] if a['job']==decision['id'] and a.get('receipt_sha256')==item['execution']['receipt_sha256']]
        if len(matches)!=1:raise TaskProtocolError('study_checkpoint_changed','搜索历史未关联唯一宿主回执。')
        attempt=matches[0];_,proof=receipt(session,attempt,arguments);_settle(attempt,proof);attempt['state']='complete'
        results.append(item['result'])
    if len(observations)!=len(results):raise TaskProtocolError('study_checkpoint_changed','搜索成功记录不在固定决策账本中。')
    return results


def validate_ledger(ledger,compiled,record,core):
    try:
        if ledger['identity']!=compiled['request_sha256'] or ledger['core_sha256']!=core or ledger['budget']!=compiled['spec']['budget']:raise ValueError()
        if type(ledger['approved']) is not bool or len(ledger['attempts'])!=record['usage']['tool_calls']:raise ValueError()
        if ledger['approved'] and ledger['approval_event_id'] not in record.get('event_receipts',{}):raise ValueError()
        ids=set();jobs={d['id'] for d in ledger['decisions']}
        if len(jobs)!=len(ledger['decisions']) or len(jobs)>compiled['planned_rounds']:raise ValueError()
        for a in ledger['attempts']:
            if not re.fullmatch('[0-9a-f]{32}',a['id']) or a['id'] in ids or a['job'] not in jobs or a['core_sha256']!=core:raise ValueError()
            ids.add(a['id'])
            if a['evaluations']!=compiled['spec']['batch_size'] or type(a['settled']) is not bool:raise ValueError()
            for key in ('wall_charge','cpu_charge','wall_limit','cpu_limit'):
                if type(a[key]) not in (int,float) or not math.isfinite(a[key]) or a[key]<0:raise ValueError()
            if not a['settled'] and (a['wall_charge']!=a['wall_limit'] or a['cpu_charge']!=a['cpu_limit']):raise ValueError()
            if a.get('receipt_sha256') is not None and not re.fullmatch('[0-9a-f]{64}',a['receipt_sha256']):raise ValueError()
        if not ledger['approved'] and (ledger['attempts'] or ledger['decisions']):raise ValueError()
    except (ValueError,KeyError,TypeError):raise TaskProtocolError('study_checkpoint_changed','研究范围、账本或批准事件无效，拒绝继续。') from None


def summary(compiled,ledger,results,complete=False):
    interpretation=analyze(compiled,results,ledger['hypotheses']);rows=[{'run_id':r['run_id'],'round':r['round'],**row} for r in results for row in r['rows']]
    decisions={d['id']:d for d in ledger['decisions']}
    for run in interpretation['run_statistics']:
        attempts=[a for a in ledger['attempts'] if decisions[a['job']]['run_id']==run['run_id']]
        run['worker_wall_seconds']=sum(a['wall_charge'] for a in attempts);run['worker_cpu_seconds']=sum(a['cpu_charge'] for a in attempts)
        memories=[a['peak_job_memory_bytes'] for a in attempts if 'peak_job_memory_bytes' in a]
        run['peak_job_memory_bytes']=max(memories) if memories else None
        run['cost_meaning']='Includes conservative reservations for failed/uncertain attempts; absent memory is unavailable, not zero.'
    cases=[]
    for case in compiled['spec']['cases']:
        ids={r['id'] for r in compiled['runs'] if r['case_id']==case['id']};rs=[r for r in rows if r['run_id'] in ids]
        cases.append({'case_id':case['id'],'parameters':case['parameters'],'evaluated':len(rs),'feasible':sum(r['feasible'] for r in rs)})
    return {'phase':7,'operation':'study','scope':'reviewed_finite_parameter_cases_and_search_budgets','approved':ledger['approved'],
        'study_complete':complete,'collection_complete':False,'jobs_completed':len(results),'jobs_total':compiled['planned_rounds'],
        'evaluations_completed':len(rows),'cases':cases,'rows':rows,'attempts':copy.deepcopy(ledger['attempts']),
        'budget':{'limits':ledger['budget'],**_charges(ledger),'meaning':'Evaluation reservations include failed/uncertain attempts and unused slots in a terminal enumeration batch. Time measures active workers; host analysis/export overhead is excluded.'},
        'decisions':copy.deepcopy(ledger['decisions']),'feedback':copy.deepcopy(ledger['feedback']),'interpretation':interpretation,
        'search_performed':bool(results),'training_performed':any(r['training_performed'] for r in results),
        'enumeration_complete':False,'general_theorem_proved':False,'stop_reason':ledger.get('stop_reason')}


def run_study(record,session,save,model_factory,*,action='start',payload=None):
    compiled=compile_study(record['request']['execution']['experiment']);spec=compiled['spec']
    with exclusive_lock(session.directory/'.session.lock'):
        core=assert_integrity()['manifest_sha256']
        if not session.state:
            session.state={'question':record['request']['objective'],'observations':[],'conversation':[]};session._begin_turn(record['request']['objective'])
        session.state.setdefault('observations',[]);session.state['delegated_task']=session.task_context
        ledger=record.get('study_ledger')
        if ledger is None:
            ledger={'identity':compiled['request_sha256'],'core_sha256':core,'budget':spec['budget'],'approved':False,'approval_event_id':None,
                'attempts':[],'decisions':[],'feedback':[],'hypotheses':copy.deepcopy(spec['hypotheses']),'knobs':dict(spec['knobs']),'focus_runs':[]}
            record['study_ledger']=ledger;save(record)
        validate_ledger(ledger,compiled,record,core)
        if not ledger['approved']:
            if action=='continue' and session.state.get('status')=='awaiting_experiment_review' and record.get('active_event'):
                ledger.update(approved=True,approval_event_id=record['active_event']);save(record)
            else:
                session.state.update(status='awaiting_experiment_review',answer='请审阅有限参数范围、搜索方法／种子、轮数、评价及时间预算。确认前不搜索或训练。',
                    experiment_review={'problem':spec['problem'],'runs':compiled['runs'],'planned_rounds':compiled['planned_rounds'],
                        'max_evaluations':compiled['planned_evaluations'],'budget':spec['budget'],'knob_intervals':{'exploration':[0.01,0.5],'elite_fraction':[0.1,0.75],'penalty_weight':[0.1,10]},
                        'scope_sha256':compiled['request_sha256'],'meaning':'Only these finite cases/methods/seeds and bounded guidance changes. Scope/budget expansion needs a new review.'})
                session.state['experiment_execution']=summary(compiled,ledger,[]);session._save();session._finalize_output();return
        results=history(compiled,ledger,session)
        def persist(complete=False):
            session.state['experiment_execution']=summary(compiled,ledger,results,complete);session._save();save(record)
        if action=='study_feedback':
            update=feedback(payload,compiled)
            known={h['id'] for h in ledger['hypotheses']}
            for h in update.get('hypotheses',[]):
                if h['id'] in known:raise TaskProtocolError('hypothesis_id_conflict','修改假设请使用新ID，旧检验记录保留。')
                known.add(h['id'])
            if len(known)>16:raise TaskProtocolError('hypothesis_limit','单个研究任务最多16条累计假设。')
            ledger['feedback'].append({'event_id':record['active_event'],**update})
            ledger['knobs'].update(update.get('knobs',{}));ledger['focus_runs']=update.get('focus_runs',ledger['focus_runs'])
            ledger['hypotheses'].extend(update.get('hypotheses',[]))
        session.state.update(status='running',answer='在已确认范围和累计预算内分段搜索、核验和诊断。')
        processed=0
        try:
            while True:
                if (session.directory/'.cancel').exists():raise InterruptedError()
                if len(ledger['decisions'])>len(results):decision=ledger['decisions'][len(results)]
                else:
                    if not eligible(compiled,results):
                        ledger['stop_reason']='授权实例达到轮数或枚举终点。';break
                    spent=_charges(ledger)
                    if spent['evaluation_reservations']+spec['batch_size']>spec['budget']['max_evaluations'] or spent['wall_seconds']>=spec['budget']['wall_seconds'] or spent['cpu_seconds']+1>spec['budget']['cpu_seconds']:
                        raise TaskControlError('study_budget_exhausted','累计资源不足，未继续消耗模型调用安排新实验。','budget_exhausted')
                    if record['usage']['tool_calls']>=record['policy']['max_tool_calls']:raise TaskControlError('task_budget_exhausted','工具预算不足，未继续调用规划模型。','budget_exhausted')
                    if spec['planner']=='model':
                        session.execution_control.before_model()
                        resources={'limits':spec['budget'],'spent':spent,'host_usage':record['usage'],
                            'recent_attempts':[{k:a[k] for k in ('job','wall_charge','cpu_charge','state')} for a in ledger['attempts'][-8:]]}
                        try:choice=model_action(model_factory(),compiled,results,ledger['knobs'],resources)
                        except Exception as error:
                            ledger['feedback'].append({'kind':'planner_rejected','exception':type(error).__name__})
                            session.state.update(status='awaiting_experiment_continue',answer='规划建议无效或模型调用失败，未执行搜索；已消耗的模型尝试保留。请检查后由用户选择继续。');persist();session._finalize_output();return
                    else:choice=checked_action(propose(compiled,results,ledger['knobs'],ledger['focus_runs']),compiled,results)
                    if choice['action']!='run':
                        ids=[h['id'] for h in ledger['hypotheses']+choice.get('hypotheses',[])]
                        if len(ids)>16 or len(ids)!=len(set(ids)):raise TaskProtocolError('hypothesis_limit','模型提出的假设ID重复或超过累计上限。')
                        ledger['hypotheses'].extend(choice.get('hypotheses',[]))
                        if choice['action']=='request_scope_change':
                            session.state.update(status='awaiting_experiment_continue',answer='规划器建议改变范围：'+choice['reason']+'。扩大范围须取消并新建任务；继续只允许原范围。')
                            ledger['feedback'].append({'kind':'scope_change_requested','reason':choice['reason']});persist();session._finalize_output();return
                        ledger['stop_reason']=choice['reason'];break
                    before=dict(ledger['knobs']);ledger['knobs'].update(choice.get('knobs',{}));run_id=choice['run_id'];previous=latest(results,run_id)
                    decision={'id':'studyjob'+str(len(ledger['decisions'])+1),'run_id':run_id,'round':previous['round']+1 if previous else 1,
                        'knobs':dict(ledger['knobs']),'previous_knobs':before,'reason':choice['reason'],'source':spec['planner']}
                    ledger['decisions'].append(decision);save(record)
                arguments=arguments_for(compiled,decision,results);previous=[a for a in ledger['attempts'] if a['job']==decision['id']]
                def commit(attempt,wrapper,proof,reused=False):
                    verify_round(arguments,wrapper['result']);_settle(attempt,proof);attempt['state']='complete'
                    memory=proof.get('measurements',{}).get('peak_job_memory_bytes')
                    if type(memory) is int and memory>=0:attempt['peak_job_memory_bytes']=memory
                    session.state['observations'].append({'tool':OPERATION,'tool_status':'native_tested','step_id':decision['id'],'experiment_job_id':decision['id'],
                        'arguments':arguments,'ok':True,'result':wrapper['result'],'execution':wrapper['execution'],'reused_execution':reused})
                    results.append(wrapper['result']);record.pop('inflight_step',None);persist()
                if previous and previous[-1].get('receipt_sha256'):
                    wrapper,proof=receipt(session,previous[-1],arguments);commit(previous[-1],wrapper,proof,True);continue
                spent=_charges(ledger);wall=spec['budget']['wall_seconds']-spent['wall_seconds'];cpu=spec['budget']['cpu_seconds']-spent['cpu_seconds']
                if spent['evaluation_reservations']+spec['batch_size']>spec['budget']['max_evaluations'] or wall<=0 or cpu<1:raise TaskControlError('study_budget_exhausted','累计研究预算不足；已完成结果保留。','budget_exhausted')
                if record['usage']['tool_calls']>=record['policy']['max_tool_calls']:raise TaskControlError('task_budget_exhausted','累计工具尝试预算不足。','budget_exhausted')
                if not session.execution_control.allowed(OPERATION):raise TaskControlError('tool_not_permitted','宿主未允许experiment_search内部操作。')
                base=session.execution_control.tool_limits;wall=min(wall,base.wall_seconds);cpu=min(math.floor(cpu),base.cpu_seconds)
                attempt={'id':uuid.uuid4().hex,'job':decision['id'],'evaluations':spec['batch_size'],'wall_limit':wall,'cpu_limit':cpu,'wall_charge':wall,'cpu_charge':cpu,
                    'core_sha256':core,'state':'reserved','settled':False,'arguments_sha256':digest(arguments)}
                ledger['attempts'].append(attempt);record['inflight_step']=decision['id'];session.execution_control.before_tool(OPERATION);persist()
                limits=TaskLimits(wall_seconds=wall,cpu_seconds=cpu,memory_mb=min(base.memory_mb,spec['budget']['memory_mb']),max_processes=base.max_processes,output_bytes=base.output_bytes,artifact_bytes=base.artifact_bytes)
                try:
                    wrapper=run_worker('experiment',{'name':OPERATION,'arguments':arguments},directory=session.directory/'tasks',limits=limits,
                        cancel_file=session.directory/'.cancel',include_receipt=True,operation_id=attempt['id'])
                    attempt['receipt_sha256']=wrapper['execution']['receipt_sha256'];save(record)
                    checked,proof=receipt(session,attempt,arguments);commit(attempt,checked,proof)
                except (KeyboardInterrupt,InterruptedError):raise
                except Exception as error:
                    from graph_research.runtime.observability import error_details
                    from .experience_evidence import failure_reference
                    item={'tool':OPERATION,'tool_status':'native_tested','step_id':decision['id']+'attempt'+str(len(previous)+1),'experiment_job_id':decision['id'],
                        'arguments':arguments,'ok':False,'error':type(error).__name__+': 搜索分段未完成。','error_details':error_details(error,phase='study.search_round')}
                    failed=failure_reference(session.directory/'tasks',error)
                    if failed:item['failed_execution']=failed
                    session.state['observations'].append(item);attempt['state']='uncertain_or_failed'
                    session.state.update(status='execution_error',answer='搜索分段失败，检查点及候选／时间预留保留。用户确认重试后另计预算。');persist();session._finalize_output();return
                processed+=1
                if processed>=spec['segment_rounds'] and eligible(compiled,results):
                    session.state.update(status='awaiting_experiment_continue',answer='本段已保存。可继续原范围，也可由可信用户调整授权区间内的探索／精英／约束引导参数。');persist();session._finalize_output();return
            session.state.update(status='experiment_complete',answer='本次有限研究已停止并保存核验证据、结构观察和假设检验；有限搜索结果不是一般定理。')
            persist(True)
        except TaskControlError as error:
            session.state.update(status=error.status,answer=str(error),control_error={'code':error.code,'message':str(error)});persist()
        except (KeyboardInterrupt,InterruptedError):
            session.state.update(status='cancelled',answer='研究已取消；已核验检查点保留，失败／不确定尝试不退预算。');persist()
        session._finalize_output()
