"""Bounded graph recipes using existing constructors and structural selectors."""
import copy
import networkx as nx
from graph_research._lazy import sympy as sp
from graph_research import graphs as gg,hypergraphs as hg
from graph_research.algebra.expressions import arithmetic_expression,integer_symbols


def _integer(value,parameters,lower=0,upper=128):
    scope={name:sp.Integer(number) for name,number in parameters.items()}
    result=arithmetic_expression(value,scope)
    if result.is_Integer is not True or not lower<=result<=upper:raise ValueError(f'尺寸表达式结果须为{lower}..{upper}的整数。')
    return int(result)


def _budget(graph):
    order=graph.order() if isinstance(graph,hg.Hypergraph) else len(graph)
    size=graph.size() if isinstance(graph,hg.Hypergraph) else graph.number_of_edges()
    if order>128 or size>(128 if isinstance(graph,hg.Hypergraph) else 1024):raise ValueError('配方结果超过128顶点或边数预算。')


def _compile_base(base,parameters):
    result=copy.deepcopy(base)
    for key in ('n','m','k','pendant_length'):
        if key in result:result[key]=_integer(result[key],parameters)
    for key in ('lengths','left_lengths','right_lengths'):
        if key in result:result[key]=[_integer(value,parameters) for value in result[key]]
    for key in ('edge_paths','vertex_paths'):
        for record in result.get(key,[]):
            record['lengths']=[_integer(value,parameters) for value in record['lengths']]
    return result


def _vertex(graph,selector,parameters):
    if isinstance(selector,bool):raise ValueError('顶点不能使用布尔值。')
    vertices=graph.vertices() if isinstance(graph,hg.Hypergraph) else list(graph)
    if not isinstance(selector,dict):
        if isinstance(selector,(str,int)) and selector in vertices:return selector
        value=_integer(selector,parameters)
        if value not in vertices:raise ValueError('指定顶点不存在。')
        return value
    if set(selector)-{'kind','value','edge','index'}:raise ValueError('顶点选择器字段未知。')
    kind=selector.get('kind')
    if kind=='vertex':return _vertex(graph,selector.get('value'),parameters)
    if kind not in ('leaf','joint'):raise ValueError('选择器kind为vertex/leaf/joint。')
    candidates=[v for v in vertices if (graph.degree(v)==1 if kind=='leaf' else graph.degree(v)>=2)]
    if 'edge' in selector:
        edges=graph.Edges if isinstance(graph,hg.Hypergraph) else list(graph.edges)
        index=_integer(selector['edge'],parameters,0,max(0,len(edges)-1))
        if not edges:raise ValueError('空图没有边选择器。')
        candidates=[v for v in candidates if v in edges[index]]
    index=_integer(selector.get('index',0),parameters,-128,127)
    try:return candidates[index]
    except IndexError:raise ValueError('结构顶点选择器没有足够候选。') from None


