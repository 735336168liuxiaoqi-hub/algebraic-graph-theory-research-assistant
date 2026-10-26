"""Explicit finite candidate collections; prepare is never converted to execute."""
import json

import jsonschema

from graph_research.errors import TaskProtocolError,FieldValidationError,schema_protocol_error
from .research_contract import obj,NAME,NUMBER,PROBLEM_SCHEMA,validate_problem,number,leaves
from graph_research.runtime.resources import MAX_EVALUATIONS,MAX_WALL_SECONDS,MAX_CPU_SECONDS,MAX_MEMORY_MB
from graph_research.runtime.serialization import json_fingerprint as digest


INTERNAL_OPERATION='experiment_evaluate'
CANDIDATE_SCHEMA=obj({'n':{'type':'integer','minimum':1,'maximum':128},
    'edges':{'type':'array','maxItems':1024,'items':{'type':'array','minItems':2,'maxItems':128,
        'items':{'type':'integer','minimum':0,'maximum':127}}}},['n','edges'])
CASE_SCHEMA=obj({'id':NAME,'parameters':{'type':'object','maxProperties':16,'propertyNames':NAME,'additionalProperties':NUMBER},
                 'candidates':{'type':'array','minItems':1,'maxItems':64,'items':CANDIDATE_SCHEMA}},['id','parameters','candidates'])
EXECUTE_SCHEMA=obj({'operation':{'const':'execute'},'problem':PROBLEM_SCHEMA,
    'cases':{'type':'array','minItems':1,'maxItems':32,'items':CASE_SCHEMA},
    'chunk_size':{'type':'integer','minimum':1,'maximum':16},
    'segment_chunks':{'type':'integer','minimum':1,'maximum':256},
    'pause_at_checkpoints':{'type':'boolean','description':'明确需要科研反馈时，在segment_chunks个分段后暂停；默认false，与权限审批分开。'},
    'budget':obj({'max_evaluations':{'type':'integer','minimum':1,'maximum':MAX_EVALUATIONS},
                  'wall_seconds':{'type':'number','minimum':1,'maximum':MAX_WALL_SECONDS},
                  'cpu_seconds':{'type':'integer','minimum':1,'maximum':MAX_CPU_SECONDS},
                  'memory_mb':{'type':'integer','minimum':64,'maximum':MAX_MEMORY_MB}},
                 ['max_evaluations','wall_seconds','cpu_seconds','memory_mb'])},['operation','problem','cases','budget'])


def resolve(value,parameters):return number(parameters[value['parameter']]) if isinstance(value,dict) else number(value)


def bind_parameters(problem,values):
    if set(values)!=set(problem['parameters']):raise ValueError('每个实例须恰好为全部研究参数赋值。')
    result={}
    for key,spec in problem['parameters'].items():
        v=number(values[key])
        if spec['kind']=='integer' and v.denominator!=1:raise ValueError('整数参数不得使用非整数。')
        if spec['role']=='fixed' and v!=number(spec['value']):raise ValueError('实例不能改变固定参数。')
        if 'minimum' in spec and v<number(spec['minimum']) or 'maximum' in spec and v>number(spec['maximum']):raise ValueError('实例参数超出声明范围。')
        if 'values' in spec and v not in {number(t) for t in spec['values']}:raise ValueError('实例参数不属于声明候选值。')
        meaning=spec['meaning']
        if meaning=='alpha' and not 0<=v<=1:raise ValueError('alpha应在[0,1]内。')
        if meaning not in ('alpha','other') and v<0:raise ValueError('计数不得为负。')
        if meaning in ('order','max_degree_vertices') and v<1 or meaning in ('uniformity','clique_order') and v<2:raise ValueError('对象规模参数不合法。')
        result[key]=int(v) if v.denominator==1 else str(v)
    return result


