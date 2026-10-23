"""Bounded labelled constructions; graph/hypergraph classes are never conflated."""
import itertools
import math


def edge_pool(domain):
    if domain['capacity']>20:raise ValueError('Enumeration pool exceeds reviewed limit')
    return [list(e) for k in domain['edge_sizes'] for e in itertools.combinations(range(domain['n']),k)]


def cardinality(domain):
    return math.comb(domain['capacity'],domain['edge_count']) if domain['edge_count'] is not None else sum(math.comb(domain['capacity'],m) for m in range(domain['max_edges']+1))


def unrank_subset(size,count,rank):
    result=[];start=0
    for remaining in range(count,0,-1):
        for v in range(start,size):
            block=math.comb(size-v-1,remaining-1)
            if rank<block:result.append(v);start=v+1;break
            rank-=block
    return result


def enumerated(domain,index):
    pool=edge_pool(domain);m=domain['edge_count']
    if not 0<=index<cardinality(domain):raise ValueError('Enumeration index out of scope')
    if m is None:
        for count in range(domain['max_edges']+1):
            block=math.comb(len(pool),count)
            if index<block:m=count;break
            index-=block
    return {'n':domain['n'],'edges':sorted(pool[i] for i in unrank_subset(len(pool),m,index))}


def random_candidate(domain,rng):
    if domain['tree']:
        from .generation import generate_hypertree
        return generate_hypertree(domain['uniformity'],domain['edge_count'],seed=rng.randrange(2**32))
    m=domain['edge_count'] if domain['edge_count'] is not None else rng.randrange(domain.get('minimum_edges',0),domain['max_edges']+1)
    edges=set();proposals=0
    if domain.get('connected') and domain['n']>1:
        seen={rng.randrange(domain['n'])};unseen=set(range(domain['n']))-seen
        while unseen:
            slots=m-len(edges);required=max(1,len(unseen)-(slots-1)*(max(domain['edge_sizes'])-1))
            k=rng.choice([k for k in domain['edge_sizes'] if k-1>=required])
            fresh=rng.sample(sorted(unseen),min(k-1,len(unseen)));old=rng.sample(sorted(seen),k-len(fresh))
            edges.add(tuple(sorted([*old,*fresh])));seen.update(fresh);unseen.difference_update(fresh)
    while len(edges)<m and proposals<max(32,32*m):
        k=rng.choice(domain['edge_sizes']);edges.add(tuple(sorted(rng.sample(range(domain['n']),k))));proposals+=1
    # A bounded collision fallback preserves the requested size, never silently
    # downgrades an m-edge experiment to a smaller class.
    if len(edges)<m:
        for k in domain['edge_sizes']:
            for edge in itertools.combinations(range(domain['n']),k):
                edges.add(edge)
                if len(edges)==m:break
            if len(edges)==m:break
    return {'n':domain['n'],'edges':[list(e) for e in sorted(edges)]}


def mutate(domain,graph,rng):
    if domain['tree']:
        degrees=[0]*graph['n']
        for edge in graph['edges']:
            for v in edge:degrees[v]+=1
        pendant=[i for i,e in enumerate(graph['edges']) if sum(degrees[v]>1 for v in e)<=1]
        if not pendant:return random_candidate(domain,rng)
        edges=[list(e) for e in graph['edges']];i=rng.choice(pendant);edge=edges[i]
        leaves=[v for v in edge if degrees[v]==1];old=next((v for v in edge if degrees[v]>1),edge[0]);leaves=[v for v in edge if v!=old]
        choices=[v for v in range(graph['n']) if v not in edge]
        if not choices:return random_candidate(domain,rng)
        edges[i]=sorted([rng.choice(choices),*leaves]);return {'n':graph['n'],'edges':edges}
    edges={tuple(e) for e in graph['edges']}
    if edges and (domain['edge_count'] is not None or len(edges)>=domain['max_edges'] or rng.random()<0.5):edges.remove(rng.choice(sorted(edges)))
    fresh=random_candidate({**domain,'tree':False,'connected':False,'minimum_edges':0,'edge_count':min(len(edges)+1,domain['capacity'])},rng)
    choices=[tuple(e) for e in fresh['edges'] if tuple(e) not in edges]
    if len(edges)<domain['max_edges'] and choices:edges.add(rng.choice(choices))
    if domain['edge_count'] is not None and len(edges)!=domain['edge_count']:return random_candidate(domain,rng)
    return {'n':graph['n'],'edges':[list(e) for e in sorted(edges)]}


def decisions(domain,choose):
    """Decode categorical actions; yields normalized O(n) observations to policy.

    choose(features, legal_actions) returns one index. Hypergraphs use sparse
    edge slots rather than enumerating all k-subsets. Duplicate sampled edges
    are collapsed and reported through the original edge-count feasibility.
    """
    n=domain['n'];edges=[];degrees=[0]*n;step=0
    def pick(options,current=()):
        nonlocal step
        features=[d/max(1,domain['max_edges']) for d in degrees]+[float(v in current) for v in range(n)]+[step/2048,len(edges)/128,len(current)/128,1.0]
        action=choose(features,list(options));step+=1
        if action not in options:raise ValueError('Policy chose a masked action')
        return action
    if domain['kind']=='simple_graph':
        possible=list(itertools.combinations(range(n),2));target=domain['edge_count']
        for i,(u,v) in enumerate(possible):
            left=len(possible)-i;have=len(edges)
            options=[0] if have>=domain['max_edges'] else [1] if target is not None and target-have==left else [0,1]
            if pick(options):edges.append([u,v]);degrees[u]+=1;degrees[v]+=1
    elif domain['tree']:
        k=domain['uniformity'];available=1
        for _ in range(domain['edge_count']):
            parent=pick(range(available));edge=[parent,*range(available,available+k-1)];available+=k-1;edges.append(edge)
            for v in edge:degrees[v]+=1
    else:
        count=domain['edge_count'] if domain['edge_count'] is not None else pick(range(domain.get('minimum_edges',0),domain['max_edges']+1))
        seen={0}
        for edge_index in range(count):
            unseen=set(range(n))-seen;slots=count-edge_index
            need=max(1,len(unseen)-(slots-1)*(max(domain['edge_sizes'])-1)) if unseen and domain.get('connected') else 0
            size_options=[i for i,k in enumerate(domain['edge_sizes']) if k-1>=need]
            k=domain['uniformity'] or domain['edge_sizes'][pick(size_options)]
            edge=[]
            for position in range(k):
                options=[v for v in range(n) if v not in edge]
                if domain.get('connected') and unseen:
                    if position==0:options=sorted(seen)
                    elif sum(v in unseen for v in edge)<need and k-position<=need-sum(v in unseen for v in edge):options=sorted(unseen-set(edge))
                edge.append(pick(options,edge))
            edge=sorted(edge);edges.append(edge)
            seen.update(edge)
            for v in edge:degrees[v]+=1
    return {'n':n,'edges':[list(e) for e in sorted(set(tuple(e) for e in edges))]}
