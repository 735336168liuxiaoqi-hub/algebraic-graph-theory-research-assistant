"""Functional graphs.matrices implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def _nodes(g):
    if g.is_multigraph() or nx.number_of_selfloops(g):
        raise ValueError("Only loopless simple graphs are supported")
    return list(g.nodes)


def degree_matrix(g):
    a = nx.to_numpy_array(g, nodelist=_nodes(g), weight=None)
    return np.diag(a.sum(axis=1))


def alpha_matrix(g, alpha=0):
    if not math.isfinite(float(alpha)) or not 0 <= alpha <= 1:
        raise ValueError("alpha must be in [0, 1]")
    a = nx.to_numpy_array(g, nodelist=_nodes(g), weight=None)
    return alpha * np.diag(a.sum(axis=1)) + (1-alpha) * a


def signless_laplacian_matrix(g):
    return degree_matrix(g) + alpha_matrix(g)


def normalized_laplace_matrix(g):
    a = alpha_matrix(g)
    d = a.sum(axis=1)
    inverse = np.zeros_like(d)
    np.divide(1, np.sqrt(d), out=inverse, where=d > 0)
    return np.diag((d > 0).astype(float)) - inverse[:, None]*a*inverse[None, :]


def distance_matrix(g):
    nodes = _nodes(g)
    d = np.asarray(nx.floyd_warshall_numpy(g, nodelist=nodes, weight=None))
    if not np.isfinite(d).all():
        raise ValueError("Distance spectrum requires connected/reachable vertex pairs")
    return d


def distLap(g):
    d = distance_matrix(g)
    return np.diag(d.sum(axis=1))-d


def is_transmission_regular(g):
    d = distance_matrix(g).sum(axis=1)
    return len(d) == 0 or bool(np.allclose(d, d[0]))


def ABC_matrix(g):
    a = alpha_matrix(g)
    d = a.sum(axis=1)
    result = np.zeros_like(a)
    for i, j in zip(*np.nonzero(a)):
        result[i, j] = math.sqrt(max(0, (d[i]+d[j]-2)/(d[i]*d[j])))
    return result


def get_Matrix(g, Type="A"):
    if not isinstance(Type,str):
        return Weighted_Adjancency_Matrix(g,Type) if callable(Type) else alpha_matrix(g,Type)
    table = {"A": lambda: alpha_matrix(g), "L": lambda: degree_matrix(g)-alpha_matrix(g),
             "Q": lambda: signless_laplacian_matrix(g), "D": lambda: distance_matrix(g),
             "DL": lambda: distLap(g), "N": lambda: normalized_laplace_matrix(g),
             "ABC": lambda: ABC_matrix(g), "S": lambda: seidel_matrix(g),
             "H":lambda:hermitian_adjacency_matrix(g),"W":lambda:nx.to_numpy_array(g,nodelist=_nodes(g),weight="weight")}
    if Type not in table:
        raise ValueError(f"Supported matrix types: {list(table)}")
    return table[Type]()


def Weighted_Adjancency_Matrix(g, f):
    nodes = _nodes(g)
    return np.array([[f(g.degree(u), g.degree(v)) if g.has_edge(u, v) else 0
                      for v in nodes] for u in nodes])


def seidel_matrix(g):
    a = alpha_matrix(g)
    return np.ones_like(a)-np.eye(len(a))-2*a


def hermitian_adjacency_matrix(g):
    nodes=list(g); index={v:i for i,v in enumerate(nodes)}
    a=np.zeros((len(nodes),len(nodes)),dtype=complex)
    for u,v in g.edges:
        if u==v: raise ValueError("Loopless graphs required")
        i,j=index[u],index[v]
        if not g.is_directed() or g.has_edge(v,u): a[i,j]=a[j,i]=1
        else: a[i,j],a[j,i]=1j,-1j
    return a


def exact_graph_matrix(g,kind="A",alpha=0):
    nodes=list(g); n=len(nodes)
    a=sp.Matrix(nx.to_numpy_array(g,nodelist=nodes,weight=None,dtype=int))
    d=sp.diag(*[sum(a.row(i)) for i in range(n)])
    if kind=="A": return a
    if kind=="L": return d-a
    if kind=="Q": return d+a
    if kind=="alpha": return sp.sympify(alpha)*d+(1-sp.sympify(alpha))*a
    if kind=="S": return sp.ones(n)-sp.eye(n)-2*a
    if kind=="H":
        return sp.Matrix(n,n,lambda i,j: 1 if a[i,j] and a[j,i] else sp.I*(a[i,j]-a[j,i]))
    if kind in ("D","DL"):
        distances=dict(nx.all_pairs_shortest_path_length(g))
        if any(len(distances[v])!=n for v in nodes): raise ValueError("All vertex pairs must be reachable")
        matrix=sp.Matrix([[distances[u][v] for v in nodes] for u in nodes])
        return matrix if kind=="D" else sp.diag(*[sum(matrix.row(i)) for i in range(n)])-matrix
    raise ValueError("Exact matrix supports A,L,Q,alpha,S,H,D,DL")


Hermitian_Adjacency_Matrix = hermitian_adjacency_matrix

__all__ = ['degree_matrix', 'alpha_matrix', 'signless_laplacian_matrix', 'normalized_laplace_matrix', 'distance_matrix', 'distLap', 'is_transmission_regular', 'ABC_matrix', 'get_Matrix', 'Weighted_Adjancency_Matrix', 'seidel_matrix', 'hermitian_adjacency_matrix', 'exact_graph_matrix', 'Hermitian_Adjacency_Matrix']
