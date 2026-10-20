"""Functional graphs.symmetry implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def orbit_subdivision(g):
    from graph_research.core.symmetry import automorphism_orbits
    return automorphism_orbits(g)


def automorphism_group(g, max_maps=100000):
    from graph_research.core.symmetry import AutomorphismGroup
    return AutomorphismGroup(g, max_maps=max_maps)


def equitable_quotient(g,blocks=None,matrix="A",alpha=0):
    from graph_research.algebra.products import Quotient_Matrix
    from graph_research.graphs.matrices import alpha_matrix, get_Matrix
    pass  # imports resolved by functional package
    nodes=list(g); index={v:i for i,v in enumerate(nodes)}
    blocks=orbit_subdivision(g) if blocks is None else [list(b) for b in blocks]
    indices=[[index[v] for v in block] for block in blocks]
    a=alpha_matrix(g,alpha) if matrix=="alpha" else get_Matrix(g,matrix)
    q=Quotient_Matrix(a,indices)
    equitable=all(np.allclose(a[np.ix_(b,c)].sum(axis=1),q[i,j]) for i,b in enumerate(indices) for j,c in enumerate(indices))
    return {"quotient":q,"blocks":blocks,"equitable":equitable}


def Quo_Mat(g, type='A'):
    return equitable_quotient(g, matrix=type)['quotient']


def distance_partition(g, v):
    distances = nx.single_source_shortest_path_length(g, v)
    return [[u for u, value in distances.items() if value == d]
            for d in sorted(set(distances.values()))]


def is_biregular_bipartite(g):
    if not nx.is_bipartite(g) or not g: return False
    colors=nx.bipartite.color(g)
    return all(len({g.degree(v) for v in g if colors[v]==color})<=1 for color in (0,1))

__all__ = ['orbit_subdivision', 'automorphism_group', 'equitable_quotient', 'Quo_Mat', 'distance_partition', 'is_biregular_bipartite']
