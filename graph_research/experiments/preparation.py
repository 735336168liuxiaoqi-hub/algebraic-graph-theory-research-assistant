"""Deterministic experiment preflight. No model, graph search or training runs."""
import copy
from fractions import Fraction
import hashlib
import json
import math
import random

import jsonschema

from .research_contract import FORMAT,PLAN_SCHEMA,validate_prepare,number,leaves


_HYPERGRAPHS=['hypergraph','uniform_hypergraph','uniform_hypertree']
_OBJECTS=['simple_graph',*_HYPERGRAPHS]
_METRICS={
    'adjacency_spectral_radius':(['simple_graph'],'adapter_available','graph_research.experiments.adapters'),
    'alpha_spectral_radius':(['simple_graph'],'adapter_available','graph_research.experiments.adapters'),
    'distance_spectral_radius':(_OBJECTS,'adapter_available','graph_research.experiments.adapters'),
    'energy':(['simple_graph'],'library_available','graph_research.workflows.energy'),
    'edge_count':(_OBJECTS,'adapter_available','graph_research.experiments.adapters')}
_PREDICATES={
    'connected':(_OBJECTS,'adapter_available'),
    'hypertree':(_HYPERGRAPHS,'adapter_available'),
    'edge_count':(_OBJECTS,'adapter_available'),
    'max_degree':(_OBJECTS,'adapter_available'),
    'max_degree_vertex_count':(_OBJECTS,'adapter_available'),
    'clique_free':(['simple_graph'],'adapter_available'),
    'matching_number':(['simple_graph'],'adapter_available')}
_DEFAULTS={'order':[4,5,6,7],'size':[3,4,5],'uniformity':[2,3],
           'max_degree':[3,4],'max_degree_vertices':[1,2],'clique_order':[3,4,5],
           'matching_number':[1,2],'alpha':[0,'1/4','1/2','3/4','19/20',1]}


def capability_catalog():
    """Availability refers to reviewed building blocks, not executable workflows."""
    return {'format':FORMAT,'phase':7,'operations':['prepare','execute','study'],'search_enabled':True,'candidate_evaluation':True,
        'objects':list(_OBJECTS),
        'metrics':[{'id':key,'objects':value[0],'status':value[1],'source':value[2]} for key,value in _METRICS.items()],
        'predicates':[{'id':key,'objects':value[0],'status':value[1]} for key,value in _PREDICATES.items()],
        'backends':[{'id':name,'status':'optional_torch' if name=='cem' else 'available'} for name in ('enumerate','random','local','cem')],
        'construction':[{'id':'hypertree_growth','objects':['uniform_hypertree'],'status':'available','meaning':'tree-only legal construction, not a generator of general hypergraphs or spectral optimization'}],
        'limits':{'order':128,'simple_graph_edges':1024,'hypertree_edges':128,'hypergraph_edges':128,'incidences':2048,'matching_verification_order':16},
        'dependencies':{'base':['numpy','networkx','sympy'],'learning_optional':['torch'],
                        'external_runtimes_required':[],'training_available':'optional_cpu_torch'},
        'meaning':'prepare remains a draft; execute evaluates supplied candidates; study searches only a reviewed finite scope. Formal metrics remain separate from training guidance.'}


