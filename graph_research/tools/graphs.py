"""JSON-facing graph calculations for model tool calls."""
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp
import graph_research.graphs as graphs
import graph_research.hypergraphs as hg


def _spec(graph):
    graph=nx.convert_node_labels_to_integers(graph)
    return {"kind":"edges","n":len(graph),"edges":[list(e) for e in graph.edges]}


def graph_construction(family,lengths=None,n=5,k=2,q=2,attachments=None,seed=42):
    lengths=lengths or [2,2,2]
    if sum(lengths)>128: raise ValueError("Total path/cycle lengths exceed128")
    if family=="theta": graph=graphs.theta_graph(lengths)
    elif family=="caterpillar":
        attachments=attachments or []
        if len(attachments)>64 or any(len(pair)!=2 or type(pair[0]) is not int or type(pair[1]) is not int or not 0<=pair[0]<=n or pair[1]<0 for pair in attachments):
            raise ValueError("Attachments must be valid spine vertices and nonnegative leaf counts")
        if n+1+sum(pair[1] for pair in attachments)>128: raise ValueError("Constructed graph exceeds128 vertices")
        graph=graphs.caterpillar(n,attachments)
    elif family=="cactus": graph=graphs.RandomCactusGraph(lengths,seed)
    elif family=="hamming":
        if q**k>128: raise ValueError("Hamming graph order exceeds128")
        graph=graphs.HammingGraph(k,q)
    elif family=="random_k_cyclic": graph=graphs.RandomKCyclicGraph(n,k,seed)
    else: raise ValueError("Unknown graph family")
    if len(graph)>128: raise ValueError("Constructed graph exceeds128 vertices")
    return {"graph":_spec(graph),"order":len(graph),"size":graph.number_of_edges()}


def graph_symmetry(kind="path",n=5,edges=None,matrix="A",alpha=0):
    if n>24: raise ValueError("Model symmetry tool limited to24 vertices")
    graph=graphs.make_graph(kind,n,edges)
    result=graphs.equitable_quotient(graph,matrix=matrix,alpha=alpha)
    return {**result,"quotient_spectrum":np.linalg.eigvals(result["quotient"])}


def graph_spectral_analysis(operation,kind="path",n=5,edges=None,alpha=0,symbolic_alpha=False):
    graph=graphs.make_graph(kind,n,edges)
    if operation=="energy": return {"energy":graphs.Energy(graph),"estrada_index":graphs.estrada_index(graph)}
    if operation=="angles":
        values,angles=graphs.angle(graph); return {"distinct_eigenvalues":values,"angles":angles}
    if operation=="projectors": return {"decomposition":graphs.spectral_projectors(graph)}
    if operation=="alpha_charpoly":
        if n>12: raise ValueError("Symbolic alpha polynomial limited to12 vertices")
        polynomial=graphs.exact_characteristic_polynomial(graph,"alpha",sp.Symbol("alpha") if symbolic_alpha else sp.Rational(str(alpha)))
        return {"polynomial":str(polynomial.as_expr()),"arithmetic":"exact"}
    raise ValueError("Unknown spectral analysis")


def compare_graphs(left,right,operation="isomorphic"):
    g,h=graphs.make_graph(**left),graphs.make_graph(**right)
    if operation=="isomorphic": return {"isomorphic":nx.is_isomorphic(g,h)}
    if operation=="cospectral":
        if max(len(g),len(h))>24: raise ValueError("Exact comparison limited to24 vertices")
        return {"cospectral":graphs.exact_characteristic_polynomial(g)==graphs.exact_characteristic_polynomial(h)}
    if operation=="subgraph_count":
        if len(g)>24 or len(h)>8: raise ValueError("Count tool supports host<=24 and pattern<=8 vertices")
        return {"non_induced_copies":graphs.Count_Subgraph(g,h)}
    raise ValueError("Unknown graph comparison")


def graph_enumeration(operation,kind="path",n=5,edges=None,start=0,end=1,length=3,degrees=None,limit=1000):
    if operation=="degree_realizations":
        result=graphs.Graphs_WithDegreeSequence(degrees or [],max_graphs=limit,max_states=100000)
        return {"graphs":[_spec(g) for g in result],"count":len(result),"isomorphism_deduplicated":True}
    graph=graphs.make_graph(kind,n,edges)
    if n>16: raise ValueError("Cycle/path enumeration tool limited to16 vertices")
    if operation=="cycles": result=graphs.findCycles(graph,length,max_cycles=limit)
    elif operation=="paths": result=graphs.All_Paths(graph,start,end,length,max_paths=limit)
    elif operation=="hamilton": result=graphs.Find_all_hamiltonian_cycles(graph,max_cycles=limit,max_states=100000)
    else: raise ValueError("Unknown graph enumeration")
    return {"results":result,"count":len(result)}


