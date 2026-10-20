"""Portable drawing styles: data only, independent of Qt, TeX and Matplotlib."""
import copy
import math
import re

from graph_research.errors import FieldValidationError

DEFAULTS={'vertex_color':'#173d3b','font_size':10,'font_family':'sans',
          'vertex_size':1.6,'line_width':.9,'line_style':'solid',
          'vertex_labels':True,'edge_labels':False,'weight_labels':True,'tension':.5,'continuity':.5,'bias':0}

GRAPH_DOCUMENT_SCHEMA={'type':'object','maxProperties':11,
    'description':'完整图对象：format=graph-research-graph、version=1，含vertices、edges、graph_type、directed、weighted及可选positions/style；与外层结构参数一致。'}


def style_schema():
    color={'type':'string','pattern':'^#[0-9a-fA-F]{6}$'}
    pair={'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':-200,'maximum':200}}
    return {'type':'object','additionalProperties':False,'properties':{
        'vertex_color':color,'edge_color':color,
        'font_size':{'type':'number','minimum':6,'maximum':36},
        'font_family':{'enum':['sans','serif','monospace']},
        'vertex_size':{'type':'number','minimum':.5,'maximum':10},
        'line_width':{'type':'number','minimum':.1,'maximum':8},
        'line_style':{'enum':['solid','dashed','dotted']},
        **{key:{'type':'number','minimum':-1,'maximum':1} for key in ('tension','continuity','bias')},
        **{key:{'type':'boolean'} for key in ('vertex_labels','edge_labels','weight_labels')},
        'edge_colors':{'type':'array','maxItems':1024,'items':color},
        'vertex_texts':{'type':'array','maxItems':128,'items':{'type':'object','additionalProperties':False,
            'properties':{'vertex':{'type':['integer','string']},'text':{'type':'string','maxLength':256}},'required':['vertex','text']}},
        'vertex_label_offsets':{'type':'array','maxItems':128,'items':{'type':'object','additionalProperties':False,
            'properties':{'vertex':{'type':['integer','string']},'xy':pair},'required':['vertex','xy']}},
        'edge_label_offsets':{'type':'array','maxItems':1024,'items':{'type':'object','additionalProperties':False,
            'properties':{'edge_index':{'type':'integer','minimum':0,'maximum':1023},'xy':pair},'required':['edge_index','xy']}}
    }}


def validate_style(style,vertices,edges):
    rules=style_schema()['properties']
    if not isinstance(style,dict):raise FieldValidationError(['style'],{'type':'object'},'绘图样式须为对象。')
    unknown=set(style)-set(rules)
    if unknown:raise FieldValidationError(['style'],{'type':'object'},'绘图样式含未知字段；请查看style契约。')
    for key,value in style.items():
        def fail(message):raise FieldValidationError(['style',key],rules[key],message)
        if key in ('vertex_color','edge_color'):
            if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):fail('颜色使用#RRGGBB格式。')
        elif key in ('font_family','line_style'):
            if value not in style_schema()['properties'][key]['enum']:fail('未知字体类别或线型。')
        elif key in ('vertex_labels','edge_labels','weight_labels'):
            if type(value) is not bool:fail('标签显示选项应为布尔值。')
        elif key in ('font_size','vertex_size','line_width','tension','continuity','bias'):
            rule=style_schema()['properties'][key]
            if type(value) not in (int,float) or not math.isfinite(value) or not rule['minimum']<=value<=rule['maximum']:fail('绘图尺寸超出允许范围。')
        elif key=='edge_colors':
            if not isinstance(value,list) or len(value)!=len(edges) or any(not isinstance(c,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',c) for c in value):fail('逐边颜色须按边顺序提供#RRGGBB，数量与边数一致。')
        elif key=='vertex_texts':
            if not isinstance(value,list) or len(value)>128:fail('自定义标签列表过长。')
            seen=set()
            for r in value:
                if not isinstance(r,dict) or set(r)!={'vertex','text'} or type(r['vertex']) not in (int,str) or r['vertex'] not in vertices or r['vertex'] in seen:fail('自定义标签标识无效或重复。')
                if not isinstance(r['text'],str) or len(r['text'])>256 or any(ord(c)<32 for c in r['text']):fail('自定义标签使用至多256字符的单行文本。')
                seen.add(r['vertex'])
        else:
            vertex=key=='vertex_label_offsets';identity='vertex' if vertex else 'edge_index';seen=set()
            if not isinstance(value,list) or len(value)>(128 if vertex else 1024):fail('标签偏移列表过长。')
            for record in value:
                if not isinstance(record,dict) or set(record)!={identity,'xy'}:fail('标签偏移需要对象标识和xy。')
                item=record[identity]
                if type(item) not in ((int,str) if vertex else (int,)):fail('标签偏移标识无效。')
                if item in seen or (item not in vertices if vertex else not 0<=item<len(edges)):fail('标签偏移标识重复或不属于当前图。')
                xy=record['xy']
                if not isinstance(xy,list) or len(xy)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>200 for v in xy):fail('标签偏移使用±200pt内的有限二维数。')
                seen.add(item)
    return copy.deepcopy(style)


def resolved_style(graph):
    return {**DEFAULTS,**graph.to_dict().get('style',{})}


def remap_style(style,old_vertices,new_vertices):
    """Change label identities when an adapter numbers vertices; offsets are in points."""
    result=copy.deepcopy(style);mapping=dict(zip(old_vertices,new_vertices))
    if 'vertex_label_offsets' in result:
        result['vertex_label_offsets']=[{**r,'vertex':mapping[r['vertex']]} for r in result['vertex_label_offsets'] if r['vertex'] in mapping]
    if 'vertex_texts' in result:result['vertex_texts']=[{**r,'vertex':mapping[r['vertex']]} for r in result['vertex_texts'] if r['vertex'] in mapping]
    return result


def reconcile_style(style,old_edges,new_vertices,new_edges,directed=False):
    """Keep per-edge offsets attached to edge identity after native structural edits."""
    result=copy.deepcopy(style)
    if 'vertex_label_offsets' in result:result['vertex_label_offsets']=[r for r in result['vertex_label_offsets'] if r['vertex'] in new_vertices]
    if 'vertex_texts' in result:result['vertex_texts']=[r for r in result['vertex_texts'] if r['vertex'] in new_vertices]
    identity=lambda e:tuple(e['vertices']) if directed else frozenset(e['vertices'])
    lookup={identity(e):i for i,e in enumerate(new_edges)}
    if 'edge_colors' in result:
        colors={identity(e):c for e,c in zip(old_edges,result['edge_colors'])}
        result['edge_colors']=[colors.get(identity(e),result.get('edge_color','#263e47')) for e in new_edges]
    if 'edge_label_offsets' in result:
        result['edge_label_offsets']=[{**r,'edge_index':lookup[identity(old_edges[r['edge_index']])]} for r in result['edge_label_offsets'] if r['edge_index']<len(old_edges) and identity(old_edges[r['edge_index']]) in lookup]
    return result
