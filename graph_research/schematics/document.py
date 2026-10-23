"""Bounded declarative paper figures. No eval, TeX execution or graph mutation."""
from dataclasses import dataclass
import json
import math
import re

from graph_research.graph_input.document import GraphDocument,document,_label

FORMAT='graph-research-schematic'
_LENGTH=re.compile(r'([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*)([+-][0-9]+)?\Z')


def length_parts(value):
    """A positive edge count or a single symbol plus an integer; never an expression evaluator."""
    if type(value) is int and 1<=value<=128:return None,value
    if isinstance(value,str) and len(value)<=48:
        match=_LENGTH.fullmatch(value.strip())
        if match:return match[1],int(match[2] or 0)
    raise ValueError('路长填写1..128的整数，或a、q+2、n-4、n_1等单个参数加减整数。')


def resolve_length(value,parameters):
    symbol,offset=length_parts(value)
    if symbol is None:return offset
    if symbol not in parameters or type(parameters[symbol]) is not int:raise ValueError('请给路长参数 '+symbol+' 指定整数。')
    result=parameters[symbol]+offset
    if not 1<=result<=128:raise ValueError('展开后的路长须在1..128之间：'+str(value))
    return result


def _finite(value,low,high,name):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError(name+'超出范围。')
    return float(value)