def build_recipe(graph_type,base,steps=None,parameters=None,assertions=None):
    """Build a graph from up to 16 whitelisted steps, recording resolved roots.

    Expressions affect only integer sizes and parameters; no Python evaluation.
    Structural selectors leaf/joint avoid dependence on legacy vertex numbers.
    Existing graph objects are not inputs and are never mutated.
    """
    parameters=dict(parameters or {});integer_symbols(parameters)
    if any(type(value) is not int or not 0<=value<=128 for value in parameters.values()):raise ValueError('参数值须为0..128整数。')
    if graph_type not in ('graph','hypergraph') or not isinstance(base,dict):raise ValueError('需要graph/hypergraph及base对象。')
    from graph_research.tools import ToolRegistry
    import jsonschema
    registry=ToolRegistry();compiled=_compile_base(base,parameters)
    if graph_type=='graph':
        from graph_research.tools.registry import GRAPH_ARGS,object_schema
        jsonschema.validate(compiled,object_schema(GRAPH_ARGS,['kind','n']))
        graph=gg.make_graph(**compiled)
    elif 'family' in compiled:
        jsonschema.validate(compiled,registry.describe('generate_hypergraph')['parameters'])
        generated=registry.call('generate_hypergraph',compiled)
        graph=hg.Hypergraph(generated['edges'],vertices=generated['vertices'])
    else:
        if set(compiled)-{'edges','vertices','weights'} or 'edges' not in compiled:raise ValueError('显式超图base使用edges、vertices、weights。')
        if len(compiled.get('vertices',[]))>128 or len(compiled['edges'])>128 or sum(map(len,compiled['edges']))>2048:raise ValueError('超图base超出关联预算。')
        graph=hg.Hypergraph(**compiled)
    _budget(graph);steps=list(steps or [])
    if len(steps)>16:raise ValueError('配方至多16步。')
    trace=[]
    for number,step in enumerate(steps):
        if not isinstance(step,dict):raise ValueError('配方步骤须为对象。')
        operation=step.get('operation');resolved={}
        allowed={'operation','root','roots','count','length','rank','left','right','edge_index','copies'}
        if set(step)-allowed:raise ValueError('配方步骤有未知字段。')
        count=_integer(step.get('count',1),parameters,0,32)
        if operation in ('attach_star','attach_path'):
            roots=step.get('roots',[step.get('root',0)])
            roots=[_vertex(graph,root,parameters) for root in roots]
            if not roots or len(set(roots))!=len(roots):raise ValueError('根集须非空且互异。')
            length=_integer(step.get('length',count),parameters,0,32)
            rank=_integer(step.get('rank',getattr(graph,'rank',2) or 3),parameters,2,8)
            if graph_type=='hypergraph' and rank<graph.rank:raise ValueError('附接rank不得小于现有最大边大小，避免隐式改变请求。')
            predicted=(graph.order() if graph_type=='hypergraph' else len(graph))+(length if operation=='attach_path' else count)*max(1,rank-1)
            if predicted>128:raise ValueError('附接预计超过顶点预算。')
            if graph_type=='hypergraph':graph=hg.add_star(graph,roots,count,rank) if operation=='attach_star' else hg.add_path(graph,roots,length,rank)
            else:
                if len(roots)!=1:raise ValueError('普通图附接指定一个根。')
                if operation=='attach_star':graph=gg.add_stars(graph,{roots[0]:count})
                else:
                    fresh=gg.operations._fresh(graph,length);graph=gg.Add_path(graph,[roots[0],*fresh])
            resolved={'roots':roots,'count':count if operation=='attach_star' else length,'rank':rank}
        elif operation=='connect':
            left=[_vertex(graph,v,parameters) for v in step.get('left',[])];right=[_vertex(graph,v,parameters) for v in step.get('right',[])]
            length=_integer(step.get('length',1),parameters,1,32)
            rank=_integer(step.get('rank',getattr(graph,'rank',2) or 3),parameters,2,8)
            if graph_type=='hypergraph' and rank<graph.rank:raise ValueError('内部路rank不得小于现有最大边大小。')
            if (graph.order() if graph_type=='hypergraph' else len(graph))+length*max(1,rank-1)>128:raise ValueError('内部路预计超过顶点预算。')
            if not left or not right:raise ValueError('connect需要left/right端点组。')
            if graph_type=='hypergraph':graph=hg.Add_innerPath(graph,[left,right],length,k=rank)
            else:
                if len(left)!=1 or len(right)!=1 or left==right:raise ValueError('普通图需要两个不同端点。')
                graph=gg.add_innerPaths(graph,{(left[0],right[0]):length-1})
            resolved={'left':left,'right':right,'edge_count':length,'rank':rank}
        elif operation=='disjoint_copies':
            copies=_integer(step.get('copies',2),parameters,1,16)
            if (graph.order() if graph_type=='hypergraph' else len(graph))*copies>128:raise ValueError('复制预计超过顶点预算。')
            graph=hg.Disjoint_Union([graph]*copies,relabel=True) if graph_type=='hypergraph' else gg.mygraphmul(graph,copies)
            resolved={'copies':copies}
        elif operation=='subdivide_edge':
            edges=graph.Edges if graph_type=='hypergraph' else list(graph.edges)
            if not edges:raise ValueError('没有边可剖分。')
            index=_integer(step.get('edge_index',0),parameters,0,len(edges)-1)
            if (graph.order() if graph_type=='hypergraph' else len(graph))+count*max(1,getattr(graph,'rank',2))>128:raise ValueError('剖分预计超过顶点预算。')
            graph=hg.subdivide_edge(graph,edges[index],count+1) if graph_type=='hypergraph' else gg.subdivide_edges(graph,[edges[index]],count)
            resolved={'edge_index':index,'count':count}
        else:raise ValueError('配方operation为attach_star/attach_path/connect/disjoint_copies/subdivide_edge。')
        _budget(graph)
        trace.append({'step':number+1,'operation':operation,'resolved':resolved,
                      'order':graph.order() if graph_type=='hypergraph' else len(graph),'size':graph.size() if graph_type=='hypergraph' else graph.number_of_edges()})
    if assertions:
        trace.append({'operation':'structural_assertions','checks':check_structure(graph,assertions,parameters)})
    return graph,trace


