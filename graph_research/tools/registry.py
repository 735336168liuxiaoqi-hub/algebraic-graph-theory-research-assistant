"""Typed, discoverable JSON tools. Only this catalog is exposed to models."""
import inspect
import json
import math
from dataclasses import dataclass
from fractions import Fraction

import jsonschema
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp

import graph_research.graphs as graphs
import graph_research.algebra.combinatorics as combinatorics
import graph_research.algebra.polynomials as polynomials
from graph_research.errors import TaskProtocolError
from graph_research.runtime.observability import measure
from graph_research.hypergraphs import Hypergraph, HyperPath, HyperStar, HyperCycle
from graph_research.tensors import Tensor


def json_value(value):
    if isinstance(value, np.ndarray): return json_value(value.tolist())
    if isinstance(value, np.generic): return json_value(value.item())
    # Gate on the object's own module first: a sympy object can only exist if
    # sympy is already loaded, so non-symbolic calls never pay the import.
    if type(value).__module__.split('.',1)[0]=='sympy':
        if isinstance(value, sp.MatrixBase): return [[str(x) for x in row] for row in value.tolist()]
        if isinstance(value, sp.Basic): return str(value)
    if isinstance(value, dict): return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [json_value(v) for v in value]
    if isinstance(value, complex): return {"real": value.real, "imag": value.imag}
    if isinstance(value, float) and not math.isfinite(value): raise ValueError("Nonfinite tool output")
    return value


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    function: object
    status: str = "native_tested"
    documentation: dict | None = None

    def definition(self, detail="full"):
        from graph_research.tools.contracts import tool_definition
        return tool_definition(self,detail)


def object_schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


INT = {"type": "integer"}
NUMBER = {"type": "number"}
NUMBERS = {"type": "array", "items": NUMBER, "maxItems": 256}
MATRIX = {"type": "array", "items": NUMBERS, "minItems": 1, "maxItems": 128}
EDGES = {"type": "array", "items": {"type": "array", "items": INT, "minItems": 2, "maxItems": 8}, "minItems": 1, "maxItems": 128}
GRAPH_ARGS = {"kind": {"enum": ["path", "cycle", "complete", "star", "empty", "edges"]},
              "n": {"type": "integer", "minimum": 1, "maximum": 128},
              "edges": {"type": "array", "items": {"type": "array", "items": INT, "minItems": 2, "maxItems": 2}, "maxItems": 1024}}


def generate_hypergraph(family, m=3, k=3, lengths=None,left_lengths=None,right_lengths=None,pendant_length=1,edge_paths=None,vertex_paths=None):
    import graph_research.hypergraphs as hg
    families = {"path": HyperPath, "star": HyperStar, "cycle": HyperCycle}
    if family in families: graph = families[family](m, k)
    elif family=="vertex_starlike": graph=hg.VStarLike(*(lengths or [1,1,1]),rank=k)
    elif family=="edge_starlike": graph=hg.EStarLike(*(lengths or [1,1,1]),rank=k)
    elif family=="bicyclic_c1": graph=hg.Bicyclic_C1(lengths or [1,1,1],k)
    elif family=="bicyclic_c2": graph=hg.Bicyclic_C2(lengths or [1,1,1],k)
    elif family=="bicyclic_c3": graph=hg.Bicyclic_C3(lengths or [1,1],k)
    elif family in ('gee','gev','gvv','gwg','ca','cva'):
        from graph_research.hypergraphs.research_families import research_family
        graph=research_family(family,m,k,left_lengths,right_lengths,pendant_length,edge_paths,vertex_paths)
    else: raise ValueError("Unknown hypergraph family")
    return {"edges": [list(e) for e in graph.Edges], "vertices": graph.vertices(),
            "order": graph.order(), "size": graph.size(), "rank": graph.rank}


def hypergraph_spectrum(edges, alpha=0, seed=42, weighted_incidence=False, weights=None, vertex_degrees=None, tolerance=1e-11, max_iterations=20000, initial_vector=None, method="auto"):
    if len(set(v for edge in edges for v in edge)) > 128:
        raise ValueError("Too many vertices")
    with measure('graph_construction'):graph = Hypergraph(edges,weights=weights,vertex_degrees=vertex_degrees)
    if alpha==1 and weighted_incidence:raise ValueError("alpha=1 does not define a positive-vector weighted incidence output")
    result = graph.alpha_spectrum(alpha, seed=seed,tolerance=tolerance,max_iterations=max_iterations,initial_vector=initial_vector,method=method)
    if weighted_incidence:
        result["weighted_incidence"] = graph.weighted_incidence_from_result(result).tolist()
        result['weighted_incidence_computation']='logsumexp; original formula, no row renormalization'
    return result


