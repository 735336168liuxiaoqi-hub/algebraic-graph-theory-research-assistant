"""Synthetic workflow acceptance cases. Live requests require explicit bounded opt-in."""
import argparse
import copy
from dataclasses import asdict
from datetime import datetime,timezone
from html import escape
from importlib.resources import files
import inspect
import json
from pathlib import Path
from threading import Event
import uuid

from graph_research.runtime.storage import safe_path,atomic_text,write_json
from graph_research.runtime.runner import TaskLimits
from graph_research.tools import ToolRegistry
from graph_research.graph_input import parse_graph
from .governance import WorkflowJournal,validate_policy
from .session import ResearchSession
from .task_control import TaskExecutionControl
from .planning import read_path
from .research_objects import fingerprint


def evaluation_cases():
    data=json.loads(files('graph_research').joinpath('data/api-evaluation.json').read_text(encoding='utf-8'))
    if data.get('version')!=1 or not 1<=len(data['cases'])<=24:raise ValueError('验收集版本或数量无效。')
    return copy.deepcopy(data['cases'])


class FixtureModel:
    def __init__(self,decisions):self.decisions=copy.deepcopy(decisions);self.context_messages=[]
    def complete(self,messages):
        self.context_messages.append(len(json.loads(messages[1]['content']).get('conversation',[])))
        if not self.decisions:raise RuntimeError('离线验收脚本已耗尽。')
        decision=self.decisions.pop(0)
        if decision.get('_fault')=='network':raise RuntimeError('合成网络中断；没有真实网络请求。')
        return decision


def _clean(value,secret):
    if isinstance(value,str):return value.replace(secret,'[密钥已隐藏]') if secret else value
    if isinstance(value,list):return [_clean(v,secret) for v in value]
    if isinstance(value,dict):return {_clean(str(k),secret):_clean(v,secret) for k,v in value.items()}
    return value


class LiveEvaluationModel:
    def __init__(self,actual,journal,task_id,cancel):self.actual=actual;self.journal=journal;self.task_id=task_id;self.cancel=cancel;self.context_messages=[]
    def complete(self,messages,*,max_output_tokens=None):
        self.context_messages.append(len(json.loads(messages[1]['content']).get('conversation',[])))
        owner=self
        class Provider:
            def __init__(self):self.actual=owner.actual
            def complete(self,messages,*,max_output_tokens=None):
                parameters=inspect.signature(self.actual.complete).parameters;options={}
                if 'max_output_tokens' in parameters:options['max_output_tokens']=max_output_tokens
                if 'cancel' in parameters:options['cancel']=owner.cancel
                return self.actual.complete(messages,**options)
        result=self.journal.model_call(self.task_id,Provider(),messages)
        return _clean(result,getattr(self.actual,'api_key',''))


def check_case(case,session,model):
    expected=case['expected'];state=session.state;observations=state.get('observations',[]);checks=[]
    def check(name,ok):checks.append({'check':name,'passed':bool(ok)})
    if 'statuses' in expected:check('工作流状态符合预期',state.get('status') in expected['statuses'])
    else:check('任务已正常完成',state.get('status') in ('tool_results_available','model_analysis_only','extension_ready'))
    for fact in expected.get('facts',[]):
        matched=False
        for observation in observations:
            if observation.get('ok') and observation.get('tool')==fact['tool']:
                try:matched=matched or fingerprint(read_path(observation['result'],fact['path']))==fingerprint(fact['value'])
                except (KeyError,ValueError,IndexError,TypeError):pass
        check('已知结果：'+fact['tool']+' / '+' / '.join(map(str,fact['path'])),matched)
    for name in expected.get('successful_tools',[]):check('调用已有工具：'+name,any(o.get('ok') and o.get('tool')==name for o in observations))
    for name in expected.get('forbidden_tools',[]):check('未误用不适用工具：'+name,not any(o.get('tool')==name for o in observations))
    if expected.get('require_plan'):check('计划完成',state.get('plan',{}).get('status')=='completed')
    if 'active_version' in expected:check('新图版本正确',(session.research_objects.get('active') or {}).get('version')==expected['active_version'])
    if 'bound_vertices' in expected:check('原始标签及孤立点保留',any(s['document']['vertices']==expected['bound_vertices'] for o in observations for s in o.get('graph_inputs',[])))
    if expected.get('no_assessment'):check('未创建新开发审批',not list((session.directory/'changes').glob('*/assessment.json')))
    if expected.get('manual_brief'):check('独立开发说明没有授权',state.get('development_brief',{}).get('authorization')=='none')
    if expected.get('reused'):check('中断后复用完成回执',any(o.get('reused_execution') for o in observations))
    if 'claims_status' in expected:check('结论来源核对结果正确',any(c.get('status')==expected['claims_status'] for c in state.get('audited_claims',[])))
    if 'answer_contains' in expected:check('明确说明适用条件',expected['answer_contains'] in state.get('answer',''))
    if 'context_messages_max' in expected:check('长历史有限窗口',len(state.get('conversation',[]))>8 and max(model.context_messages,default=0)<=expected['context_messages_max'])
    usage=session.workflow_usage()
    for key in ('model_calls','tool_calls'):
        if key in expected:check('累计'+('模型请求' if key=='model_calls' else '计算尝试')+'次数正确',usage[key]==expected[key])
    check('未安装任何扩展包',not list(session.store.directory.rglob('ready.json')))
    check('结果包成功生成',session.export_error is None and session.result_bundle is not None)
    return checks


