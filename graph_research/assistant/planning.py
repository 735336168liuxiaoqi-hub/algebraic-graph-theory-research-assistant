"""Bounded existing-tool plans and JSON-only dependency resolution."""
import copy
import uuid
import jsonschema

from .research_objects import canonical,fingerprint,get_object,prepare_call
from .task_contract import obj,JSON_PATH
from graph_research.graph_input.adapters import graph_targets

IDENTIFIER={'type':'string','pattern':r'^[A-Za-z][A-Za-z0-9_-]{0,31}$'}
REF=obj({'id':{'type':'string'},'version':{'type':'integer'}},['id','version'])
STEP_REF=obj({'step':IDENTIFIER},['step'])
BINDING=obj({'step':IDENTIFIER,'path':JSON_PATH},['step','path'])
STEP=obj({'id':IDENTIFIER,'description':{'type':'string','minLength':1,'maxLength':300},
          'tool':{'type':'string','minLength':1,'maxLength':64},'arguments':{'type':'object'},
          'bindings':{'type':'object','maxProperties':32,'additionalProperties':BINDING},
          'graph_refs':{'type':'object','minProperties':1,'maxProperties':12,'additionalProperties':{'oneOf':[REF,STEP_REF]}},
          'independent_graph':{'type':'boolean'}},['id','description','tool','arguments'])
PLAN=obj({'title':{'type':'string','minLength':1,'maxLength':300},
          'steps':{'type':'array','minItems':1,'maxItems':10,'items':STEP},'pause':{'type':'boolean'}},['title','steps'])


def new_plan(spec,registry,objects,control=None,review=False):
    if len(canonical(spec).encode('utf-8'))>100000:raise ValueError('任务计划超过100KB。')
    jsonschema.validate(spec,PLAN)
    if control is not None and len(spec['steps'])>control.record['policy']['max_tool_calls']-control.record['usage']['tool_calls']:raise ValueError('计划超过本任务剩余工具调用预算，请缩小范围。')
    known=set();steps=copy.deepcopy(spec['steps'])
    for step in steps:
        if step['id'] in known:raise ValueError('计划步骤编号不能重复。')
        if control is not None and not control.allowed(step['tool']):raise ValueError('计划包含未获允许的工具。')
        definition=registry.describe(step['tool']);props=definition['parameters']['properties']
        if objects.get('active') and graph_targets(definition) and not step.get('graph_refs') and step.get('independent_graph') is not True:raise ValueError('计划必须明确绑定研究对象，另外构图请标明independent_graph:true。')
        for key,binding in step.get('bindings',{}).items():
            if key not in props or key in step['arguments'] or binding['step'] not in known:raise ValueError('参数绑定必须使用独立参数并引用前序步骤。')
        dynamic=False
        for target,ref in step.get('graph_refs',{}).items():
            if target not in graph_targets(definition):raise ValueError('计划图对象的目标位置不适用。')
            if 'step' in ref:
                if ref['step'] not in known:raise ValueError('图版本只能来自前序步骤。')
                dynamic=True
            else:get_object(objects,ref)
        args=step['arguments']
        if step.get('graph_refs') and not dynamic:args=prepare_call(definition,args,step['graph_refs'],objects)[0]
        # Validate all immediately known fields before any planned calculation.
        for key,value in args.items():
            if key not in props:raise ValueError('计划包含未知参数：'+key)
            jsonschema.validate(value,props[key])
        if not step.get('bindings') and not dynamic:jsonschema.validate(args,definition['parameters'])
        step['status']='waiting';known.add(step['id'])
    return {'id':uuid.uuid4().hex,'scope_sha256':fingerprint(spec),'spec':copy.deepcopy(spec),'title':spec['title'],'steps':steps,'cursor':0,
            'status':'awaiting_review' if review or spec.get('pause',False) else 'running'}


def validate_saved_plan(plan):
    jsonschema.validate(plan['spec'],PLAN)
    actual=[{k:v for k,v in step.items() if k!='status'} for step in plan['steps']]
    if fingerprint(plan['spec'])!=plan['scope_sha256'] or actual!=plan['spec']['steps'] or plan['title']!=plan['spec']['title'] or type(plan['cursor']) is not int or not 0<=plan['cursor']<=len(actual):raise ValueError('保存的计划范围或步骤已变化。')
    for index,step in enumerate(plan['steps']):
        if index<plan['cursor'] and step['status']!='completed':raise ValueError('保存的计划进度不一致。')
    return plan


def read_path(value,path):
    for component in path:
        if isinstance(value,dict) and isinstance(component,str):value=value[component]
        elif isinstance(value,list) and type(component) is int and 0<=component<len(value):value=value[component]
        else:raise ValueError('结果路径只能读取JSON键或有效列表索引。')
    return copy.deepcopy(value)


def resolve_step(plan,observations):
    validate_saved_plan(plan)
    step=plan['steps'][plan['cursor']];known={o['plan_step']:o for o in observations if o.get('plan_id')==plan['id'] and o.get('ok') and 'plan_step' in o}
    decision={k:copy.deepcopy(step[k]) for k in ('tool','arguments','graph_refs','independent_graph') if k in step};decision['action']='call'
    for key,binding in step.get('bindings',{}).items():
        if binding['step'] not in known:raise ValueError('前序步骤没有成功结果，不能继续绑定。')
        try:decision['arguments'][key]=read_path(known[binding['step']]['result'],binding['path'])
        except (KeyError,IndexError,TypeError):raise ValueError('前序结果没有所需字段：'+key) from None
    for target,ref in decision.get('graph_refs',{}).items():
        if 'step' in ref:
            previous=known.get(ref['step'],{})
            if not previous.get('output_graph_ref'):raise ValueError('前序步骤没有可复用的新图版本。')
            decision['graph_refs'][target]=copy.deepcopy(previous['output_graph_ref'])
    return decision


def plan_text(plan):
    if not plan:return ''
    names={'waiting':'待执行','running':'执行中','completed':'已完成','failed':'失败'}
    lines=[plan['title']]
    indexes={step['id']:i for i,step in enumerate(plan['steps'],1)}
    for index,step in enumerate(plan['steps'],1):
        lines.append(str(index)+'. '+step['description']+' · '+names.get(step['status'],step['status']))
        refs=[]
        for target,ref in step.get('graph_refs',{}).items():
            role={'graph':'输入图','left':'左侧图','right':'右侧图','base':'初始图','case':'批量图'}.get(target,target)
            refs.append(role+'：'+('取自第'+str(indexes.get(ref['step'],'?'))+'步的新图' if 'step' in ref else ref['id']+' 第'+str(ref['version'])+'版'))
        if refs:lines.append('   '+'；'.join(refs))
    if plan.get('error'):lines.append('暂停原因：'+plan['error'])
    return '\n'.join(lines)
