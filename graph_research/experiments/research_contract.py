"""Bounded data contracts for research experiments, independent of model SDKs."""
import copy
from fractions import Fraction
import json
import math
import re

import jsonschema

from graph_research.errors import TaskProtocolError,schema_protocol_error


FORMAT='graph-research-experiment/1'
NAME={'type':'string','pattern':'^[A-Za-z][A-Za-z0-9_]{0,31}$'}
NUMBER={'oneOf':[{'type':'number'},{'type':'string','maxLength':64}]}
REFERENCE={'oneOf':[NUMBER,{'type':'object','properties':{'parameter':NAME},'required':['parameter'],'additionalProperties':False}]}


def obj(properties,required=()):
    return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}


ARGUMENTS={'type':'object','maxProperties':8,'propertyNames':NAME,'additionalProperties':{'oneOf':[
    {'type':['number','string','boolean'],'maxLength':128},
    obj({'parameter':NAME},['parameter'])]}}
PARAMETER=obj({'kind':{'enum':['integer','real']},'role':{'enum':['fixed','explore']},
               'meaning':{'enum':['order','size','uniformity','max_degree','max_degree_vertices','clique_order','matching_number','alpha','other']},
               'value':NUMBER,'minimum':NUMBER,'maximum':NUMBER,
               'values':{'type':'array','minItems':1,'maxItems':32,'uniqueItems':True,'items':NUMBER}},['kind','role','meaning'])
CONSTRAINT={'oneOf':[
    obj({'predicate':NAME,'arguments':ARGUMENTS},['predicate']),
    obj({'all':{'type':'array','minItems':1,'maxItems':16,'items':{'$ref':'#/$defs/constraint'}}},['all']),
    obj({'any':{'type':'array','minItems':1,'maxItems':16,'items':{'$ref':'#/$defs/constraint'}}},['any']),
    obj({'not':{'$ref':'#/$defs/constraint'}},['not'])]}
PROBLEM_SCHEMA=obj({'version':{'const':1},'question':{'type':'string','minLength':1,'maxLength':4000},
    'intent':{'enum':['parameterized_extremum','extremum','counterexample','construction']},
    'object':obj({'type':{'enum':['simple_graph','hypergraph','uniform_hypergraph','uniform_hypertree']},'order':REFERENCE,'uniformity':REFERENCE},['type']),
    'parameters':{'type':'object','maxProperties':16,'propertyNames':NAME,'additionalProperties':PARAMETER},
    'constraints':{'$ref':'#/$defs/constraint'},
    'objective':obj({'metric':NAME,'direction':{'enum':['maximize','minimize','satisfy']},'arguments':ARGUMENTS},['metric','direction']),
    'assumptions':{'type':'array','maxItems':12,'items':{'type':'string','maxLength':1000}}},
    ['version','question','intent','object','parameters','objective'])
PROBLEM_SCHEMA['$defs']={'constraint':CONSTRAINT}
PROBLEM_SCHEMA['$id']='urn:graph-research:experiment:problem:1'
PREPARE_SCHEMA=obj({'operation':{'const':'prepare'},'problem':PROBLEM_SCHEMA,
    'max_cases':{'type':'integer','minimum':1,'maximum':32},'seed':{'type':'integer','minimum':0,'maximum':2**32-1}},['operation','problem'])
PLAN_SCHEMA=obj({'format':{'const':FORMAT},'problem_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},
    'phase':{'const':'preparation'},'status':{'enum':['draft','needs_clarification','capability_gap']},
    'executable':{'const':False},'approved':{'const':False},
    'cases':{'type':'array','maxItems':32,'items':obj({'id':NAME,'parameters':{'type':'object'},
        'derived':{'type':'object'},'feasibility':{'const':'necessary_conditions_only'}},['id','parameters','derived','feasibility'])},
    'issues':{'type':'array','items':obj({'code':NAME,'kind':{'enum':['clarification','capability_gap','notice']},
        'message':{'type':'string'}},['code','kind','message'])},
    'estimate':{'type':'object'},'coverage':{'type':'object'},'capabilities':{'type':'array','items':{'type':'object'}},
    'next_steps':{'type':'array','items':{'type':'string'}},'scientific_results':{'const':False}},
    ['format','problem_sha256','phase','status','executable','approved','cases','issues','estimate','coverage','capabilities','next_steps','scientific_results'])
FEEDBACK_SCHEMA=obj({'case_id':NAME,'status':{'enum':['planned','running','completed','failed','cancelled','interrupted']},
    'evaluations':{'type':'integer','minimum':0},'feasible_candidates':{'type':'integer','minimum':0},
    'objective_value':{'type':['number','null']},'reward_version':{'type':['string','null'],'maxLength':128},
    'evidence_ids':{'type':'array','maxItems':32,'items':NAME}},['case_id','status','evaluations','feasible_candidates','evidence_ids'])