def run_evaluation(directory,*,case_ids=None,live=False,model=None,limits=None,cancel=None,on_progress=None):
    if type(live) is not bool:raise ValueError('验收模式需要明确选择。')
    if live:
        required={'max_model_calls','max_tool_calls','max_input_tokens','max_output_tokens','request_output_tokens'}
        if model is None or not isinstance(limits,dict) or not required<=set(limits) or any(limits[k] is None for k in required):raise ValueError('真实验收需要模型及明确的总请求、工具、输入/输出token与单次输出上限。')
    policy=validate_policy(limits or {'max_model_calls':100,'max_tool_calls':200})
    cases=evaluation_cases();selected=set(case_ids) if case_ids is not None else {c['id'] for c in cases}
    if not selected or not selected<={c['id'] for c in cases}:raise ValueError('请选择已有验收样例。')
    cases=[c for c in cases if c['id'] in selected]
    root=safe_path(directory)/('run_'+uuid.uuid4().hex);root.mkdir(parents=True,exist_ok=False);cancel=cancel or Event()
    live_journal=WorkflowJournal(root/'live-budget');live_journal.configure(policy);live_id=uuid.uuid4().hex;live_journal.start(live_id)
    registry=ToolRegistry();control_record={'policy':{'allowed_tools':list(registry.tools),'allow_extensions':True,'max_model_calls':10000,'max_tool_calls':policy['max_tool_calls'],'tool_limits':asdict(TaskLimits())},'usage':{'model_calls':0,'tool_calls':0}}
    control=TaskExecutionControl(control_record,lambda record:write_json(root/'tool-budget.json',record))
    rows=[];stop_live=False
    for index,case in enumerate(cases):
        if cancel.is_set():rows.append({'id':case['id'],'title':case['title'],'status':'not_run','reason':'用户停止'});continue
        use_live=live and not case.get('host_only',False)
        if use_live and stop_live:rows.append({'id':case['id'],'title':case['title'],'status':'not_run','reason':'触发预算或服务错误，后续真实样例暂停'});continue
        if on_progress:on_progress({'index':index+1,'total':len(cases),'title':case['title'],'stage':'running'})
        actual=LiveEvaluationModel(model,live_journal,live_id,cancel) if use_live else FixtureModel(case['script'])
        session=ResearchSession(root/'cases'/case['id'],root/'empty-extension-store',execution_control=control)
        if case.get('budget'):session.workflow.configure(case['budget'])
        if case.get('graph'):session.bind_graph(parse_graph(**{'text':case['graph']['text'],**{k:v for k,v in case['graph'].items() if k!='text'}}))
        try:
            session.ask(case['question'],actual,cancel_event=cancel)
            if case.get('resume') and not use_live and session.state.get('status')=='execution_error':session.continue_run(actual,cancel_event=cancel)
            for round_index in range(1,case.get('history_rounds',1)):
                if cancel.is_set():break
                session.reply(case['question']+'第'+str(round_index+1)+'轮。'+('合成资料。'*200),actual,cancel_event=cancel)
            checks=check_case(case,session,actual)
            row={'id':case['id'],'title':case['title'],'mode':'live' if use_live else 'offline_control' if live else 'offline',
                 'status':'passed' if all(c['passed'] for c in checks) else 'failed','checks':checks,
                 'workflow_status':session.state.get('status'),'usage':session.workflow_usage(),
                 'answer':session.state.get('answer','')[:4000],
                 'result_bundle':session.result_bundle,'session':str(session.directory)}
        except Exception as error:
            row={'id':case['id'],'title':case['title'],'status':'failed','error':_clean(str(error),getattr(model,'api_key',''))}
        rows.append(row)
        if use_live and session.state.get('status') in ('budget_exhausted','execution_error','cancelled'):stop_live=True
        if on_progress:on_progress({'index':index+1,'total':len(cases),'title':case['title'],'stage':row['status']})
    report={'format':'graph-research-api-evaluation','version':1,'fixture_version':1,'created_at':datetime.now(timezone.utc).isoformat(),
            'mode':'live_with_offline_controls' if live else 'offline','model':getattr(model,'model',None) if live else None,
            'rows':rows,'summary':{kind:sum(row['status']==kind for row in rows) for kind in ('passed','failed','not_run')},
            'live_usage':live_journal.summary(live_id),'real_model_requests':live_journal.summary(live_id)['model_calls'] if live else 0,
            'total_tool_attempts':control_record['usage']['tool_calls'],'tool_attempt_limit':policy['max_tool_calls'],
            'scope':'固定合成任务与机器可核对标准，不使用当前科研历史或记忆，不自动批准扩展，不代表一般数学正确性或全部真实任务质量。'}
    write_json(root/'report.json',report)
    lines=['# API流程验收','',report['scope'],'','模式：'+report['mode'],'']
    for row in rows:lines.append('- '+row['title']+'：'+row['status']+('；'+row['error'] if row.get('error') else ''))
    atomic_text(root/'report.md','\n'.join(lines)+'\n')
    html='<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>API流程验收</title><h1>API流程验收</h1><p>'+escape(report['scope'])+'</p><table border="1" cellpadding="8"><tr><th>样例</th><th>结果</th><th>检查</th></tr>'
    html+=''.join('<tr><td>'+escape(row['title'])+'</td><td>'+escape({'passed':'通过','failed':'未通过','not_run':'未运行'}[row['status']])+'</td><td>'+escape(('；'.join(c['check']+('：通过' if c['passed'] else '：失败') for c in row.get('checks',[])) or row.get('reason',row.get('error','')))+('\n'+row.get('answer','') if row['status']=='failed' else ''))+'</td></tr>' for row in rows)+'</table>'
    atomic_text(root/'report.html',html)
    return {'directory':str(root.resolve()),'report':str((root/'report.json').resolve()),**report['summary'],'real_model_requests':report['real_model_requests'],'total_tool_attempts':report['total_tool_attempts'],'live_usage':report['live_usage']}


