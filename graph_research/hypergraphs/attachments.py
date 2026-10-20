"""Shared-root hyperedge stars, distinct from a chain of pendant edges."""
from .model import Hypergraph


def add_star(h,R,s,rank=None):
    """Return a copy with s new hyperedges sharing exactly the supplied roots.

    Original edge weights and isolated vertices are preserved. New edges have
    unit weights. Default rank is the original maximum edge size. Custom
    independent diagonal degrees require a separate explicit update first.
    """
    roots=list(R) if isinstance(R,(tuple,list,set,frozenset)) else [R]
    if len(set(roots))!=len(roots) or not set(roots)<=set(h.Vertices):raise ValueError('根集须为不同的已有顶点。')
    if type(s) is not int or not 0<=s<=4096:raise ValueError('附接边数须为0..4096。')
    if s==0:return h.copy()
    k=h.rank if rank is None else max(h.rank,rank)
    if type(k) is not int or k<2 or len(roots)>=k:raise ValueError('根集大小须小于目标边大小，目标边大小至少为2。')
    if h.vertex_degrees is not None:raise ValueError('附接前需明确重新指定独立D对角；此接口不静默丢弃已有对角。')
    vertices=list(h.Vertices);known=set(vertices);candidate=max([v for v in vertices if type(v) is int]+[-1])+1;edges=[]
    for _ in range(s):
        new=[]
        while len(new)<k-len(roots):
            if candidate not in known:new.append(candidate);known.add(candidate)
            candidate+=1
        vertices.extend(new);edges.append(roots+new)
    return Hypergraph([*h.hyperedges(),*edges],vertices=vertices,weights=[*h.weights,*([1]*s)])


def add_stars(h,rootsk,rank=None):
    """Apply a roots->count mapping or a sequence of (roots,count) records."""
    records=list(rootsk.items()) if isinstance(rootsk,dict) else list(rootsk)
    result=h.copy()
    for roots,count in records:result=add_star(result,roots,count,rank)
    return result
