"""Primary graph/hypergraph checks and numerical objectives; no search or training."""
from .research_contract import validate_problem,leaves
from .execution_contract import bind_parameters,resolve,validate_candidate,digest

METRICS={'adjacency_spectral_radius','alpha_spectral_radius','distance_spectral_radius','edge_count'}
PREDICATES={'connected','hypertree','clique_free','edge_count','max_degree','max_degree_vertex_count','matching_number'}


def check_supported(problem,parameters):
    kind=problem['object']['type'];metric=problem['objective']['metric']
    if metric not in METRICS:raise ValueError('该指标尚未接入可执行评价器。')
    if kind in ('uniform_hypergraph','uniform_hypertree'):
        k=resolve(problem['object']['uniformity'],parameters)
        if not 2<=k<=128:raise ValueError('一致度支持2..128。')
    if kind!='simple_graph' and metric not in ('distance_spectral_radius','edge_count'):
        raise ValueError('超图当前仅接入距离矩阵谱与边数，不代用普通图矩阵或邻接张量。')
    for node,_ in leaves(problem.get('constraints',{'all':[]})):
        if node['predicate'] not in PREDICATES:raise ValueError('该约束没有可执行检查器。')
        if kind!='simple_graph' and node['predicate'] in ('clique_free','matching_number'):
            raise ValueError('普通图的禁团/匹配数语义不能直接用于超图。')
        if kind=='simple_graph' and node['predicate']=='hypertree':
            raise ValueError('hypertree是超图的关联树约束。')


def evaluate_logic(node,predicate):
    if 'predicate' in node:return bool(predicate(node['predicate'],node.get('arguments',{})))
    if 'all' in node:return all([evaluate_logic(child,predicate) for child in node['all']])
    if 'any' in node:return any([evaluate_logic(child,predicate) for child in node['any']])
    return not evaluate_logic(node['not'],predicate)


def primary_data(problem,parameters,candidate):
    import networkx as nx
    import numpy as np
    n=candidate['n'];edges=candidate['edges'];kind=problem['object']['type'];degrees=[0]*n
    for edge in edges:
        for v in edge:degrees[v]+=1
    incidence=nx.Graph();incidence.add_nodes_from(('v',v) for v in range(n));incidence.add_nodes_from(('e',i) for i in range(len(edges)))
    incidence.add_edges_from((('v',v),('e',i)) for i,e in enumerate(edges) for v in e)
    connected=nx.is_connected(incidence)
    graph=None
    if kind=='simple_graph':
        graph=nx.Graph();graph.add_nodes_from(range(n));graph.add_edges_from(edges)
    maximum=max(degrees);props={'order':n,'size':len(edges),'degrees':degrees,'max_degree':maximum,
        'max_degree_vertex_count':degrees.count(maximum),'connected':connected,
        'uniform':len(set(map(len,edges)))<=1,'hypertree':nx.is_tree(incidence)}
    predicates={node['predicate'] for node,_ in leaves(problem.get('constraints',{'all':[]}))}
    if 'matching_number' in predicates:
        if n>16:raise ValueError('独立匹配数核验目前限16顶点。')
        props['matching_number']=len(nx.max_weight_matching(graph,maxcardinality=True))
    def predicate(name,args):
        if name=='connected':return connected
        if name=='hypertree':return props['hypertree']
        value=resolve(args['r' if name=='clique_free' else 'value'],parameters)
        if name=='clique_free':return value>n or not any(len(c)>=value for c in nx.find_cliques(graph))
        return props[{'edge_count':'size','max_degree':'max_degree','max_degree_vertex_count':'max_degree_vertex_count','matching_number':'matching_number'}[name]]==value
    object_valid=('order' not in problem['object'] or n==resolve(problem['object']['order'],parameters))
    if kind in ('uniform_hypergraph','uniform_hypertree'):
        k=resolve(problem['object']['uniformity'],parameters)
        object_valid=object_valid and all(len(e)==k for e in edges)
    if kind=='uniform_hypertree':object_valid=object_valid and props['hypertree']
    constrained=evaluate_logic(problem.get('constraints',{'all':[]}),predicate)
    metric=problem['objective']['metric'];domain=connected or metric!='distance_spectral_radius'
    matrix=None
    if object_valid and constrained and domain and metric!='edge_count':
        if metric=='distance_spectral_radius':
            matrix=np.zeros((n,n),dtype=float)
            for u in range(n):
                lengths=nx.single_source_shortest_path_length(incidence,('v',u))
                for v in range(n):matrix[u,v]=lengths[('v',v)]//2
        else:
            matrix=nx.to_numpy_array(graph,nodelist=range(n),dtype=float)
            if metric=='alpha_spectral_radius':
                alpha=float(resolve(problem['objective']['arguments']['alpha'],parameters))
                matrix=(1-alpha)*matrix+alpha*np.diag(degrees)
    return props,bool(object_valid),bool(constrained),bool(domain),matrix


