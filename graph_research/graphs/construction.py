"""Functional graphs.construction implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def HammingGraph(d, q):
    if type(d) is not int or type(q) is not int or d < 1 or q < 1:
        raise ValueError("d and q must be positive integers")
    g = nx.empty_graph(1)
    for _ in range(d):
        g = nx.cartesian_product(g, nx.complete_graph(q))
    return nx.convert_node_labels_to_integers(g)


def fan_graph(n):
    return nx.full_join(nx.empty_graph(1), nx.path_graph(n), rename=("h", "p"))


def rose_graph(lengths):
    g = nx.Graph()
    g.add_node(0)
    for length in lengths:
        if length < 3:
            raise ValueError("Each petal is a cycle of length >=3")
        nodes = [0]+list(range(len(g), len(g)+length-1))
        nx.add_cycle(g, nodes)
    return g


def make_graph(kind="path", n=5, edges=None):
    """普通图输入适配；自定义图必须kind='edges'并显式给n。

    n是完整顶点数(含孤立点)，顶点0..n-1；不会根据edges推断n。
    其他图族忽略edges。仅无自环、无重边的无向简单图：重复或反向重复的边
    会直接报错，不会被合并成权重，也不支持多重图输入。
    """
    from graph_research.graphs.matrices import _nodes
    if type(n) is not int or not 0 <= n <= 256:
        raise ValueError("n must be an integer in [0,256]")
    table = {"path": nx.path_graph, "cycle": nx.cycle_graph,
             "complete": nx.complete_graph, "empty": nx.empty_graph,
             "star": lambda count: nx.star_graph(max(0, count-1)) if count else nx.Graph()}
    if kind == "edges":
        g = nx.empty_graph(n)
        pairs = list(edges or [])
        if any(len(e) != 2 or any(type(v) is not int or not 0 <= v < n for v in e) for e in pairs):
            raise ValueError("Edges must be pairs of vertex indices in range(n)")
        # NetworkX silently collapses repeated and reversed pairs in a simple
        # graph. That would change the object the caller asked about, so the
        # duplicate is rejected instead of being reinterpreted as a weight.
        seen = set()
        for u, v in pairs:
            key = (u, v) if u <= v else (v, u)
            if key in seen:
                raise ValueError(f"Duplicate edge ({key[0]},{key[1]}): repeated or reversed edges are not "
                                 "merged into weights; weighted and multigraph inputs are not supported")
            seen.add(key)
        g.add_edges_from(pairs)
        _nodes(g)
        return g
    if kind not in table or (kind == "cycle" and n < 3):
        raise ValueError("Unsupported graph family or invalid cycle order")
    return table[kind](n)


def RandomKCyclicGraph(n,k,seed=None):
    if not 0<=k<=(n-1)*(n-2)//2 or n<1: raise ValueError("Invalid connected graph order/cycle rank")
    rng=random.Random(seed)
    g=nx.from_prufer_sequence([rng.randrange(n) for _ in range(n-2)]) if n>=2 else nx.empty_graph(1)
    choices=list(nx.non_edges(g)); rng.shuffle(choices); g.add_edges_from(choices[:k])
    return g


def RandBipartite(m, n, seed=None):
    return nx.bipartite.random_graph(m, n, 0.5, seed=seed)


def random_oriente(g,seed=None):
    rng=random.Random(seed); result=nx.DiGraph(); result.add_nodes_from(g)
    result.add_edges_from((u,v) if rng.random()<0.5 else (v,u) for u,v in g.edges)
    return result


def theta_graph(lengths):
    from graph_research.graphs.operations import add_innerPaths
    if len(lengths)<2 or any(type(n) is not int or n<1 for n in lengths) or list(lengths).count(1)>1:
        raise ValueError("At least two positive path lengths, with at most one direct edge")
    return add_innerPaths(nx.empty_graph(2),{(0,1):[n-1 for n in lengths]},relabel=True)


def Generalized_Theta(K):
    from graph_research.graphs.operations import add_innerPaths
    if len(K)!=2: raise ValueError("Supply forward and backward path-length lists")
    graph=nx.empty_graph(2,create_using=nx.DiGraph)
    return add_innerPaths(graph,{(0,1):[n-1 for n in K[0]],(1,0):[n-1 for n in K[1]]},relabel=True)


def caterpillar(d,D):
    from graph_research.graphs.operations import add_stars
    if type(d) is not int or d<0: raise ValueError("Nonnegative spine edge count required")
    return add_stars(nx.path_graph(d+1),D)


def RandomCactusGraph(lc,seed=None):
    from graph_research.graphs.operations import _fresh
    rng=random.Random(seed); graph=nx.empty_graph(1)
    for length in lc:
        if type(length) is not int or length<3: raise ValueError("Cycle lengths must be >=3")
        root=rng.choice(list(graph)); new=_fresh(graph,length-1)
        nx.add_cycle(graph,[root]+new)
    return graph


def rand_cactus_graph(cn,ml,seed=None):
    rng=random.Random(seed)
    if cn<0 or ml<3: raise ValueError("Nonnegative cycle count and max length>=3 required")
    return RandomCactusGraph([rng.randint(3,ml) for _ in range(cn)],seed)


def Random_Unicyclic_Graph(bk,c,seed=None):
    from graph_research.graphs.operations import _fresh
    rng=random.Random(seed)
    if c<3 or any(n<1 for n in bk): raise ValueError("Cycle length>=3 and positive tree orders required")
    graph=nx.cycle_graph(c)
    for n in bk:
        root=rng.randrange(c)
        tree=nx.from_prufer_sequence([rng.randrange(n) for _ in range(n-2)]) if n>=2 else nx.empty_graph(1)
        labels=_fresh(graph,n-1); mapping={0:root}; mapping.update(dict(zip(range(1,n),labels)))
        graph=nx.compose(graph,nx.relabel_nodes(tree,mapping))
    return graph


def genreg(n,d,g=None,seed=None):
    graph=nx.random_regular_graph(d,n,seed=seed)
    if g is not None:
        cycles=nx.minimum_cycle_basis(graph)
        if cycles and min(map(len,cycles))<g: raise ValueError("Sample does not satisfy requested girth; no unbounded rejection loop is used")
    return graph

__all__ = ['HammingGraph', 'fan_graph', 'rose_graph', 'make_graph', 'RandomKCyclicGraph', 'RandBipartite', 'random_oriente', 'theta_graph', 'Generalized_Theta', 'caterpillar', 'RandomCactusGraph', 'rand_cactus_graph', 'Random_Unicyclic_Graph', 'genreg']