def check_structure(graph,assertions,parameters=None):
    """Fail a recipe if explicit structural claims are false; no sampling."""
    if not isinstance(assertions,dict) or set(assertions)-{'order','size','rank','uniform','connected','bipartite','cycle_rank','linear','degree_sequence'}:raise ValueError('未知结构断言。')
    hyper=isinstance(graph,hg.Hypergraph);incidence=graph.incidence_graph() if hyper else graph
    actual={'order':graph.order(),'size':graph.size() if hyper else graph.number_of_edges(),'connected':nx.is_connected(incidence) if len(incidence) else False,
            'bipartite':nx.is_bipartite(incidence),'cycle_rank':incidence.number_of_edges()-len(incidence)+nx.number_connected_components(incidence),
            'degree_sequence':sorted([graph.degree(v) for v in (graph.vertices() if hyper else graph)])}
    if hyper:
        actual.update(rank=graph.rank,uniform=graph.is_uniform(),linear=all(len(set(a)&set(b))<=1 for i,a in enumerate(graph.Edges) for b in graph.Edges[i+1:]))
    checks=[]
    for key,expected in assertions.items():
        if key not in actual:raise ValueError(f'{key}仅适用于超图。')
        if isinstance(actual[key],bool):
            if type(expected) is not bool:raise ValueError('逻辑断言须为true/false。')
        elif key=='degree_sequence':expected=sorted(_integer(v,parameters or {}) for v in expected)
        else:expected=_integer(expected,parameters or {},0,2048)
        if actual[key]!=expected:raise ValueError(f'结构断言失败：{key}期望{expected}，实际{actual[key]}。')
        checks.append({'property':key,'expected':expected,'actual':actual[key],'verified':True})
    return checks


def graph_recipe(graph_type,base,steps=None,parameters=None,assertions=None):
    graph,trace=build_recipe(graph_type,base,steps,parameters,assertions)
    if graph_type=='graph':
        nodes=list(graph);index={v:i for i,v in enumerate(nodes)}
        spec={'kind':'edges','n':len(nodes),'edges':[[index[u],index[v]] for u,v in graph.edges()]}
        return {'graph_type':graph_type,'graph_spec':spec,'graph_spec_labels':nodes,'order':len(nodes),'size':graph.number_of_edges(),'construction_steps':trace,'parameters':parameters or {}}
    return {'graph_type':graph_type,'hypergraph_spec':{'edges':graph.hyperedges(),'vertices':graph.vertices(),'weights':graph.weights.tolist()},
            'order':graph.order(),'size':graph.size(),'rank':graph.rank,'uniform':graph.is_uniform(),'construction_steps':trace,'parameters':parameters or {}}
