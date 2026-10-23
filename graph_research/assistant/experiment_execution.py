"""Approved finite experiments with conservative durable attempt accounting."""
import copy
from fractions import Fraction
import json
import math
import re
import uuid

from graph_research.errors import TaskProtocolError
from graph_research.runtime.storage import exclusive_lock,safe_path,read_json
from graph_research.runtime.evidence import file_hash
from graph_research.runtime.integrity import assert_integrity
from graph_research.runtime.runner import TaskLimits,run_worker
from .task_control import TaskControlError
from graph_research.experiments.execution_contract import compile_execution,INTERNAL_OPERATION,digest
from graph_research.experiments.verification import verify_evaluation


def check_chunk(arguments,value):
    if value.get('scope')!='provided_candidate_collection' or value.get('search_performed') is not False or value.get('general_theorem_proved') is not False:
        raise TaskProtocolError('experiment_evidence_invalid','分段结果越出了明确候选评价的结论范围。')
    if value.get('case_id')!=arguments['case_id'] or value.get('evaluations_completed')!=len(arguments['candidates']) or len(value.get('rows',[]))!=len(arguments['candidates']):
        raise TaskProtocolError('experiment_evidence_invalid','分段结果与明确候选数量不一致。')
    for item,row in zip(arguments['candidates'],value['rows']):
        if row.get('candidate_id')!=item['id'] or not verify_evaluation(arguments['problem'],arguments['parameters'],item['graph'],row)['passed']:
            raise TaskProtocolError('experiment_evidence_invalid','候选约束或指标证据未通过独立核验。')


def _receipt(session,job,attempt):
    """Recover only a host-pinned complete receipt, never an unanchored file."""
    pin=attempt.get('receipt_sha256')
    if not pin:return None
    directory=safe_path(session.directory/'tasks'/('task_'+attempt['id']),root=session.directory/'tasks')
    receipt_path=directory/'execution.json'
    if file_hash(receipt_path)!=pin:raise TaskProtocolError('experiment_receipt_changed','实验回执已改变，拒绝恢复或重算。')
    receipt,_=read_json(receipt_path,max_bytes=1024*1024)
    if receipt.get('status')!='complete' or receipt.get('kind')!='experiment' or receipt.get('core_manifest_sha256')!=attempt['core_sha256']:
        raise TaskProtocolError('experiment_receipt_changed','实验回执类型、版本或状态无效。')
    for name in ('request','result'):
        if file_hash(directory/(name+'.json'))!=receipt[name+'_sha256']:
            raise TaskProtocolError('experiment_evidence_changed','实验输入或结果文件已改变。')
    request,_=read_json(directory/'request.json',max_bytes=256*1024);payload,_=read_json(directory/'result.json',max_bytes=4*1024*1024)
    if request.get('name')!=INTERNAL_OPERATION or digest(request.get('arguments'))!=digest(job['arguments']) or payload.get('ok') is not True:
        raise TaskProtocolError('experiment_evidence_changed','实验结果与原始分段输入不符。')
    check_chunk(job['arguments'],payload['result'])
    return {'result':payload['result'],'execution':{'task_id':directory.name,'directory':str(directory),'receipt_sha256':pin}},receipt


def _charges(ledger):
    return {'evaluation_reservations':sum(a['evaluations'] for a in ledger['attempts']),
            'wall_seconds':sum(a['wall_charge'] for a in ledger['attempts']),
            'cpu_seconds':sum(a['cpu_charge'] for a in ledger['attempts'])}


