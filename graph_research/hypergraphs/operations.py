"""Functional hypergraphs.operations implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def _fresh(h,count):
    start=max([v for v in h.Vertices if type(v) is int]+[-1])+1
    return list(range(start,start+count))


def _simple(edges,vertices=None,weights=None):
    from graph_research.hypergraphs.model import Hypergraph
    result=[]; values=[]; known={}
    for e,w in zip(edges,weights if weights is not None else itertools.repeat(1)):
        e=tuple(dict.fromkeys(e)); key=frozenset(e)
        if len(e)<2: raise ValueError("Identification would collapse an edge to fewer than2 vertices")
        if key in known:
            if not math.isclose(float(w),values[known[key]]): raise ValueError("Conflicting weights on merged duplicate edges")
            continue
        known[key]=len(result); result.append(e); values.append(float(w))
    return Hypergraph(result,vertices=vertices,weights=values)


def _roots(h,v):
    try: single=v in h._index
    except TypeError: single=False
    return [v] if single else list(v)


def Index(h,e):
    key=frozenset(e)
    return [i for i,edge in enumerate(h.Edges) if frozenset(edge)==key]


def append_edges(h):
    return [e for e in h.Edges if sum((h.degree(v) > 1 for v in e)) <= 1]


def add_path(h,v,s,rank=0,copy=True):
    graph=h.copy() if copy else h
    r=max(graph.rank,rank); roots=_roots(graph,v)
    if type(s) is not int or s<0 or (s and (r<2 or not 1<=len(roots)<r)):
        raise ValueError("Nonnegative edge count and fewer roots than the rank are required")
    if not set(roots)<=set(graph.Vertices): raise ValueError("Unknown attachment vertices")
    for _ in range(s):
        new=roots+_fresh(graph,r-len(roots)); graph.add_edges([new]); roots=[new[-1]]
    return graph


def add_paths(h,D,rank=0,copy=True):
    graph=h.copy() if copy else h
    for root,lengths in dict(D).items():
        for length in lengths if isinstance(lengths,(list,tuple)) else [lengths]:
            graph=add_path(graph,root,length,rank,copy=False)
    return graph


def merge_vertices(h,VGs,relabel=False,nv="w_"):
    mapping={v:v for v in h.Vertices}; used=set()
    for i,group in enumerate(VGs):
        group=list(group)
        if not set(group)<=set(h.Vertices) or used&set(group): raise ValueError("Merge groups must be disjoint subsets of vertices")
        used.update(group); label=(nv,i)
        if label in mapping: raise ValueError("Generated merge label collides with an existing vertex")
        for v in group: mapping[v]=label
    graph=_simple([[mapping[v] for v in e] for e in h.Edges],list(dict.fromkeys(mapping.values())),h.weights)
    return graph.Relabel() if relabel else graph


def Add_innerPath(h,VLP,l,k=None,relabel=False,nv="w"):
    if len(VLP)!=2 or type(l) is not int or l<0: raise ValueError("Two endpoint groups and nonnegative edge count required")
    left,right=[_roots(h,v) for v in VLP]; rank=h.rank if k is None else k
    if not set(left+right)<=set(h.Vertices): raise ValueError("Unknown path endpoint")
    if l==0: return merge_vertices(h,[list(dict.fromkeys(left+right))],relabel,nv)
    if rank<2 or not left or not right: raise ValueError("Invalid rank or empty endpoint group")
    graph=h.copy()
    if l==1:
        roots=list(dict.fromkeys(left+right))
        if len(roots)>rank: raise ValueError("Endpoint groups exceed rank")
        graph.add_edges([roots+_fresh(graph,rank-len(roots))])
    else:
        if len(left)>=rank or len(right)>=rank: raise ValueError("Each endpoint group must leave room for an internal vertex")
        for i in range(l):
            if i==0:
                connector=_fresh(graph,1)[0]
                vertices=left+[connector]
                graph.add_edges([vertices+list(range(connector+1,connector+1+rank-len(vertices)))])
                root=connector
            elif i==l-1:
                vertices=[root]+right
                graph.add_edges([vertices+_fresh(graph,rank-len(vertices))])
            else:
                new=_fresh(graph,rank-1); graph.add_edges([[root]+new]); root=new[0]
    return graph.Relabel() if relabel else graph


def Add_innerPaths(h,D,relabel=False,nv="w"):
    graph=h.copy()
    for pair,lengths in dict(D).items():
        for length in lengths if isinstance(lengths,(list,tuple)) else [lengths]: graph=Add_innerPath(graph,pair,length)
    return graph.Relabel() if relabel else graph


def blowup_edge(h,k):
    """Add k private vertices to EACH edge; k is an increment, not a rank."""
    from graph_research.hypergraphs.model import Hypergraph
    if type(k) is not int or k<0: raise ValueError("Nonnegative extra-vertex count required")
    new=_fresh(h,h.size()*k)
    return Hypergraph([list(e)+new[i*k:(i+1)*k] for i,e in enumerate(h.Edges)],weights=h.weights)


def BlowSomeEdges(h,blowedges):
    from graph_research.hypergraphs.model import Hypergraph
    graph=h.copy(); edges=graph.hyperedges(); vertices=graph.vertices(); weights=graph.weights.copy()
    for e,count in blowedges.items():
        indices=Index(graph,e)
        if len(indices)!=1 or type(count) is not int or count<0: raise ValueError("Unknown edge or invalid expansion count")
        fresh=_fresh(Hypergraph(edges,vertices=vertices,weights=weights),count)
        edges[indices[0]]=tuple(e)+tuple(fresh); vertices+=fresh
    return Hypergraph(edges,vertices=vertices,weights=weights)


def blowup_vertex(h,d):
    """Replace each vertex by ALL its clones inside each incident edge (rank changes)."""
    from graph_research.hypergraphs.model import Hypergraph
    counts={v:d for v in h.Vertices} if type(d) is int else dict(d)
    if any(type(n) is not int or n<1 for n in counts.values()): raise ValueError("Positive clone counts required")
    copies={v:[(v,i) for i in range(counts.get(v,1))] for v in h.Vertices}
    edges=[list(itertools.chain.from_iterable(copies[v] for v in e)) for e in h.Edges]
    return Hypergraph(edges,vertices=list(itertools.chain.from_iterable(copies.values())),weights=h.weights).Relabel()


def Blow_Up(h,VS,relabel=False):
    """Cartesian clone expansion: choose ONE clone of each endpoint in each edge."""
    from graph_research.hypergraphs.model import Hypergraph
    counts={v:VS for v in h.Vertices} if type(VS) is int else dict(VS)
    if any(type(n) is not int or n<1 for n in counts.values()): raise ValueError("Positive clone counts required")
    copies={v:[(v,i) for i in range(counts.get(v,1))] for v in h.Vertices}
    edges=[]; weights=[]
    for e,w in zip(h.Edges,h.weights):
        new=list(itertools.product(*(copies[v] for v in e))); edges+=new; weights += [w]*len(new)
        if len(edges)>100000: raise RuntimeError("Clone expansion budget exceeded")
    graph=Hypergraph(edges,vertices=list(itertools.chain.from_iterable(copies.values())),weights=weights)
    return graph.Relabel() if relabel else graph


def Disjoint_Union(graphs,relabel=False):
    from graph_research.hypergraphs.model import Hypergraph
    edges=[]; vertices=[]; weights=[]
    for i,h in enumerate(graphs):
        edges += [[(i,v) for v in e] for e in h.Edges]
        vertices += [(i,v) for v in h.Vertices]; weights += list(h.weights)
    graph=Hypergraph(edges,vertices=vertices,weights=weights)
    return graph.Relabel() if relabel else graph


def Coalescence_Hypergraphs(g,h,VLP,relabel=False):
    left,right=VLP
    if len(left)!=len(right): raise ValueError("Same number of identification groups required")
    union=Disjoint_Union([g,h]); groups=[]
    for a,b in zip(left,right): groups.append([(0,v) for v in _roots(g,a)]+[(1,v) for v in _roots(h,b)])
    return merge_vertices(union,groups,relabel)


def Rooted_Product(h,DvH,relabel=True):
    graphs=[h]+[item[1] for item in DvH.values()]
    groups=[[(0,v),(i,root)] for i,(v,(root,_)) in enumerate(DvH.items(),1)]
    return merge_vertices(Disjoint_Union(graphs),groups,relabel)


def subdivide_edge(h,e,k):
    """Replace an edge by a loose k-edge path, preserving its non-leaf anchors."""
    if type(k) is not int or k<1: raise ValueError("Positive replacement path edge count required")
    indices=Index(h,e)
    if len(indices)!=1: raise ValueError("An exact edge must be specified")
    edge=h.Edges[indices[0]]; anchors=[v for v in edge if h.degree(v)>1]
    if len(anchors)>2: raise ValueError("Subdivision supports at most two non-leaf anchors")
    if k==1: return h.copy()
    if not anchors: anchors=[edge[0]]
    graph=h.delete_edges([edge],replace=False)
    graph=graph.delete_vertices([v for v in edge if v not in anchors and h.degree(v)==1],replace=False)
    return Add_innerPath(graph,anchors,k,k=h.uniform()) if len(anchors)==2 else add_path(graph,anchors,k,rank=h.uniform())


def vertice_releasing(h,i,L):
    from graph_research.hypergraphs.model import Hypergraph
    if not 0<=i<h.size() or not set(L)<=set(h.Edges[i]): raise ValueError("Invalid edge or release vertices")
    mapping=dict(zip(L,_fresh(h,len(L))))
    edges=h.hyperedges(); edges[i]=tuple(mapping.get(v,v) for v in edges[i])
    return Hypergraph(edges,vertices=list(dict.fromkeys(h.Vertices+list(mapping.values()))),weights=h.weights)


def split_vertex(h,v,n):
    from graph_research.hypergraphs.model import Hypergraph
    if v not in h.Vertices or type(n) is not int or n<1: raise ValueError("Invalid vertex or split count")
    edges=[]; weights=[]
    for i,(e,w) in enumerate(zip(h.Edges,h.weights)):
        if v not in e: edges.append(e); weights.append(w)
        else:
            for j in range(n): edges.append([(v,i,j) if u==v else u for u in e]); weights.append(w)
    return Hypergraph(edges,weights=weights).Relabel()


def cartesian_product_H(h,g):
    vertices=list(itertools.product(h.Vertices,g.Vertices)); edges=[]; weights=[]
    for v in h.Vertices:
        for e,w in zip(g.Edges,g.weights): edges.append([(v,u) for u in e]); weights.append(w)
    for v in g.Vertices:
        for e,w in zip(h.Edges,h.weights): edges.append([(u,v) for u in e]); weights.append(w)
    return _simple(edges,vertices,weights).Relabel()


def TotalGraph(h):
    """Original function builds the incidence bipartite graph, not an ordinary total graph."""
    return h.incidence_graph()


def WeightedLineGraph(h):
    return h.intersection_graph()


def spanning_subgraph(h, E):
    return h.spanning_subgraph([i for e in E for i in Index(h, e)])


def induced_subgraph(h, U):
    return h.induced_subgraph(U)


def IsIsomorphic(g, h):
    return nx.is_isomorphic(g.incidence_graph(), h.incidence_graph(),
                            node_match=nx.algorithms.isomorphism.categorical_node_match("bipartite", -1))


def CyclomaticNumber(h):
    g = h.incidence_graph()
    return g.number_of_edges()-g.number_of_nodes()+nx.number_connected_components(g)

__all__ = ['Index', 'append_edges', 'add_path', 'add_paths', 'merge_vertices', 'Add_innerPath', 'Add_innerPaths', 'blowup_edge', 'BlowSomeEdges', 'blowup_vertex', 'Blow_Up', 'Disjoint_Union', 'Coalescence_Hypergraphs', 'Rooted_Product', 'subdivide_edge', 'vertice_releasing', 'split_vertex', 'cartesian_product_H', 'TotalGraph', 'WeightedLineGraph', 'spanning_subgraph', 'induced_subgraph', 'IsIsomorphic', 'CyclomaticNumber']
