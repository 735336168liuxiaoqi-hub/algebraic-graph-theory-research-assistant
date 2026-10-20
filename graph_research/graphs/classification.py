"""Bounded generalized-line recognition with a constructive, checked witness.

An exact cover of induced clique-minus-matching blocks is searched. Vertices
in a missing pair are private to that block; other vertices occur in at most
two blocks. Distinct blocks meet in at most one vertex. This is exactly the
root graph plus cocktail-party construction. A negative search certificate
requires replay; it is not advertised as a short forbidden-subgraph witness.
"""
from itertools import combinations
import hashlib
import json
import networkx as nx


def _fingerprint(g):
    return hashlib.sha256(json.dumps({'n':len(g),'edges':sorted([sorted(edge) for edge in g.edges()])},sort_keys=True).encode()).hexdigest()


def _search(g,budget):
    edges=sorted(tuple(sorted(edge)) for edge in g.edges());edge_number={frozenset(edge):i for i,edge in enumerate(edges)};candidates=[]
    for size in range(2,len(g)+1):
        for members in combinations(sorted(g),size):
            missing=[(u,v) for u,v in combinations(members,2) if not g.has_edge(u,v)]
            private=[v for pair in missing for v in pair]
            if len(set(private))!=len(private):continue
            mask=sum(1<<edge_number[frozenset((u,v))] for u,v in combinations(members,2) if g.has_edge(u,v))
            if mask:candidates.append((set(members),set(private),mask,missing))
    by_edge=[[i for i,c in enumerate(candidates) if c[2]&(1<<e)] for e in range(len(edges))]
    # Large compatible blocks first; ties retain deterministic subset order.
    for indexes in by_edge:indexes.sort(key=lambda i:-candidates[i][2].bit_count())
    visited=0;exhausted=False
    def search(remaining,selected,memberships,private):
        nonlocal visited,exhausted
        visited+=1
        if visited>budget:exhausted=True;return None
        if not remaining:return selected
        choices=None
        for e in range(len(edges)):
            if not remaining&(1<<e):continue
            compatible=[]
            for i in by_edge[e]:
                members,paired,mask,_=candidates[i]
                if mask&remaining!=mask or members&private or any(memberships[v]>=2 for v in members) or any(memberships[v] for v in paired):continue
                if any(len(members&candidates[j][0])>1 for j in selected):continue
                compatible.append(i)
            if choices is None or len(compatible)<len(choices):choices=compatible
            if not choices:break
        for i in choices or []:
            members,paired,mask,_=candidates[i];counts=memberships.copy()
            for v in members:counts[v]+=1
            result=search(remaining^mask,[*selected,i],counts,private|paired)
            if result is not None:return result
            if exhausted:return None
        return None
    answer=search((1<<len(edges))-1,[],dict.fromkeys(g,0),set())
    blocks=None if answer is None else [{'vertices':sorted(candidates[i][0]),'missing_pairs':[list(pair) for pair in candidates[i][3]]} for i in answer]
    return blocks,visited,exhausted


def verify_generalized_line_certificate(g,certificate):
    """Verify a positive witness by reconstructing all original adjacencies.

    Negative certificates require a deterministic full search replay and their
    recorded state count; budget exhaustion is never a negative verdict.
    """
    if not isinstance(g,nx.Graph) or g.is_directed() or g.is_multigraph() or not 1<=len(g)<=10 or set(g)!=set(range(len(g))) or nx.number_of_selfloops(g):return False
    if not isinstance(certificate,dict) or certificate.get('graph_sha256')!=_fingerprint(g):return False
    if certificate.get('type')=='exhaustive_no_cover':
        budget=certificate.get('search_budget',0)
        if type(budget) is not int or not 1<=budget<=200000 or type(certificate.get('states')) is not int:return False
        blocks,states,exhausted=_search(g,budget)
        return blocks is None and not exhausted and states==certificate.get('states')
    if certificate.get('type')!='constructive_cover':return False
    cover=certificate.get('blocks',[]);memberships={v:[] for v in g};reconstructed=nx.Graph();reconstructed.add_nodes_from(g)
    if not isinstance(cover,list) or len(cover)>45:return False
    for i,block in enumerate(cover):
        if not isinstance(block,dict):return False
        members=block.get('vertices',[]);pairs=block.get('missing_pairs',[])
        if not isinstance(members,list) or len(members)>10 or any(type(v) is not int for v in members) or not isinstance(pairs,list) or len(pairs)>5:return False
        if len(members)<2 or len(set(members))!=len(members) or not set(members)<=set(g):return False
        used=[];missing=set()
        for pair in pairs:
            if not isinstance(pair,list) or len(pair)!=2 or any(type(v) is not int for v in pair) or pair[0]==pair[1] or not set(pair)<=set(members):return False
            used.extend(pair);missing.add(frozenset(pair))
        if len(set(used))!=len(used):return False
        for v in members:memberships[v].append(i)
        for u,v in combinations(members,2):
            if frozenset((u,v)) not in missing:
                if reconstructed.has_edge(u,v):return False
                reconstructed.add_edge(u,v)
        if any(g.has_edge(*pair) for pair in pairs):return False
    if any(len(group)>2 for group in memberships.values()):return False
    for i,block in enumerate(cover):
        if any(len(set(block['vertices'])&set(other['vertices']))>1 for other in cover[i+1:]):return False
        if any(len(memberships[v])!=1 for pair in block['missing_pairs'] for v in pair):return False
    return {frozenset(e) for e in reconstructed.edges}=={frozenset(e) for e in g.edges}


def graph_class_certificate(kind='path',n=5,edges=None,search_budget=100000):
    """Recognize generalized line graphs, at most ten vertices, exact or undecided."""
    from graph_research.graphs import make_graph
    if n>10 or not 1<=search_budget<=200000:raise ValueError('构造证书搜索限10顶点，状态预算1..200000。')
    g=make_graph(kind,n,edges);blocks,states,exhausted=_search(g,search_budget)
    result={'status':'indeterminate' if exhausted else 'recognized' if blocks is not None else 'not_generalized_line',
            'generalized_line_graph':None if exhausted else blocks is not None,'states':states,
            'interpretation':'广义线图=简单根图的线图加各根点的鸡尾酒会图附件。正证书逐项重构邻接；负证书需重放穷尽搜索，非短禁图证书。'}
    if exhausted:return result
    certificate={'type':'constructive_cover' if blocks is not None else 'exhaustive_no_cover','graph_sha256':_fingerprint(g),'states':states,'search_budget':search_budget}
    if blocks is not None:certificate['blocks']=blocks
    result.update(certificate=certificate,verified=verify_generalized_line_certificate(g,certificate))
    if not result['verified']:raise ArithmeticError('广义线图证书复核失败。')
    return result
