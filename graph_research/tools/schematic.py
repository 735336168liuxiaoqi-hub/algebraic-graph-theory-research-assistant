"""One explicit paper-scene tool; symbolic export cannot silently become a graph."""
from pathlib import Path
import uuid
from graph_research.schematics import SchematicDocument,expand,save,to_tikz


def hypergraph_schematic(diagram,operation='export',parameters=None,vertex_labels=False):
    """Export a symbolic scene or explicitly instantiate bounded integer lengths."""
    scene=SchematicDocument(diagram)
    if operation=='expand':
        graph=expand(scene,parameters);data=graph.to_dict()
        index={v:i for i,v in enumerate(data['vertices'])}
        mapped=[[index[v] for v in e['vertices']] for e in data['edges']]
        import networkx as nx
        support=nx.Graph();support.add_nodes_from(range(graph.order))
        for edge in mapped:support.add_edges_from((edge[0],v) for v in edge[1:])
        compatible=bool(mapped) and len(mapped[0])<=8 and nx.is_connected(support)
        return {'graph_document':data,'hypergraph_spec':{'vertices':list(range(graph.order)),'edges':[[index[v] for v in e['vertices']] for e in data['edges']]},
                'vertex_mapping':[{'index':i,'label':v} for v,i in index.items()],
                'spectral_input':{'edges':mapped} if compatible else None,
                'numerical_note':'可将spectral_input绑定到超图谱工具。' if compatible else '完整图已保留；含孤立点/不连通/阶数超限时，不提供正向量求谱输入。',
                'order':graph.order,'size':graph.size,'rank':len(graph.edges[0]['vertices']) if graph.edges else None,
                'interpretation':'已明确赋值并展开的独立超图；不是将示意省略号当成一条边。'}
    if operation!='export':raise ValueError('operation选择export或expand。')
    if parameters:raise ValueError('导出不使用展开参数；请选择expand明确实例化。')
    output=Path.cwd()/'outputs'/'schematics'/uuid.uuid4().hex
    files={}
    for key,name in [('tex','diagram.tex'),('fragment','diagram-tikz.tex'),('svg','diagram.svg'),('scene','diagram.json')]:
        files[key]=str(save(scene,output/name,standalone=key!='fragment',vertex_labels=vertex_labels))
    code=to_tikz(scene,vertex_labels=vertex_labels)
    return {'diagram':scene.to_dict(),'files':files,'tikz':code if len(code)<=60000 else None,'conditions':scene.conditions(),
            'interpretation':'论文示意图。边内省略点表示未展示顶点，路中省略表示未展示超边。符号路长先赋整数再展开计算；首尾示意边段不限制参数的最小路长。'}


def definition(object_schema):
    label={'type':['integer','string']};xy={'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':-100,'maximum':100}}
    vertex=object_schema({'id':label,'xy':xy},['id','xy'])
    edge=object_schema({'vertices':{'type':'array','minItems':2,'maxItems':128,'items':label,'uniqueItems':True},'shape':{'enum':['ellipse','circle']},'vertex_ellipsis':{'type':'boolean'}},['vertices'])
    path=object_schema({'start':label,'end':label,'length':{'anyOf':[{'type':'integer','minimum':1,'maximum':128},{'type':'string','maxLength':48}]},
        'brace':{'enum':['left','right','none']},'first_edges':{'type':'integer','minimum':0,'maximum':4},'last_edges':{'type':'integer','minimum':0,'maximum':4},
        'ellipsis':{'type':'boolean'},'label_offset':{'type':'number','minimum':.08,'maximum':2},'vertex_ellipsis':{'type':'boolean'}},['start','end','length'])
    spec=object_schema({'format':{'const':'graph-research-schematic'},'version':{'const':1},'name':{'type':'string','minLength':1,'maxLength':80},
        'rank':{'anyOf':[{'type':'integer','minimum':2,'maximum':128},{'const':'k'}]},'vertices':{'type':'array','maxItems':128,'items':vertex},
        'edges':{'type':'array','maxItems':128,'items':edge},'paths':{'type':'array','maxItems':64,'items':path},'source_graph':{'type':'object'},
        'style':object_schema({**{k:{'type':'string','pattern':'^#[0-9a-fA-F]{6}$'} for k in ('line_color','vertex_color','edge_fill')},'line_width':{'type':'number','minimum':.003,'maximum':.08},'vertex_radius':{'type':'number','minimum':.008,'maximum':.12}})},['vertices'])
    return ('hypergraph_schematic','鼠标论文示意图：符号超路、花括号、TeX/SVG与明确整数展开。',hypergraph_schematic,
            object_schema({'diagram':spec,'operation':{'enum':['export','expand']},'parameters':{'type':'object','maxProperties':64,'additionalProperties':{'type':'integer','minimum':-1000000,'maximum':1000000}},'vertex_labels':{'type':'boolean'}},['diagram']))