def _validate_ledger(ledger,compiled,record,core):
    """Reject corrupted checkpoints before trusting any budget or receipt path."""
    jobs={job['id']:job for job in compiled['jobs']};ids=set()
    try:
        if ledger['version']!=1 or type(ledger['approved']) is not bool or not isinstance(ledger['attempts'],list):raise ValueError()
        if len(ledger['attempts'])!=record['usage']['tool_calls']:raise ValueError()
        for attempt in ledger['attempts']:
            if not isinstance(attempt,dict) or not re.fullmatch('[0-9a-f]{32}',attempt['id']) or attempt['id'] in ids:raise ValueError()
            ids.add(attempt['id']);job=jobs[attempt['job']]
            if type(attempt['evaluations']) is not int or attempt['evaluations']!=len(job['arguments']['candidates']) or attempt['core_sha256']!=core:raise ValueError()
            if attempt['state'] not in {'reserved','complete','uncertain_or_failed'} or type(attempt['settled']) is not bool:raise ValueError()
            for key in ('wall_limit','cpu_limit','wall_charge','cpu_charge'):
                if type(attempt[key]) not in (int,float) or not math.isfinite(attempt[key]) or attempt[key]<0:raise ValueError()
            if min(attempt['wall_limit'],attempt['cpu_limit'])<=0:raise ValueError()
            if not attempt['settled'] and (attempt['wall_charge']!=attempt['wall_limit'] or attempt['cpu_charge']!=attempt['cpu_limit']):raise ValueError()
            if attempt.get('receipt_sha256') is not None and not re.fullmatch('[0-9a-f]{64}',attempt['receipt_sha256']):raise ValueError()
            if attempt['settled'] and not attempt.get('receipt_sha256'):raise ValueError()
        if not ledger['approved'] and (ledger['attempts'] or ledger['approval_event_id'] is not None):raise ValueError()
        if ledger['approved'] and ledger['approval_event_id'] not in record.get('event_receipts',{}):raise ValueError()
    except (ValueError,TypeError,KeyError):
        raise TaskProtocolError('experiment_checkpoint_changed','实验账本、资源计数或批准事件无效，拒绝继续。') from None


def _settle(attempt,receipt):
    if attempt.get('settled'):return
    measurements=receipt.get('measurements',{})
    for field,key in [('wall_charge','host_elapsed_seconds'),('cpu_charge','cpu_seconds')]:
        value=measurements.get(key)
        if type(value) in (int,float) and math.isfinite(value) and value>=0:attempt[field]=float(value)
    attempt['settled']=True


def _completed(session,compiled):
    from .results import _execution
    known={};jobs={job['id']:job for job in compiled['jobs']}
    for observation in session.state.get('observations',[]):
        if observation.get('tool')!=INTERNAL_OPERATION or not observation.get('ok'):continue
        job_id=observation.get('experiment_job_id');job=jobs.get(job_id)
        if job is None or digest(observation['arguments'])!=digest(job['arguments']):raise TaskProtocolError('experiment_checkpoint_changed','实验步骤与固定计划不一致。')
        if _execution(session,observation,'experiment-check',False,[])[0]!='verified_execution':raise TaskProtocolError('experiment_checkpoint_changed','历史实验缺少有效执行证据。')
        check_chunk(job['arguments'],observation['result'])
        if job_id in known:raise TaskProtocolError('experiment_checkpoint_changed','同一实验分段出现重复成功记录。')
        known[job_id]=observation
    expected=[j['id'] for j in compiled['jobs']]
    if set(known)!=set(expected[:len(known)]):raise TaskProtocolError('experiment_checkpoint_changed','实验进度存在缺段或乱序。')
    return known


def summarize(compiled,ledger,observations):
    jobs={j['id']:j for j in compiled['jobs']};success={o['experiment_job_id']:o for o in observations if o.get('tool')==INTERNAL_OPERATION and o.get('ok')}
    rows=[];cases=[];direction=compiled['spec']['problem']['objective']['direction']
    for case in compiled['spec']['cases']:
        case_rows=[]
        for job in compiled['jobs']:
            if job['arguments']['case_id']==case['id'] and job['id'] in success:
                case_rows.extend(success[job['id']]['result']['rows'])
        feasible=[row for row in case_rows if row['feasible']]
        chosen=(feasible[0] if direction=='satisfy' else min(feasible,key=lambda r:r['objective_estimate']) if direction=='minimize' else max(feasible,key=lambda r:r['objective_estimate'])) if feasible else None
        certified=False
        if chosen and direction!='satisfy':
            bounds=list(map(Fraction,chosen['objective_interval']));others=[r for r in feasible if r is not chosen]
            certified=all((bounds[1]<=Fraction(r['objective_interval'][0]) if direction=='minimize' else bounds[0]>=Fraction(r['objective_interval'][1])) for r in others)
        complete=len(case_rows)==len(case['candidates'])
        cases.append({'case_id':case['id'],'parameters':case['parameters'],'evaluated':len(case_rows),'feasible':len(feasible),
                      'collection_complete':complete,'selected_candidate':copy.deepcopy(chosen),
                      'selection':'first_verified_feasible_candidate' if direction=='satisfy' else 'numerical_ranking_of_feasible_candidates','selected_no_worse_certified_in_evaluated_set':certified,
                      'candidate_collection_optimum_certified':bool(complete and chosen and certified)})
        rows.extend({'case_id':case['id'],**row} for row in case_rows)
    return {'phase':3,'scope':'provided_candidate_collection','approved':ledger['approved'],
            'jobs_completed':len(success),'jobs_total':len(jobs),'collection_complete':len(success)==len(jobs),
            'evaluations_completed':len(rows),'cases':cases,'rows':rows,'budget':{'limits':ledger['budget'],**_charges(ledger),
            'meaning':'Candidate attempts are reserved before execution and never refunded; missing resource measurements retain conservative reservations. Wall/CPU are active worker usage, not paused time.'},
            'attempts':copy.deepcopy(ledger['attempts']),'search_performed':False,'training_performed':False,
            'enumeration_complete':False,'general_theorem_proved':False,
            'limitations':['Only the explicitly supplied collection was evaluated.','Certified intervals can overlap; numerical ranking alone does not certify the best candidate.','Worker startup/cleanup and resource enforcement may cross a deadline briefly; overrun stops subsequent chunks.']}


