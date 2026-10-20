"""Functional graphs.operations implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def _fresh(g,number):
    start=max([v for v in g if type(v) is int]+[-1])+1
    while any(v in g for v in range(start,start+number)): start+=number+1
    return list(range(start,start+number))


def seidel_switching(g, vertices):
    result = g.copy()
    selected = set(vertices)
    if not selected <= set(g):
        raise ValueError("Unknown switching vertex")
    for u in selected:
        for v in set(g)-selected:
            if result.has_edge(u, v):
                result.remove_edge(u, v)
            else:
                result.add_edge(u, v)
    return result


def Graph_Power(g, n):
    return nx.power(g, n)


def Add_path(g, vertices, copy=True):
    result = g.copy() if copy else g
    nx.add_path(result, vertices)
    return result


def add_paths(g, D, copy=True):
    result = g.copy() if copy else g
    for vertices in D:
        nx.add_path(result, vertices)
    return result


def Add_cycles(g, *cycles, copy=True):
    result = g.copy() if copy else g
    for cycle in cycles:
        nx.add_cycle(result, cycle)
    return result


def Delete_Vertices(g, vertices, copy=True):
    result = g.copy() if copy else g
    result.remove_nodes_from(vertices)
    return result


def Delete_Edges(g, edges, copy=True):
    result = g.copy() if copy else g
    result.remove_edges_from(edges)
    return result


def Add_Edges(g, edges, copy=True):
    result = g.copy() if copy else g
    result.add_edges_from(edges)
    return result


def coalescence_graphs(graphs, roots, relabel=True):
    if len(graphs) != len(roots):
        raise ValueError("One root per graph is required")
    out = nx.Graph()
    for index, (g, root) in enumerate(zip(graphs, roots)):
        if root not in g:
            raise ValueError("Root must belong to its graph")
        mapping = {v: ("root" if v == root else (index, v)) for v in g}
        out = nx.compose(out, nx.relabel_nodes(g, mapping))
    return nx.convert_node_labels_to_integers(out) if relabel else out


def union_graphs(graphs, relabel=True):
    if relabel:
        return nx.disjoint_union_all(graphs)
    return nx.compose_all(graphs)


def join_graphs(graphs, relabel=True):
    result = nx.Graph()
    for i, g in enumerate(graphs):
        h = nx.relabel_nodes(g, {v: (i, v) for v in g})
        previous = list(result)
        result = nx.compose(result, h)
        result.add_edges_from(itertools.product(previous, h))
    return nx.convert_node_labels_to_integers(result) if relabel else result


def add_stars(g,D,copy=True):
    result=g.copy() if copy else g
    for root,count in dict(D).items():
        if root not in result or type(count) is not int or count<0: raise ValueError("Invalid star attachment")
        result.add_edges_from((root,v) for v in _fresh(result,count))
    return result


def add_innerPaths(g,D,relabel=False):
    result=g.copy()
    for (u,v),lengths in dict(D).items():
        if u not in g or v not in g: raise ValueError("Unknown path endpoint")
        for count in lengths if isinstance(lengths,(list,tuple)) else [lengths]:
            if type(count) is not int or count<0: raise ValueError("Internal-vertex count must be nonnegative")
            nx.add_path(result,[u]+_fresh(result,count)+[v])
    return nx.convert_node_labels_to_integers(result) if relabel else result


def K_subdivide_graph(g,k,relabel=False):
    if type(k) is not int or k<0: raise ValueError("k is the number of inserted vertices per edge")
    result=g.copy(); edges=list(g.edges)
    result.remove_edges_from(edges)
    for u,v in edges: nx.add_path(result,[u]+_fresh(result,k)+[v])
    return nx.convert_node_labels_to_integers(result) if relabel else result


def part_join(g,h,sU=None,sV=None,relabel=True):
    left=list(g if sU is None else sU); right=list(h if sV is None else sV)
    result=nx.disjoint_union(g,h)
    gm={v:i for i,v in enumerate(g)}; hm={v:len(g)+i for i,v in enumerate(h)}
    result.add_edges_from((gm[u],hm[v]) for u in left for v in right)
    if relabel: return result
    return nx.relabel_nodes(result,{**{i:(0,v) for v,i in gm.items()},**{i:(1,v) for v,i in hm.items()}})


def H_join(h,GL,UL=None,relabel=True):
    nodes=list(h)
    graphs=[GL.get(v,nx.empty_graph(1)) for v in nodes] if isinstance(GL,dict) else list(GL)
    if len(graphs)!=len(nodes): raise ValueError("One replacing graph per base vertex required")
    result=nx.Graph(); mappings={}
    for v,g in zip(nodes,graphs):
        mappings[v]={u:(v,u) for u in g}
        result=nx.compose(result,nx.relabel_nodes(g,mappings[v]))
    selected={v:list(g) if UL is None else list(UL[i]) for i,(v,g) in enumerate(zip(nodes,graphs))}
    for u,v in h.edges:
        result.add_edges_from((mappings[u][a],mappings[v][b]) for a in selected[u] for b in selected[v])
    return nx.convert_node_labels_to_integers(result) if relabel else result


def HJQM(h,dND,alpha=None):
    """Average alpha quotient; equitable only when replacing graphs are regular."""
    a=sp.Symbol("alpha") if alpha is None else sp.sympify(alpha)
    nodes=list(h); sizes=[sp.sympify(dND.get(v,(1,0))[0]) for v in nodes]
    degrees=[2*sp.sympify(dND.get(v,(1,0))[1])/sizes[i] for i,v in enumerate(nodes)]
    adjacency=sp.Matrix(nx.to_numpy_array(h,nodelist=nodes,dtype=int))
    off=adjacency*sp.diag(*sizes)
    return (1-a)*off+sp.diag(*degrees)+a*sp.diag(*[sum(off.row(i)) for i in range(len(nodes))])


def rooted_product(g,DvH,relabel=True):
    result=nx.relabel_nodes(g,{v:(0,v) for v in g})
    for number,(vertex,(root,h)) in enumerate(DvH.items(),1):
        if vertex not in g or root not in h: raise ValueError("Root must belong to its graph")
        mapping={v:((0,vertex) if v==root else (number,v)) for v in h}
        result=nx.compose(result,nx.relabel_nodes(h,mapping))
    return nx.convert_node_labels_to_integers(result) if relabel else result


def corona_graphs(g,h):
    base=g.copy(); result=nx.relabel_nodes(base,{v:(0,v) for v in base})
    for i,vertex in enumerate(base,1):
        child=nx.relabel_nodes(h,{v:(i,v) for v in h})
        result=nx.compose(result,child); result.add_edges_from(((0,vertex),u) for u in child)
    return nx.convert_node_labels_to_integers(result)


def sew_graphs(g,h,Vpairs,relabel=True):
    result=nx.compose(nx.relabel_nodes(g,{v:(0,v) for v in g}),nx.relabel_nodes(h,{v:(1,v) for v in h}))
    for u,v in Vpairs:
        if u not in g or v not in h: raise ValueError("Unknown vertex identification")
        result=nx.contracted_nodes(result,(0,u),(1,v),self_loops=False,copy=False)
    return nx.convert_node_labels_to_integers(result) if relabel else result


def linkGraph(g,h,u,v,k,relabel=True):
    if type(k) is not int or k<0: raise ValueError("Path edge count must be nonnegative")
    if k==0: return sew_graphs(g,h,[(u,v)],relabel)
    result=nx.compose(nx.relabel_nodes(g,{w:(0,w) for w in g}),nx.relabel_nodes(h,{w:(1,w) for w in h}))
    nx.add_path(result,[(0,u)]+[(2,i) for i in range(k-1)]+[(1,v)])
    return nx.convert_node_labels_to_integers(result) if relabel else result


def Blowup(g,U,k):
    if k<1: raise ValueError("Positive clone count required")
    selected=set(U)
    copies={v:[(v,i) for i in range(k)] if v in selected else [(v,0)] for v in g}
    result=nx.Graph(); result.add_nodes_from(itertools.chain.from_iterable(copies.values()))
    for u,v in g.edges: result.add_edges_from(itertools.product(copies[u],copies[v]))
    return nx.convert_node_labels_to_integers(result)


def Rotate_Edges(g,e):
    u,v=e[:2]
    if set(g[u])&set(g[v]): return None
    result=g.copy()
    for w in list(g[v]):
        if w!=u: result.remove_edge(v,w); result.add_edge(u,w)
    return result

__all__ = ['seidel_switching', 'Graph_Power', 'Add_path', 'add_paths', 'Add_cycles', 'Delete_Vertices', 'Delete_Edges', 'Add_Edges', 'coalescence_graphs', 'union_graphs', 'join_graphs', 'add_stars', 'add_innerPaths', 'K_subdivide_graph', 'part_join', 'H_join', 'HJQM', 'rooted_product', 'corona_graphs', 'sew_graphs', 'linkGraph', 'Blowup', 'Rotate_Edges']
