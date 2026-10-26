"""Finite reviewed studies: replaceable searches and bounded controller actions."""
import copy
import json
import math
import jsonschema

from graph_research.errors import TaskProtocolError,FieldValidationError,schema_protocol_error
from .research_contract import obj,NAME,NUMBER,PROBLEM_SCHEMA,validate_problem,leaves
from .execution_contract import bind_parameters,resolve,digest,EXECUTE_SCHEMA
from graph_research.runtime.resources import MAX_ROUNDS,MAX_BATCH_SIZE,MAX_EVALUATIONS,MAX_THREADS,MAX_SEGMENT_EVALUATIONS

OPERATION='experiment_search'
CASE_SCHEMA=obj({'id':NAME,'parameters':{'type':'object','maxProperties':16,'additionalProperties':NUMBER}},['id','parameters'])
KNOBS_SCHEMA=obj({'exploration':{'type':'number','minimum':0.01,'maximum':0.5},
    'elite_fraction':{'type':'number','minimum':0.1,'maximum':0.75},
    'penalty_weight':{'type':'number','minimum':0.1,'maximum':10}})
HYPOTHESIS_SCHEMA=obj({'id':NAME,'type':{'enum':['metric_bound','universal_structure','candidate_pattern']},
    'relation':{'enum':['le','ge']},'value':NUMBER,'property':{'enum':['regular','bipartite','complete_multipartite','is_tree','hypertree']},
    'expected':{'type':'boolean'},'statement':{'type':'string','maxLength':2000},'source':{'type':'string','maxLength':1000}},['id','type'])
STUDY_SCHEMA=obj({'operation':{'const':'study'},'problem':PROBLEM_SCHEMA,
    'cases':{'type':'array','minItems':1,'maxItems':8,'items':CASE_SCHEMA},
    'case_limit':{'type':'integer','minimum':1,'maximum':8},
    'methods':{'type':'array','minItems':1,'maxItems':4,'uniqueItems':True,'items':{'enum':['enumerate','random','local','cem']}},
    'seeds':{'type':'array','minItems':1,'maxItems':4,'uniqueItems':True,'items':{'type':'integer','minimum':0,'maximum':2**32-1}},
    'rounds':{'type':'integer','minimum':1,'maximum':MAX_ROUNDS},'batch_size':{'type':'integer','minimum':2,'maximum':MAX_BATCH_SIZE},
    'worker_rounds':{'type':'integer','minimum':1,'maximum':128,'description':'一个受保护进程连续训练的代数，共用模型与优化状态；每段计一次工具尝试，每段最多4096次候选评价。大研究建议显式配置。'},
    'cpu_threads':{'type':'integer','minimum':1,'maximum':MAX_THREADS,'description':'CPU数值线程数，不得超过宿主tool_threads；CPU秒按所有线程累计，与墙钟秒分别设置。'},
    'stagnation_patience':{'type':'integer','minimum':0,'maximum':MAX_ROUNDS,'description':'规则调度的停滞代数阈值；0表示不因停滞提前结束，仍受授权代数、评价数和时间预算限制。'},
    'segment_rounds':{'type':'integer','minimum':1,'maximum':128},'planner':{'enum':['rules','model']},
    'pause_at_checkpoints':{'type':'boolean','description':'用户明确需要科研反馈时才按segment_rounds暂停；默认false，不是资源审批。'},
    'adaptive':{'type':'boolean'},'knobs':KNOBS_SCHEMA,
    'max_edges':{'type':'integer','minimum':0,'maximum':128},
    'edge_sizes':{'type':'array','minItems':1,'maxItems':16,'uniqueItems':True,'items':{'type':'integer','minimum':2,'maximum':128}},
    'max_actions':{'type':'integer','minimum':1,'maximum':2048},
    'budget':EXECUTE_SCHEMA['properties']['budget'],
    'hypotheses':{'type':'array','maxItems':8,'items':HYPOTHESIS_SCHEMA}},['operation','problem','budget'])
ACTION_SCHEMA={'oneOf':[
    obj({'action':{'const':'run'},'run_id':NAME,'knobs':KNOBS_SCHEMA,'reason':{'type':'string','maxLength':1000}},['action','run_id','reason']),
    obj({'action':{'enum':['stop','request_scope_change']},'reason':{'type':'string','maxLength':1000},
        'hypotheses':{'type':'array','maxItems':4,'items':HYPOTHESIS_SCHEMA}},['action','reason'])]}


def required_arguments(problem,parameters):
    return {node['predicate']:node.get('arguments',{}) for node,required in leaves(problem.get('constraints',{'all':[]})) if required}


