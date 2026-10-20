"""Reviewed NetworkX operations with explicit label and simple-graph semantics."""
import math
import numbers
import networkx as nx


def _simple(graph):
    if graph.is_directed() or graph.is_multigraph() or nx.number_of_selfloops(graph):
        raise ValueError('需要无自环、无重边的无向简单图。')


def BaseGraph(graph):
    """Return the 2-core, including correct empty/isolated-vertex handling.

    This implements leaf/isolate pruning, rather than preserving the old
    routine's early stop when an isolated vertex happened to be present.
    """
    _simple(graph)
    return nx.k_core(graph,k=2)


def Relabel(H,L=None,inv=False):
    """Return a relabeled copy. Lists order old vertices; dicts map old to new.

    Unlisted vertices follow in insertion order. A dict may be partial but
    cannot merge vertices; complete the permutation explicitly if necessary.
    Input mappings and graph attributes are never modified.
    """
    nodes=list(H)
    if isinstance(L,dict):
        if not set(L)<=set(nodes):raise ValueError('重编号映射包含不存在的顶点。')
        mapping=dict(L)
    else:
        if L is None:
            try:order=sorted(nodes)
            except TypeError:order=nodes
        else:order=list(L)
        if len(set(order))!=len(order) or not set(order)<=set(nodes):raise ValueError('顶点顺序不能重复或包含未知顶点。')
        order=order+[v for v in nodes if v not in order]
        mapping=dict(zip(order,reversed(range(len(nodes))) if inv else range(len(nodes))))
    labels=[mapping.get(v,v) for v in nodes]
    if len(set(labels))!=len(nodes):raise ValueError('重编号不能合并顶点；请提供不冲突的完整映射。')
    return nx.relabel_nodes(H,mapping,copy=True)


def sorted_label(H,v,rev=False):
    """Relabel by finite real vector values in node order, preserving ties stably."""
    nodes=list(H);values=list(v)
    if len(values)!=len(nodes) or any(isinstance(x,bool) or not isinstance(x,numbers.Real) or not math.isfinite(float(x)) for x in values):
        raise ValueError('每个顶点需要一个有限实数，向量顺序须与顶点顺序相同。')
    order=sorted(range(len(nodes)),key=lambda i:float(values[i]),reverse=rev)
    return Relabel(H,[nodes[i] for i in order])


def generalized_line_graph(graph):
    """Old GF(2) incidence formula equals the ordinary line graph for simple graphs.

    This is not a generalized-line-graph recognition algorithm.
    """
    _simple(graph)
    return nx.line_graph(graph)


def subdivide_edges(graph,edges=None,count=1):
    """Insert count new vertices per selected edge; preserve all original nodes."""
    _simple(graph)
    if type(count) is not int or count<0:raise ValueError('每条边插入的顶点数必须是非负整数。')
    selected=list(graph.edges) if edges is None else [tuple(e) for e in edges]
    if any(len(e)!=2 or not graph.has_edge(*e) for e in selected) or len({frozenset(e) for e in selected})!=len(selected):
        raise ValueError('剖分边必须存在且不能重复。')
    result=graph.copy();label=max([v for v in graph if type(v) is int]+[-1])+1
    if not count:return result
    for u,v in selected:
        attributes=dict(result[u][v]);result.remove_edge(u,v);previous=u
        for _ in range(count):
            while label in result:label+=1
            result.add_edge(previous,label,**attributes);previous=label;label+=1
        result.add_edge(previous,v,**attributes)
    return result
