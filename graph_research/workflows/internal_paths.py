"""Explicit or unambiguous incidence paths, with documented internal-loose-path checks."""
import networkx as nx
from graph_research.hypergraphs import Hypergraph


def hypergraph_path_analysis(edges,start,end,edge_indices=None,weights=None,weighted_incidence=False,alpha=0):
    h=Hypergraph(edges,weights=weights)
    if h.order()>128 or h.size()>128:raise ValueError('路径分析至多128顶点/128超边。')
    if start==end or start not in h.Vertices or end not in h.Vertices:raise ValueError('起终点须为不同的已有顶点。')
    if edge_indices is None:
        incidence=h.incidence_graph();a,b=('v',start),('v',end)
        if not nx.has_path(incidence,a,b):raise ValueError('起终点不连通。')
        path=nx.shortest_path(incidence,a,b);bridges={frozenset(edge) for edge in nx.bridges(incidence)}
        if any(frozenset((u,v)) not in bridges for u,v in zip(path,path[1:])):
            raise ValueError('起终点间有路径歧义；请用edge_indices明确指定边序列。')
        chosen=[node[1] for node in path if node[0]=='e']
    else:chosen=list(edge_indices)
    if not chosen or len(chosen)>64 or any(type(i) is not int or not 0<=i<h.size() for i in chosen) or len(set(chosen))!=len(chosen):
        raise ValueError('edge_indices须为不重复的有效边序列，长度1..64。')
    route=[h.Edges[i] for i in chosen]
    if start not in route[0] or end not in route[-1]:raise ValueError('边序列未按起终点方向排列。')
    joints=[]
    for left,right in zip(route,route[1:]):
        intersection=set(left)&set(right)
        if len(intersection)!=1:raise ValueError('内部松路要求相邻边恰交一个顶点。')
        joints.append(next(iter(intersection)))
    for i,edge in enumerate(route):
        if any(set(edge)&set(other) for other in route[i+2:]):raise ValueError('内部松路的非相邻边不能相交。')
    spine=[start,*joints,end]
    if len(set(spine))!=len(spine):raise ValueError('路径主干顶点不能重复。')
    if any(start in edge for edge in route[1:]) or any(end in edge for edge in route[:-1]):raise ValueError('端点同时出现在其他路径边中。')
    private=set(v for edge in route for v in edge)-set(spine)
    violations=[{'vertex':v,'ambient_degree':h.degree(v),'expected_degree':2} for v in joints if h.degree(v)!=2]
    violations += [{'vertex':v,'ambient_degree':h.degree(v),'expected_degree':1} for v in h.Vertices if v in private and h.degree(v)!=1]
    rows=[h.Vertices.index(v) for v in spine];matrix=h.incidence_matrix()
    result={'status':'internal_loose_path' if not violations else 'path_with_side_branches',
            'internal_loose_path':not violations,'spine_vertices':spine,'edge_indices':chosen,'path_edges':[list(edge) for edge in route],
            'incidence_submatrix':matrix[rows][:,chosen].tolist(),'violations':violations,
            'interpretation':'行按起点、内部交点、终点排序，列按有向边序列；内部交点全图度为2，私有点全图度为1。'}
    if weighted_incidence:
        spectrum=h.alpha_spectrum(alpha);b=h.weighted_incidence_from_result(spectrum)
        result.update(weighted_incidence_submatrix=b[rows][:,chosen].tolist(),rho=spectrum['rho'],relative_residual=spectrum['relative_residual'],
                      normalization='submatrix of the ORIGINAL whole-hypergraph Perron weighted incidence; not renormalized on the path')
    return result