def graph_invariants(kind="path", n=5, edges=None):
    g = graphs.make_graph(kind, n, edges)
    if len(g) == 0:
        raise ValueError("graph_invariants requires at least one vertex; connectivity is undefined for the null graph")
    return {"order": len(g), "size": g.number_of_edges(), "degrees": [g.degree(v) for v in g],
            "connected": nx.is_connected(g), "bipartite": nx.is_bipartite(g),
            "components": nx.number_connected_components(g),
            "diameter": nx.diameter(g) if nx.is_connected(g) else None}


def graph_characteristic_polynomial(kind="path", n=5, edges=None, matrix="A"):
    if n > 24: raise ValueError("Exact polynomial tool limited to24 vertices")
    return {"polynomial": str(graphs.charpolys_for_graph(graphs.make_graph(kind, n, edges), matrix).as_expr())}


def matching_polynomial(kind="path", n=5, edges=None):
    p = combinatorics.matching_generating_function(graphs.make_graph(kind, n, edges))
    return {"generating_polynomial": str(p.as_expr()), "coefficients_ascending": list(reversed(p.all_coeffs()))}


def matrix_analysis(matrix):
    a = np.asarray(matrix, dtype=float)
    if a.ndim != 2 or min(a.shape) == 0 or not np.isfinite(a).all():
        raise ValueError("Finite rectangular matrix required")
    out = {"shape": list(a.shape), "rank": int(np.linalg.matrix_rank(a))}
    if a.shape[0] == a.shape[1]:
        out["determinant_numeric"] = float(np.linalg.det(a))
        out["eigenvalues"] = json_value(np.linalg.eigvals(a))
    return out


def polynomial_roots(coefficients, a, b):
    if not coefficients or coefficients[0] == 0 or a > b:
        raise ValueError("Nonzero leading coefficient and ordered interval required")
    x = sp.Symbol("x")
    p = sp.Poly.from_list([sp.Rational(str(c)) for c in coefficients], x)
    return {"polynomial": str(p.as_expr()), "interval": [a, b], "endpoint_convention": "closed",
            "distinct_real_root_count": polynomials.num_realroots(p, a, b),
            "roots": polynomials.find_all_roots(p, a, b)}


def quotient_matrix(matrix, blocks):
    a = np.asarray(matrix, dtype=float)
    q = graphs.Quotient_Matrix(a, blocks)
    from graph_research.algebra.products import _partition_indices
    blocks = _partition_indices(blocks,a.shape[0])
    equitable = all(np.allclose(a[np.ix_(b, c)].sum(axis=1), q[i, j])
                    for i, b in enumerate(blocks) for j, c in enumerate(blocks))
    return {"quotient": q.tolist(), "equitable": equitable}


def tensor_spectrum(data):
    a = np.asarray(data, dtype=float)
    if a.size > 100000 or a.ndim > 6: raise ValueError("Dense tensor too large")
    rho, x = Tensor(a).SpectralRadius()
    return {"rho": rho, "perron_vector": x.tolist()}


def combinatorial_calculation(operation, n=5, k=2, parts=None,generators=None,board=None,side='right'):
    if operation in ('cycle_index','cayley_graph'):
        from graph_research.algebra.groups import group_calculation
        if generators is None:raise ValueError('群计算需要提供生成元置换generators。')
        if operation=='cycle_index' and side!='right':raise ValueError('side仅用于Cayley图；循环指标与乘法侧无关。')
        return {'operation':operation,**group_calculation(operation,generators,side=side)}
    if operation=='rook_polynomial':
        if board is None or not board or not board[0] or max(len(board),len(board[0]))>10 or any(len(row)!=len(board[0]) for row in board):
            raise ValueError('车多项式需要非空矩形0/1棋盘，每维最多10。')
        if any(type(cell) is not int or cell not in (0,1) for row in board for cell in row):raise ValueError('棋盘仅接受0/1整数；1为可放置车的格子。')
        polynomial=combinatorics.rook_polynomial(board)
        return {'operation':operation,'polynomial':str(polynomial.as_expr()),
                'coefficients_ascending':[int(polynomial.nth(i)) for i in range(polynomial.degree()+1)],
                'board':board,'shape':[len(board),len(board[0])],
                'interpretation':'x^k的系数为放置k个互不攻击的车的方法数；1格可用，0格禁用。'}
    if operation == "partition_number": result = combinatorics.Partition_Number(n,k)
    elif operation == "divisibility_matrix": result = combinatorics.divMatrix(n)
    elif operation == "mobius_matrix": result = combinatorics.mobuisMatrix(n)
    elif operation == "cycle_type_count": result = combinatorics.num_cycletype(parts or [])
    else: raise ValueError("Unknown combinatorial operation")
    return {"operation":operation,"result":json_value(result)}


