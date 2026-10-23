"""Independent set/BFS/DP checks and rational matrix bounds; no eigensolver."""
from fractions import Fraction
from functools import lru_cache
import math

from .execution_contract import resolve,digest,validate_candidate,bind_parameters
from .research_contract import validate_problem,leaves


def _data(candidate):
    n=candidate['n'];edges=candidate['edges'];incidence=[[] for _ in range(n)];neighbors=[set() for _ in range(n)]
    parent=list(range(n+len(edges)));acyclic=True
    def root(v):
        while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
        return v
    for i,edge in enumerate(edges):
        for v in edge:
            incidence[v].append(i);neighbors[v].update(u for u in edge if u!=v)
            a,b=root(v),root(n+i)
            if a==b:acyclic=False
            else:parent[a]=b
    connected=all(root(v)==root(0) for v in range(n+len(edges)))
    degrees=list(map(len,incidence));maximum=max(degrees)
    return {'order':n,'size':len(edges),'degrees':degrees,'max_degree':maximum,
            'max_degree_vertex_count':degrees.count(maximum),'connected':connected,
            'uniform':len(set(map(len,edges)))<=1,'hypertree':connected and acyclic},incidence,neighbors


def _matching(neighbors):
    if len(neighbors)>16:raise ValueError('独立匹配数DP限16点。')
    masks=[sum(1<<u for u in row) for row in neighbors]
    @lru_cache(None)
    def maximum(mask):
        if not mask:return 0
        bit=mask&-mask;u=bit.bit_length()-1;rest=mask^bit;best=maximum(rest);options=masks[u]&rest
        while options:
            v=options&-options;options^=v;best=max(best,1+maximum(rest^v))
            if best==mask.bit_count()//2:break
        return best
    return maximum((1<<len(neighbors))-1)


def _clique(neighbors,r):
    n=len(neighbors)
    if r>n:return False
    masks=[sum(1<<v for v in row) for row in neighbors]
    visits=0
    def visit(mask,need):
        nonlocal visits
        visits+=1
        if visits>100000:raise ValueError('独立禁团核验超出节点预算，拒绝出具证书。')
        if need==0:return True
        while mask.bit_count()>=need:
            bit=mask&-mask;mask^=bit
            if visit(mask&masks[bit.bit_length()-1],need-1):return True
        return False
    return visit((1<<n)-1,r)


def _logic(node,predicate):
    if 'predicate' in node:return predicate(node['predicate'],node.get('arguments',{}))
    if 'not' in node:return not _logic(node['not'],predicate)
    answers=[_logic(child,predicate) for child in node.get('all',node.get('any',[]))]
    return all(answers) if 'all' in node else any(answers)


def independent_matrix(problem,parameters,candidate):
    n=candidate['n'];edges=candidate['edges'];metric=problem['objective']['metric'];props,incidence,_=_data(candidate)
    matrix=[[Fraction() for _ in range(n)] for _ in range(n)]
    if metric=='distance_spectral_radius':
        for start in range(n):
            distances={start:0};queue=[start];seen_edges=set()
            for u in queue:
                for i in incidence[u]:
                    if i in seen_edges:continue
                    seen_edges.add(i)
                    for v in edges[i]:
                        if v not in distances:distances[v]=distances[u]+1;queue.append(v)
            if len(distances)!=n:raise ValueError('距离谱要求连通。')
            matrix[start]=[Fraction(distances[v]) for v in range(n)]
    else:
        alpha=resolve(problem['objective']['arguments']['alpha'],parameters) if metric=='alpha_spectral_radius' else Fraction()
        for u in range(n):matrix[u][u]=alpha*props['degrees'][u]
        for u,v in edges:matrix[u][v]=matrix[v][u]=1-alpha
    return matrix


def matrix_bounds(matrix,vector):
    n=len(matrix)
    if not isinstance(vector,list) or len(vector)!=n or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in vector):raise ValueError('谱证书须包含正的有限向量。')
    x=list(map(Fraction,vector));action=[sum((a*b for a,b in zip(row,x)),Fraction()) for row in matrix]
    ratios=[a/b for a,b in zip(action,x)]
    rayleigh=sum((a*b for a,b in zip(action,x)),Fraction())/sum((v*v for v in x),Fraction())
    lower=max(rayleigh,min(ratios),max(matrix[i][i] for i in range(n)))
    upper=max(ratios)
    return {'interval':[str(lower),str(upper)],'rayleigh_lower':str(rayleigh),
            'collatz_upper':str(upper),'arithmetic':'exact_rational_of_stored_vector'}


