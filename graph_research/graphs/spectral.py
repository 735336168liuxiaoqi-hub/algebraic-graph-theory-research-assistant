"""Functional graphs.spectral implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def eigenpairs(g, type="L", order=0, spe=False):
    from graph_research.algebra.numeric import eigenpair
    from graph_research.graphs.matrices import get_Matrix
    return eigenpair(get_Matrix(g, type), spe=spe, order=order)


def Spectral_Radius(g, type="L", order=0, spe=False):
    from graph_research.algebra.numeric import spectral_radius
    from graph_research.graphs.matrices import get_Matrix
    return spectral_radius(get_Matrix(g, type))


def Energy(g, poly=False, **kwargs):
    if poly:
        raise ValueError("Use charpolys_for_graph for exact polynomial output")
    return float(np.abs(eigenpairs(g, type="A", spe=True)).sum())


def estrada_index(g):
    return float(np.exp(eigenpairs(g, type="A", spe=True)).sum())


def inertias_of_graph(g, type="A", tolerance=1e-9):
    values = eigenpairs(g, type=type, spe=True)
    if np.iscomplexobj(values) and np.max(np.abs(values.imag)) > tolerance:
        raise ValueError("Inertia requires a real symmetric spectrum")
    values = values.real
    return (int(np.sum(values > tolerance)), int(np.sum(values < -tolerance)),
            int(np.sum(np.abs(values) <= tolerance)))


def signature(g, type="A"):
    p, n, _ = inertias_of_graph(g, type)
    return p-n


def graph_spectrum(kind="path", n=5, edges=None, matrix="A", alpha=0):
    """返回普通图完整双精度矩阵谱，重复特征值保留、按值降序。

    另含matrix、nodes/edges、rho；D/DL要求连通。只有非负矩阵附数值
    relative_residual，否则该字段为None。不是超图张量Perron接口。

    spectrum 与 rho 来自同一次 Hermitian 分解：当谱半径就是最大特征值时
    （本函数产出的非负或半正定矩阵均如此），二者在位级别完全相同。
    """
    from graph_research.graphs.construction import make_graph
    from graph_research.graphs.matrices import alpha_matrix, get_Matrix
    g = make_graph(kind, n, edges)
    if not g:
        raise ValueError("Spectrum requires at least one vertex")
    a = alpha_matrix(g, alpha) if matrix == "alpha" else get_Matrix(g, matrix)
    if not np.array_equal(a, a.conj().T):
        raise ValueError("graph_spectrum requires a Hermitian matrix")
    values, vectors = np.linalg.eigh(a)
    order = np.argsort(values)[::-1]
    values = values[order]
    # Spectral radius is max|lambda|. For the nonnegative and PSD matrices built
    # here that is the largest eigenvalue, so both fields share one computation.
    if np.all(a >= 0) or values[0] >= -values[-1]:
        rho, vector = float(values[0]), vectors[:, order[0]]
    else:
        rho, vector = float(-values[-1]), vectors[:, order[-1]]
    x = np.real_if_close(vector)
    return {"nodes": list(g), "edges": [list(e) for e in g.edges], "matrix_type": matrix,
            "matrix": a.tolist(), "spectrum": values.tolist(), "rho": rho,
            "relative_residual": float(np.linalg.norm(a@x-rho*x)) if np.all(a >= 0) else None}


def Spectral_Radius_digraph(g,a=0,niter=2000):
    from graph_research.algebra.numeric import spectral_radius
    from graph_research.graphs.matrices import alpha_matrix
    pass  # imports resolved by functional package
    return spectral_radius(alpha_matrix(g,a))


def H_Spectra_Radius(matrix):
    a=np.asarray(matrix,dtype=complex)
    if not np.allclose(a,a.conj().T): raise ValueError("A Hermitian matrix is required")
    return float(np.linalg.eigvalsh(a).max())


def spectral_projectors(g,matrix="A",tolerance=1e-8):
    from graph_research.graphs.matrices import get_Matrix
    pass  # imports resolved by functional package
    a=np.asarray(get_Matrix(g,matrix))
    if not np.allclose(a,a.conj().T): raise ValueError("Orthogonal decomposition requires a Hermitian matrix")
    values,vectors=np.linalg.eigh(a)
    groups=[]
    for i in range(len(values)-1,-1,-1):
        if not groups or abs(values[i]-values[groups[-1][0]])>tolerance: groups.append([i])
        else: groups[-1].append(i)
    return [{"eigenvalue":float(values[block[0]]),"multiplicity":len(block),
             "basis":vectors[:,block],"projector":vectors[:,block]@vectors[:,block].conj().T}
            for block in groups]


def Spectral_decomposition(g):
    groups=spectral_projectors(g)
    return [v["eigenvalue"] for v in groups],np.column_stack([v["basis"] for v in groups])


def angle(g):
    groups=spectral_projectors(g)
    return [v["eigenvalue"] for v in groups],np.array([np.sqrt(np.maximum(0,np.diag(v["projector"]).real)) for v in groups])


def perron_order(g,matrix="A"):
    pass  # imports resolved by functional package
    value,vector=eigenpairs(g,type=matrix)
    if np.sum(vector.real)<0: vector=-vector
    return [v for _,v in sorted(zip(vector.real,list(g)),key=lambda item:item[0],reverse=True)]


def sort_vertice_by_perron_vector(g,T="A"):
    """Return relabeled graph and numeric order; no Sage plot object."""
    order=perron_order(g,T)
    return nx.relabel_nodes(g,{v:i for i,v in enumerate(order)}),order


def findCospe(graphs,reference=None,type="A"):
    from graph_research.graphs.polynomials import exact_characteristic_polynomial
    groups=defaultdict(list)
    for g in graphs:
        key=tuple(exact_characteristic_polynomial(g,type).all_coeffs())
        groups[key].append(g)
    if reference is not None:
        key=tuple(exact_characteristic_polynomial(reference,type).all_coeffs())
        return next(iter(groups.get(key,[])),None)
    return [group for group in groups.values() if len(group)>1]


def sortGraphbyInvariant(graphs,Invs,rev=False,ndigits=5):
    functions=[Invs] if callable(Invs) else list(Invs)
    return sorted(graphs,key=lambda g:tuple(round(float(f(g)),ndigits) for f in functions),reverse=rev)


def groupbyinv(graphs,inv):
    groups=defaultdict(list)
    for g in graphs: groups[inv(g)].append(g)
    return list(groups.values())


def is_WF(g):
    from graph_research.graphs.matrices import get_Matrix
    pass  # imports resolved by functional package
    a=get_Matrix(g,"A"); n=len(g)
    return np.linalg.matrix_rank(np.column_stack([np.linalg.matrix_power(a,k)@np.ones(n) for k in range(n)]))==n


def sum_connectivity(g):
    return sum(((g.degree(u) + g.degree(v)) ** (-0.5) for u, v in g.edges))

__all__ = ['eigenpairs', 'Spectral_Radius', 'Energy', 'estrada_index', 'inertias_of_graph', 'signature', 'graph_spectrum', 'Spectral_Radius_digraph', 'H_Spectra_Radius', 'spectral_projectors', 'Spectral_decomposition', 'angle', 'perron_order', 'sort_vertice_by_perron_vector', 'findCospe', 'sortGraphbyInvariant', 'groupbyinv', 'is_WF', 'sum_connectivity']