def graph_edit(operation, kind="path", n=5, edges=None, vertices=None, edit_edges=None, power=2,core_k=2,labels=None,subdivisions=1,replacement=None,endpoints=None):
    graph = graphs.make_graph(kind,n,edges)
    if operation == "complement": result = nx.complement(graph)
    elif operation == "line_graph": result = nx.convert_node_labels_to_integers(nx.line_graph(graph))
    elif operation == "power": result = graphs.Graph_Power(graph,power)
    elif operation == "delete_vertices": result = graphs.Delete_Vertices(graph,vertices or [])
    elif operation == "delete_edges": result = graphs.Delete_Edges(graph,edit_edges or [])
    elif operation == "add_edges":
        if any(v not in graph for edge in edit_edges or [] for v in edge): raise ValueError("New edge uses an unknown vertex")
        result = graphs.Add_Edges(graph,edit_edges or [])
    elif operation == "seidel_switch": result = graphs.seidel_switching(graph,vertices or [])
    elif operation=='replace_edge':
        if replacement is None or endpoints is None or not edit_edges or len(edit_edges)!=1:raise ValueError('需要替换图replacement、两个端点endpoints及恰好一条edit_edges。')
        other=graphs.make_graph(**replacement)
        if len(graph)+len(other)-2>128:raise ValueError('替换结果超过128顶点。')
        result=graphs.replace_edges_by_graph(graph,[other],edit_edges,[endpoints])
    elif operation=='replace_edges':
        if replacement is None or endpoints is None or not edit_edges:raise ValueError('批量替换需要replacement、endpoints及非空edit_edges。')
        other=graphs.make_graph(**replacement)
        if len(graph)+len(edit_edges)*(len(other)-2)>128:raise ValueError('批量替换结果超过128顶点。')
        result=graphs.replace_edges_by_graph(graph,[other]*len(edit_edges),edit_edges,[endpoints]*len(edit_edges))
    elif operation=='partial_product':
        if replacement is None or not vertices or len(set(vertices))!=len(vertices) or any(v not in graph for v in vertices):raise ValueError('局部笛卡尔积需要replacement及不重复的已有vertices。')
        other=graphs.make_graph(**replacement)
        if len(graph)+len(vertices)*(len(other)-1)>128:raise ValueError('局部笛卡尔积结果超过128顶点。')
        result=graphs.PartProduct(graph,vertices,other)
    elif operation == 'core':result=nx.k_core(graph,k=int(core_k))
    elif operation == 'relabel':
        if labels is None or len(labels)!=len(graph):raise ValueError('labels须为按原顶点顺序列出的全部新标签。')
        result=graphs.Relabel(graph,dict(zip(graph,labels)))
    elif operation == 'subdivide_edges':
        selected=list(graph.edges) if edit_edges is None else edit_edges
        if len(graph)+len(selected)*int(subdivisions)>128:raise ValueError('剖分结果超出128个顶点。')
        result=graphs.subdivide_edges(graph,selected,int(subdivisions))
    else: raise ValueError("Unknown graph edit")
    nodes=list(result);index={v:i for i,v in enumerate(nodes)}
    return {"vertices":nodes,"edges":[list(e) for e in result.edges],'order':len(result),'size':result.number_of_edges(),
            'graph_spec':{'kind':'edges','n':len(result),'edges':[[index[u],index[v]] for u,v in result.edges]},
            'graph_spec_labels':nodes,'note':'graph_spec按graph_spec_labels顺序重新编号；空图不能送入要求n>=1的谱工具。'}


