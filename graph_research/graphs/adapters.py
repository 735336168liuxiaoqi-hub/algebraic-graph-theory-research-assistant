"""Reviewed NetworkX replacements for remaining ordinary-graph helpers.

Functions return copies unless an explicit copy=False is provided. Weighted
matrices here are separate from the existing unweighted graph-spectrum tools.
"""
from collections import defaultdict
import math
import numbers
import networkx as nx
import numpy as np


def _graph(g):
    if not isinstance(g,nx.Graph) or g.is_multigraph() or nx.number_of_selfloops(g):
        raise ValueError('需要无重边、无自环的NetworkX图。')


def _fresh(g,count):
    value=max([v for v in g if type(v) is int]+[-1])+1;result=[]
    while len(result)<count:
        if value not in g:result.append(value)
        value+=1
    return result


def _weight(value):
    if isinstance(value,bool) or not isinstance(value,numbers.Number):raise ValueError('边权须为有限数。')
    converted=complex(value)
    if not math.isfinite(converted.real) or not math.isfinite(converted.imag):raise ValueError('边权须为有限数。')
    return value


def set_edge_weight(g,edges_weights=None,default_weight=1,*,copy=True):
    """Assign edge->weight or weight->[edges]; fill missing weights only.

    Validate every update before changing anything. Unlike the Sage method,
    the default is a copy; copy=False explicitly requests in-place changes.
    """
    _graph(g);_weight(default_weight);updates={}
    for key,value in dict(edges_weights or {}).items():
        pairs=[(key,value)] if isinstance(key,tuple) and len(key)==2 else [(tuple(edge),key) for edge in value]
        for edge,weight in pairs:
            if len(edge)!=2 or not g.has_edge(*edge):raise ValueError('赋权边不存在。')
            updates[edge]=_weight(weight)
    effective={(u,v):default_weight if data.get('weight') is None else data['weight'] for u,v,data in g.edges(data=True)}
    for edge,value in updates.items():
        key=edge if edge in effective else edge[::-1];effective[key]=value
    for value in effective.values():_weight(value)
    result=g.copy() if copy else g
    nx.set_edge_attributes(result,effective,'weight')
    return result


def weight_edges(g,weights=None):
    """Return a weighted adjacency ndarray; never modify the input graph."""
    result=set_edge_weight(g,weights)
    dtype=complex if any(complex(data['weight']).imag for _,_,data in result.edges(data=True)) else float
    return nx.to_numpy_array(result,nodelist=list(result),weight='weight',dtype=dtype)


def complex_weight(g,edges):
    """Hermitian adjacency: selected orientations get i and reverse gets -i.

    Requires an undirected graph. Use a directed COPY internally because a
    single undirected edge attribute cannot hold two opposite complex weights.
    """
    _graph(g)
    if g.is_directed():raise ValueError('此适配接口需要无向图及指定的边方向。')
    chosen=[tuple(edge) for edge in edges]
    if any(len(e)!=2 or not g.has_edge(*e) for e in chosen) or len({frozenset(e) for e in chosen})!=len(chosen):
        raise ValueError('方向边须存在，每条无向边只能指定一个方向。')
    result=set_edge_weight(g).to_directed()
    for u,v in chosen:result[u][v]['weight']=1j;result[v][u]['weight']=-1j
    matrix=nx.to_numpy_array(result,nodelist=list(g),weight='weight',dtype=complex)
    if not np.allclose(matrix,matrix.conj().T):raise ValueError('未定向边的原权重须为实数，结果必须为厄米矩阵。')
    return matrix