def hypergraph_structure(edges,operation="incidence",alpha=0):
    """JSON结构/方程分支；完整参数与返回契约见tool_docs.json。

    incidence/distances/line_graph/orbits允许非一致；distances需连通。
    equations与matching_poly需一致，且前者只返回方程、后者不是张量
    特征多项式。多分支的模型说明统一由registry生成，避免两份说明漂移。
    """
    graph=hg.Hypergraph(edges)
    if operation=="incidence": return {"vertices":graph.vertices(),"edges":[list(e) for e in graph.Edges],"incidence":graph.incidence_matrix(),"degrees":graph.degree_sequence(),"cycle_rank":hg.CyclomaticNumber(graph)}
    if operation=="distances": return {"vertices":graph.vertices(),"distances":graph.distance_matrix()}
    if operation=="line_graph":
        line=hg.WeightedLineGraph(graph)
        return {"nodes":list(line),"weighted_edges":[[u,v,d["weight"]] for u,v,d in line.edges(data=True)]}
    if operation=="orbits":
        if graph.order()>24: raise ValueError("Symmetry tool limited to24 vertices")
        return {"vertex_orbits":graph.orbit_subdivision()}
    if operation=="equations": return {"alpha_equations":[str(e) for e in graph.alpha_eigen_equations(sp.Rational(str(alpha)))],"variables":[f"x{i}" for i in range(graph.order())]}
    if operation=='laplacian_equations':return {'laplacian_equations':[str(eq) for eq in graph.eigenVfun()], 'variables':[f'x{i}' for i in range(graph.order())]}
    if operation=="matching_poly":
        return {"matching_polynomial":str(hg.Matching_Polynomial(graph,sp.Rational(str(alpha))).as_expr()),"note":"Matching polynomial is not the general tensor characteristic polynomial"}
    raise ValueError("Unknown hypergraph calculation")


def hypergraph_transform(edges,operation,vertex=0,count=1,rank=3,edge_index=0,groups=None,vertices=None,roots=None):
    graph=hg.Hypergraph(edges)
    if count*max(1,graph.size())*rank>256: raise ValueError("Transformation expansion exceeds tool budget")
    if operation=="attach_path": result=hg.add_path(graph,vertex,count,rank)
    elif operation=='attach_star':
        chosen=[vertex] if roots is None else roots;k=max(graph.rank,rank)
        if graph.order()+count*max(0,k-len(chosen))>128 or graph.size()+count>128:raise ValueError('附星结果超过128顶点/128边。')
        result=hg.add_star(graph,chosen,count,rank=rank)
    elif operation=="expand_edges": result=hg.blowup_edge(graph,count)
    elif operation=="clone_all": result=hg.blowup_vertex(graph,{vertex:count})
    elif operation=="clone_cartesian": result=hg.Blow_Up(graph,{vertex:count},relabel=True)
    elif operation=="merge": result=hg.merge_vertices(graph,groups or [],relabel=True)
    elif operation=="subdivide": result=hg.subdivide_edge(graph,graph.Edges[edge_index],count)
    elif operation=="induced": result=graph.induced_subgraph(vertices or [])
    else: raise ValueError("Unknown hypergraph transformation")
    return {"edges":[list(e) for e in result.Edges],"vertices":result.vertices(),"order":result.order(),"size":result.size(),"rank":result.rank,"uniform":result.is_uniform()}


def hypergraph_quotient_spectrum(edges,alpha=0):
    graph=hg.Hypergraph(edges)
    if graph.order()>24 or graph.size()>16: raise ValueError("Orbit quotient tool limited to24 vertices and16 edges")
    quotient=hg.Quotient_Graph(graph)
    original=graph.alpha_spectrum(alpha); reduced=quotient.alpha_spectrum(alpha)
    return {"original_rho":original["rho"],"quotient_rho":reduced["rho"],
            "absolute_difference":abs(original["rho"]-reduced["rho"]),
            "vertex_orbits":quotient.blocks,"quotient_terms":quotient.terms(),"quotient_type":"vertex_orbit_operator",
            "diagonal_degrees":quotient.vertex_degrees,"original_residual":original["relative_residual"],
            "quotient_residual":reduced["relative_residual"]}


