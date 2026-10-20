"""Functional graphs.enumeration implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def Count_Subgraph(g, h, max_embeddings=100000):
    """Non-induced copies, dividing monomorphisms by automorphisms of h."""
    def count(iterator):
        result=0
        for _ in iterator:
            result+=1
            if result>max_embeddings: raise RuntimeError("Subgraph embedding enumeration budget exceeded")
        return result
    embeddings = count(nx.algorithms.isomorphism.GraphMatcher(g,h).subgraph_monomorphisms_iter())
    automorphisms = count(nx.algorithms.isomorphism.GraphMatcher(h,h).isomorphisms_iter())
    return embeddings//automorphisms


def get_appand_paths(g):
    result=[]
    for root in g:
        if g.degree(root)!=1: continue
        path=[root]; current=root
        while True:
            new=[v for v in g[current] if v not in path]
            if not new or (len(path)>1 and g.degree(current)!=2): break
            current=new[0]; path.append(current)
        if path not in result and path[::-1] not in result: result.append(path)
    return result


def path_tree(g,v,max_paths=50000):
    result=nx.Graph(); result.add_node((v,)); stack=[(v,)]
    while stack:
        path=stack.pop()
        for u in g[path[-1]]:
            if u not in path:
                child=path+(u,); result.add_edge(path,child); stack.append(child)
                if len(result)>max_paths: raise RuntimeError("Path-tree expansion budget exceeded")
    return result


def All_Paths(g,start,end,length="all",max_paths=50000):
    result=[]
    for path in nx.all_simple_paths(g,start,end,cutoff=None if length=="all" else length):
        if length=="all" or len(path)-1==length: result.append(path)
        if len(result)>max_paths: raise RuntimeError("Path enumeration budget exceeded")
    return result


def findCycles(g,length=None,max_cycles=10000):
    result=[]
    for cycle in nx.simple_cycles(g,length_bound=length):
        if length is None or len(cycle)==length: result.append(cycle)
        if len(result)>max_cycles: raise RuntimeError("Cycle enumeration budget exceeded")
    return result


def Find_all_hamiltonian_cycles(g,max_cycles=10000,max_states=1000000):
    if not g: return []
    root=next(iter(g)); result=[]; order={v:i for i,v in enumerate(g)}; states=0
    def visit(path):
        nonlocal states
        states+=1
        if states>max_states: raise RuntimeError("Hamiltonian search state budget exceeded")
        if len(path)==len(g):
            if g.has_edge(path[-1],root) and (g.is_directed() or order[path[1]]<order[path[-1]]):
                result.append(list(path))
                if len(result)>max_cycles: raise RuntimeError("Hamiltonian cycle budget exceeded")
            return
        for v in g[path[-1]]:
            if v not in path: visit(path+[v])
    if len(g)>=3: visit([root])
    return result


def Find_hamiltonian_cycle(g,max_states=1000000):
    if len(g)<3: return None
    root=next(iter(g)); states=0
    def visit(path):
        nonlocal states
        states+=1
        if states>max_states: raise RuntimeError("Hamiltonian search state budget exceeded")
        if len(path)==len(g): return path if g.has_edge(path[-1],root) else None
        for v in g[path[-1]]:
            if v not in path:
                found=visit(path+[v])
                if found is not None: return found
        return None
    return visit([root])


def Graphs_WithDegreeSequence(D,max_graphs=10000,max_states=1000000):
    """Exact non-isomorphic realizations; deterministic and limited to n<=9."""
    D=list(D); n=len(D)
    if n>9: raise ValueError("Exact realization enumeration supports at most9 vertices")
    if any(type(d) is not int for d in D) or not nx.is_graphical(D): return []
    graphs=[]; states=0
    def visit(g,residual):
        nonlocal states
        states+=1
        if states>max_states: raise RuntimeError("Degree-realization search budget exceeded")
        active=[v for v in range(n) if residual[v]>0]
        if not active:
            if not any(nx.is_isomorphic(g,h) for h in graphs): graphs.append(g.copy())
            if len(graphs)>max_graphs: raise RuntimeError("Too many graph realizations")
            return
        u=max(active,key=lambda v:residual[v]); count=residual[u]
        candidates=[v for v in active if v!=u and not g.has_edge(u,v)]
        for chosen in itertools.combinations(candidates,count):
            updated=list(residual); updated[u]=0
            for v in chosen: updated[v]-=1
            if min(updated,default=0)<0 or not nx.is_graphical(updated): continue
            child=g.copy(); child.add_edges_from((u,v) for v in chosen); visit(child,updated)
    visit(nx.empty_graph(n),D)
    return graphs


findDiCycles = findCycles

__all__ = ['Count_Subgraph', 'get_appand_paths', 'path_tree', 'All_Paths', 'findCycles', 'Find_all_hamiltonian_cycles', 'Find_hamiltonian_cycle', 'Graphs_WithDegreeSequence', 'findDiCycles']