def replace_edges_by_graph(g,graphs,edges,endpoints,relabel=False):
    """Replace edges by rooted graphs, preserving isolates and attributes.

    Fresh integer labels isolate every replacement's internal vertices. Root
    node attributes remain those of the original graph, not the replacement.
    """
    _graph(g);replacements=list(graphs);selected=[tuple(e) for e in edges];roots=[tuple(pair) for pair in endpoints]
    if len(replacements)!=len(selected) or len(roots)!=len(selected):raise ValueError('替换图、边和端点对应表须等长。')
    if any(len(e)!=2 or not g.has_edge(*e) for e in selected) or len({frozenset(e) if not g.is_directed() else e for e in selected})!=len(selected):
        raise ValueError('替换边须存在且不能重复。')
    for h,pair in zip(replacements,roots):
        _graph(h)
        if h.is_directed()!=g.is_directed() or len(pair)!=2 or pair[0]==pair[1] or not set(pair)<=set(h):
            raise ValueError('替换图方向须一致，并提供两个不同的已有端点。')
    result=g.copy();result.remove_edges_from(selected)
    for h,(u,v),pair in zip(replacements,selected,roots):
        internal=[node for node in h if node not in pair];mapping=dict(zip(internal,_fresh(result,len(internal))))
        mapping.update(zip(pair,(u,v)))
        for node in internal:result.add_node(mapping[node],**dict(h.nodes[node]))
        result.add_edges_from((mapping[a],mapping[b],dict(data)) for a,b,data in h.edges(data=True))
    return nx.convert_node_labels_to_integers(result) if relabel else result


def edge2graph(g,e,v1,v2,h):
    """Replace one edge by h, identifying h's roots v1/v2 with its endpoints."""
    return replace_edges_by_graph(g,[h],[e],[(v1,v2)])


def PartProduct(g,selected,h,prod=None):
    """Take the graph product on the selected induced subgraph and reconnect."""
    _graph(g);_graph(h);chosen=set(selected)
    if not chosen<=set(g) or g.is_directed() or h.is_directed():raise ValueError('局部图积需要已有顶点和无向简单图。')
    outside=set(g)-chosen;product=nx.cartesian_product if prod is None else prod;result=product(g.subgraph(chosen).copy(),h)
    if any(not isinstance(v,tuple) or len(v)!=2 or v[0] not in chosen for v in result):raise ValueError('图积的顶点须为(原选中顶点,另一个图顶点)。')
    if set(result)&outside:raise ValueError('图积顶点标签与外部顶点冲突；请先重编号。')
    for u,data in g.nodes(data=True):
        if u in outside:result.add_node(u,**dict(data))
    result.add_edges_from((u,v,dict(data)) for u,v,data in g.edges(data=True) if u in outside and v in outside)
    for product_vertex in list(result):
        if product_vertex in outside:continue
        u=product_vertex[0]
        for v in g[u]:
            if v in outside:result.add_edge(product_vertex,v,**dict(g[u][v]))
    result.graph.update(g.graph)
    return result


def pick_vertices(g,*args):
    """Group vertices by increasing degree; optional k selects kth degree group."""
    groups=defaultdict(list)
    for node,degree in g.degree():groups[degree].append(node)
    result=dict(sorted(groups.items()))
    if not args:return result
    if len(args)!=1 or type(args[0]) is not int:raise ValueError('最多提供一个整数度序号。')
    keys=list(result)
    try:key=keys[args[0]]
    except IndexError:raise ValueError('度序号超出范围。') from None
    return key,result[key]


def list2dict(records):
    """Group pairs by their first member, preserving input order."""
    result={}
    for key,value in records:result.setdefault(key,[]).append(value)
    return result


def Index(edges):
    """Return explicitly stored edge indices; does not infer NetworkX edge IDs."""
    return [edge.index for edge in edges]


def Cycle(vertices):
    """Construct a simple cycle in the supplied vertex order, length at least 3."""
    nodes=list(vertices)
    if len(nodes)<3 or len(set(nodes))!=len(nodes):raise ValueError('简单圈至少需要3个不同顶点。')
    graph=nx.Graph();nx.add_cycle(graph,nodes);return graph