def space(problem,parameters,settings):
    """Describe construction, including any deliberate restriction of the space."""
    from .adapters import check_supported
    check_supported(problem,parameters);obj=problem['object'];kind=obj['type'];requirements=required_arguments(problem,parameters)
    k=int(resolve(obj['uniformity'],parameters)) if 'uniformity' in obj else None
    m=int(resolve(requirements['edge_count']['value'],parameters)) if 'edge_count' in requirements else None
    tree=kind=='uniform_hypertree' or 'hypertree' in requirements
    from .adapters import tensor_metric
    tensor_connected=tensor_metric(problem) and resolve(problem['objective'].get('arguments',{}).get('alpha',0),parameters)<1
    connected=tree or 'connected' in requirements or problem['objective']['metric']=='distance_spectral_radius' or tensor_connected
    n=int(resolve(obj['order'],parameters)) if 'order' in obj else (1+(k-1)*m if tree and k is not None and m is not None else None)
    if n is None:raise ValueError('搜索需声明图阶参数引用，或由一致超树条件推导阶数；参数可由prepare建议，无需用户预先选值。')
    if not 1<=n<=128:raise ValueError('搜索图阶限1..128。')
    if n>16 and any(node['predicate']=='matching_number' for node,_ in leaves(problem.get('constraints',{'all':[]}))):raise ValueError('独立匹配核验限16顶点。')
    sizes=[2] if kind=='simple_graph' else [k] if k is not None else sorted(settings.get('edge_sizes') or list(range(2,min(n,3)+1)))
    sizes=[s for s in sizes if s<=n]
    capacity=sum(math.comb(n,s) for s in sizes)
    maximum=min(settings['max_edges'],capacity,1024 if kind=='simple_graph' else 128)
    if kind!='simple_graph':maximum=min(maximum,2048//max(sizes,default=2))
    if m is not None:
        if m>capacity or m>(1024 if kind=='simple_graph' else 128):raise ValueError('固定边数超出该候选空间。')
        maximum=m
    if tree and kind!='simple_graph':
        if k is None:raise ValueError('非一致超树的专用构造尚待实现；一般非一致超图可正常搜索。')
        if (n-1)%(k-1):raise ValueError('该一致超树的阶数与一致度不相容。')
        implied=(n-1)//(k-1)
        if m is not None and m!=implied:raise ValueError('超树的n/k/m不相容。')
        m=maximum=implied
    minimum_edges=math.ceil((n-1)/(max(sizes,default=2)-1)) if connected else 0
    if (m if m is not None else maximum)<minimum_edges:raise ValueError('边数／max_edges不足以构造连通候选，请调整有限范围后重新审阅。')
    if kind!='simple_graph' and maximum*max(sizes,default=0)>2048:raise ValueError('超图构造关联次数超过2048。')
    return {'kind':kind,'n':n,'uniformity':k,'edge_count':m,'max_edges':maximum,'edge_sizes':sizes,'capacity':capacity,
        'tree':tree and kind!='simple_graph','connected':connected,'minimum_edges':minimum_edges,
        'restricted_edge_sizes':kind=='hypergraph' and sizes!=list(range(2,n+1)),
        'scope':'labelled_unweighted_distinct_edges','meaning':'Tree growth is used only when the tree condition is mandatory.'}


def validate_hypothesis(hypothesis,kind):
    jsonschema.validate(hypothesis,HYPOTHESIS_SCHEMA)
    if hypothesis['type']=='metric_bound':
        if set(hypothesis)-{'id','type','relation','value','statement','source'} or not {'relation','value'}<=set(hypothesis):raise ValueError('数值界假设需relation/value。')
        resolve(hypothesis['value'],{})
    else:
        if set(hypothesis)-{'id','type','property','expected','statement','source'} or not {'property','expected'}<=set(hypothesis):raise ValueError('结构假设需property/expected。')
        if kind!='simple_graph' and hypothesis['property'] in ('bipartite','complete_multipartite'):raise ValueError('普通图的分部性质不能直接代用于超图。')
        if kind!='simple_graph' and hypothesis['property']=='is_tree':raise ValueError('超图树性使用hypertree，明确指关联图连通无环。')
        if kind=='simple_graph' and hypothesis['property']=='hypertree':raise ValueError('普通图树性请使用is_tree。')
    return copy.deepcopy(hypothesis)


def compile_study(value):
    from .preparation import prepare_experiment
    try:
        jsonschema.validate(value,STUDY_SCHEMA)
        spec=json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False));spec['problem']=validate_problem(spec['problem'])
        if spec['problem']['intent']=='counterexample':raise ValueError('请使用明确的hypotheses检验命题；不能把高分直接称为反例。')
        for key,default in [('case_limit',2),('methods',['random','local']),('seeds',[42]),('rounds',2),('batch_size',8),('segment_rounds',128),('worker_rounds',1),('cpu_threads',1),
                            ('planner','rules'),('adaptive',True),('max_edges',128),('max_actions',1024),('stagnation_patience',0),('pause_at_checkpoints',False)]:spec.setdefault(key,default)
        spec.setdefault('knobs',{});spec['knobs']={**{'exploration':0.1,'elite_fraction':0.25,'penalty_weight':1.0},**spec['knobs']}
        if 'cases' not in spec:
            draft=prepare_experiment({'operation':'prepare','problem':spec['problem'],'max_cases':spec['case_limit'],'seed':spec['seeds'][0]})
            if any(i['kind']=='clarification' for i in draft['plan']['issues']):raise ValueError('数学解释仍需澄清；请先查看prepare的问题说明。')
            spec['cases']=[{'id':case['id'],'parameters':case['parameters']} for case in draft['plan']['cases']]
        if not spec['cases']:raise ValueError('没有可提议的参数实例；这不证明图类无解。')
        ids=set();runs=[]
        for case in spec['cases']:
            if case['id'] in ids:raise ValueError('实例ID重复。')
            ids.add(case['id']);case['parameters']=bind_parameters(spec['problem'],case['parameters'])
            domain=space(spec['problem'],case['parameters'],spec)
            for method in spec['methods']:
                if method=='enumerate' and domain['capacity']>20:raise ValueError('精确枚举当前限20个潜在超边／图边位置；改用random/local/cem。')
                actions=(domain['capacity'] if domain['kind']=='simple_graph' else domain['max_edges']*(max(domain['edge_sizes'],default=0)+1)+1)
                if method=='cem' and actions>spec['max_actions']:
                    raise TaskProtocolError('invalid_experiment_study',f'CEM需要{actions}个动作，当前max_actions为{spec["max_actions"]}，协议上限为2048；请缩小试跑范围或改用其他后端。',
                        field_path=['max_actions'],validation={'maximum':2048})
                for seed in spec['seeds']:runs.append({'id':'run'+str(len(runs)+1),'case_id':case['id'],'parameters':case['parameters'],'space':domain,'method':method,'seed':seed})
        if len(runs)>32:raise ValueError('一轮study至多32个方法／种子／参数组合。')
        planned=len(runs)*spec['rounds']*spec['batch_size']
        if planned>spec['budget']['max_evaluations']:
            raise TaskProtocolError('invalid_experiment_study',f'实验计划需要{planned}次候选评价，超过本次预算；未执行计算。',
                field_path=['budget','max_evaluations'],validation={'minimum':planned,'maximum':MAX_EVALUATIONS})
        if spec['batch_size']*spec['worker_rounds']>MAX_SEGMENT_EVALUATIONS:
            raise TaskProtocolError('invalid_experiment_study','单个计算分段最多4096次候选评价，请减小worker_rounds或batch_size。',field_path=['worker_rounds'],validation={'maximum':max(1,MAX_SEGMENT_EVALUATIONS//spec['batch_size'])})
        spec.setdefault('hypotheses',[])
        spec['hypotheses']=[validate_hypothesis(h,spec['problem']['object']['type']) for h in spec['hypotheses']]
        if len({h['id'] for h in spec['hypotheses']})!=len(spec['hypotheses']):raise ValueError('假设ID重复。')
        return {'spec':spec,'runs':runs,'planned_rounds':len(runs)*spec['rounds'],'planned_calls':len(runs)*math.ceil(spec['rounds']/spec['worker_rounds']),'planned_evaluations':planned,'request_sha256':digest(spec)}
    except jsonschema.ValidationError as error:
        raise schema_protocol_error(error,'invalid_experiment_study','study字段无效。') from None
    except FieldValidationError as error:
        raise TaskProtocolError('invalid_experiment_study',str(error),field_path=['problem',*error.field_path],validation=error.validation) from None
    except TaskProtocolError:raise
    except (ValueError,TypeError,KeyError) as error:
        raise TaskProtocolError('invalid_experiment_study',str(error) if isinstance(error,ValueError) and not isinstance(error,jsonschema.ValidationError) else 'study输入不符合有限研究协议。') from None


def validate_study(value):return compile_study(value)['spec']
