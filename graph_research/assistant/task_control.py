"""Host-enforced delegation limits; no model state can alter these counters."""
from dataclasses import dataclass,field,asdict

from graph_research.runtime.runner import TaskLimits
from .task_contract import TaskProtocolError


class TaskControlError(RuntimeError):
    def __init__(self,code,message,status='blocked'):
        self.code=code;self.status=status;super().__init__(message)


@dataclass(frozen=True)
class SubagentLimits:
    max_model_calls:int=10
    max_tool_calls:int=10
    allow_extensions:bool=True
    allowed_tools:tuple|None=None
    tool_limits:TaskLimits=field(default_factory=TaskLimits)

    def __post_init__(self):
        if type(self.max_model_calls) is not int or not 0<=self.max_model_calls<=40:raise ValueError('Invalid host model-call ceiling')
        if type(self.max_tool_calls) is not int or not 0<=self.max_tool_calls<=100:raise ValueError('Invalid host tool-call ceiling')
        if type(self.allow_extensions) is not bool:raise ValueError('allow_extensions must be boolean')
        if self.allowed_tools is not None and (not isinstance(self.allowed_tools,tuple) or any(not isinstance(n,str) for n in self.allowed_tools)):raise ValueError('Host allowed_tools must be a tuple or None')

    def resolve(self,task):
        constraints=task['constraints']
        model_mode=task['execution']['mode']=='agent' or (task['execution']['mode']=='counterexample' and task['execution']['counterexample'].get('planner','rules')=='model')
        policy={'max_model_calls':constraints.get('max_model_calls',self.max_model_calls if model_mode else 0),
                'max_tool_calls':constraints.get('max_tool_calls',self.max_tool_calls),
                'allow_extensions':constraints.get('allow_extensions',self.allow_extensions),
                'allowed_tools':constraints.get('allowed_tools',list(self.allowed_tools) if self.allowed_tools is not None else None),
                'tool_limits':asdict(self.tool_limits)}
        for key in ('max_model_calls','max_tool_calls'):
            if policy[key]>getattr(self,key):raise TaskProtocolError('host_limit_exceeded','请求不能提高宿主的调用预算。')
        if policy['allow_extensions'] and not self.allow_extensions:raise TaskProtocolError('host_limit_exceeded','宿主不允许开发扩展。')
        if self.allowed_tools is not None and (policy['allowed_tools'] is None or not set(policy['allowed_tools'])<=set(self.allowed_tools)):
            raise TaskProtocolError('host_limit_exceeded','请求的工具超出宿主白名单。')
        for key,value in constraints.get('tool_limits',{}).items():
            if value>policy['tool_limits'][key]:raise TaskProtocolError('host_limit_exceeded','请求不能提高宿主的单次计算限额。')
            policy['tool_limits'][key]=value
        TaskLimits(**policy['tool_limits'])
        if task['execution']['mode']=='batch':
            from .batch_workflow import compile_batch
            steps=compile_batch(task)['steps']
            if len(steps)>policy['max_tool_calls']:raise TaskProtocolError('batch_budget_insufficient',f"批量展开需要{len(steps)}次工具尝试，当前预算{policy['max_tool_calls']}；未执行任何步骤。")
            if policy['allowed_tools'] is not None and any(step['tool'] not in policy['allowed_tools'] for step in steps):raise TaskProtocolError('tool_not_permitted','批量计划使用了宿主白名单之外的工具。')
        if task['execution']['mode']=='scan':
            from .spectral_scan import execution_steps
            steps=execution_steps(task)
            if len(steps)>policy['max_tool_calls']:raise TaskProtocolError('scan_budget_insufficient',f"扫描需要{len(steps)}次工具尝试，当前预算{policy['max_tool_calls']}；请由可信宿主显式配置足够额度，未执行或拆分绕过预算。")
            if policy['allowed_tools'] is not None and any(step['tool'] not in policy['allowed_tools'] for step in steps):raise TaskProtocolError('tool_not_permitted','扫描使用的构图/谱工具不在宿主白名单。')
        if task['execution']['mode']=='tools':
            from .spectral_scan import execution_steps
            required=len(execution_steps(task))
            if required>policy['max_tool_calls'] and constraints.get('fail_fast',False):
                raise TaskProtocolError('tools_budget_insufficient',f"固定步骤需要{required}次工具尝试，超过预算{policy['max_tool_calls']}；fail_fast已启用，整体拒绝且未执行任何步骤。默认不启用fail_fast时保留跑满预算并保留前序结果的语义。")
        if task['execution']['mode']=='counterexample':
            required={'graph_counterexample_round','graph_counterexample_verify'}
            if policy['max_tool_calls']<2:raise TaskProtocolError('search_budget_insufficient','反例搜索至少预留一轮搜索和一次独立核验，未开始计算。')
            if policy['allowed_tools'] is not None and not required<=set(policy['allowed_tools']):raise TaskProtocolError('tool_not_permitted','反例搜索及独立核验工具必须同时在宿主白名单中。')
            if model_mode and policy['max_model_calls']<1:raise TaskProtocolError('search_model_disabled','模型策略需要宿主显式提供模型预算；可选择rules离线运行。')
        return policy

    def accepts(self,policy):
        if policy['max_model_calls']>self.max_model_calls or policy['max_tool_calls']>self.max_tool_calls:return False
        if policy['allow_extensions'] and not self.allow_extensions:return False
        if self.allowed_tools is not None and (policy['allowed_tools'] is None or not set(policy['allowed_tools'])<=set(self.allowed_tools)):return False
        return all(value<=asdict(self.tool_limits)[key] for key,value in policy['tool_limits'].items())


class TaskExecutionControl:
    def __init__(self,record,save):self.record=record;self.save=save

    @property
    def tool_limits(self):return TaskLimits(**self.record['policy']['tool_limits'])

    def allowed(self,name):
        allowed=self.record['policy']['allowed_tools']
        return allowed is None or name in allowed or name in self.record.get('approved_tools',[])

    def catalog(self,registry):return [entry for entry in registry.catalog(detail='model') if self.allowed(entry['name'])]

    def _consume(self,kind):
        key=kind+'_calls';maximum=self.record['policy']['max_'+key]
        if self.record['usage'][key]>=maximum:raise TaskControlError('task_budget_exhausted','委派任务的总调用预算已用尽；恢复或换交互编号不能重置预算。','budget_exhausted')
        self.record['usage'][key]+=1;self.save(self.record)

    def before_model(self):self._consume('model')

    def before_tool(self,name):
        if not self.allowed(name):raise TaskControlError('tool_not_permitted','工具不在本任务的可用范围内：'+str(name))
        self._consume('tool')

    def before_extension(self):
        if not self.record['policy']['allow_extensions']:raise TaskControlError('extension_not_permitted','本任务不允许开发扩展；请由宿主重新委派允许提出开发申请的任务。')
