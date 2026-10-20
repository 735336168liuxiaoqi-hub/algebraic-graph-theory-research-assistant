"""Human-requested graph exports in a standalone chat; no model or approval action."""
import copy
import json
import uuid

import jsonschema

from .session import _session_action
from graph_research.runtime.runner import run_tool,TaskLimits

ALLOWED={'hypergraph_plot','graph_tikz','hypergraph_tikz','graph_layout','hypergraph_schematic'}


@_session_action
def present_graph(session,name,arguments,*,cancel_event=None,graph_inputs=None):
    mode=session.task_context.get('interaction_mode')
    if session.execution_control is not None or mode not in (None,'standalone_chat') or mode is None and session.results_mode!='api':raise ValueError('手工图形操作仅用于独立桌面对话，不接管委派任务。')
    if session.state.get('status')=='running':raise ValueError('请等待当前任务结束后再导出。')
    if name not in ALLOWED or name=='hypergraph_schematic' and arguments.get('operation','export')!='export':raise ValueError('手工入口仅接受已有图形导出/布局工具。')
    fresh=not session.turns and not session.state.get('question')
    registry=session._registry();definition=registry.describe(name)
    if registry.tools[name].status!='native_tested' or not definition['availability']['available']:raise ValueError('图形工具未就绪。')
    encoded=json.dumps(arguments,allow_nan=False)
    if len(encoded)>100000:raise ValueError('图形参数超过100000字符。')
    arguments=json.loads(encoded);jsonschema.validate(arguments,definition['parameters'])
    session.task_context.setdefault('interaction_mode','standalone_chat')
    if graph_inputs:
        from graph_research.graph_input.adapters import validate_bindings
        graph_inputs=validate_bindings(definition,arguments,graph_inputs)
    observation={'tool':name,'arguments':arguments,'tool_status':'native_tested','origin':'manual_graph'}
    if graph_inputs:observation['graph_inputs']=copy.deepcopy(graph_inputs)
    if fresh:
        session.state.update(question='手工图形处理',observations=[],conversation=[],status='tool_results_available',answer='手工图形处理，无模型请求。')
        session._begin_turn('手工图形处理')
    if not session.state.get('workflow_task_id'):
        session.state['workflow_task_id']=uuid.uuid4().hex
        if session.turns:session.turns[-1]['workflow_task_id']=session.state['workflow_task_id']
    task_id=session.state['workflow_task_id'];session.workflow.start(task_id);session._save()
    try:
        if cancel_event is not None and cancel_event.is_set():raise InterruptedError('用户已取消图形操作。')
        from dataclasses import replace
        limits=TaskLimits();usage=session.workflow.summary(task_id);ceiling=usage['policy']['max_active_seconds']
        if ceiling is not None:limits=replace(limits,wall_seconds=min(limits.wall_seconds,max(.001,ceiling-usage['active_seconds'])))
        def invoke(operation_id):
            return run_tool(name,arguments,session.store.directory,directory=session.directory/'tasks',limits=limits,cancel=cancel_event,include_receipt=True,
                operation_id=operation_id,**({'graph_inputs':graph_inputs} if graph_inputs else {}))
        value,operation_id=session.workflow.tool_call(task_id,uuid.uuid4().hex,observation,registry,invoke)
        observation.update(ok=True,result=value['result'],execution=value['execution'],operation_id=operation_id)
        if value.get('reused_execution'):observation['reused_execution']=value['reused_execution']
    except Exception as error:
        from graph_research.runtime.observability import error_details
        observation.update(ok=False,error=str(error),error_details=error_details(error,phase='manual.graph_presentation'))
    session.state.setdefault('observations',[]).append(observation)
    session._observe_tools(registry);session._save();session._finalize_output()
    return copy.deepcopy(observation)
