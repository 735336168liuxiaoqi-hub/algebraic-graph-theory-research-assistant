"""One protected search round with raw metrics, safe checkpoints and no model."""
import copy
import json
import math
import random

from .adapters import evaluate_candidate
from .execution_contract import digest
from .search_space import cardinality,enumerated,random_candidate,mutate

VERSION='graph-search/1'


def score(row,problem,knobs):
    """Training guidance cannot override feasibility or replace the raw metric."""
    if row['feasible']:
        value=0 if problem['objective']['direction']=='satisfy' else row['objective_estimate']*(-1 if problem['objective']['direction']=='minimize' else 1)
        return 1+math.atan(value)/math.pi
    props=row['properties'];loss=float(not row['object_valid'])+float(not row['metric_domain_satisfied'])+float(not row['constraints_satisfied'])
    from .execution_contract import resolve
    def penalty(node):
        if 'not' in node:return 0.0  # Formal feasibility remains authoritative.
        if 'all' in node:return sum(penalty(c) for c in node['all'])
        if 'any' in node:return min((penalty(c) for c in node['any']),default=0)
        name=node['predicate'];args=node.get('arguments',{})
        key={'edge_count':'size','max_degree':'max_degree','max_degree_vertex_count':'max_degree_vertex_count','matching_number':'matching_number'}.get(name)
        if key:
            target=float(resolve(args['value'],row['parameters']))
            return abs(props[key]-target)/max(1,abs(target))
        return float(not props.get(name,True)) if name in ('connected','hypertree') else 0.0
    return -knobs['penalty_weight']*(loss+penalty(problem.get('constraints',{'all':[]})))


def _tuple(value):return tuple(_tuple(v) for v in value) if isinstance(value,list) else value


def run_round(arguments,*,policy=None):
    """Host-fixed arguments only; no source code, path or executable accepted."""
    from .search_contract import compile_study
    required={'problem','run','settings','knobs','round','checkpoint','limit'}
    if set(arguments)!=required:raise ValueError('Invalid study round fields')
    a=arguments;run=a['run'];settings=a['settings'];method=run['method'];limit=a['limit']
    # Validate against the same public contract even inside the protected worker.
    spec={'operation':'study','problem':a['problem'],'cases':[{'id':run['case_id'],'parameters':run['parameters']}],
          'methods':[method],'seeds':[run['seed']],'rounds':1,'batch_size':limit,'budget':{'max_evaluations':limit,'wall_seconds':30,'cpu_seconds':30,'memory_mb':1024},**settings,'knobs':a['knobs']}
    normalized=compile_study(spec)
    if normalized['runs'][0]['space']!=run['space']:raise ValueError('Search domain changed')
    identity=digest({'version':VERSION,'problem':a['problem'],'run':run,'settings':settings})
    old=copy.deepcopy(a['checkpoint']);rng=random.Random(run['seed'])
    if old is not None:
        if old.get('version')!=VERSION or old.get('identity')!=identity or old.get('round')!=a['round']-1:raise ValueError('Checkpoint version, domain or round mismatch')
        rng.setstate(_tuple(old['rng']))
    elif a['round']!=1:raise ValueError('Missing preceding checkpoint')
    checkpoint=old or {'version':VERSION,'identity':identity,'round':0,'cursor':0,'elites':[],'best':None,'stagnation':0}
    reward_version=digest({'problem':a['problem'],'knobs':a['knobs'],'score_version':1})
    previous_reward=checkpoint.get('reward_version');rescored=previous_reward is not None and previous_reward!=reward_version
    # Raw metrics remain immutable. Changing guidance only rescales/reorders cached elites.
    elites=checkpoint['elites'];rows=[];trajectories=[];domain=run['space']
    if method=='cem':
        from .neural_search import Policy
        if policy is None:policy=Policy(domain,run['seed'],checkpoint.get('neural'),cpu_threads=settings.get('cpu_threads',1))
    total=cardinality(domain) if method=='enumerate' else None
    for index in range(limit):
        if method=='enumerate':
            if checkpoint['cursor']>=total:break
            graph=enumerated(domain,checkpoint['cursor']);checkpoint['cursor']+=1
        elif method=='random':graph=random_candidate(domain,rng)
        elif method=='local':
            parent=checkpoint['best']
            graph=mutate(domain,parent['candidate'],rng) if parent is not None and rng.random()>=a['knobs']['exploration'] else random_candidate(domain,rng)
        elif method=='cem':
            graph,trajectory=policy.sample(rng,a['knobs']['exploration']);trajectories.append(trajectory)
        else:raise ValueError('Unknown search method')
        row=evaluate_candidate(a['problem'],run['parameters'],graph);row['candidate_id']='round'+str(a['round'])+'candidate'+str(index+1)
        row['training_score']=score(row,a['problem'],a['knobs']);row['reward_version']=reward_version;rows.append(row)
        parent=checkpoint['best']
        if parent is None or score(row,a['problem'],a['knobs'])>score(parent,a['problem'],a['knobs']):checkpoint['best']=copy.deepcopy(row)
    pool=[{'row':r,'trajectory':t} for r,t in zip(rows,trajectories)] if method=='cem' else [{'row':r,'trajectory':None} for r in rows]
    pool+=elites
    pool.sort(key=lambda item:score(item['row'],a['problem'],a['knobs']),reverse=True)
    keep=max(1,min(4,math.ceil(max(1,len(rows))*a['knobs']['elite_fraction'])))
    elites=pool[:keep]
    if pool and (checkpoint['best'] is None or score(pool[0]['row'],a['problem'],a['knobs'])>score(checkpoint['best'],a['problem'],a['knobs'])):
        checkpoint['best']=copy.deepcopy(pool[0]['row'])
    for item in elites:
        item['row']['training_score']=score(item['row'],a['problem'],a['knobs']);item['row']['reward_version']=reward_version
    if checkpoint['best'] is not None:
        checkpoint['best']['training_score']=score(checkpoint['best'],a['problem'],a['knobs']);checkpoint['best']['reward_version']=reward_version
    if policy is not None:
        policy.learn([item['trajectory'] for item in elites if item['trajectory'] is not None])
        checkpoint['neural']=policy.state()
    prior_best=old.get('best') if old else None;best=checkpoint['best']
    improved=bool(best and (prior_best is None or score(best,a['problem'],a['knobs'])>score(prior_best,a['problem'],a['knobs'])))
    checkpoint.update(round=a['round'],rng=rng.getstate(),elites=elites,reward_version=reward_version,
        stagnation=0 if improved else checkpoint['stagnation']+1)
    if len(json.dumps(checkpoint,ensure_ascii=False).encode())>180*1024:raise ValueError('Checkpoint exceeds safe JSON input limit; reduce action sequence or batch size')
    return {'version':VERSION,'run_id':run['id'],'round':a['round'],'rows':rows,'evaluations_completed':len(rows),
        'checkpoint':checkpoint,'reward_version':reward_version,'cached_elites_rescored':len(elites) if rescored else 0,
        'diagnostics':{'feasible':sum(r['feasible'] for r in rows),'labelled_diversity':len({r['candidate_sha256'] for r in rows}),
            'best_feasible':max((r['objective_estimate'] for r in rows if r['feasible']),default=None) if a['problem']['objective']['direction']!='minimize' else min((r['objective_estimate'] for r in rows if r['feasible']),default=None),
            'improved_training_rank':improved,'stagnation':checkpoint['stagnation']},
        'enumeration':{'visited':checkpoint['cursor'],'total':str(total) if total is not None else None,'complete':method=='enumerate' and checkpoint['cursor']==total,
            'restricted_edge_sizes':domain['restricted_edge_sizes'],'scope':domain},
        'search_performed':True,'training_performed':method=='cem','general_theorem_proved':False}