def validate_candidate(value,kind):
    try:jsonschema.validate(value,CANDIDATE_SCHEMA)
    except jsonschema.ValidationError as error:
        raise schema_protocol_error(error,'invalid_candidate','候选图字段无效。') from None
    n=value['n'];edges=value['edges'];seen=set()
    if kind not in ('simple_graph','hypergraph','uniform_hypergraph','uniform_hypertree'):raise ValueError('未知的研究对象类型。')
    if kind!='simple_graph' and (len(edges)>128 or sum(map(len,edges))>2048):raise ValueError('超图至多128条边、2048次关联。')
    for index,edge in enumerate(edges):
        if len(set(edge))!=len(edge):
            error=FieldValidationError(['edges',index],{'uniqueItems':True},'简单图不允许自环。' if kind=='simple_graph' and len(edge)==2 else '同一条超边内不能重复顶点。')
            error.code='self_loop' if kind=='simple_graph' and len(edge)==2 else 'duplicate_vertex'
            raise error
        for vertex_index,vertex in enumerate(edge):
            if vertex>=n:
                error=FieldValidationError(['edges',index,vertex_index],{'type':'integer','minimum':0,'maximum':n-1},'顶点编号必须小于声明的n。')
                error.code='vertex_out_of_range';raise error
        if kind=='simple_graph' and len(edge)!=2:raise FieldValidationError(['edges',index],{'minItems':2,'maxItems':2},'普通图的边必须有两个顶点。')
        key=tuple(sorted(edge))
        if key in seen:
            error=FieldValidationError(['edges',index],{'uniqueItems':True},'该边与前面的边重复，顶点顺序不影响判定。')
            error.code='duplicate_edge';raise error
        seen.add(key)
    return {'n':n,'edges':[list(e) for e in sorted(seen)]}


def validate_execute(value):
    from .adapters import check_supported
    try:
        jsonschema.validate(value,EXECUTE_SCHEMA)
        result=json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False))
        result['problem']=validate_problem(result['problem']);problem=result['problem'];known=set();count=0
        if problem['intent']=='counterexample':raise ValueError('反例执行还需要正式的待检验命题接口；当前仅评价明确候选集合。')
        for case_index,case in enumerate(result['cases']):
            if case['id'] in known:raise ValueError('实验实例ID不能重复。')
            known.add(case['id']);case['parameters']=bind_parameters(problem,case['parameters'])
            try:check_supported(problem,case['parameters'])
            except FieldValidationError as error:
                raise TaskProtocolError('invalid_experiment_execution',str(error),field_path=['problem',*error.field_path],validation=error.validation) from None
            checked=[]
            for candidate_index,candidate in enumerate(case['candidates']):
                try:checked.append(validate_candidate(candidate,problem['object']['type']))
                except (FieldValidationError,TaskProtocolError) as error:
                    failure=TaskProtocolError('invalid_experiment_execution',str(error),
                        field_path=['cases',case_index,'candidates',candidate_index,*getattr(error,'field_path',[])],
                        validation=getattr(error,'validation',{}))
                    failure.error_code=error.code;raise failure from None
            case['candidates']=checked
            count+=len(case['candidates'])
            if any(c['n']>16 for c in case['candidates']) and any(n['predicate']=='matching_number' for n,_ in leaves(problem.get('constraints',{'all':[]}))):
                raise ValueError('独立匹配数核验目前限16顶点。')
        if count>256:raise ValueError('一次执行至多256个明确候选。')
        if count>result['budget']['max_evaluations']:raise ValueError('候选数超过本次评价预算，未执行计算。')
        result.setdefault('chunk_size',4);result.setdefault('segment_chunks',256);result.setdefault('pause_at_checkpoints',False)
        return result
    except jsonschema.ValidationError as error:
        raise schema_protocol_error(error,'invalid_experiment_execution','实验执行字段无效。') from None
    except TaskProtocolError:raise
    except (ValueError,TypeError,KeyError) as error:
        raise TaskProtocolError('invalid_experiment_execution',str(error) if isinstance(error,ValueError) and not isinstance(error,jsonschema.ValidationError) else '实验执行输入不符合有限候选协议。') from None


def compile_execution(value):
    spec=validate_execute(value);jobs=[]
    for case in spec['cases']:
        for start in range(0,len(case['candidates']),spec['chunk_size']):
            jobs.append({'id':'job'+str(len(jobs)+1),'arguments':{'problem':spec['problem'],'case_id':case['id'],
                'parameters':case['parameters'],'candidates':[{'id':'candidate'+str(i+1),'graph':c} for i,c in enumerate(case['candidates'][start:start+spec['chunk_size']],start)]}})
    return {'request_sha256':digest(spec),'spec':spec,'jobs':jobs,'evaluations':sum(len(c['candidates']) for c in spec['cases']),
            'scope':'provided_candidate_collection','enumeration_complete':False,'general_theorem_proved':False}
