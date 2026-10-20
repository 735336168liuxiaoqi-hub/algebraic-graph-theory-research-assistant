"""Durable host-only budgets and tool intents; uncertain work never replays silently."""
import copy
import inspect
import math
from pathlib import Path
import re
import time
from types import SimpleNamespace
import uuid

from graph_research.runtime.storage import read_json,write_json,safe_path
from graph_research.runtime.integrity import assert_integrity
from graph_research.runtime.evidence import file_hash,environment_info
from .research_objects import fingerprint
from .task_control import TaskControlError


DEFAULT_POLICY={'max_model_calls':10,'max_tool_calls':10,'max_input_tokens':None,'max_output_tokens':None,
                'max_active_seconds':None,'max_cost':None,'input_per_million':None,'output_per_million':None,
                'currency':'未指定','reuse_results':True,'request_output_tokens':4096}


def validate_policy(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULT_POLICY):raise ValueError('预算配置字段无效。')
    value={**DEFAULT_POLICY,**value}
    for name,maximum in [('max_model_calls',100),('max_tool_calls',200),('request_output_tokens',32768)]:
        if type(value[name]) is not int or not (16 if name=='request_output_tokens' else 1)<=value[name]<=maximum:raise ValueError('预算范围无效：'+name)
    for name in ('max_input_tokens','max_output_tokens'):
        if value[name] is not None and (type(value[name]) is not int or not 1<=value[name]<=10000000):raise ValueError('token预算无效。')
    for name in ('max_active_seconds','max_cost','input_per_million','output_per_million'):
        if value[name] is not None and (type(value[name]) not in (int,float) or not math.isfinite(value[name]) or value[name]<0):raise ValueError('时间、金额与单价需要非负有限数。')
    if value['max_active_seconds']==0:raise ValueError('活动用时上限应大于0。')
    if value['max_active_seconds'] is not None and value['max_active_seconds']>86400:raise ValueError('活动用时最多86400秒。')
    if not isinstance(value['currency'],str) or not 1<=len(value['currency'])<=20 or type(value['reuse_results']) is not bool:raise ValueError('预算币种或复用选项无效。')
    if value['max_cost'] is not None and any(value[k] is None for k in ('input_per_million','output_per_million')):raise ValueError('设置金额上限前需要填写输入、输出单价。')
    return copy.deepcopy(value)


def usage_tokens(value):
    if not isinstance(value,dict):return None
    pair=[value.get('input_tokens',value.get('prompt_tokens')),value.get('output_tokens',value.get('completion_tokens'))]
    if all(type(v) is int and 0<=v<=1000000000 for v in pair):return {'input_tokens':pair[0],'output_tokens':pair[1]}
    return None


class RecoveryRequired(TaskControlError):
    def __init__(self,key):
        self.key=key
        super().__init__('uncertain_tool_execution','该步骤可能已开始，但没有可核验的完成回执。请检查记录后明确选择重新执行；不会自动重算。','recovery_required')


