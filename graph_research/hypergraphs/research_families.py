"""Research families composed from existing loose paths/cycles and attachments.

All constructors preserve the requested rank. Endpoints are selected by
incidence/degree, not brittle historic vertex numbers. No new spectral
algorithm or automatically generated extension is installed.
"""
from .families import HyperPath,HyperCycle
from .operations import add_paths
import math
import numbers


def _lengths(values):
    result=[values] if type(values) is int else list(values or [])
    if len(result)>8 or any(isinstance(value,bool) or not isinstance(value,numbers.Real) or not 0<=value<=32 or not math.isfinite(value) or value!=int(value) for value in result):
        raise ValueError('每组至多8条悬挂路，长度须为0..32的整数边数。')
    return [int(value) for value in result]


def _ends(m,k):
    graph=HyperPath(m,k)
    left=[v for v in graph.Edges[0] if graph.degree(v)==1]
    right=[v for v in graph.Edges[-1] if graph.degree(v)==1]
    return graph,left,right


def Gee(m,left_lengths,right_lengths,k=3):
    """Attach one path at each selected leaf on both ends of a loose path."""
    left,right=_lengths(left_lengths),_lengths(right_lengths);graph,lroots,rroots=_ends(m,k)
    if m==1:
        if len(left)+len(right)>k:raise ValueError('单边主干没有足够的不同根点；不会自动增大k。')
        rroots=list(reversed(rroots[len(left):]))
    if len(left)>len(lroots) or len(right)>len(rroots):raise ValueError('端边上的悬挂根点数量不足。')
    return add_paths(graph,{**dict(zip(lroots,left)),**dict(zip(rroots,right))},rank=k)


def Gev(m,left_lengths,right_lengths,k=3):
    """Left paths have separate roots; all right paths share one other end leaf."""
    left,right=_lengths(left_lengths),_lengths(right_lengths);graph,lroots,rroots=_ends(m,k)
    if len(left)>len(lroots):raise ValueError('左端边没有足够的悬挂根点。')
    if m==1:rroots=list(reversed(rroots[len(left):]))
    if right and not rroots:raise ValueError('左右附接需要不同根点。')
    attachments=dict(zip(lroots,left))
    if right:attachments[rroots[-1] if m>1 else rroots[0]]=right
    return add_paths(graph,attachments,rank=k)


def Gvv(m,VL,VR,k=3):
    """All left paths share a leaf; all right paths share a different end leaf."""
    left,right=_lengths(VL),_lengths(VR);graph,lroots,rroots=_ends(m,k)
    return add_paths(graph,{lroots[0]:left,rroots[-1]:right},rank=k)


def GWG(m,De=None,Dv=None,k=3):
    """Attach at degree-1 leaves of indexed edges and at named shared vertices.

    De maps zero-based spine edge indices to path lengths at separate leaves;
    Dv maps existing degree>1 spine vertices to lengths sharing that root.
    Inputs are copied. Rank is never silently increased, including m=1.
    """
    graph=HyperPath(m,k);attachments={}
    for index,values in dict(De or {}).items():
        if type(index) is not int or not 0<=index<m:raise ValueError('主干边序号超出范围。')
        lengths=_lengths(values);roots=[v for v in graph.Edges[index] if graph.degree(v)==1]
        if len(lengths)>len(roots):raise ValueError('该主干边的悬挂根点不足；不会自动改变一致度。')
        attachments.update(zip(roots,lengths))
    for vertex,values in dict(Dv or {}).items():
        if vertex not in graph.Vertices or graph.degree(vertex)<=1:raise ValueError('vertex_paths须选择主干上度大于1的共享顶点。')
        attachments[vertex]=_lengths(values)
    return add_paths(graph,attachments,rank=k)


def Ca(m,a=1,k=3):
    """Loose cycle with a pendant path at a degree-1 vertex; requires k>=3."""
    if type(a) is not int or not 0<=a<=32:raise ValueError('悬挂路长度须为0..32的整数。')
    graph=HyperCycle(m,k);roots=[v for v in graph.Edges[-1] if graph.degree(v)==1]
    if not roots:raise ValueError('Ca需要存在1度点，普通二元圈请使用Cva。')
    return add_paths(graph,{roots[-1]:a},rank=k)


def Cva(m,a=1,k=3):
    """Loose cycle with a pendant path at a degree-2 intersection vertex."""
    if type(a) is not int or not 0<=a<=32:raise ValueError('悬挂路长度须为0..32的整数。')
    graph=HyperCycle(m,k);root=next(v for v in graph.Vertices if graph.degree(v)==2)
    return add_paths(graph,{root:a},rank=k)


def research_family(family,m=3,k=3,left_lengths=None,right_lengths=None,pendant_length=1,edge_paths=None,vertex_paths=None):
    """JSON adapter for the six constructors; bound output before allocation."""
    m,k=int(m),int(k)
    left,right=_lengths(left_lengths),_lengths(right_lengths)
    if family in ('gee','gev','gvv'):extra=sum(left)+sum(right)
    elif family in ('ca','cva'):extra=int(pendant_length)
    elif family=='gwg':extra=sum(sum(_lengths(record['lengths'])) for record in [*(edge_paths or []),*(vertex_paths or [])])
    else:raise ValueError('未知定制图族。')
    if (m+extra)*max(1,k-1)+(0 if family in ('ca','cva') else 1)>128 or m+extra>128:raise ValueError('构造结果超出128个顶点/128条边的工具预算。')
    if family=='gee':return Gee(m,left,right,k)
    if family=='gev':return Gev(m,left,right,k)
    if family=='gvv':return Gvv(m,left,right,k)
    if family=='ca':return Ca(m,int(pendant_length),k)
    if family=='cva':return Cva(m,int(pendant_length),k)
    def unique(records,key):
        result={}
        for record in records or []:
            value=int(record[key])
            if value in result:raise ValueError('附接记录的根/边序号不能重复。')
            result[value]=_lengths(record['lengths'])
        return result
    return GWG(m,unique(edge_paths,'edge_index'),unique(vertex_paths,'vertex'),k)
