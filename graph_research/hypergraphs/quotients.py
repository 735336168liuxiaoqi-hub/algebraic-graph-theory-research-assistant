"""Functional hypergraphs.quotients implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def edge_representative_quotient(h,max_selections=100000):
    """Edge-orbit representative quotient with edge weights AND original diagonal degrees."""
    from graph_research.core.symmetry import automorphism_orbits
    from graph_research.hypergraphs.model import Hypergraph
    graph=h._symmetry_graph()
    blocks=automorphism_orbits(graph,[("e",i) for i in range(h.size())],lambda a,b:a["color"]==b["color"])
    for attempt,choice in enumerate(itertools.product(*blocks)):
        if attempt>=max_selections: raise RuntimeError("Quotient representative search budget exceeded")
        selected=[h.Edges[node[1]] for node in choice]
        candidate=Hypergraph(selected)
        if candidate.is_connected(): break
    else: raise ValueError("No connected representative quotient found")
    weights=[]; k=h.uniform()
    for e,block in zip(selected,blocks):
        multiplicities={v:sum(v in h.Edges[node[1]] for node in block) for v in e}
        weights.append(math.prod(multiplicities.values())**(1/k))
    vertices=candidate.vertices()
    if not np.allclose(h.weights,1) or h.vertex_degrees is not None:
        raise ValueError("Edge-orbit quotient formula currently requires an unweighted original hypergraph")
    return Hypergraph(selected,vertices=vertices,weights=weights,vertex_degrees=[h.degree(v) for v in vertices]).Relabel()


class OrbitQuotient:
    """Exact equitable tensor ACTION on vertex orbits, not a simple hypergraph.

    A row is a sum of degree-(k-1) monomials. Repeated orbit indices are allowed
    in these monomials. They cannot in general be represented by simple edges.
    """
    def __init__(self,h,blocks=None):
        self.original=h.copy(); self.rank=h.uniform()
        if not h.is_connected(): raise ValueError("Connected hypergraph required")
        self.blocks=h.orbit_subdivision() if blocks is None else [list(b) for b in blocks]
        flattened=list(itertools.chain.from_iterable(self.blocks))
        if any(not block for block in self.blocks) or len(flattened)!=h.order() or set(flattened)!=set(h.Vertices):
            raise ValueError("Nonempty blocks must partition all original vertices")
        membership={v:i for i,block in enumerate(self.blocks) for v in block}
        d=h.incidence_matrix()@h.weights if h.vertex_degrees is None else h.vertex_degrees
        self.vertex_degrees=np.array([d[h._index[block[0]]] for block in self.blocks])
        self.rows=[]
        for i,block in enumerate(self.blocks):
            reference=None
            for vertex in block:
                row={}
                for e,w in zip(h.Edges,h.weights):
                    if vertex not in e: continue
                    powers=[0]*len(self.blocks)
                    for v in e:
                        if v!=vertex: powers[membership[v]]+=1
                    key=tuple(powers); row[key]=row.get(key,0)+float(w)
                if reference is None: reference=row
                elif reference.keys()!=row.keys() or any(not math.isclose(reference[p],row[p],rel_tol=1e-12,abs_tol=1e-12) for p in row):
                    raise ValueError("Partition is not equitable for the hypergraph tensor action")
                if not math.isclose(float(d[h._index[vertex]]),float(self.vertex_degrees[i])):
                    raise ValueError("Diagonal degrees are not constant on a block")
            self.rows.append(reference)

    def order(self):
        return len(self.blocks)
    def vertices(self):
        return list(range(self.order()))
    def terms(self):
        return [{"target_orbit":i,"powers":list(powers),"coefficient":coefficient}
                for i,row in enumerate(self.rows) for powers,coefficient in sorted(row.items())]

    def alpha_spectrum(self,alpha=0,tolerance=1e-11,max_iterations=20000,seed=42):
        if not math.isfinite(float(alpha)) or not 0<=alpha<1: raise ValueError("alpha must be in [0,1)")
        if not 0<tolerance<1 or type(max_iterations) is not int or max_iterations<1: raise ValueError("Invalid convergence controls")
        x=np.random.default_rng(seed).uniform(.5,1,self.order()); x/=x.sum()
        def ratios(vector):
            return np.array([alpha*self.vertex_degrees[i]+(1-alpha)*sum(
                    coefficient*math.prod(float(t)**power for t,power in zip(vector,powers))
                    for powers,coefficient in row.items())/vector[i]**(self.rank-1)
                    for i,row in enumerate(self.rows)])
        for iteration in range(1,max_iterations+1):
            with np.errstate(over="raise",divide="raise",invalid="raise"):
                q=ratios(x); rho=float((q.max()+q.min())/2)
                residual=float(np.max(np.abs(q-rho))/max(1,abs(rho)))
                if residual<=tolerance: break
                x*=(q+1)**(1/(self.rank-1)); x/=x.sum()
        else: raise ArithmeticError("Orbit quotient iteration did not converge")
        membership={v:i for i,block in enumerate(self.blocks) for v in block}
        expanded=np.array([x[membership[v]] for v in self.original.Vertices]); expanded/=expanded.sum()
        h=self.original
        degrees=h.incidence_matrix()@h.weights if h.vertex_degrees is None else h.vertex_degrees
        actual=[]
        for i,v in enumerate(h.Vertices):
            adjacency=sum(float(w)*math.prod(expanded[h._index[u]] for u in e if u!=v)
                          for e,w in zip(h.Edges,h.weights) if v in e)
            actual.append(alpha*degrees[i]+(1-alpha)*adjacency/expanded[i]**(self.rank-1))
        checked=max(abs(t-rho) for t in actual)/max(1,abs(rho))
        if checked>max(1e-13,tolerance*1.01): raise ArithmeticError("Expanded quotient vector failed original tensor equations")
        return {"rho":rho,"perron_vector":x.tolist(),"expanded_perron_vector":expanded.tolist(),
                "relative_residual":float(checked),"collatz_lower":float(min(actual)),"collatz_upper":float(max(actual)),
                "vertex_orbits":self.blocks,"quotient_terms":self.terms(),"alpha":alpha,
                "iterations":iteration,"quotient_type":"vertex_orbit_operator"}

    def Alpha_Spectral_Radius(self,alpha=0,**kwargs):
        result=self.alpha_spectrum(alpha,**kwargs)
        return result["rho"],np.asarray(result["perron_vector"])


def Quotient_Graph(h,blocks=None):
    """Spectrally faithful vertex-orbit operator; no simple-hypergraph claim."""
    return OrbitQuotient(h,blocks)

__all__ = ['edge_representative_quotient', 'OrbitQuotient', 'Quotient_Graph']
