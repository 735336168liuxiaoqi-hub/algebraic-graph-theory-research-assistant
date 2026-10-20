"""Functional graphs.polynomials implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def charpolys_for_graph(g, type="L", variable="x"):
    from graph_research.graphs.matrices import get_Matrix
    a = get_Matrix(g, type)
    if not np.equal(a, np.round(a)).all():
        raise ValueError("Exact graph polynomial currently supports integral matrices")
    return sp.Matrix(a.astype(int)).charpoly(sp.Symbol(variable)).as_poly()


def exact_characteristic_polynomial(g,kind="A",alpha=0,variable="x"):
    from graph_research.graphs.matrices import exact_graph_matrix
    return exact_graph_matrix(g,kind,alpha).charpoly(sp.Symbol(variable)).as_poly()


def abs_polynomial(f):
    p=f if isinstance(f,sp.Poly) else sp.Poly(f)
    return sp.Poly.from_dict({key:abs(value) for key,value in p.terms()},p.gen)


def rev_polynomial(f,n=None):
    p=f if isinstance(f,sp.Poly) else sp.Poly(f)
    degree=max(p.degree(),p.degree() if n is None else n)
    return sp.Poly(sp.expand(p.gen**degree*p.as_expr().subs(p.gen,1/p.gen)),p.gen)


def abscharpoly(g):
    return abspm(exact_characteristic_polynomial(g))


def abscharpoly_path(n):
    x=sp.Symbol("x")
    return sp.Poly(sum(sp.binomial(n-k,k)*x**(n-2*k) for k in range(n//2+1)),x)


def gen_poly(k,h0,h1):
    if type(k) is not int or k<0: raise ValueError("Nonnegative subdivision count required")
    h0=h0 if isinstance(h0,sp.Poly) else sp.Poly(h0)
    h1=h1 if isinstance(h1,sp.Poly) else sp.Poly(h1,h0.gen)
    if k==0: return h0
    previous,current=h0,h1
    for _ in range(1,k): previous,current=current,sp.Poly(h0.gen,h0.gen)*current+previous
    return current


def abscharpoly_subdivide_edge(g,e,k):
    from graph_research.graphs.operations import _fresh
    if not g.has_edge(*e) or type(k) is not int or k<0: raise ValueError("An existing edge and nonnegative inserted-vertex count are required")
    graph=g.copy(); graph.remove_edge(*e); nx.add_path(graph,[e[0]]+_fresh(graph,k)+[e[1]])
    return abscharpoly(graph)


def absch_addclaws(g, S):
    from graph_research.graphs.operations import add_stars
    return abscharpoly(add_stars(g, S))


def Energy_Diff(h,g,**kwargs):
    """Direct E(h)-E(g); legacy integral normalization is not reproduced."""
    from graph_research.graphs.spectral import Energy
    if kwargs.get("wep"): raise ValueError("Quadrature-error output does not apply to direct spectral energy")
    pass  # imports resolved by functional package
    return Energy(h)-Energy(g)


def is_quasiorder_comparable(h,g):
    p=abscharpoly(h)-abscharpoly(g)
    return {sp.sign(value) for value in p.all_coeffs() if value!=0}


abspm = abs_polynomial


reversed_polynomial = rev_polynomial


gen_poly1 = gen_poly

__all__ = ['charpolys_for_graph', 'exact_characteristic_polynomial', 'abs_polynomial', 'rev_polynomial', 'abscharpoly', 'abscharpoly_path', 'gen_poly', 'abscharpoly_subdivide_edge', 'absch_addclaws', 'Energy_Diff', 'is_quasiorder_comparable', 'abspm', 'reversed_polynomial', 'gen_poly1']