def mygraphmul(g,*args):
    """Positive integer -> disjoint copies; graph arguments -> Cartesian products."""
    _graph(g)
    if len(args)==1 and type(args[0]) is int:
        if args[0]<1:raise ValueError('复制次数须为正整数。')
        return g.copy() if args[0]==1 else nx.disjoint_union_all([g]*args[0])
    if not args:raise ValueError('需要复制次数或另一个图。')
    result=g.copy()
    for other in args:
        _graph(other);result=nx.cartesian_product(result,other)
    return result


def mygraphsub(g,h):
    """Delete h's edges from a copy of g, retaining every original vertex."""
    result=g.copy();result.remove_edges_from(h.edges());return result


def random_symmetric_matrix(n,x=0,y=1,*,seed=None):
    """NumPy integer symmetric ndarray with inclusive integer bounds and local RNG."""
    if type(n) is not int or not 0<=n<=512 or type(x) is not int or type(y) is not int or not -(2**62)<=x<=y<2**62:
        raise ValueError('阶数须为0..512，整数上下界须有序且在支持范围内。')
    rng=np.random.default_rng(seed);a=rng.integers(x,y+1,size=(n,n),dtype=np.int64)
    lower=np.tril(a);return lower+np.tril(a,-1).T


def AMdb(g):
    """Adjacency weights 1/d(u)+1/d(v); isolates contribute zero rows/columns."""
    _graph(g)
    if g.is_directed():raise ValueError('需要无向图。')
    nodes=list(g);index={v:i for i,v in enumerate(nodes)};matrix=np.zeros((len(g),len(g)))
    for u,v in g.edges():matrix[index[u],index[v]]=matrix[index[v],index[u]]=1/g.degree(u)+1/g.degree(v)
    return matrix


def checksign1(polynomial):
    """Signs of nonzero polynomial coefficients; symbolic signs stay symbolic."""
    from graph_research._lazy import sympy as sp
    value=polynomial if isinstance(polynomial,sp.Poly) else sp.Poly(polynomial)
    return {sp.sign(coefficient) for coefficient in value.coeffs() if coefficient!=0}


def polynomials_for_addstarsgraph(g,D,type='L'):
    """Schur expression after attaching D[v] unit-weight leaves at each v.

    Supports L and Q of an unweighted undirected simple graph, at most twelve
    original vertices. Counts may be nonnegative integer SymPy symbols other
    than x; numeric counts total at most 256.
    Returns a SymPy expression, not a claim that symbolic counts fix a degree.
    The old A branch used the wrong leaf diagonal and is rejected explicitly.
    """
    from graph_research._lazy import sympy as sp
    from .matrices import exact_graph_matrix
    _graph(g)
    if g.is_directed() or type not in ('L','Q') or len(g)>12:raise ValueError('此Schur表达式支持至多12原顶点的无向L/Q。')
    if any(data.get('weight',1)!=1 for _,_,data in g.edges(data=True)):raise ValueError('需要无权原图。')
    values=dict(D)
    if not set(values)<=set(g):raise ValueError('附叶顶点不存在。')
    counts={}
    for node,value in values.items():
        if isinstance(value,bool):raise ValueError('附叶数须为非负整数或具有相应假设的符号。')
        expression=sp.Integer(value) if isinstance(value,numbers.Integral) else value
        if not isinstance(expression,sp.Expr) or expression.is_integer is not True or expression.is_nonnegative is not True:
            raise ValueError('附叶数须为非负整数或具有相应假设的符号。')
        if any(str(symbol)=='x' for symbol in expression.free_symbols):raise ValueError('附叶参数不能与特征变量x同名。')
        counts[node]=expression
    x=sp.Symbol('x');diagonal=sp.diag(*[counts.get(v,0) for v in g]);total=sum(counts.values(),sp.S.Zero)
    if total.is_Integer and total>256:raise ValueError('数值附叶总数至多256；大规模请使用不展开的符号计数。')
    core=x*sp.eye(len(g))-exact_graph_matrix(g,type)-(1+1/(x-1))*diagonal
    return sp.factor(sp.cancel(core.det()*(x-1)**total))