def verify_evaluation(problem,parameters,candidate,result):
    """Rebuild constraints and matrix from raw edges; never trust stored scores."""
    try:
        problem=validate_problem(problem);parameters=bind_parameters(problem,parameters)
        # Check semantics locally; do not import or reuse the primary evaluator.
        metric=problem['objective']['metric'];kind=problem['object']['type']
        if metric not in {'edge_count','adjacency_spectral_radius','alpha_spectral_radius','distance_spectral_radius'}:raise ValueError('Unsupported metric')
        if kind!='simple_graph' and (metric not in {'edge_count','distance_spectral_radius'} or any(n['predicate'] in {'clique_free','matching_number'} for n,_ in leaves(problem.get('constraints',{'all':[]})))):raise ValueError('Unsupported hypergraph semantics')
        if kind=='simple_graph' and any(n['predicate']=='hypertree' for n,_ in leaves(problem.get('constraints',{'all':[]}))):raise ValueError('Hypertree predicate requires a hypergraph')
        candidate=validate_candidate(candidate,problem['object']['type']);props,_,neighbors=_data(candidate)
        if any(node['predicate']=='matching_number' for node,_ in leaves(problem.get('constraints',{'all':[]}))):props['matching_number']=_matching(neighbors)
        def predicate(name,args):
            if name=='connected':return props['connected']
            if name=='hypertree':return props['hypertree']
            if name=='clique_free':return not _clique(neighbors,int(resolve(args['r'],parameters)))
            key={'edge_count':'size','max_degree':'max_degree','max_degree_vertex_count':'max_degree_vertex_count','matching_number':'matching_number'}[name]
            return props[key]==resolve(args['value'],parameters)
        obj=problem['object'];valid='order' not in obj or candidate['n']==resolve(obj['order'],parameters)
        if obj['type'] in ('uniform_hypergraph','uniform_hypertree'):valid=valid and all(len(e)==resolve(obj['uniformity'],parameters) for e in candidate['edges'])
        if obj['type']=='uniform_hypertree':valid=valid and props['hypertree']
        constrained=_logic(problem.get('constraints',{'all':[]}),predicate)
        domain=props['connected'] or problem['objective']['metric']!='distance_spectral_radius'
        feasible=bool(valid and constrained and domain)
        passed=(result.get('problem_sha256')==digest(problem) and result.get('parameters')==parameters and result.get('candidate')==candidate
                and result.get('candidate_sha256')==digest(candidate) and result.get('properties')==props
                and result.get('mathematical_proof') is False
                and result.get('object_valid')==bool(valid) and result.get('constraints_satisfied')==bool(constrained)
                and result.get('metric_domain_satisfied')==bool(domain) and result.get('feasible')==feasible)
        certificate=result.get('certificate')
        if feasible:
            if problem['objective']['metric']=='edge_count':
                expected={'method':'exact_edge_count','interval':[str(props['size']),str(props['size'])]}
                passed=passed and certificate==expected and result.get('objective_estimate')==props['size']
            else:
                rebuilt=matrix_bounds(independent_matrix(problem,parameters,candidate),certificate['vector'])
                passed=passed and certificate.get('method')=='exact_rational_rayleigh_collatz' and all(certificate.get(k)==v for k,v in rebuilt.items())
                estimate=result.get('objective_estimate');passed=passed and type(estimate) in (int,float) and math.isfinite(estimate)
                lo,hi=map(lambda v:float(Fraction(v)),rebuilt['interval']);tolerance=1e-8*max(1,abs(lo),abs(hi))
                passed=passed and lo-tolerance<=estimate<=hi+tolerance
            passed=passed and result.get('objective_interval')==certificate['interval']
        else:passed=passed and certificate is None and result.get('objective_estimate') is None and result.get('objective_interval') is None
        return {'passed':bool(passed),'independent':True,'constraints':'set_bfs_union_find_clique_dp',
                'metric':'exact_count' if problem['objective']['metric']=='edge_count' else 'rational_spectral_enclosure',
                'meaning':'Constraints and enclosure verified; numerical estimate is not a proof of exact eigenvalue or global optimality.'}
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,ZeroDivisionError):
        return {'passed':False,'independent':True,'reason':'invalid_or_inconsistent_evidence'}