def evaluation_command(arguments):
    parser=argparse.ArgumentParser(description='固定合成API流程验收；默认离线，不自动重试或批准开发')
    parser.add_argument('--live',action='store_true');parser.add_argument('--output',default='outputs/api-evaluations');parser.add_argument('--case',action='append',dest='case_ids')
    for flag in ('max-model-calls','max-tool-calls','max-input-tokens','max-output-tokens','request-output-tokens'):parser.add_argument('--'+flag,type=int)
    parser.add_argument('--input-price',type=float);parser.add_argument('--output-price',type=float);parser.add_argument('--currency',default='未指定');parser.add_argument('--max-cost',type=float)
    options=parser.parse_args(arguments);limits=None;model=None
    if options.live:
        names=('max_model_calls','max_tool_calls','max_input_tokens','max_output_tokens','request_output_tokens')
        if any(getattr(options,name) is None for name in names):parser.error('--live必须同时明确全部五项调用与token上限；可能产生服务商费用。')
        limits={name:getattr(options,name) for name in names};limits.update(input_per_million=options.input_price,output_per_million=options.output_price,currency=options.currency,max_cost=options.max_cost)
        validate_policy(limits)
        from .model import ConfiguredModel
        model=ConfiguredModel()
    result=run_evaluation(options.output,case_ids=options.case_ids,live=options.live,model=model,limits=limits)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if not result['failed'] and not result['not_run'] else 2