CLAIM_SCHEMA=obj({'id':NAME,'statement':{'type':'string','minLength':1,'maxLength':4000},
    'level':{'enum':['numerical_observation','verified_instance','finite_coverage','literature_theorem','conjecture','proof_sketch']},
    'scope':{'type':'object'},'evidence_ids':{'type':'array','maxItems':32,'items':NAME},
    'limitations':{'type':'array','items':{'type':'string','maxLength':1000}}},['id','statement','level','scope','evidence_ids','limitations'])


def _error(message):raise TaskProtocolError('invalid_experiment',message)


def number(value):
    """Small finite JSON numbers or rational strings; no expression evaluation."""
    if type(value) not in (int,float,str):_error('参数只接受有限数或有理数字符串。')
    if isinstance(value,str) and (len(value)>64 or not re.fullmatch(r'[+-]?(?:\d+/\d+|\d+(?:\.\d+)?)',value)):
        _error('参数字符串使用整数、小数或分数，例如1/3；不接受表达式。')
    if isinstance(value,float) and not math.isfinite(value):_error('参数须为有限数。')
    try:result=Fraction(str(value))
    except (ValueError,ZeroDivisionError,OverflowError):_error('参数数值无效。')
    if abs(result)>10**9:_error('参数绝对值不能超过10^9。')
    return result


def _bounded(value,depth=0,counter=None):
    if counter is None:counter=[0]
    counter[0]+=1
    if depth>20 or counter[0]>4096:_error('实验定义嵌套或节点过多。')
    if isinstance(value,dict):
        for v in value.values():_bounded(v,depth+1,counter)
    elif isinstance(value,list):
        for v in value:_bounded(v,depth+1,counter)


def leaves(node,required=True,depth=0):
    if depth>4:_error('约束逻辑最多嵌套4层。')
    if 'predicate' in node:return [(node,required)]
    if 'not' in node:return leaves(node['not'],False,depth+1)
    key='all' if 'all' in node else 'any'
    return [leaf for child in node[key] for leaf in leaves(child,required and key=='all',depth+1)]