def exact_matrix_operation(matrix, operation="rref",actions=None,row_index=0,row_terms=None):
    a = sp.Matrix([[sp.Rational(str(v)) for v in row] for row in matrix])
    if max(a.shape)>12: raise ValueError("Exact matrix tool limited to12 rows/columns")
    if operation=='elementary':
        from graph_research.algebra.elementary import do_Actions,do_show_ops
        if actions is None:raise ValueError('请提供行列变换步骤actions。')
        names={'swap_rows':'r1','scale_row':'r2','add_row':'r3','swap_columns':'c1','scale_column':'c2','add_column':'c3'}
        instructions=[]
        for record in actions:
            name=names[record['kind']];target=int(record['target'])
            if name[1]=='1':values=[target,int(record['source'])] if 'source' in record else None
            elif name[1]=='2':values=[target,sp.Rational(str(record['factor']))] if 'factor' in record else None
            else:values=[target,int(record['source']),sp.Rational(str(record['factor']))] if 'source' in record and 'factor' in record else None
            if values is None:raise ValueError('交换需要source，数乘需要factor，加倍数需要两者。')
            instructions.append([name,*values])
        result=do_Actions(a,instructions)
        return {'matrix':json_value(result),'latex':do_show_ops(a,instructions),'arithmetic':'exact'}
    if operation=='split_row':
        from graph_research.algebra.elementary import split_row
        if row_terms is None:raise ValueError('请提供拆分行向量row_terms。')
        rows=[[sp.Rational(str(value)) for value in row] for row in row_terms]
        pieces=split_row(a,int(row_index),rows,disp=False)
        return {'matrices':[json_value(part) for part in pieces[1:]],'original_determinant':str(a.det()),
                'term_determinants':[str(part.det()) for part in pieces[1:]],'latex':split_row(a,int(row_index),rows)}
    if operation == "rref":
        result,pivots = a.rref(); return {"matrix":json_value(result),"pivot_columns":list(pivots)}
    if operation == "determinant": return {"determinant":str(a.det())}
    if operation == "inverse": return {"matrix":json_value(a.inv())}
    if operation == "charpoly": return {"polynomial":str(a.charpoly().as_expr())}
    raise ValueError("Unknown exact matrix operation")


def tensor_operation(data, operation="symmetrize", exponent=2):
    tensor = Tensor(np.asarray(data,dtype=float))
    if tensor.size()>10000 or tensor.rank>6: raise ValueError("Tensor too large")
    if operation == "symmetrize": return {"tensor":tensor.symmetrized().array.tolist()}
    if operation == "transpose": return {"tensor":tensor.transpose().array.tolist()}
    if operation == "entrywise_power": return {"tensor":(tensor**exponent).array.tolist()}
    if operation == "properties": return {"shape":list(tensor.shape),"symmetric":tensor.is_symmetric(),"diagonal":tensor.is_diagonal_tensor()}
    raise ValueError("Unknown tensor operation")


