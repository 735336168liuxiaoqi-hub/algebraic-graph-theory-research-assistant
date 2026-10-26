"""One experiment entry: validate identity, handle optional confirmation, execute."""
import copy
from graph_research.runtime.storage import exclusive_lock
from graph_research.runtime.integrity import assert_integrity
from graph_research.errors import TaskProtocolError
from graph_research.runtime.serialization import json_fingerprint


def valid_confirmation(record,compiled,core):
    confirmation=record.get('experiment_confirmation')
    if not isinstance(confirmation,dict) or not isinstance(confirmation.get('event_id'),str):return False
    return (confirmation=={'event_id':confirmation.get('event_id'),'scope_sha256':compiled['request_sha256'],
            'core_sha256':core,'policy_sha256':json_fingerprint(record['policy'])}
            and confirmation.get('event_id') in record.get('event_receipts',{}))


def validate_experiment_identity(ledger,compiled,record,core,*,require_ready=True):
    """Scope/resource identity is required for every run, not an approval state."""
    if (type(ledger['version']) is not int or ledger['version']!=2 or ledger['request_sha256']!=compiled['request_sha256']
            or ledger['core_sha256']!=core or ledger['policy_sha256']!=json_fingerprint(record['policy'])
            or ledger['budget']!=compiled['spec']['budget']):raise ValueError('Experiment identity changed')
    if require_ready and record['policy'].get('confirm_experiments',True) and not valid_confirmation(record,compiled,core):
        raise ValueError('Requested confirmation has not been received')


def experiment_failure_status(error):
    """A known pre-entry blockage needs diagnosis, not a meaningless approval."""
    if (getattr(error,'protected_startup_phase',None) is not None
            or getattr(error,'phase',None)=='before_worker_entry'
            or getattr(error,'error_code',None) in ('venv_configuration_unreadable','venv_configuration_invalid',
                'python_stdlib_access_denied','protected_worker_startup_failed')):return 'blocked'
    return 'execution_error'


def run_experiment(record,session,save,model_factory,*,action='start',payload=None):
    operation=record['request']['execution']['experiment']['operation']
    if operation=='prepare':return run_preparation(record,session)
    from graph_research.experiments.execution_contract import compile_execution
    from graph_research.experiments.search_contract import compile_study
    from .experiment_execution import run_execution,summarize
    from .experiment_study import run_study,summary
    compiled=(compile_study if operation=='study' else compile_execution)(record['request']['execution']['experiment'])
    spec=compiled['spec'];key='study_ledger' if operation=='study' else 'experiment_ledger'
    with exclusive_lock(session.directory/'.session.lock'):
        core=assert_integrity()['manifest_sha256']
        if not session.state:
            session.state={'question':record['request']['objective'],'observations':[],
                'conversation':[{'role':'user','content':record['request']['objective']}]}
            session._begin_turn(record['request']['objective'])
        session.state.setdefault('observations',[]);session.state['delegated_task']=session.task_context
        if key not in record:
            ledger={'version':2,'request_sha256':compiled['request_sha256'],'core_sha256':core,
                'policy_sha256':json_fingerprint(record['policy']),'budget':spec['budget'],'attempts':[]}
            if operation=='study':ledger.update(decisions=[],feedback=[],hypotheses=copy.deepcopy(spec['hypotheses']),knobs=dict(spec['knobs']),focus_runs=[])
            record[key]=ledger;save(record)
        ledger=record[key]
        try:validate_experiment_identity(ledger,compiled,record,core,require_ready=False)
        except (KeyError,ValueError,TypeError):raise TaskProtocolError('experiment_scope_changed','实验范围、预算、核心或宿主策略已变化，请新建任务。') from None
        needs_confirmation=record['policy'].get('confirm_experiments',True)
        if needs_confirmation or spec['pause_at_checkpoints']:
            plan={'problem':spec['problem'],'budget':spec['budget'],'scope_sha256':compiled['request_sha256']}
            if operation=='study':plan.update(runs=compiled['runs'],planned_rounds=compiled['planned_rounds'],
                max_evaluations=compiled['planned_evaluations'],planned_calls=compiled['planned_calls'],worker_rounds=spec['worker_rounds'],
                batch_size=spec['batch_size'],cpu_threads=spec['cpu_threads'])
            else:plan.update(candidate_collection=spec['cases'],case_count=len(spec['cases']),evaluations=compiled['evaluations'],chunks=len(compiled['jobs']))
            session.state['experiment_plan']=plan
        if needs_confirmation:
            if not valid_confirmation(record,compiled,core):
                if record.get('experiment_confirmation'):raise TaskProtocolError('experiment_confirmation_changed','已保存的用户确认与任务不匹配。')
                if action=='continue' and session.state.get('status')=='awaiting_experiment_review' and record.get('active_event') in record.get('event_receipts',{}):
                    record['experiment_confirmation']={'event_id':record['active_event'],'scope_sha256':compiled['request_sha256'],
                        'core_sha256':core,'policy_sha256':json_fingerprint(record['policy'])};save(record)
                    session.state['experiment_confirmation']=copy.deepcopy(record['experiment_confirmation'])
                else:
                    session.state.update(status='awaiting_experiment_review',answer='用户或宿主要求初审。请确认本次固定范围和预算；确认后连续执行，科研反馈暂停另行设置。')
                    session.state['experiment_execution']=summary(compiled,ledger,[]) if operation=='study' else summarize(compiled,ledger,session.state['observations'])
                    session._save();session._finalize_output();return
        session._save()
    if operation=='study':return run_study(record,session,save,model_factory,compiled=compiled,action=action,payload=payload)
    return run_execution(record,session,save,compiled=compiled,action=action)


def run_preparation(record,session):
    from graph_research.experiments.preparation import prepare_experiment
    with exclusive_lock(session.directory/'.session.lock'):
        current=assert_integrity()['manifest_sha256']
        saved=session.state.get('experiment_core_sha256')
        if saved is not None and saved!=current:
            raise TaskProtocolError('experiment_core_changed','实验准备实现已改变，请新建任务，不混用旧草案。')
        if not session.state:
            session.state={'question':record['request']['objective'],'observations':[],
                           'conversation':[{'role':'user','content':record['request']['objective']}]}
            session._begin_turn(record['request']['objective'])
        report=prepare_experiment(record['request']['execution']['experiment'])
        if record['request'].get('definitions'):
            report['plan']['issues'].append({'code':'text_definitions','kind':'notice',
                'message':'definitions是上下文资料，不自动成为计算约束。必要条件须在problem中形式化；无法映射的数学条件再向用户澄清。'})
        session.state.update(status='experiment_prepared',experiment_preparation=report,
                             experiment_core_sha256=current,delegated_task=session.task_context,
                             answer='已保存研究问题、能力缺口和有限实验计划草案。阶段1未执行搜索、训练、模型调用或文献检索，也未批准资源。')
        session._save();session._finalize_output()