def verify_round(arguments,result):
    from .verification import verify_evaluation
    if result.get('version')!=VERSION or result.get('run_id')!=arguments['run']['id'] or result.get('round')!=arguments['round'] or result.get('general_theorem_proved') is not False:raise ValueError('Search evidence scope mismatch')
    rows=result.get('rows',[])
    if result.get('search_performed') is not True or result.get('training_performed')!=(arguments['run']['method']=='cem'):raise ValueError('Search/training flags invalid')
    if result.get('evaluations_completed')!=len(rows) or len(rows)>arguments['limit']:raise ValueError('Search evaluation count mismatch')
    expected_reward=digest({'problem':arguments['problem'],'knobs':arguments['knobs'],'score_version':1})
    for i,row in enumerate(rows):
        if row.get('candidate_id')!='round'+str(arguments['round'])+'candidate'+str(i+1) or not verify_evaluation(arguments['problem'],arguments['run']['parameters'],row['candidate'],row)['passed']:raise ValueError('Search metric/constraint evidence invalid')
        if row.get('training_score')!=score(row,arguments['problem'],arguments['knobs']) or row.get('reward_version')!=expected_reward:raise ValueError('Training score changed independently of raw metric')
    if arguments['run']['method']=='enumerate':
        start=(arguments['checkpoint'] or {}).get('cursor',0);domain=arguments['run']['space'];total=cardinality(domain)
        if len(rows)!=min(arguments['limit'],total-start):raise ValueError('Enumeration omitted candidates')
        for offset,row in enumerate(rows):
            if digest(enumerated(domain,start+offset))!=row['candidate_sha256']:raise ValueError('Enumeration index/candidate mismatch')
        if result['enumeration']['visited']!=start+len(rows) or result['enumeration']['total']!=str(total) or result['enumeration']['complete']!=(start+len(rows)==total):raise ValueError('Enumeration coverage mismatch')
    elif result['enumeration']['complete'] is not False:raise ValueError('Heuristic search cannot claim exhaustive coverage')
    if result['checkpoint']['round']!=arguments['round'] or result['checkpoint']['reward_version']!=expected_reward:raise ValueError('Checkpoint does not match this round')
    identity=digest({'version':VERSION,'problem':arguments['problem'],'run':arguments['run'],'settings':arguments['settings']})
    if result['checkpoint']['identity']!=identity:raise ValueError('Checkpoint identity mismatch')
    def raw_hash(row):return digest({k:v for k,v in row.items() if k not in ('training_score','reward_version')})
    prior=arguments['checkpoint'] or {};allowed={raw_hash(r) for r in rows}
    allowed.update(raw_hash(e['row']) for e in prior.get('elites',[]))
    if prior.get('best'):allowed.add(raw_hash(prior['best']))
    cached=[e['row'] for e in result['checkpoint']['elites']]+([result['checkpoint']['best']] if result['checkpoint']['best'] else [])
    if any(raw_hash(row) not in allowed for row in cached):raise ValueError('Checkpoint introduced an unevaluated elite')
    return True
