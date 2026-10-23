"""Preparation-only research tasks through the durable subagent interface."""
from graph_research.runtime.storage import exclusive_lock
from graph_research.runtime.integrity import assert_integrity
from graph_research.errors import TaskProtocolError


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
            report['plan']['issues'].append({'code':'text_definitions','kind':'clarification',
                'message':'definitions中的文字未成为可计算约束；请将必要条件明确加入problem。'})
            report['plan']['status']='needs_clarification'
        session.state.update(status='experiment_prepared',experiment_preparation=report,
                             experiment_core_sha256=current,delegated_task=session.task_context,
                             answer='已保存研究问题、能力缺口和有限实验计划草案。阶段1未执行搜索、训练、模型调用或文献检索，也未批准资源。')
        session._save();session._finalize_output()
