"""Evidence-scoped structural observations and executable hypothesis checks."""
from collections import Counter
from fractions import Fraction

from .execution_contract import digest,resolve


def features(candidate,kind,detailed=True):
    n=candidate['n'];edges=candidate['edges'];degrees=[0]*n;adj=[set() for _ in range(n+len(edges))]
    for i,edge in enumerate(edges):
        for v in edge:degrees[v]+=1;adj[v].add(n+i);adj[n+i].add(v)
    seen=set();components=0
    for start in range(len(adj)):
        if start in seen:continue
        components+=1;seen.add(start);queue=[start]
        for u in queue:
            for v in adj[u]-seen:seen.add(v);queue.append(v)
    result={'degree_histogram':dict(sorted(Counter(degrees).items())),'regular':len(set(degrees))<=1,
        'component_count':components,'incidence_cycle_rank':sum(map(len,edges))-len(adj)+components,
        'hypertree':components==1 and sum(map(len,edges))==len(adj)-1,
        'pendant_vertices':sum(d==1 for d in degrees),'edge_size_histogram':dict(sorted(Counter(map(len,edges)).items())),
        'maximum_degree_vertices':[v for v,d in enumerate(degrees) if d==max(degrees)],
        'pendant_edges':sum(sum(degrees[v]>1 for v in edge)<=1 for edge in edges)}
    if kind=='simple_graph':
        result['is_tree']=result.pop('hypertree')
        neighbors=[set() for _ in range(n)]
        for u,v in edges:neighbors[u].add(v);neighbors[v].add(u)
        colors={};bipartite=True
        for start in range(n):
            if start in colors:continue
            colors[start]=0;queue=[start]
            for u in queue:
                for v in neighbors[u]:
                    if v not in colors:colors[v]=1-colors[u];queue.append(v)
                    elif colors[u]==colors[v]:bipartite=False
        # Nonadjacency plus equality must form equivalence classes.
        pending=set(range(n));parts=[];multipartite=True
        while pending:
            u=min(pending);part={u}|(set(range(n))-neighbors[u]-{u})
            if any((set(range(n))-neighbors[v])!=part for v in part):multipartite=False;break
            parts.append(sorted(part));pending-=part
        result.update(bipartite=bipartite,bipartition=[sorted(v for v,c in colors.items() if c==color) for color in (0,1)] if bipartite else None,
            complete_multipartite=multipartite,parts=parts if multipartite else None)
    elif detailed:
        high=result['maximum_degree_vertices'];distances=[]
        for start in high:
            ds={start:0};queue=[start]
            for u in queue:
                for v in adj[u]:
                    if v not in ds:ds[v]=ds[u]+1;queue.append(v)
            distances.extend(ds[v]//2 for v in high if v>start and v in ds)
        anchors={i for i,links in enumerate(adj) if len(links)!=2};visited=set();skeleton=[]
        for start in sorted(anchors):
            for neighbor in sorted(adj[start]):
                if (start,neighbor) in visited:continue
                previous=start;current=neighbor;length=1;visited.add((start,neighbor));visited.add((neighbor,start))
                while current not in anchors:
                    nxt=next(v for v in adj[current] if v!=previous);visited.add((current,nxt));visited.add((nxt,current));previous,current=current,nxt;length+=1
                skeleton.append({'from':('v' if start<n else 'e')+str(start if start<n else start-n),
                    'to':('v' if current<n else 'e')+str(current if current<n else current-n),'incidence_length':length})
        result.update(maximum_degree_distance_profile=sorted(distances),incidence_skeleton=skeleton,
            skeleton_note='Degree-two chains are contracted; isolated all-degree-two cycle components are represented by incidence_cycle_rank, not mistaken for empty trees.')
    return result


def quotient(problem,parameters,candidate,description):
    """Exact equitable quotient for a recognized complete multipartite graph."""
    parts=description.get('parts');metric=problem['objective']['metric']
    if not parts or len(parts)>8 or metric not in ('adjacency_spectral_radius','alpha_spectral_radius'):return None
    import sympy as sp
    a=resolve(problem['objective']['arguments']['alpha'],parameters) if metric=='alpha_spectral_radius' else Fraction()
    alpha=sp.Rational(a.numerator,a.denominator);sizes=list(map(len,parts));n=candidate['n']
    q=sp.Matrix([[alpha*(n-size) if i==j else (1-alpha)*sizes[j] for j in range(len(sizes))] for i,size in enumerate(sizes)])
    return {'part_sizes':sizes,'matrix':[[str(v) for v in row] for row in q.tolist()],
        'characteristic_polynomial':str(q.charpoly('x').as_expr()),'scope':'equitable quotient of this verified instance; not a theorem about all feasible graphs'}


def isomorphic(a,b,kind):
    """Return a checked isomorphism witness; equal degree sequences never suffice."""
    if a['n']!=b['n'] or len(a['edges'])!=len(b['edges']):return None
    if a['n']>12 or len(a['edges'])>16:return None
    import networkx as nx
    def graph(c):
        g=nx.Graph();g.add_nodes_from((('v',i),{'side':'vertex'}) for i in range(c['n']))
        for i,e in enumerate(c['edges']):g.add_node(('e',i),side='edge');g.add_edges_from((('v',v),('e',i)) for v in e)
        return g
    matcher=nx.algorithms.isomorphism.GraphMatcher(graph(a),graph(b),node_match=lambda x,y:x['side']==y['side'])
    if not matcher.is_isomorphic():return None
    mapping={v:matcher.mapping[('v',v)][1] for v in range(a['n'])}
    if len(set(mapping.values()))!=b['n'] or {tuple(sorted(mapping[v] for v in e)) for e in a['edges']}!={tuple(sorted(e)) for e in b['edges']}:raise ValueError('Isomorphism witness invalid')
    return mapping


def analyze(compiled,results,hypotheses=None):
    """Results are already receipt-checked; retain source IDs and counterevidence."""
    problem=compiled['spec']['problem'];kind=problem['object']['type'];direction=problem['objective']['direction']
    rows=[{'run_id':r['run_id'],'round':r['round'],**row} for r in results for row in r['rows']]
    feasible=[row for row in rows if row['feasible']];descriptions={};selected=[];classes=[];runs=[]
    def description(row):
        key=row['candidate_sha256']
        if key not in descriptions:descriptions[key]=features(row['candidate'],kind)
        return descriptions[key]
    for run in compiled['runs']:
        rr=[r for r in rows if r['run_id']==run['id']];ff=[r for r in rr if r['feasible']]
        best=(min(ff,key=lambda r:r['objective_estimate']) if direction=='minimize' else max(ff,key=lambda r:r['objective_estimate'])) if ff else None
        runs.append({'run_id':run['id'],'case_id':run['case_id'],'method':run['method'],'seed':run['seed'],'evaluated':len(rr),'feasible':len(ff),
            'feasible_rate':len(ff)/len(rr) if rr else None,'labelled_diversity':len({r['candidate_sha256'] for r in rr}),
            'best_feasible':best['objective_estimate'] if best else None,'best_candidate_sha256':best['candidate_sha256'] if best else None})
        if best:
            d=description(best);group=None;mapping=None
            # Bound expensive matching; unclassified means unknown, not a new class.
            for i,representative in enumerate(classes[:8]):
                mapping=isomorphic(best['candidate'],representative['candidate'],kind)
                if mapping is not None:group=i;break
            if group is None and best['candidate']['n']<=12 and len(classes)<8 and len(best['candidate']['edges'])<=16:
                group=len(classes);classes.append({'candidate':best['candidate'],'candidate_sha256':best['candidate_sha256']});mapping={i:i for i in range(best['candidate']['n'])}
            selected.append({'run_id':run['id'],'candidate_sha256':best['candidate_sha256'],'candidate':best['candidate'],'objective_estimate':best['objective_estimate'],
                'objective_interval':best['objective_interval'],'features':d,'isomorphism_class':group,'isomorphism_witness':mapping,
                'isomorphism_status':'witness_checked' if group is not None else 'not_classified_within_analysis_limit',
                'quotient':quotient(problem,run['parameters'],best['candidate'],d)})
    hypotheses=hypotheses if hypotheses is not None else compiled['spec'].get('hypotheses',[])
    checks=[]
    for hypothesis in hypotheses:
        witnesses=[];unknown=0;tested=0
        candidates=feasible if hypothesis['type']!='candidate_pattern' else [r for r in feasible if any(s['run_id']==r['run_id'] and s['candidate_sha256']==r['candidate_sha256'] for s in selected)]
        for row in candidates:
            tested+=1;contradicted=False
            if hypothesis['type']=='metric_bound':
                lo,hi=map(Fraction,row['objective_interval']);value=resolve(hypothesis['value'],{})
                contradicted=lo>value if hypothesis['relation']=='le' else hi<value
                unknown+=int(not contradicted and not (hi<=value if hypothesis['relation']=='le' else lo>=value))
            else:contradicted=features(row['candidate'],kind,detailed=False)[hypothesis['property']]!=hypothesis['expected']
            if contradicted and len(witnesses)<8:witnesses.append({'run_id':row['run_id'],'round':row['round'],'candidate_id':row['candidate_id'],'candidate':row['candidate'],'objective_interval':row['objective_interval']})
        checks.append({'hypothesis':hypothesis,'tested':tested,'interval_inconclusive':unknown,'witnesses':witnesses,
            'status':('pattern_contradicted' if hypothesis['type']=='candidate_pattern' else 'verified_counterexample') if witnesses else 'not_refuted_in_tested_samples',
            'proven':False,'meaning':'A candidate pattern is only an observation about selected search results; it is not a theorem about extremizers.'})
    complete=[]
    for result in results:
        if result['enumeration']['complete']:complete.append({'run_id':result['run_id'],'visited':result['enumeration']['visited'],'domain':result['enumeration']['scope'],'restricted_edge_sizes':result['enumeration']['restricted_edge_sizes']})
    conjectures=[]
    for case in compiled['spec']['cases']:
        run_ids={r['id'] for r in compiled['runs'] if r['case_id']==case['id']};ss=[s for s in selected if s['run_id'] in run_ids]
        for property_name in ('regular','is_tree','hypertree','complete_multipartite','bipartite'):
            if ss and all(s['features'].get(property_name) is True for s in ss):
                supporting=[r for r in compiled['runs'] if r['id'] in {s['run_id'] for s in ss}]
                conjectures.append({'level':'conjecture','case_id':case['id'],'property':property_name,'statement':'Best observed feasible candidates share this property; global extremizers remain unproved.',
                    'evidence_run_ids':[s['run_id'] for s in ss],'independent_seeds':len({r['seed'] for r in supporting if r['method']!='enumerate'}),
                    'deterministic_repetitions':sum(r['method']=='enumerate' for r in supporting),'methods':sorted({r['method'] for r in supporting}),
                    'next_falsification':'Try held-out parameters, independent seeds and another approved backend; new scope needs user review.'})
    return {'run_statistics':runs,'selected_structures':selected,'hypothesis_checks':checks,'finite_coverage':complete,'candidate_conjectures':conjectures,
        'claims':[{'level':'verified_instance','statement':'Selected candidates satisfy the declared constraints and have independently verified objective enclosures.' if selected else 'No feasible candidate was found in these evaluations; nonexistence is not established.'},
                  {'level':'numerical_observation','statement':'Compare methods/seeds using raw objectives, feasibility, labelled diversity and receipt costs; no method is presumed superior.'}],
        'general_theorem_proved':False,'literature_status':'not_searched','limitations':['Finite parameter cases are not a universal parameter domain.','Heuristic failure is not a proof of nonexistence.','Isomorphism matching is bounded to 12 vertices, 16 edges and 8 representatives; degree histograms alone never establish isomorphism.','Candidate patterns and symbolic quotients of instances are not general extremal proofs.']}


def analyze_streamed(compiled, results, rows_factory, hypotheses):
    """One full evidence pass; retain only counters, distinct hashes and witnesses."""
    problem=compiled['spec']['problem'];kind=problem['object']['type'];direction=problem['objective']['direction']
    stats={r['id']:{'evaluated':0,'feasible':0,'seen':set(),'best':None} for r in compiled['runs']}
    checks={h['id']:{'hypothesis':h,'tested':0,'interval_inconclusive':0,'witnesses':[]} for h in hypotheses if h['type']!='candidate_pattern'}
    for row in rows_factory():
        own=stats[row['run_id']];own['evaluated']+=1;own['seen'].add(row['candidate_sha256'])
        if not row['feasible']:continue
        own['feasible']+=1;best=own['best']
        if best is None or (row['objective_estimate']<best['objective_estimate'] if direction=='minimize' else row['objective_estimate']>best['objective_estimate']):
            own['best']=row
        for check in checks.values():
            h=check['hypothesis'];check['tested']+=1
            if h['type']=='metric_bound':
                lo,hi=map(Fraction,row['objective_interval']);target=resolve(h['value'],{})
                contradicted=lo>target if h['relation']=='le' else hi<target
                check['interval_inconclusive']+=int(not contradicted and not (hi<=target if h['relation']=='le' else lo>=target))
            else:contradicted=features(row['candidate'],kind,detailed=False)[h['property']]!=h['expected']
            if contradicted and len(check['witnesses'])<8:
                check['witnesses'].append({k:row[k] for k in ('run_id','round','candidate_id','candidate','objective_interval')})
    representatives=[]
    for run in compiled['runs']:
        best=stats[run['id']]['best'];previous=next((r for r in reversed(results) if r['run_id']==run['id']),None)
        if previous:
            representatives.append({**previous,'rows':[best] if best else []})
    report=analyze(compiled,representatives,[h for h in hypotheses if h['type']=='candidate_pattern'])
    for run in report['run_statistics']:
        own=stats[run['run_id']];best=own['best']
        run.update(evaluated=own['evaluated'],feasible=own['feasible'],labelled_diversity=len(own['seen']),
                   feasible_rate=own['feasible']/own['evaluated'] if own['evaluated'] else None,
                   best_feasible=best['objective_estimate'] if best else None)
    pattern_checks={c['hypothesis']['id']:c for c in report['hypothesis_checks']}
    ordered=[]
    for h in hypotheses:
        if h['type']=='candidate_pattern':
            ordered.append(pattern_checks[h['id']]);continue
        check=checks[h['id']]
        check.update(status='verified_counterexample' if check['witnesses'] else 'not_refuted_in_tested_samples',proven=False,
                     meaning='Every feasible evaluation in the receipt-verified streamed archive was checked.')
        ordered.append(check)
    report.update(hypothesis_checks=ordered,analysis_complete=True,analysis_scope='all receipt-verified candidate records; bounded retained witnesses')
    return report