def validate_problem(value):
    _bounded(value)
    try:
        encoded=json.dumps(value,ensure_ascii=False,allow_nan=False)
        if len(encoded.encode('utf-8'))>32768:_error('实验问题最多32KiB。')
        jsonschema.validate(value,PROBLEM_SCHEMA)
    except jsonschema.ValidationError as error:
        raise schema_protocol_error(error,'invalid_experiment','实验问题字段无效。') from None
    except (ValueError,TypeError):_error('实验问题结构不符合协议；请查看experiment_contracts。')
    result=json.loads(encoded);parameters=result['parameters']
    for name,spec in parameters.items():
        if spec['role']=='fixed':
            if 'value' not in spec or set(spec)&{'minimum','maximum','values'}:_error('固定参数只提供value。')
        elif 'value' in spec:_error('探索参数使用范围或values，不提供固定value。')
        if 'values' in spec and set(spec)&{'minimum','maximum'}:_error('参数使用values或上下界之一。')
        values=[number(v) for key in ('value','minimum','maximum') if (v:=spec.get(key)) is not None]
        values += [number(v) for v in spec.get('values',[])]
        if 'minimum' in spec and 'maximum' in spec and number(spec['minimum'])>number(spec['maximum']):_error('参数下界不能大于上界。')
        if len({number(v) for v in spec.get('values',[])})!=len(spec.get('values',[])):_error('values中存在数值相同的重复项。')
        if spec['kind']=='integer' and any(v.denominator!=1 for v in values):_error('整数参数不能含非整数值。')
        meaning=spec['meaning']
        if meaning not in ('alpha','other') and spec['kind']!='integer':_error('规模、度和计数参数应声明为integer。')
        if meaning=='alpha' and any(not 0<=v<=1 for v in values):_error('alpha参数范围为[0,1]。')
        if meaning in ('order','uniformity','max_degree_vertices','clique_order') and any(v<1 for v in values):_error('对象规模和计数参数须为正。')
        if meaning in ('uniformity','clique_order') and any(v<2 for v in values):_error('一致度或禁团阶数至少为2。')
        if meaning in ('size','max_degree','matching_number') and any(v<0 for v in values):_error('边数、最大度和匹配数不能为负。')
    def references(v):
        if isinstance(v,dict):
            if set(v)=={'parameter'} and v['parameter'] not in parameters:_error('引用了未声明的参数。')
            for child in v.values():references(child)
        elif isinstance(v,list):
            for child in v:references(child)
    references(result['object']);references(result['objective']);references(result.get('constraints',{}))
    predicates=leaves(result['constraints']) if 'constraints' in result else []
    if len(predicates)>32:_error('约束最多32个叶节点。')
    signatures={'connected':set(),'hypertree':set(),'clique_free':{'r'},'edge_count':{'value'},'max_degree':{'value'},
                'max_degree_vertex_count':{'value'},'matching_number':{'value'}}
    def typed(value,meaning):
        if isinstance(value,dict):
            if parameters[value['parameter']]['meaning']!=meaning:_error('参数含义与引用位置不一致：'+meaning)
        else:
            v=number(value)
            if meaning=='alpha':
                if not 0<=v<=1:_error('alpha须在[0,1]内。')
            elif v.denominator!=1 or v<0 or (meaning in ('order','uniformity','max_degree_vertices','clique_order') and v<1) or (meaning in ('uniformity','clique_order') and v<2):
                _error('计数、阶数或一致度数值无效。')
    for key,meaning in [('order','order'),('uniformity','uniformity')]:
        if key in result['object']:typed(result['object'][key],meaning)
    if result['object']['type']=='simple_graph' and 'uniformity' in result['object']:_error('普通图不另行指定超边一致度。')
    for predicate,_ in predicates:
        name=predicate['predicate'];args=predicate.get('arguments',{})
        if name in signatures and set(args)!=signatures[name]:_error('已有约束的参数名称不符合契约。')
        meaning={'clique_free':'clique_order','edge_count':'size','max_degree':'max_degree',
                 'max_degree_vertex_count':'max_degree_vertices','matching_number':'matching_number'}.get(name)
        if meaning:typed(args['r' if name=='clique_free' else 'value'],meaning)
    metric=result['objective']['metric'];arguments=result['objective'].get('arguments',{})
    if metric=='alpha_spectral_radius':
        if set(arguments)!={'alpha'}:_error('alpha_spectral_radius需明确alpha参数。')
        typed(arguments['alpha'],'alpha')
    elif metric in ('adjacency_spectral_radius','distance_spectral_radius','energy','edge_count') and arguments:
        _error('该指标不接受额外参数。')
    if result['object']['type'] in ('uniform_hypergraph','uniform_hypertree') and 'uniformity' not in result['object']:
        _error('一致超图需声明uniformity；具体取值可以是自由参数。')
    if result['object']['type']=='hypergraph' and 'uniformity' in result['object']:
        _error('指定一致度请使用uniform_hypergraph；hypergraph允许不同大小的超边。')
    result.setdefault('assumptions',[])
    return result


def validate_prepare(value):
    _bounded(value)
    try:jsonschema.validate(value,PREPARE_SCHEMA)
    except jsonschema.ValidationError as error:
        raise schema_protocol_error(error,'invalid_experiment','准备实验字段无效。') from None
    result=copy.deepcopy(value);result['problem']=validate_problem(result['problem'])
    return result


def operation_schema():
    from .execution_contract import EXECUTE_SCHEMA
    from .search_contract import STUDY_SCHEMA
    return {'oneOf':[PREPARE_SCHEMA,EXECUTE_SCHEMA,STUDY_SCHEMA]}


def validate_experiment(value):
    if value.get('operation')=='prepare':return validate_prepare(value)
    if value.get('operation')=='study':
        from .search_contract import validate_study
        return validate_study(value)
    from .execution_contract import validate_execute
    return validate_execute(value)


def contracts():
    from .preparation import capability_catalog
    from .execution_contract import EXECUTE_SCHEMA,CANDIDATE_SCHEMA
    from .search_contract import STUDY_SCHEMA,ACTION_SCHEMA
    from .controller import FEEDBACK_SCHEMA
    return copy.deepcopy({'protocol':FORMAT,'phase':7,'operations':['prepare','execute','study'],
        'problem':PROBLEM_SCHEMA,'preparation':PREPARE_SCHEMA,'plan':PLAN_SCHEMA,
        'execution':EXECUTE_SCHEMA,'candidate':CANDIDATE_SCHEMA,
        'study':STUDY_SCHEMA,'controller_action':ACTION_SCHEMA,'study_feedback':FEEDBACK_SCHEMA,
        'run_feedback':FEEDBACK_SCHEMA,'claim':CLAIM_SCHEMA,'capabilities':capability_catalog(),
        'meaning':'prepare only drafts; execute evaluates supplied candidates; study searches within a reviewed finite scope with optional CPU CEM and bounded planning. None establishes a general theorem.'})