def directed_graph_spectrum(n,arcs,matrix="H",alpha=0):
    if any(len(e)!=2 or any(type(v) is not int or not 0<=v<n for v in e) or e[0]==e[1] for e in arcs):
        raise ValueError("Loopless arcs with vertices in range(n) required")
    graph=nx.DiGraph(); graph.add_nodes_from(range(n)); graph.add_edges_from(arcs)
    a=graphs.get_Matrix(graph,alpha if matrix=="alpha" else matrix)
    values,vectors=np.linalg.eig(a); index=int(np.argmax(np.abs(values)))
    value=values[index]; vector=vectors[:,index]
    return {"nodes":list(graph),"matrix":a,"spectrum":values,"rho":float(abs(value)),
            "dominant_eigenvalue":value,"relative_residual":float(np.linalg.norm(a@vector-value*vector)/max(1,abs(value)))}


def extra_tool_definitions(graph_args,edges,obj):
    number={"type":"number","minimum":0,"exclusiveMaximum":1}
    integers={"type":"array","items":{"type":"integer","minimum":1,"maximum":32},"minItems":1,"maxItems":16}
    spec=obj(graph_args)
    return [
        ("graph_construction","构造theta图、毛毛虫、仙人掌、Hamming图或给定圈秩随机图。",graph_construction,obj({"family":{"enum":["theta","caterpillar","cactus","hamming","random_k_cyclic"]},"lengths":integers,"n":{"type":"integer","minimum":1,"maximum":64},"k":{"type":"integer","minimum":0,"maximum":16},"q":{"type":"integer","minimum":1,"maximum":8},"attachments":{"type":"array","items":{"type":"array","items":{"type":"integer"},"minItems":2,"maxItems":2}},"seed":{"type":"integer","minimum":0}},["family"])),
        ("graph_symmetry","计算顶点自同构轨道、对应平均商矩阵，并检查等价划分。",graph_symmetry,obj({**graph_args,"matrix":{"enum":["A","L","Q","alpha","D"]},"alpha":number})),
        ("graph_spectral_analysis","计算能量、谱投影、图角或精确含符号alpha的特征多项式。",graph_spectral_analysis,obj({**graph_args,"operation":{"enum":["energy","angles","projectors","alpha_charpoly"]},"alpha":number,"symbolic_alpha":{"type":"boolean"}},["operation"])),
        ("compare_graphs","判断同构/同谱或计算非诱导子图份数。left为宿主，right为模式。",compare_graphs,obj({"left":spec,"right":spec,"operation":{"enum":["isomorphic","cospectral","subgraph_count"]}},["left","right"])),
        ("graph_enumeration","有预算地枚举指定长度路/圈、Hamilton圈或给定度序列的非同构实现。",graph_enumeration,obj({**graph_args,"operation":{"enum":["cycles","paths","hamilton","degree_realizations"]},"start":{"type":"integer"},"end":{"type":"integer"},"length":{"type":"integer","minimum":1,"maximum":16},"degrees":{"type":"array","items":{"type":"integer","minimum":0,"maximum":8},"maxItems":9},"limit":{"type":"integer","minimum":1,"maximum":1000}},["operation"])),
        ("hypergraph_structure","超图关联/距离/线图/轨道/特征方程/匹配多项式计算。匹配多项式不是一般张量特征多项式。",hypergraph_structure,obj({"edges":edges,"operation":{"enum":["incidence","distances","line_graph","orbits","equations","matching_poly","laplacian_equations"]},"alpha":number},["edges"])),
        ("hypergraph_transform","添加悬挂路、扩边、两种顶点克隆、合并、剖分或取诱导子超图。",hypergraph_transform,obj({"edges":edges,"operation":{"enum":["attach_path","expand_edges","clone_all","clone_cartesian","merge","subdivide","induced","attach_star"]},"vertex":{"type":"integer"},"count":{"type":"integer","minimum":1,"maximum":16},"rank":{"type":"integer","minimum":2,"maximum":8},"edge_index":{"type":"integer","minimum":0},"groups":{"type":"array","items":{"type":"array","items":{"type":"integer"}}},"vertices":{"type":"array","items":{"type":"integer"}},"roots":{"type":"array","minItems":1,"maxItems":8,"uniqueItems":True,"items":{"type":"integer"}}},["edges","operation"])),
        ("hypergraph_quotient_spectrum","构造保留特征方程的顶点轨道商算子，将约化向量展开回原图检查，并比较alpha谱半径。商算子不是普通简单超图。",hypergraph_quotient_spectrum,obj({"edges":edges,"alpha":number},["edges"]))
        ,("directed_graph_spectrum","有向简单图的Hermitian邻接矩阵、普通邻接/出度L/alpha矩阵与复数谱。",directed_graph_spectrum,obj({"n":{"type":"integer","minimum":1,"maximum":64},"arcs":{"type":"array","items":{"type":"array","items":{"type":"integer"},"minItems":2,"maxItems":2},"maxItems":1024},"matrix":{"enum":["H","A","L","alpha"]},"alpha":number},["n","arcs"]))
    ]