def _json(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def _value(value):
    value=value if isinstance(value,Fraction) else number(value)
    return int(value) if value.denominator==1 else str(value)


def _domain(spec):
    if spec['role']=='fixed':return [_value(spec['value'])]
    if 'values' in spec:return [_value(v) for v in spec['values']]
    low=number(spec['minimum']) if 'minimum' in spec else None
    high=number(spec['maximum']) if 'maximum' in spec else None
    values=[number(v) for v in _DEFAULTS.get(spec['meaning'],[])]
    values=[v for v in values if (low is None or v>=low) and (high is None or v<=high)]
    if low is not None:values.append(low if spec['kind']=='real' else Fraction(math.ceil(low)))
    if high is not None:values.append(high if spec['kind']=='real' else Fraction(math.floor(high)))
    if low is not None and high is not None:
        middle=(low+high)/2;values.append(middle if spec['kind']=='real' else Fraction(math.floor(middle)))
    values=sorted(set(v for v in values if (low is None or v>=low) and (high is None or v<=high)))
    return [_value(v) for v in values[:8]]


def _resolve(value,case):return number(case[value['parameter']]) if isinstance(value,dict) else number(value)


def _necessary(problem,case):
    """Only unconditional requirements may eliminate a proposed parameter case."""
    obj=problem['object'];derived={};kind=obj['type']
    n=_resolve(obj['order'],case) if 'order' in obj else None
    requirements={}
    for node,required in leaves(problem.get('constraints',{'all':[]})):
        if not required:continue
        name=node['predicate'];args=node.get('arguments',{})
        if name in requirements and name in ('edge_count','max_degree','max_degree_vertex_count','matching_number'):
            if _resolve(requirements[name]['value'],case)!=_resolve(args['value'],case):return None
        requirements[name]=args
    def argument(name,key='value'):
        args=requirements.get(name)
        return _resolve(args[key],case) if args is not None else None
    m=argument('edge_count');delta=argument('max_degree');q=argument('max_degree_vertex_count')
    if kind!='simple_graph':
        k=_resolve(obj['uniformity'],case) if 'uniformity' in obj else None
        tree_required=kind=='uniform_hypertree' or 'hypertree' in requirements
        connected_required=tree_required or 'connected' in requirements or problem['objective']['metric']=='distance_spectral_radius'
        if tree_required and k is not None and m is not None:
            implied=1+(k-1)*m;derived['order']=int(implied)
            if n is not None and n!=implied:return None
            n=implied
        if m is not None and delta is not None and delta>m:return None
        if k is not None and m is not None and n is not None:
            if m>0 and k>n:return None
            if k<=n and m>math.comb(int(n),int(k)):return None
            if connected_required and (k-1)*m<n-1:return None
            if delta is not None and q is not None:
                minimum_other_degree=1 if connected_required and n>1 else 0
                if q*delta+(n-q)*minimum_other_degree>k*m:return None
                if k*m>q*delta+(n-q)*(delta-1):return None
    else:
        if n is not None and m is not None and m>n*(n-1)/2:return None
        if n is not None and delta is not None and delta>n-1:return None
        r=argument('clique_free','r')
        if n is not None and r is not None and r>n:derived['clique_condition_vacuous']=True
    if n is not None and n.denominator==1:derived['order']=int(n)
    if n is not None and q is not None and q>n:return None
    mu=argument('matching_number')
    if n is not None and mu is not None and mu>n//2:return None
    return derived


def prepare_experiment(request):
    """Produce an explicitly unapproved draft, never an execution authorization."""
    request=validate_prepare(request);problem=request['problem'];kind=problem['object']['type'];issues=[];capabilities=[]
    def issue(code,kind,message):issues.append({'code':code,'kind':kind,'message':message})
    metric=problem['objective']['metric'];cap=_METRICS.get(metric)
    if cap is None or kind not in cap[0]:issue('metric_unavailable','capability_gap','目标指标尚未有适用于该对象的已登记实现。')
    capabilities.append({'kind':'metric','id':metric,'status':cap[1] if cap and kind in cap[0] else 'unsupported'})
    for node,_ in leaves(problem.get('constraints',{'all':[]})):
        predicate=node['predicate'];cap=_PREDICATES.get(predicate)
        status=cap[1] if cap and kind in cap[0] else 'unsupported'
        capabilities.append({'kind':'predicate','id':predicate,'status':status})
        if status in ('unsupported','needs_adapter'):issue('predicate_adapter','capability_gap','约束 '+predicate+' 需要实现或验收独立适配器。')
    if problem['intent']=='extremum' and ('order' not in problem['object'] or any(p['meaning']=='order' and p['role']=='explore' for p in problem['parameters'].values())):
        issue('scope_interpretation','clarification','未固定图阶或给出完整有限域，不能直接声明全局最大值；建议明确研究参数化极值函数。')
    if problem['intent']=='counterexample':
        issue('witness_definition','clarification','反例任务还需可计算的待检验命题或参照对象；高分候选不能自动称为反例。')
    if kind=='simple_graph' and 'order' not in problem['object']:
        issue('order_reference','clarification','建议将图阶声明为自由参数并引用；无需用户预先选择具体数值。')
    if kind=='uniform_hypertree' or kind in _HYPERGRAPHS and any(required and node['predicate']=='hypertree' for node,required in leaves(problem.get('constraints',{'all':[]}))):
        issue('hypertree_generator','notice','超树构造和搜索会核查最大度及其顶点个数；生成器不保证直接满足这些等式，失败样本不能解释为该类无解。度按关联超边数计算。')
    if kind!='simple_graph' and metric in ('adjacency_spectral_radius','alpha_spectral_radius'):
        issue('matrix_tensor','clarification','普通图矩阵、超图邻接张量与距离矩阵不是同一目标；张量评价尚未接入此工作流。')
    issue('preparation_only','notice','prepare仅准备草案，不搜索、训练或批准资源。明确候选用execute；有限搜索用study，均须用户确认。')
    domains={key:_domain(spec) for key,spec in problem['parameters'].items()}
    if any(not values for values in domains.values()):issue('domain_unspecified','clarification','部分参数没有可推导的初始采样值，需要补充含义或提供候选范围。')
    cases=[];seen=set();rng=random.Random(request.get('seed',42));maximum=request.get('max_cases',16)
    total=math.prod(len(v) for v in domains.values());rejected=0
    for _ in range(maximum*40):
        if len(cases)>=min(maximum,total) or not total:break
        values={key:rng.choice(v) for key,v in domains.items()};signature=_json(values)
        if signature in seen:continue
        seen.add(signature);derived=_necessary(problem,values)
        if derived is None:rejected+=1;continue
        cases.append({'id':'case'+str(len(cases)+1),'parameters':values,'derived':derived,'feasibility':'necessary_conditions_only'})
    if not cases:issue('no_proposed_cases','notice','没有生成通过必要条件检查的采样点；这不证明参数类无解。')
    if any(c['derived'].get('clique_condition_vacuous') for c in cases):
        issue('trivial_clique_cases','notice','部分采样点r大于图阶，禁团条件自动满足；后续可作低成本基准，不应重复高成本搜索。')
    if any(p['meaning']=='alpha' and any(number(v)==1 for v in domains[name]) for name,p in problem['parameters'].items()):
        issue('alpha_endpoint','notice','alpha=1为度对角矩阵端点，应与0<=alpha<1的极图唯一性分析分开。')
    gap=any(i['kind']=='capability_gap' for i in issues);clarify=any(i['kind']=='clarification' for i in issues)
    orders=[c['derived']['order'] for c in cases if 'order' in c['derived']];order=max(orders,default=None)
    estimate={'proposed_cases':len(cases),'actual_tool_calls':0,'actual_model_calls':0,'candidate_evaluations':0,
              'wall_seconds_prediction':None,'needs_measured_pilot':True,'resource_authorization':False,
              'dense_float64_matrix_bytes':str(order*order*8) if order is not None else None,
              'matrix_estimate_meaning':'One dense matrix only; excludes solver workspaces, graphs and training state.'}
    if kind=='simple_graph' and order is not None:
        length=order*(order-1)//2
        estimate['legacy_cem_boolean_trajectory_bytes_batch200']=str(200*(length+1)*2*length)
        estimate['cem_estimate_meaning']='Original trainer observation array only; not the memory budget of an implemented backend.'
    plan={'format':FORMAT,'problem_sha256':hashlib.sha256(_json(problem).encode()).hexdigest(),
          'phase':'preparation','status':'needs_clarification' if clarify else 'capability_gap' if gap else 'draft',
          'executable':False,'approved':False,'cases':cases,'issues':issues,'estimate':estimate,
          'coverage':{'sampling':'bounded_seeded_parameter_sample','proposed_domains':domains,
                      'parameter_combinations':str(total),'rejected_necessary_conditions':rejected,
                      'enumeration_complete':False,'general_theorem_proved':False,
                      'meaning':'Suggested finite experiment scope, not the domain of a mathematical theorem.'},
          'capabilities':capabilities,'scientific_results':False,
          'next_steps':['明确待澄清的数学解释和能力缺口。','提供明确候选集合及有限预算，提交独立的execute请求。',
                        '有限搜索可提交study；实际用户确认参数范围、方法、轮数和总预算后执行。']}
    jsonschema.validate(plan,PLAN_SCHEMA)
    return {'problem':copy.deepcopy(problem),'plan':plan,'claims':[],'executed':False,
            'dependencies_installed':False,'preparation_method':'deterministic_rules_v1',
            'literature_status':'not_searched','model_planning_available':False}