def _validate(data):
    if not isinstance(data,dict) or set(data)-{'format','version','name','rank','vertices','edges','paths','source_graph','style'}:raise ValueError('示意图包含未知字段。')
    if data.get('format',FORMAT)!=FORMAT or type(data.get('version',1)) is not int or data.get('version',1)!=1:raise ValueError('不支持的示意图格式/版本。')
    name=data.get('name','论文示意图');rank=data.get('rank','k')
    if not isinstance(name,str) or not 1<=len(name)<=80 or any(ord(c)<32 for c in name):raise ValueError('名称使用1..80字符的单行文本。')
    if rank!='k' and (type(rank) is not int or not 2<=rank<=128):raise ValueError('一致度填写k或2..128整数。')
    vertices=data.get('vertices',[]);edges=data.get('edges',[]);paths=data.get('paths',[])
    if not isinstance(vertices,list) or len(vertices)>128:raise ValueError('示意图最多128个锚点。')
    normalized=[]
    for v in vertices:
        if not isinstance(v,dict) or set(v)!={'id','xy'}:raise ValueError('锚点格式为{"id":"v","xy":[0,0]}。')
        xy=v['xy']
        if not isinstance(xy,list) or len(xy)!=2:raise ValueError('锚点使用二维坐标。')
        normalized.append({'id':_label(v['id']),'xy':[_finite(t,-100,100,'坐标') for t in xy]})
    ids=[v['id'] for v in normalized];coords=[v['xy'] for v in normalized]
    if len(set(ids))!=len(ids) or len({tuple(xy) for xy in coords})!=len(coords):raise ValueError('锚点标签或坐标重复。')
    members=set(ids);n_edges=[];seen=set()
    if not isinstance(edges,list) or len(edges)>128:raise ValueError('示意图最多128条中心超边。')
    for e in edges:
        if not isinstance(e,dict) or set(e)-{'vertices','shape','vertex_ellipsis'}:raise ValueError('中心边只接受vertices、shape、vertex_ellipsis。')
        vs=e.get('vertices',[]);shape=e.get('shape','ellipse');dots=e.get('vertex_ellipsis',False)
        if not isinstance(vs,list) or len(vs)<2 or len(set(map(_label,vs)))!=len(vs) or not set(vs)<=members:raise ValueError('中心边选择至少两个不同的已有锚点。')
        if type(rank) is int and len(vs)>rank:raise ValueError('中心边的不同连接顶点数超过一致度。')
        if shape not in ('ellipse','circle') or type(dots) is not bool:raise ValueError('中心边形状或边内省略标记无效。')
        if frozenset(vs) in seen:raise ValueError('中心超边重复。')
        seen.add(frozenset(vs));n_edges.append({'vertices':vs[:],'shape':shape,'vertex_ellipsis':dots})
    if sum(len(e['vertices']) for e in n_edges)>2048:raise ValueError('中心边的总关联数最多2048。')
    n_paths=[];pairs=set();drawn=0
    if not isinstance(paths,list) or len(paths)>64:raise ValueError('示意图最多64段超路。')
    for p in paths:
        if not isinstance(p,dict) or set(p)-{'start','end','length','brace','first_edges','last_edges','ellipsis','label_offset','vertex_ellipsis'}:raise ValueError('超路包含未知字段。')
        a,b=_label(p.get('start')),_label(p.get('end'))
        if a not in members or b not in members or a==b:raise ValueError('超路需要两个不同的已有端点。')
        key=frozenset((a,b))
        if key in pairs:raise ValueError('同一端点对暂不支持重叠超路。')
        pairs.add(key);length=p.get('length','a');symbol,_=length_parts(length)
        brace=p.get('brace','left');first=p.get('first_edges',1);last=p.get('last_edges',1)
        if brace not in ('left','right','none') or any(type(t) is not int or not 0<=t<=4 for t in (first,last)):raise ValueError('花括号方向或首尾展示边数无效。')
        dotted=p.get('ellipsis',symbol is not None or length>first+last)
        inner=p.get('vertex_ellipsis',True)
        if type(dotted) is not bool or type(inner) is not bool or symbol and not dotted:raise ValueError('符号路长须使用路中省略显示。')
        if symbol is None and not dotted and length>16:raise ValueError('完整绘制最多16条超边，请使用省略显示。')
        if symbol is None and dotted and length<=first+last:dotted=False
        drawn+=first+last+1 if dotted else length
        n_paths.append({'start':a,'end':b,'length':length.strip() if isinstance(length,str) else length,'brace':brace,
                        'first_edges':first,'last_edges':last,'ellipsis':dotted,'label_offset':_finite(p.get('label_offset',.28),.08,2,'标签距离'),
                        'vertex_ellipsis':inner})
    if drawn>1024:raise ValueError('绘制边段总数最多1024。')
    defaults={'line_color':'#161616','vertex_color':'#c03036','edge_fill':'#eeeeee','line_width':.018,'vertex_radius':.030}
    style=data.get('style',{})
    if not isinstance(style,dict) or set(style)-set(defaults)-{'graph_label'}:raise ValueError('示意图样式包含未知字段。')
    style={**defaults,**style}
    if 'graph_label' in style:
        from graph_research.graph_input.figure_label import validate
        style['graph_label']=validate(style['graph_label'])
    for key in ('line_color','vertex_color','edge_fill'):
        if not isinstance(style[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',style[key]):raise ValueError('颜色使用#RRGGBB。')
        style[key]=style[key].lower()
    style['line_width']=_finite(style['line_width'],.003,.08,'线宽')
    style['vertex_radius']=_finite(style['vertex_radius'],.008,.12,'顶点半径')
    result={'format':FORMAT,'version':1,'name':name,'rank':rank,'vertices':normalized,'edges':n_edges,'paths':n_paths,'style':style}
    if data.get('source_graph') is not None:result['source_graph']=GraphDocument(data['source_graph']).to_dict()
    if len(json.dumps(result,ensure_ascii=False).encode('utf-8'))>256*1024:raise ValueError('示意图数据最多256KiB。')
    return result


@dataclass(frozen=True,init=False)
class SchematicDocument:
    """Immutable *display* object. It is not accepted as a numerical GraphDocument."""
    _serialized:str
    def __init__(self,data):object.__setattr__(self,'_serialized',json.dumps(_validate(data),ensure_ascii=False,allow_nan=False))
    def to_dict(self):return json.loads(self._serialized)
    def conditions(self):
        data=self.to_dict();conditions=[]
        if data['rank']=='k':conditions.append('k为整数，k≥'+str(max([2]+[len(e['vertices']) for e in data['edges']])))
        for p in data['paths']:
            symbol,offset=length_parts(p['length'])
            if symbol is not None:conditions.append(f'{symbol}为整数，{symbol}{offset:+d}≥1' if offset else symbol+'为正整数')
        return list(dict.fromkeys(conditions))


def from_graph(graph):
    """Copy an unweighted undirected uniform graph to a paper scene; never mutate it."""
    if not isinstance(graph,GraphDocument):graph=GraphDocument(graph)
    if graph.directed or graph.weighted or not graph.uniform:raise ValueError('论文示意图导入先支持无向、无权、一致图；其他图可继续使用原有完整绘图。')
    data=graph.to_dict();xy=data.get('positions')
    if xy is None:
        from graph_research.hypergraphs import Hypergraph
        from graph_research.rendering.geometry import vertex_positions
        layout=vertex_positions(Hypergraph([e['vertices'] for e in graph.edges],vertices=list(graph.vertices)),seed=42)
        xy=[[float(t) for t in layout[v]] for v in graph.vertices]
    if xy:
        low=[min(p[i] for p in xy) for i in (0,1)];high=[max(p[i] for p in xy) for i in (0,1)]
        span=max(high[i]-low[i] for i in (0,1)) or 1
        xy=[[(p[i]-(low[i]+high[i])/2)*6/span for i in (0,1)] for p in xy]
    return SchematicDocument({'name':graph.name,'rank':len(graph.edges[0]['vertices']) if graph.size else 'k',
                              'vertices':[{'id':v,'xy':p} for v,p in zip(graph.vertices,xy)],
                              'edges':[{'vertices':e['vertices']} for e in graph.edges], 'source_graph':data,
                              **({'style':{'graph_label':data['style']['graph_label']}} if data.get('style',{}).get('graph_label') else {})})


def template(kind='E'):
    """Independent visual building blocks: blank, vertex arms, edge arms, two cores."""
    vertices=[];edges=[];paths=[]
    def vertex(label,x,y):vertices.append({'id':label,'xy':[x,y]})
    def path(a,b,length,brace='left',**extra):paths.append({'start':a,'end':b,'length':length,'brace':brace,**extra})
    if kind=='blank':return SchematicDocument({})
    if kind=='E':
        vertex('v',0,0)
        for label,x,y in [('a',0,2.5),('b',-2.165,-1.25),('c',2.165,-1.25)]:vertex(label,x,y);path('v',label,label)
    elif kind in ('F','H'):
        points=[(0,.24),(-.208,-.12),(.208,-.12)] if kind=='F' else [(-.18,.18),(-.18,-.18),(.18,-.18),(.18,.18)]
        ids=[]
        for i,(x,y) in enumerate(points):
            v='v'+str(i);label=chr(97+i);ids.append(v);vertex(v,x,y);vertex(label,x*10,y*10)
            path(v,label,label,'left')
        edges.append({'vertices':ids,'shape':'circle'})
    elif kind=='G':
        for side,sign in [('l',-1),('r',1)]:
            vertex(side,sign*.65,0);vertex(side+'u',sign*1.3,.22);vertex(side+'d',sign*1.3,-.22)
            edges.append({'vertices':[side,side+'u',side+'d']})
            for i,dy in enumerate((1.4,-1.4)):
                label=chr((97 if side=='l' else 99)+i);vertex(label,sign*3.4,dy)
                path(side+('u' if i==0 else 'd'),label,label,'right' if (side=='l')==(i==0) else 'left')
        path('l','r','q+2','right',first_edges=0,last_edges=0,label_offset=.40)
    else:raise ValueError('模板选择blank、E、F、H或G。')
    return SchematicDocument({'name':kind+'型论文示意图','rank':'k','vertices':vertices,'edges':edges,'paths':paths})


def compress_path(scene,edge_indices,endpoints=None):
    """Collapse a genuine loose chain only; reject hidden branching/external incidence."""
    data=scene.to_dict();indices=list(edge_indices);rank=data['rank'];edges=data['edges']
    if type(rank) is not int or len(indices)<3 or len(set(indices))!=len(indices) or any(type(i) is not int or not 0<=i<len(edges) for i in indices):raise ValueError('选择至少3条完整具体超边，并给出数值一致度。')
    selected=[set(edges[i]['vertices']) for i in indices]
    if any(len(e)!=rank for e in selected):raise ValueError('只能压缩顶点已完整列出的具体超边。')
    neighbors={i:[] for i in range(len(selected))}
    for i in neighbors:
        for j in range(i):
            common=selected[i]&selected[j]
            if len(common)>1:raise ValueError('相邻超边共享多个顶点，不是松路。')
            if common:neighbors[i].append(j);neighbors[j].append(i)
    ends=[i for i,ns in neighbors.items() if len(ns)==1]
    if len(ends)!=2 or any(len(ns)>2 for ns in neighbors.values()):raise ValueError('所选超边不是单条无分支松路。')
    order=[ends[0]]
    while len(order)<len(selected):
        nxt=[i for i in neighbors[order[-1]] if i not in order]
        if len(nxt)!=1:raise ValueError('所选超路不连通。')
        order.append(nxt[0])
    joints=[next(iter(selected[a]&selected[b])) for a,b in zip(order,order[1:])]
    if len(set(joints))!=len(joints):raise ValueError('多个连接共享同一顶点，不是松路。')
    outside=set().union(*(set(e['vertices']) for i,e in enumerate(edges) if i not in indices))
    outside.update(v for p in data['paths'] for v in (p['start'],p['end']))
    candidates=[selected[order[0]]-{joints[0]},selected[order[-1]]-{joints[-1]}]
    if endpoints is None:endpoints=[sorted(c&outside or c,key=lambda v:(type(v).__name__,str(v)))[0] for c in candidates]
    if len(endpoints)!=2 or not all(v in c for v,c in zip(endpoints,candidates)):
        if len(endpoints)==2 and all(v in c for v,c in zip(reversed(endpoints),candidates)):endpoints=list(reversed(endpoints))
        else:raise ValueError('端点须位于所选路的两个末端超边。')
    hidden=set().union(*selected)-set(endpoints)
    if hidden&outside:raise ValueError('路内顶点存在外部连接，不能省略这些分支。')
    data['vertices']=[v for v in data['vertices'] if v['id'] not in hidden]
    data['edges']=[e for i,e in enumerate(edges) if i not in indices]
    data['paths'].append({'start':endpoints[0],'end':endpoints[1],'length':len(indices),'ellipsis':True})
    return SchematicDocument(data)


def expand(scene,parameters=None):
    """Explicitly instantiate a fresh concrete graph; generated labels may differ from a compressed source."""
    data=scene.to_dict();parameters=parameters or {}
    if not isinstance(parameters,dict) or len(parameters)>64 or any(not isinstance(k,str) or type(v) is not int or abs(v)>1000000 for k,v in parameters.items()):raise ValueError('参数填写整数JSON对象，例如{"a":3,"k":4}。')
    rank=data['rank'] if type(data['rank']) is int else parameters.get('k')
    if type(rank) is not int or not 2<=rank<=128:raise ValueError('请给k指定2..128整数。')
    lengths=[resolve_length(p['length'],parameters) for p in data['paths']]
    if len(data['edges'])+sum(lengths)>128:raise ValueError('展开最多128条超边。')
    ids=[v['id'] for v in data['vertices']];positions=[v['xy'][:] for v in data['vertices']];pos=dict(zip(ids,positions));edges=[];used=set(ids)
    def new(xy):
        label='@s'+str(len(ids))
        while label in used:label+='x'
        if len(ids)>=128:raise ValueError('展开最多128个顶点；请减小路长或一致度。')
        while xy in positions:xy=[xy[0]+.0001,xy[1]+.0001]
        used.add(label);ids.append(label);positions.append(xy);pos[label]=xy;return label
    def add(members):
        if len(members)>rank:raise ValueError('中心边的连接顶点数超过k。')
        members=members[:];center=[sum(pos[v][i] for v in members)/len(members) for i in (0,1)]
        while len(members)<rank:
            t=len(members);members.append(new([center[0]+.05*math.cos(t),center[1]+.05*math.sin(t)]))
        edges.append({'vertices':members,'weight':1})
    for e in data['edges']:add(e['vertices'])
    for p,m in zip(data['paths'],lengths):
        a,b=pos[p['start']],pos[p['end']];chain=[p['start']]
        for j in range(1,m):chain.append(new([a[i]+(b[i]-a[i])*j/m for i in (0,1)]))
        chain.append(p['end'])
        for u,v in zip(chain,chain[1:]):add([u,v])
    label=data['style'].get('graph_label')
    return document(ids,edges,graph_type='hypergraph',name=data['name'][:72]+'（已展开）',positions=positions,
                    **({'style':{'graph_label':label}} if label else {}))