def _positive_vector(matrix):
    """Per-component Perron approximations also cover disconnected matrices."""
    import numpy as np
    n=len(matrix);pending=set(range(n));vector=np.ones(n)
    while pending:
        start=min(pending);pending.remove(start);component=[start];queue=[start]
        while queue:
            u=queue.pop()
            neighbors=[int(v) for v in np.flatnonzero(matrix[u]) if int(v) in pending]
            pending.difference_update(neighbors);queue.extend(neighbors);component.extend(neighbors)
        block=matrix[np.ix_(component,component)]
        _,vectors=np.linalg.eigh(block);x=np.maximum(np.abs(vectors[:,-1]),1e-12)
        vector[component]=x/np.max(x)
    return vector.tolist()


def evaluate_candidate(problem,parameters,candidate):
    """Trusted Python evaluation API; delegated tasks use the protected worker."""
    import numpy as np
    from .verification import matrix_bounds,verify_evaluation,independent_matrix
    problem=validate_problem(problem);parameters=bind_parameters(problem,parameters);check_supported(problem,parameters)
    candidate=validate_candidate(candidate,problem['object']['type'])
    props,valid,constrained,domain,matrix=primary_data(problem,parameters,candidate)
    feasible=valid and constrained and domain;estimate=None;certificate=None
    if feasible:
        if problem['objective']['metric']=='edge_count':
            estimate=props['size'];certificate={'method':'exact_edge_count','interval':[str(estimate),str(estimate)]}
        else:
            estimate=float(np.linalg.eigvalsh(matrix)[-1]);vector=_positive_vector(matrix)
            exact=independent_matrix(problem,parameters,candidate)
            certificate={'method':'exact_rational_rayleigh_collatz','vector':vector,**matrix_bounds(exact,vector)}
    result={'problem_sha256':digest(problem),'parameters':parameters,'candidate':candidate,'candidate_sha256':digest(candidate),
            'properties':props,'object_valid':valid,'constraints_satisfied':constrained,'metric_domain_satisfied':domain,
            'feasible':feasible,'objective_estimate':estimate,'certificate':certificate,
            'objective_interval':certificate['interval'] if certificate else None,'mathematical_proof':False}
    result['verification']=verify_evaluation(problem,parameters,candidate,result)
    if not result['verification']['passed']:raise ArithmeticError('独立评价核验未通过。')
    return result


def evaluate_chunk(arguments):
    if set(arguments)!={'problem','parameters','case_id','candidates'}:raise ValueError('固定实验分段输入字段无效。')
    if not isinstance(arguments['candidates'],list) or not 1<=len(arguments['candidates'])<=16:raise ValueError('每段评价1..16个明确候选。')
    rows=[];ids=set()
    for item in arguments['candidates']:
        if set(item)!={'id','graph'} or item['id'] in ids:raise ValueError('候选标识无效或重复。')
        ids.add(item['id']);row=evaluate_candidate(arguments['problem'],arguments['parameters'],item['graph'])
        rows.append({'candidate_id':item['id'],**row})
    return {'case_id':arguments['case_id'],'rows':rows,'evaluations_completed':len(rows),
            'scope':'provided_candidate_collection','search_performed':False,'general_theorem_proved':False}
