"""Functional hypergraphs.families implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def _family_parameters(m, k):
    if type(m) is not int or type(k) is not int or m < 1 or k < 2:
        raise ValueError("Positive edge count and rank >=2 are required")


def HyperPath(l, k=2):
    from graph_research.hypergraphs.model import Hypergraph
    _family_parameters(l, k)
    next_vertex = l+1
    edges = []
    for i in range(l):
        edges.append([i, i+1]+list(range(next_vertex, next_vertex+k-2)))
        next_vertex += k-2
    return Hypergraph(edges)


def HyperStar(e, k=2):
    from graph_research.hypergraphs.model import Hypergraph
    _family_parameters(e, k)
    return Hypergraph([[0]+list(range(1+i*(k-1), 1+(i+1)*(k-1))) for i in range(e)])


def HyperCycle(e, k=2):
    from graph_research.hypergraphs.model import Hypergraph
    _family_parameters(e, k)
    if e == 2 and k > 2:
        return Hypergraph([list(range(k)), [0, k-1]+list(range(k, 2*k-2))])
    if e < 3:
        raise ValueError("A simple loose cycle needs >=3 edges (or 2 when k>=3)")
    return Hypergraph([[i, (i+1)%e]+list(range(e+i*(k-2), e+(i+1)*(k-2))) for i in range(e)])


def CompleteHyperG(n, r):
    from graph_research.hypergraphs.model import Hypergraph
    return Hypergraph(itertools.combinations(range(n), r), vertices=range(n))


def VStarLike(*lengths, rank=3):
    from graph_research.hypergraphs.model import Hypergraph
    from graph_research.hypergraphs.operations import add_paths
    return add_paths(Hypergraph(vertices=[0]), {0: list(lengths)}, rank=rank)


def EStarLike(*lengths,rank=None):
    from graph_research.hypergraphs.operations import add_paths
    rank=max(2,len(lengths),rank or 0)
    return add_paths(HyperPath(1,rank),{i:length for i,length in enumerate(lengths)})


def Bicyclic_C1(p,k=3,relabel=True):
    from graph_research.hypergraphs.operations import Add_innerPaths, Disjoint_Union
    if k<3 or len(p)!=3 or any(type(n) is not int or n<1 for n in p): raise ValueError("C1 requires rank>=3 and three positive path edge counts")
    graph=Disjoint_Union([HyperPath(1,k),HyperPath(1,k)],relabel=True)
    left,right=graph.Edges
    graph=Add_innerPaths(graph,{(left[0],left[1]):p[0],(right[0],right[1]):p[1],(left[2],right[2]):p[2]})
    return graph.Relabel() if relabel else graph


def Bicyclic_C2(p,k=3,relabel=True):
    from graph_research.hypergraphs.operations import Add_innerPaths, Disjoint_Union
    if k<3 or len(p)!=3 or any(type(n) is not int or n<1 for n in p): raise ValueError("C2 requires rank>=3 and three positive path edge counts")
    graph=Disjoint_Union([HyperPath(1,k),HyperPath(1,k)],relabel=True)
    left,right=graph.Edges
    graph=Add_innerPaths(graph,{(left[i],right[i]):p[i] for i in range(3)})
    return graph.Relabel() if relabel else graph


def Bicyclic_C3(p,k=4,relabel=True):
    from graph_research.hypergraphs.operations import Add_innerPaths
    if k<4 or len(p)!=2 or any(type(n) is not int or n<1 for n in p): raise ValueError("C3 requires rank>=4 and two positive path edge counts")
    graph=HyperPath(1,k); e=graph.Edges[0]
    graph=Add_innerPaths(graph,{(e[0],e[1]):p[0],(e[2],e[3]):p[1]})
    return graph.Relabel() if relabel else graph


def Bicyclic_C1s(n,k=3):
    return [Bicyclic_C1([a,b,n-a-b],k) for a in range(1,n-1) for b in range(1,a+1) if n-a-b>=1]


def Bicyclic_C2s(n,k=3):
    return [Bicyclic_C2([a,b,n-a-b],k) for a in range(1,n-1) for b in range(1,a+1) if 1<=n-a-b<=b]

__all__ = ['HyperPath', 'HyperStar', 'HyperCycle', 'CompleteHyperG', 'VStarLike', 'EStarLike', 'Bicyclic_C1', 'Bicyclic_C2', 'Bicyclic_C3', 'Bicyclic_C1s', 'Bicyclic_C2s']