def run_execution(record,session,save,*,action='start'):
    request=record['request'];compiled=compile_execution(request['execution']['experiment']);spec=compiled['spec']
    with exclusive_lock(session.directory/'.session.lock'):
        core=assert_integrity()['manifest_sha256']
        if not session.state:
            session.state={'question':request['objective'],'observations':[],'conversation':[{'role':'user','content':request['objective']}]}
            session._begin_turn(request['objective'])
        session.state.setdefault('observations',[])
        session.state['delegated_task']=session.task_context
        ledger=record.get('experiment_ledger')
        if ledger is None:
            ledger={'version':1,'request_sha256':compiled['request_sha256'],'core_sha256':core,'budget':spec['budget'],
                    'approved':False,'approval_event_id':None,'attempts':[]}
            record['experiment_ledger']=ledger;save(record)
        if ledger['request_sha256']!=compiled['request_sha256'] or ledger['core_sha256']!=core or ledger['budget']!=spec['budget']:
            raise TaskProtocolError('experiment_scope_changed','实验定义、预算或核心版本改变，请新建任务。')
        _validate_ledger(ledger,compiled,record,core)
        if not ledger['approved']:
            if action=='continue' and session.state.get('status')=='awaiting_experiment_review' and record.get('active_event'):
                ledger.update(approved=True,approval_event_id=record['active_event']);save(record)
            else:
                session.state.update(status='awaiting_experiment_review',
                    experiment_review={'problem':spec['problem'],'case_count':len(spec['cases']),'candidate_collection':spec['cases'],'evaluations':compiled['evaluations'],
                        'chunks':len(compiled['jobs']),'budget':spec['budget'],'scope_sha256':compiled['request_sha256'],
                        'meaning':'Only evaluate this explicit collection. No CEM, graph generation or theorem proof.'},
                    answer='请确认本次明确候选集合、分段数量和总预算。确认前不执行计算；如需修改范围，请取消并提交新任务。')
                session.state['experiment_execution']=summarize(compiled,ledger,session.state['observations'])
                session._save();session._finalize_output();return
        session.state.update(status='running',answer='正在分段评价明确候选并独立核验。')
        known=_completed(session,compiled)
        # A crash may occur after saving the observation but before settling its ledger.
        for job_id,observation in known.items():
            attempts=[a for a in ledger['attempts'] if a['job']==job_id and a.get('receipt_sha256')==observation['execution']['receipt_sha256']]
            if len(attempts)!=1:raise TaskProtocolError('experiment_checkpoint_changed','已完成分段与宿主固定回执不一致。')
            attempt=attempts[0];_,receipt=_receipt(session,next(j for j in compiled['jobs'] if j['id']==job_id),attempt)
            attempt['state']='complete';_settle(attempt,receipt)
            if record.get('inflight_step')==job_id:record.pop('inflight_step',None)
        def persist():
            session.state['experiment_execution']=summarize(compiled,ledger,session.state['observations'])
            session._save();save(record)
        def commit(job,attempt,wrapper,receipt,recovered=False):
            check_chunk(job['arguments'],wrapper['result'])
            observation={'tool':INTERNAL_OPERATION,'tool_status':'native_tested','step_id':job['id'],
                         'experiment_job_id':job['id'],'case_id':job['arguments']['case_id'],'arguments':job['arguments'],
                         'ok':True,'result':wrapper['result'],'execution':wrapper['execution']}
            if recovered:observation['reused_execution']=True
            session.state['observations'].append(observation);known[job['id']]=observation
            attempt['state']='complete';_settle(attempt,receipt);record.pop('inflight_step',None);persist()
        processed=0
        try:
            for job in compiled['jobs']:
                if job['id'] in known:continue
                if (session.directory/'.cancel').exists():raise InterruptedError('Experiment cancelled')
                previous=[a for a in ledger['attempts'] if a['job']==job['id']]
                if previous and previous[-1].get('receipt_sha256'):
                    wrapper,receipt=_receipt(session,job,previous[-1]);commit(job,previous[-1],wrapper,receipt,True);continue
                if previous:previous[-1]['state']='uncertain_or_failed'
                spent=_charges(ledger);budget=ledger['budget'];count=len(job['arguments']['candidates'])
                wall=budget['wall_seconds']-spent['wall_seconds'];cpu=budget['cpu_seconds']-spent['cpu_seconds']
                if spent['evaluation_reservations']+count>budget['max_evaluations'] or wall<=0 or cpu<1:
                    raise TaskControlError('experiment_budget_exhausted','实验累计资源预算不足；已完成结果保留，恢复不会重置预算。','budget_exhausted')
                if record['usage']['tool_calls']>=record['policy']['max_tool_calls']:
                    raise TaskControlError('task_budget_exhausted','分段工具尝试预算已用尽。','budget_exhausted')
                if not session.execution_control.allowed(INTERNAL_OPERATION):raise TaskControlError('tool_not_permitted','宿主未允许实验评价操作。')
                base=session.execution_control.tool_limits
                wall=min(wall,base.wall_seconds);cpu=min(math.floor(cpu),base.cpu_seconds)
                attempt={'id':uuid.uuid4().hex,'job':job['id'],'evaluations':count,'wall_limit':wall,'cpu_limit':cpu,
                         'wall_charge':wall,'cpu_charge':cpu,'state':'reserved','settled':False,'core_sha256':core}
                ledger['attempts'].append(attempt);record['inflight_step']=job['id']
                session.execution_control.before_tool(INTERNAL_OPERATION)  # Atomic record includes reservation and increment.
                persist()
                limits=TaskLimits(wall_seconds=wall,cpu_seconds=cpu,memory_mb=min(base.memory_mb,budget['memory_mb']),
                                  max_processes=base.max_processes,output_bytes=base.output_bytes,artifact_bytes=base.artifact_bytes)
                try:
                    wrapper=run_worker('experiment',{'name':INTERNAL_OPERATION,'arguments':job['arguments']},directory=session.directory/'tasks',
                                       limits=limits,cancel_file=session.directory/'.cancel',include_receipt=True,operation_id=attempt['id'])
                    attempt['receipt_sha256']=wrapper['execution']['receipt_sha256'];save(record)
                    checked,receipt=_receipt(session,job,attempt);commit(job,attempt,checked,receipt)
                except (InterruptedError,KeyboardInterrupt):raise
                except Exception as error:
                    attempt['state']='uncertain_or_failed'
                    from graph_research.runtime.observability import error_details
                    from .experience_evidence import failure_reference
                    observation={'tool':INTERNAL_OPERATION,'tool_status':'native_tested','step_id':job['id']+'-attempt'+str(len(previous)+1),
                        'experiment_job_id':job['id'],'arguments':job['arguments'],'ok':False,'error':type(error).__name__+': 分段未完成，请查看任务回执。',
                        'error_details':error_details(error,phase='experiment.chunk_execution')}
                    failed=failure_reference(session.directory/'tasks',error)
                    if failed:observation['failed_execution']=failed
                    session.state['observations'].append(observation)
                    session.state.update(status='execution_error',answer='实验分段中断；评价尝试和资源预留保留。用户选择继续后，仅重试未核验分段，重试另计预算。')
                    persist();session._finalize_output();return
                processed+=1
                if processed>=spec['segment_chunks'] and len(known)<len(compiled['jobs']):
                    session.state.update(status='awaiting_experiment_continue',answer='本段已核验并保存。继续将复用已完成结果，在原累计预算内评价剩余候选。')
                    persist();session._finalize_output();return
            session.state.update(status='experiment_complete',answer='明确候选集合已评价并核验；结果不代表搜索全部图或证明一般极值定理。')
        except TaskControlError as error:
            session.state.update(status=error.status,answer=str(error),control_error={'code':error.code,'message':str(error)})
        except (InterruptedError,KeyboardInterrupt):
            session.state.update(status='cancelled',answer='实验已取消；已核验分段保留，未完成尝试按预留计账。继续需要可信用户事件，预算不会重置。')
        persist();session._finalize_output()
