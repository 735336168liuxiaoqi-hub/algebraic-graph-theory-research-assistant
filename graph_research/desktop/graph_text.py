"""Structured bilingual graph captions; never rewrite graph or vertex identities."""
import json
import re
from .i18n import UiText,language,translations

ROLE_NAMES={'输入图':'Input graph','结果图':'Result graph','构图结果':'Constructed graph',
    '左侧图':'Left graph','右侧图':'Right graph','左图':'Left graph','右图':'Right graph',
    '配方初始图':'Recipe base graph','初始图':'Initial graph','批量图':'Batch graph',
    '图输入中的当前图':'Current graph from Graph input','未命名图':'Untitled graph','论文示意图':'Paper schematic','实现图':'Realization'}


def _name(value):
    """Localize only standard generated names/suffixes, retaining custom name text."""
    suffix='（已展开）'
    if value.endswith(suffix):return _name(value[:-len(suffix)])+' (Expanded)'
    if re.fullmatch('[EFHG]型论文示意图',value):return value[0]+' paper schematic'
    return ROLE_NAMES.get(value,value)


def quantity(number,singular,plural=None):return f'{number} {singular if number==1 else plural or singular+"s"}'


def role_text(value):
    if isinstance(value,UiText):return value.english
    for name,english in ROLE_NAMES.items():
        if value.startswith(name+' ') and value[len(name)+1:].isdecimal():return english+' '+value[len(name)+1:]
    return ROLE_NAMES.get(value,translations().get(value,value))


def graph_summary(graph,*,role=None,expanded_notice=False,recipe=False):
    kind='超图' if graph.graph_type=='hypergraph' else '有向图' if graph.directed else '普通图'
    english_kind='Hypergraph' if graph.graph_type=='hypergraph' else 'Directed graph' if graph.directed else 'Graph'
    edge_word='超边' if graph.graph_type=='hypergraph' else '有向边' if graph.directed else '边'
    english_edge='hyperedge' if graph.graph_type=='hypergraph' else 'arc' if graph.directed else 'edge'
    zh=[graph.name,kind,f'{graph.order}个顶点 / {graph.size}条{edge_word}']
    en=[_name(graph.name),english_kind,quantity(graph.order,'vertex','vertices')+' / '+quantity(graph.size,english_edge)]
    if role and role!=graph.name:zh.insert(0,role);en.insert(0,role_text(role))
    if graph.weighted:zh.append('带权');en.append('Weighted')
    if graph.graph_type=='hypergraph':
        zh.append('无超边' if not graph.size else '一致' if graph.uniform else '非一致')
        en.append('No hyperedges' if not graph.size else 'Uniform' if graph.uniform else 'Non-uniform')
    if recipe:zh.append('含构图配方');en.append('Includes construction recipe')
    chinese=' · '.join(zh);english=' · '.join(en)
    if expanded_notice:chinese+='；已生成独立具体超图。';english+='; expanded as a separate concrete hypergraph.'
    return UiText(chinese,english)


def preview_title(role):return UiText('结构预览 · '+role,'Structure preview · '+role_text(role))


def mapping_text(sources):
    from graph_research.graph_input.document import GraphDocument
    lines=[]
    for source in sources:
        try:
            graph=GraphDocument(source['document']);target=source.get('target')
            role={'left':'左侧图','right':'右侧图','base':'配方初始图','graph':'输入图'}.get(target,'批量图')
            if target=='case':role+=' '+str(source.get('case_index',0)+1)
            caption=graph_summary(graph,role=role)
            lines.append(caption.english if language()=='en' else str(caption))
            for record in source.get('vertex_mapping',[])[:128]:
                label=record['label'];text=json.dumps(label,ensure_ascii=False) if isinstance(label,str) else str(label)
                lines.append('  '+str(record['index'])+' → '+text)
            if not source.get('vertex_mapping'):lines.append('  Original vertex labels are retained.' if language()=='en' else '  此工具保留原始顶点标签。')
        except (ValueError,KeyError,TypeError):lines.append('Invalid input graph record; inspect the original data.' if language()=='en' else '输入图资料格式无效，请检查原始记录。')
    return '\n'.join(lines)


def schematic_conditions(scene):
    from graph_research.schematics.document import length_parts
    data=scene.to_dict();english=[]
    if data['rank']=='k':english.append('k must be an integer; k ≥ '+str(max([2]+[len(edge['vertices']) for edge in data['edges']])))
    for path in data['paths']:
        symbol,offset=length_parts(path['length'])
        if symbol is not None:
            english.append(f'{symbol} must be an integer; {symbol}{offset:+d} ≥ 1' if offset else symbol+' must be a positive integer')
    return UiText('；'.join(scene.conditions()) or '具体路长示意；可导出TeX或展开成新超图。',
                  '; '.join(dict.fromkeys(english)) or 'Specified path lengths; export TeX or expand to a concrete hypergraph.')