class WorkflowJournal:
    """One session lock must cover mutations. Credentials/messages are never stored."""
    def __init__(self,directory):
        self.directory=safe_path(directory);self.path=self.directory/'workflow-journal.json'
        self.data=read_json(self.path,max_bytes=16*1024*1024)[0] if self.path.exists() else {'version':1,'policy':copy.deepcopy(DEFAULT_POLICY),'tasks':{}}
        if self.data.get('version')!=1 or not isinstance(self.data.get('tasks'),dict):raise ValueError('工作流日志损坏，不能重置预算或自动恢复。')
        validate_policy(self.data['policy'])
        for key,task in self.data['tasks'].items():
            self._id(key);validate_policy(task['policy'])
            if not isinstance(task.get('model_requests'),list) or not isinstance(task.get('tool_calls'),dict):raise ValueError('工作流使用记录无效。')
            elapsed=task.get('active_seconds')
            if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0:raise ValueError('工作流计时无效。')
            if any(type(task.get(k,0)) is not int or task.get(k,0)<0 for k in ('legacy_model_calls','legacy_tool_calls')):raise ValueError('历史用量记录无效。')
            for row in task['model_requests']:
                self._id(row['id'])
                if row.get('status') not in ('completed','uncertain') or any(type(row['reserved'].get(k)) is not int or row['reserved'][k]<0 for k in ('input_tokens','output_tokens')) or row.get('usage') is not None and usage_tokens(row['usage']) is None:raise ValueError('工作流用量记录无效。')
            for call,value in task['tool_calls'].items():
                self._id(call);self._id(value['operation_id'])
                if value.get('status') not in ('inflight','complete','interrupted','failed','abandoned'):raise ValueError('工具执行意图状态无效。')

    @staticmethod
    def _id(value):
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('工作流标识无效。')

    def save(self):write_json(self.path,self.data)

    def configure(self,policy,task_id=None):
        policy=validate_policy({**self.data['policy'],**policy})
        if task_id in self.data['tasks'] and self.data['tasks'][task_id]['model_requests']:
            previous=self.data['tasks'][task_id]['policy']
            if any(previous[k]!=policy[k] for k in ('input_per_million','output_per_million','currency')):raise ValueError('本任务已有请求，单价与币种不能追溯改写。请在新对话开始前配置单价。')
        self.data['policy']=policy
        if task_id in self.data['tasks']:self.data['tasks'][task_id]['policy']=copy.deepcopy(policy)
        self.save()

    def start(self,task_id,*,legacy_models=0,legacy_tools=0):
        self._id(task_id)
        if task_id not in self.data['tasks']:
            self.data['tasks'][task_id]={'policy':copy.deepcopy(self.data['policy']),'model_requests':[],
                                         'tool_calls':{},'active_seconds':0.,'legacy_model_calls':legacy_models,'legacy_tool_calls':legacy_tools}
            self.save()
        return self.data['tasks'][task_id]

    def summary(self,task_id=None):
        tasks=[self.data['tasks'][task_id]] if task_id in self.data['tasks'] else list(self.data['tasks'].values()) if task_id is None else []
        rows=[r for task in tasks for r in task['model_requests']]
        known=[r['usage'] for r in rows if r.get('usage') is not None]
        reserved=[r['reserved'] for r in rows if r.get('usage') is None]
        result={'model_calls':len(rows)+sum(t.get('legacy_model_calls',0) for t in tasks),'legacy_unknown_requests':sum(t.get('legacy_model_calls',0) for t in tasks),
                'tool_calls':sum(len(t['tool_calls'])+t.get('legacy_tool_calls',0) for t in tasks),
                'known_input_tokens':sum(r['input_tokens'] for r in known),'known_output_tokens':sum(r['output_tokens'] for r in known),
                'unknown_usage_requests':len(reserved)+sum(t.get('legacy_model_calls',0) for t in tasks),
                'reserved_input_tokens':sum(r['input_tokens'] for r in reserved),'reserved_output_tokens':sum(r['output_tokens'] for r in reserved),
                'active_seconds':sum(t['active_seconds'] for t in tasks),'uncertain_tool_calls':sum(r['status']=='inflight' for t in tasks for r in t['tool_calls'].values())}
        if len(tasks)==1:
            p=tasks[0]['policy'];result['policy']=copy.deepcopy(p)
            rates=(p['input_per_million'],p['output_per_million'])
            result['known_cost']=None if any(r is None for r in rates) else (result['known_input_tokens']*rates[0]+result['known_output_tokens']*rates[1])/1e6
            result['cost_with_reservations']=None if result['known_cost'] is None else result['known_cost']+(result['reserved_input_tokens']*rates[0]+result['reserved_output_tokens']*rates[1])/1e6
            result['currency']=p['currency']
        return result

    def _check(self,task_id,kind,reserved=None):
        task=self.start(task_id);p=task['policy'];s=self.summary(task_id)
        if s[kind+'_calls']>=p['max_'+kind+'_calls']:raise TaskControlError('workflow_budget_exhausted','本任务的'+('模型请求' if kind=='model' else '工具调用')+'预算已用尽，暂停和重启不会重置。','budget_exhausted')
        if p['max_active_seconds'] is not None and s['active_seconds']>=p['max_active_seconds']:raise TaskControlError('workflow_time_exhausted','本任务活动用时预算已用尽。','budget_exhausted')
        if reserved:
            if s['legacy_unknown_requests'] and any(p[k] is not None for k in ('max_cost','max_input_tokens','max_output_tokens')):raise TaskControlError('legacy_usage_unknown','旧任务缺少历史用量，无法在新增token或金额上限下确认余额；请保留记录并开始新任务。','budget_exhausted')
            for name in ('input_tokens','output_tokens'):
                ceiling=p['max_'+name]
                if ceiling is not None and s['known_'+name]+s['reserved_'+name]+reserved[name]>ceiling:raise TaskControlError('workflow_token_budget','下一请求的预留用量超过本任务token预算。','budget_exhausted')
            if p['max_cost'] is not None:
                projected=s['cost_with_reservations']+(reserved['input_tokens']*p['input_per_million']+reserved['output_tokens']*p['output_per_million'])/1e6
                if projected>p['max_cost']:raise TaskControlError('workflow_cost_budget','下一请求的预留金额超过本任务配置预算。','budget_exhausted')

    def model_call(self,task_id,model,messages,*,before_start=None):
        from .research_objects import canonical
        task=self.start(task_id);adapter=getattr(model,'actual',model)
        settings=getattr(adapter,'settings',None);output=min(getattr(settings,'max_output_tokens',None) or task['policy']['request_output_tokens'],task['policy']['request_output_tokens'])
        reserved={'input_tokens':len(canonical(messages).encode('utf-8'))+2048,'output_tokens':output}
        self._check(task_id,'model',reserved)
        if before_start is not None:before_start()
        row={'id':uuid.uuid4().hex,'status':'uncertain','reserved':reserved,'usage':None,'request_sha256':fingerprint(messages)}
        from .model_config import ModelSettings
        if isinstance(settings,ModelSettings):
            row['model_selection']={'model':settings.model,'protocol':settings.mode,'reasoning_effort':getattr(settings,'reasoning_effort',None)}
        task['model_requests'].append(row);self.save();started=time.monotonic()
        if hasattr(adapter,'last_usage'):adapter.last_usage=None
        try:
            kwargs={'max_output_tokens':output} if 'max_output_tokens' in inspect.signature(model.complete).parameters else {}
            result=model.complete(messages,**kwargs);row['status']='completed';return result
        finally:
            row['usage']=usage_tokens(getattr(adapter,'last_usage',None));elapsed=time.monotonic()-started
            row['seconds']=elapsed;task['active_seconds']+=elapsed;self.save()

    def tool_call(self,task_id,key,observation,registry,invoke,*,before_start=None):
        self._id(key);task=self.start(task_id)
        identity={k:observation[k] for k in ('tool','arguments','graph_inputs','research_refs') if k in observation}
        signature=fingerprint({'input':identity,'core':assert_integrity()['manifest_sha256'],'environment':environment_info(),'tool':registry.tools[observation['tool']].definition()['status'],
                               'source':(registry.tools[observation['tool']].documentation or {}).get('source_sha256')})
        entry=task['tool_calls'].get(key)
        if entry is not None and entry['signature']!=signature:raise ValueError('保存的执行意图与当前输入、版本或工具来源不一致。')
        if entry is None:
            for old_key,old in task['tool_calls'].items():
                if old['signature']==signature and old['status'] in ('inflight','interrupted','failed'):
                    try:result=self._recover(old,identity)
                    except (ValueError,OSError,KeyError,TypeError):raise RecoveryRequired(old_key) from None
                    old['status']='complete';self.save();result['reused_execution']=old_key;return result,old['operation_id']
        if entry is None and task['policy']['reuse_results'] and observation['tool']!='research_environment':
            for old_key,old in task['tool_calls'].items():
                if old['signature']==signature and old['status']=='complete':
                    result=self._recover(old,identity);result['reused_execution']=old_key;return result,old['operation_id']
        if entry is None:
            self._check(task_id,'tool')
            if before_start is not None:before_start()
            entry={'signature':signature,'operation_id':uuid.uuid4().hex,'tool':identity['tool'],'status':'inflight'}
            task['tool_calls'][key]=entry;self.save()
        workspace=self.directory/'tasks'/('task_'+entry['operation_id'])
        if entry['status'] not in ('inflight','complete') and not workspace.exists():raise RecoveryRequired(key)
        if entry['status']=='complete' or workspace.exists():
            try:
                result=self._recover(entry,identity);entry['status']='complete';self.save();result['reused_execution']=key;return result,entry['operation_id']
            except (ValueError,OSError,KeyError,TypeError):raise RecoveryRequired(key) from None
        started=time.monotonic()
        try:
            result=invoke(entry['operation_id']);entry['status']='complete';return result,entry['operation_id']
        except (InterruptedError,KeyboardInterrupt):entry['status']='interrupted';raise
        except Exception:
            entry['status']='failed';raise
        finally:
            entry['seconds']=time.monotonic()-started;task['active_seconds']+=entry['seconds'];self.save()

    def _recover(self,entry,identity):
        from .results import _execution
        observation=entry.get('observation')
        if not observation:
            workspace=self.directory/'tasks'/('task_'+entry['operation_id'])
            receipt=read_json(workspace/'execution.json')[0]
            if receipt.get('status')!='complete':raise ValueError('没有完成回执。')
            payload=read_json(workspace/'result.json',max_bytes=4*1024*1024)[0]
            observation={**copy.deepcopy(identity),'ok':True,'result':payload['result'],'execution':{'task_id':workspace.name,'directory':str(workspace.resolve()),'receipt_sha256':file_hash(workspace/'execution.json')}}
        if any(fingerprint(observation.get(k))!=fingerprint(identity.get(k)) for k in ('tool','arguments','graph_inputs','research_refs')):raise ValueError('保存的结果不属于本次执行输入。')
        if _execution(SimpleNamespace(directory=self.directory),observation,'recovered',False,[])[0]!='verified_execution':raise ValueError('结果缺少有效回执。')
        return {k:copy.deepcopy(observation[k]) for k in ('result','execution')}

    def permit_retry(self,task_id,key):
        task=self.data['tasks'][task_id];entry=task['tool_calls'][key]
        if entry['status']=='complete':
            try:
                request=read_json(self.directory/'tasks'/('task_'+entry['operation_id'])/'request.json',max_bytes=256*1024)[0]
                self._recover(entry,{k:request[k] for k in ('arguments','graph_inputs','research_refs') if k in request}|{'tool':request['name']})
            except (ValueError,OSError,KeyError,TypeError):pass
            else:raise ValueError('已完成步骤应复用回执，不应重新执行。')
        # Retain the charged attempt; the new intent consumes another slot.
        entry['status']='abandoned';entry['signature']='abandoned:'+entry['signature']
        task['tool_calls'][uuid.uuid4().hex]=entry;del task['tool_calls'][key]
        self.save()