class ToolRegistry:
    def __init__(self):
        from graph_research.runtime.integrity import assert_integrity
        assert_integrity()
        self.tools = {}
        definitions = [
            ("generate_hypergraph", "构造松路/超星/松圈、点心/边心像星超树、三类双圈超图。m是边数，k是秩；C1/C2要求k>=3，C3要求k>=4。", generate_hypergraph,
             object_schema({"family": {"enum": ["path", "star", "cycle","vertex_starlike","edge_starlike","bicyclic_c1","bicyclic_c2","bicyclic_c3","gee","gev","gvv","gwg","ca","cva"]}, "m": {"type":"integer","minimum":1,"maximum":32}, "k":{"type":"integer","minimum":2,"maximum":8},"lengths":{"type":"array","items":{"type":"integer","minimum":1,"maximum":16},"minItems":1,"maxItems":8},
                "left_lengths":{"type":"array","items":{"type":"integer","minimum":0,"maximum":16},"maxItems":8},
                "right_lengths":{"type":"array","items":{"type":"integer","minimum":0,"maximum":16},"maxItems":8},
                "pendant_length":{"type":"integer","minimum":0,"maximum":16},
                "edge_paths":{"type":"array","maxItems":32,"items":object_schema({"edge_index":{"type":"integer","minimum":0,"maximum":31},"lengths":{"type":"array","maxItems":8,"items":{"type":"integer","minimum":0,"maximum":16}}},["edge_index","lengths"])},
                "vertex_paths":{"type":"array","maxItems":32,"items":object_schema({"vertex":{"type":"integer","minimum":0,"maximum":127},"lengths":{"type":"array","maxItems":8,"items":{"type":"integer","minimum":0,"maximum":16}}},["vertex","lengths"])}}, ["family"])),
            ("hypergraph_spectrum", "一致超图α谱半径及独立有理数复核；α<1要求连通，α=1返回度对角端点。", hypergraph_spectrum,
             object_schema({"edges": EDGES, "alpha": {"type":"number","minimum":0,"maximum":1}, "seed": {"type":"integer","minimum":0,"maximum":2**32-1}, "weighted_incidence":{"type":"boolean"},"weights":NUMBERS,"vertex_degrees":NUMBERS,"tolerance":{"type":"number","minimum":1e-13,"maximum":0.01},"max_iterations":{"type":"integer","minimum":1,"maximum":20000},"initial_vector":{"type":"array","minItems":1,"maxItems":128,"items":{"type":"number","exclusiveMinimum":0}},"method":{"enum":["iteration","auto","newton_noda"]}}, ["edges"])),
            ("graph_spectrum", "普通无向简单图的A/L/Q/D/DL/N/ABC/S/alpha矩阵与完整数值谱。", graphs.graph_spectrum,
             object_schema({**GRAPH_ARGS,"matrix":{"enum":["A","L","Q","D","DL","N","ABC","S","alpha"]},"alpha":{"type":"number","minimum":0,"maximum":1}})),
            ("graph_invariants", "普通图的顶点数、边数、度序列、连通性、二分性和直径。", graph_invariants, object_schema(GRAPH_ARGS)),
            ("graph_characteristic_polynomial", "普通图的精确整系数特征多项式，最多24顶点。", graph_characteristic_polynomial, object_schema({**GRAPH_ARGS,"matrix":{"enum":["A","L","Q","D","DL","S"]}})),
            ("matching_polynomial", "普通简单图的匹配数生成多项式sum(m_k*x^k)，最多24顶点。", matching_polynomial, object_schema(GRAPH_ARGS)),
            ("matrix_analysis", "有限数值矩阵的秩、方阵行列式和特征值。", matrix_analysis, object_schema({"matrix":MATRIX}, ["matrix"])),
            ("polynomial_roots", "有理系数单变量多项式在闭区间的不同实根计数及隔离，系数从高次到低次。", polynomial_roots, object_schema({"coefficients":{"type":"array","items":NUMBER,"minItems":2,"maxItems":33},"a":NUMBER,"b":NUMBER}, ["coefficients","a","b"])),
            ("quotient_matrix", "按给定顶点划分计算平均商矩阵，并检查划分是否等价。", quotient_matrix, object_schema({"matrix":MATRIX,"blocks":{"type":"array","items":{"type":"array","items":INT,"minItems":1},"minItems":1}}, ["matrix","blocks"])),
            ("tensor_spectrum", "小规模非负立方张量的谱半径，未收敛明确报错。", tensor_spectrum, object_schema({"data":{"type":"array","minItems":1,"maxItems":128}}, ["data"])),
            ("combinatorial_calculation", "精确计算分拆数、整除/Möbius矩阵和给定轮换类型的置换数量。", combinatorial_calculation,
             object_schema({"operation":{"enum":["partition_number","divisibility_matrix","mobius_matrix","cycle_type_count","cycle_index","cayley_graph","rook_polynomial"]},"n":{"type":"integer","minimum":0,"maximum":32},"k":{"type":"integer","minimum":0,"maximum":32},"parts":{"type":"array","items":{"type":"integer","minimum":1,"maximum":32},"maxItems":32},"generators":{"type":"array","minItems":1,"maxItems":8,"items":{"type":"array","minItems":1,"maxItems":8,"items":{"type":"integer","minimum":0,"maximum":7}}},
                "board":{"type":"array","minItems":1,"maxItems":10,"items":{"type":"array","minItems":1,"maxItems":10,"items":{"type":"integer","enum":[0,1]}}},
                "side":{"enum":["right","left","twosided"]}},["operation"])),
            ("graph_edit", "对简单图作补图、线图、图幂、删点删边、加边或Seidel切换。", graph_edit,
             object_schema({**GRAPH_ARGS,"operation":{"enum":["complement","line_graph","power","delete_vertices","delete_edges","add_edges","seidel_switch","core","relabel","subdivide_edges","replace_edge","replace_edges","partial_product"]},"vertices":{"type":"array","items":INT,"maxItems":128},"edit_edges":GRAPH_ARGS["edges"],"power":{"type":"integer","minimum":1,"maximum":8},
                "core_k":{"type":"integer","minimum":0,"maximum":128},
                "labels":{"type":"array","minItems":1,"maxItems":128,"uniqueItems":True,"items":{"type":["integer","string"]}},
                "subdivisions":{"type":"integer","minimum":0,"maximum":16},
                "replacement":object_schema(GRAPH_ARGS,["kind","n"]),"endpoints":{"type":"array","minItems":2,"maxItems":2,"uniqueItems":True,"items":{"type":"integer","minimum":0,"maximum":127}}},["operation"])),
            ("exact_matrix_operation", "有理数精确矩阵的行最简形、逆、行列式和特征多项式；小数按十进制有理数解释。", exact_matrix_operation,object_schema({"matrix":MATRIX,"operation":{"enum":["rref","inverse","determinant","charpoly","elementary","split_row"]},
                "actions":{"type":"array","maxItems":32,"items":object_schema({"kind":{"enum":["swap_rows","scale_row","add_row","swap_columns","scale_column","add_column"],"description":"交换行、数乘行、加行倍数，或对应的列操作。"},"target":{"type":"integer","minimum":0,"maximum":11,"description":"0起始目标行/列序号。"},"source":{"type":"integer","minimum":0,"maximum":11,"description":"0起始源行/列序号，须与目标不同。"},"factor":{**NUMBER,"description":"精确数乘或加倍数的系数。"}},["kind","target"])},
                "row_index":{"type":"integer","minimum":0,"maximum":11},"row_terms":{"type":"array","maxItems":12,"items":{"type":"array","minItems":1,"maxItems":12,"items":NUMBER}}},["matrix"])),
            ("tensor_operation", "小张量的对称化、转置、逐项幂和结构检查。", tensor_operation,object_schema({"data":{"type":"array","minItems":1,"maxItems":128},"operation":{"enum":["symmetrize","transpose","entrywise_power","properties"]},"exponent":{"type":"integer","minimum":0,"maximum":8}},["data"])),
        ]
        from graph_research.tools.graphs import extra_tool_definitions
        definitions.extend(extra_tool_definitions(GRAPH_ARGS,EDGES,object_schema))
        from graph_research.tools.symbolic import symbolic_tool_definitions
        definitions.extend(symbolic_tool_definitions(object_schema))
        from graph_research.tools.elimination import elimination_tool_definitions
        definitions.extend(elimination_tool_definitions(object_schema))
        from graph_research.rendering.plotting import plotting_tool_definitions
        definitions.extend(plotting_tool_definitions(object_schema))
        from graph_research.rendering.editor import editor_tool_definitions
        definitions.extend(editor_tool_definitions(object_schema))
        from graph_research.rendering.tikz import tikz_tool_definitions
        definitions.extend(tikz_tool_definitions(object_schema))
        from .schematic import definition as schematic_definition
        definitions.append(schematic_definition(object_schema))
        from graph_research.tools.research import research_tool_definitions
        definitions.extend(research_tool_definitions(object_schema,GRAPH_ARGS))
        from graph_research.tools.library_entries import library_entry_definitions
        definitions.extend(library_entry_definitions(object_schema,GRAPH_ARGS))
        for name, description, function, schema in definitions:
            self.register(Tool(name, description, schema, function))

    def register(self, tool):
        if tool.name in self.tools: raise ValueError("Existing tool names cannot be overwritten")
        from graph_research.tools.contracts import enrich_tool
        enrich_tool(tool)
        jsonschema.Draft202012Validator.check_schema(tool.parameters)
        self.tools[tool.name] = tool

    def catalog(self, detail="full"):
        """Return reviewed tool contracts; optional model/index views are smaller."""
        return [tool.definition(detail=detail) for tool in self.tools.values()]

    def describe(self, name):
        """Return a complete contract for one registered name, without executing."""
        if name not in self.tools: raise TaskProtocolError("tool_not_found", f"Unknown tool: {name}")
        return self.tools[name].definition(detail="full")

    def call(self, name, arguments):
        if name not in self.tools: raise TaskProtocolError("tool_not_found", f"Unknown tool: {name}")
        if not isinstance(arguments, dict): raise ValueError("Tool arguments must be an object")
        encoded = json.dumps(arguments, allow_nan=False)
        if len(encoded) > 100000: raise ValueError("Tool input too large")
        tool = self.tools[name]
        with measure('argument_validation'):jsonschema.validate(arguments, tool.parameters)
        with measure('tool_function'):value=tool.function(**arguments)
        with measure('result_conversion'):return json_value(value)
