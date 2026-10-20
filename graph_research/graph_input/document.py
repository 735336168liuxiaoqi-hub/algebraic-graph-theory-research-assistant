"""Versioned graph data. No evaluation, pickle, model, file or UI access."""
from dataclasses import dataclass
import hashlib
import json
import math
import re
import networkx as nx

FORMAT='graph-research-graph'
MAX_TEXT=1024*1024


def display_label(value):
    """Keep numeric string identities visually distinct from integer vertices."""
    return '"'+value+'"' if isinstance(value,str) and value.lstrip('-').isdigit() else str(value)


class GraphInputError(ValueError):
    def __init__(self,message,line=None):
        self.line=line
        super().__init__((f'第{line}行：' if line else '')+message)


def strict_json(text):
    if not isinstance(text,str) or len(text)>MAX_TEXT:raise GraphInputError('输入最多1MB文本。')
    def pairs(items):
        data={}
        for key,value in items:
            if key in data:raise GraphInputError('JSON字段重复：'+key)
            data[key]=value
        return data
    def reject(value):raise GraphInputError('不接受非有限数：'+value)
    try:return json.loads(text,object_pairs_hook=pairs,parse_constant=reject)
    except (json.JSONDecodeError,RecursionError) as error:raise GraphInputError('JSON格式无效。',getattr(error,'lineno',None)) from None


def _label(value):
    if type(value) is int and abs(value)<=2**53-1:return value
    if isinstance(value,str) and 1<=len(value)<=128 and not any(ord(char)<32 for char in value):return value
    raise GraphInputError('顶点标签使用JSON安全整数（绝对值≤2^53−1）或1..128字符的文本；不接受布尔值。')


def weight_parts(value):
    if isinstance(value,dict):
        if set(value)!={'real','imag'}:raise GraphInputError('复权使用{"real":实部,"imag":虚部}。')
        real,imag=value['real'],value['imag']
    else:real,imag=value,0
    if any(type(v) not in (int,float) or abs(v)>10**6 or not math.isfinite(v) for v in (real,imag)):
        raise GraphInputError('边权须有限，实部和虚部绝对值≤10^6。')
    return real,imag


def weight_value(real,imag):return {'real':real,'imag':imag} if imag else real


def _validate(data):
    if not isinstance(data,dict) or set(data)-{'format','version','name','graph_type','directed','weighted','vertices','edges','positions','recipe','style'}:raise GraphInputError('图对象包含未知字段或不是对象。')
    if data.get('format')!=FORMAT or type(data.get('version')) is not int or data['version']!=1:raise GraphInputError('不支持的图对象格式/版本。')
    kind=data.get('graph_type','graph');directed=data.get('directed',False);weighted=data.get('weighted',False)
    if kind not in ('graph','hypergraph') or type(directed) is not bool or type(weighted) is not bool:raise GraphInputError('请选择普通图/超图及布尔方向、权重标记。')
    if kind=='hypergraph' and directed:raise GraphInputError('当前图对象不支持有向超图。')
    name=data.get('name','未命名图')
    if not isinstance(name,str) or not name.strip() or len(name)>80 or any(ord(c)<32 for c in name):raise GraphInputError('图名须为1..80字符的单行文本。')
    vertices=data.get('vertices',[]);edges=data.get('edges',[])
    if not isinstance(vertices,list) or len(vertices)>128:raise GraphInputError('最多128个顶点。')
    vertices=[_label(v) for v in vertices]
    if len(set(vertices))!=len(vertices):raise GraphInputError('完整顶点列表中有重复标签。')
    if not isinstance(edges,list) or len(edges)>(128 if kind=='hypergraph' else 1024):raise GraphInputError('边数超过普通图1024/超图128的上限。')
    normalized=[];seen=set();incidences=0
    for index,record in enumerate(edges):
        if not isinstance(record,dict) or set(record)-{'vertices','weight'}:raise GraphInputError(f'第{index+1}条边使用vertices和可选weight字段。')
        members=record.get('vertices');prefix=f'第{index+1}条边：'
        if not isinstance(members,list) or not 2<=len(members)<=128 or (kind=='graph' and len(members)!=2):raise GraphInputError(prefix+'普通边恰含2点，超边含2..128点。')
        members=[_label(v) for v in members];incidences+=len(members)
        if len(set(members))!=len(members):raise GraphInputError(prefix+'边内顶点重复或出现自环。')
        if not set(members)<=set(vertices):raise GraphInputError(prefix+'有顶点未列入完整顶点列表。')
        key=tuple(members) if directed else frozenset(members)
        if key in seen:raise GraphInputError(prefix+'与已有边重复。')
        seen.add(key);real,imag=weight_parts(record.get('weight',1))
        if not weighted and (real!=1 or imag):raise GraphInputError(prefix+'含非单位权，请启用带权模式。')
        if kind=='hypergraph' and (imag or real<=0):raise GraphInputError(prefix+'超边权须为正实数。')
        normalized.append({'vertices':members,'weight':weight_value(real,imag)})
    if incidences>2048:raise GraphInputError('总关联次数最多2048。')
    positions=data.get('positions')
    if positions is not None:
        if not isinstance(positions,list) or len(positions)!=len(vertices):raise GraphInputError('坐标须按顶点列表顺序一一填写。')
        for xy in positions:
            if not isinstance(xy,list) or len(xy)!=2 or any(type(v) not in (int,float) or abs(v)>10**9 or not math.isfinite(v) for v in xy):raise GraphInputError('坐标须为有限二维数，绝对值≤10^9。')
        if len({tuple(xy) for xy in positions})!=len(vertices):raise GraphInputError('不同顶点的坐标不能完全相同。')
    recipe=data.get('recipe')
    if recipe is not None:
        if not isinstance(recipe,dict) or set(recipe)-{'graph_type','base','steps','parameters','assertions'} or not isinstance(recipe.get('base'),dict) or len(json.dumps(recipe,ensure_ascii=False,allow_nan=False))>32768:raise GraphInputError('保存的构图配方须为≤32KB的graph_recipe参数对象，不含可执行代码。')
        if not isinstance(recipe.get('steps',[]),list) or len(recipe.get('steps',[]))>16:raise GraphInputError('配方步骤最多16项。')
    style={}
    if 'style' in data:
        from .styles import validate_style
        style={'style':validate_style(data['style'],vertices,normalized)}
    return {'format':FORMAT,'version':1,'name':name,'graph_type':kind,'directed':directed,'weighted':weighted,'vertices':vertices,'edges':normalized,**({'positions':positions} if positions is not None else {}),**({'recipe':recipe} if recipe is not None else {}),**style}


@dataclass(frozen=True,init=False)
class GraphDocument:
    """Immutable serialized snapshot; callers receive fresh dictionaries/lists."""
    _serialized:str

    def __init__(self,data):
        value=_validate(data)
        object.__setattr__(self,'_serialized',json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False))

    def to_dict(self):return json.loads(self._serialized)
    @property
    def vertices(self):return tuple(self.to_dict()['vertices'])
    @property
    def edges(self):return self.to_dict()['edges']
    @property
    def graph_type(self):return self.to_dict()['graph_type']
    @property
    def directed(self):return self.to_dict()['directed']
    @property
    def weighted(self):return self.to_dict()['weighted']
    @property
    def name(self):return self.to_dict()['name']
    @property
    def order(self):return len(self.vertices)
    @property
    def size(self):return len(self.edges)
    @property
    def uniform(self):return len({len(edge['vertices']) for edge in self.edges})<=1
    @property
    def sha256(self):return hashlib.sha256(self._serialized.encode('utf-8')).hexdigest()

    def with_updates(self,**updates):
        data=self.to_dict()
        if any(key in updates and updates[key]!=data[key] for key in ('vertices','edges','graph_type','directed','weighted')):data.pop('recipe',None)
        return GraphDocument({**data,**updates})

    def summary(self):
        kind='超图' if self.graph_type=='hypergraph' else '有向图' if self.directed else '普通图'
        return f'{self.name} · {kind} · {self.order}点 / {self.size}边'+(' · 带权' if self.weighted else '')+(' · '+('无超边' if not self.size else '一致' if self.uniform else '非一致') if self.graph_type=='hypergraph' else '')


def document(vertices,edges,*,graph_type='graph',directed=False,weighted=False,name='未命名图',positions=None,style=None):
    return GraphDocument({'format':FORMAT,'version':1,'name':name,'graph_type':graph_type,'directed':directed,'weighted':weighted,
                          'vertices':list(vertices),'edges':edges,**({'positions':positions} if positions is not None else {}),**({'style':style} if style is not None else {})})


def from_networkx(graph,pos=None):
    """Capture a bounded graph for drawing without importing plotting dependencies."""
    if graph.is_multigraph() or nx.number_of_selfloops(graph):raise GraphInputError('绘图不支持自环或多重边。')
    def number(value):
        if isinstance(value,complex):return {'real':value.real,'imag':value.imag} if value.imag else value.real
        return value.item() if hasattr(value,'item') else value
    records=[{'vertices':[u,v],'weight':number(d.get('weight',1))} for u,v,d in graph.edges(data=True)]
    stored=pos if pos is not None else graph.graph.get('pos')
    return document(list(graph),records,directed=graph.is_directed(),weighted=any(weight_parts(e['weight'])!=(1,0) for e in records),
        positions=[list(stored[v]) for v in graph] if stored is not None else None,style=graph.graph.get('style'))


def from_hypergraph(graph,pos=None):
    """Preserve positive hyperedge weights and stored coordinates as JSON data."""
    stored=pos if pos is not None else getattr(graph,'_pos',None)
    records=[{'vertices':list(e),'weight':float(w)} for e,w in zip(graph.Edges,graph.weights)]
    return document(graph.vertices(),records,graph_type='hypergraph',weighted=any(e['weight']!=1 for e in records),
        positions=[list(stored[v]) for v in graph.Vertices] if stored else None)


def same_numbered_structure(left,right):
    """Match a verified original to its 0-based calculation input, including zero weights."""
    def signature(graph):
        index={v:i for i,v in enumerate(graph.vertices)};edges=set()
        for edge in graph.edges:
            members=tuple(index[v] for v in edge['vertices'])
            members=members if graph.directed else tuple(sorted(members))
            edges.add((members,*weight_parts(edge['weight'])))
        return graph.order,graph.graph_type,graph.directed,frozenset(edges)
    return signature(left)==signature(right)


def tokens(text,line=None):
    """Quoted JSON strings retain string identity; bare canonical integers become ints."""
    result=[];index=0;decoder=json.JSONDecoder()
    while index<len(text):
        if text[index].isspace() or text[index]==',':index+=1;continue
        if text[index]=='"':
            try:value,end=decoder.raw_decode(text[index:])
            except json.JSONDecodeError:raise GraphInputError('字符串双引号未闭合或转义无效。',line) from None
            if not isinstance(value,str):raise GraphInputError('引号中的标签须为字符串。',line)
            index+=end
            if index<len(text) and not (text[index].isspace() or text[index]==','):raise GraphInputError('顶点之间请用空格或逗号分隔。',line)
        else:
            match=re.match(r'[^\s,]+',text[index:]);value=match.group();index+=len(value)
            if re.fullmatch(r'-?(0|[1-9][0-9]*)',value):
                try:value=int(value)
                except ValueError:raise GraphInputError('整数标签过长。',line) from None
        try:result.append(_label(value))
        except GraphInputError as error:raise GraphInputError(str(error),line) from None
    return result


def _vertex_text(text):
    result=[]
    for number,line in enumerate(text.splitlines(),1):result.extend(tokens(line,number))
    if len(result)>128 or len(set(result))!=len(result):raise GraphInputError('顶点列表重复或超过128点。')
    return result


def _split_weight(text):
    quoted=False;escaped=False
    for index,char in enumerate(text):
        if char=='"' and not escaped:quoted=not quoted
        if char=='|' and not quoted:return text[:index],text[index+1:]
        escaped=char=='\\' and not escaped
    return text,None


def _edge_text(text,vertices,kind,directed,weighted,name):
    edges=[];inferred=[];seen={};locations=[]
    for number,line in enumerate(text.splitlines(),1):
        if not line.strip():continue
        members,weight=_split_weight(line.strip());members=members.strip()
        if members.startswith(('{','(','[')):
            closing={'{':'}','(':')','[':']'}[members[0]]
            if not members.endswith(closing):raise GraphInputError('边的括号不匹配。',number)
            members=members[1:-1]
        values=tokens(members,number)
        if not 2<=len(values)<=128 or (kind=='graph' and len(values)!=2):raise GraphInputError('普通边每行2点；超边每行至少2点。',number)
        if len(set(values))!=len(values):raise GraphInputError('边内顶点重复或自环。',number)
        if vertices and not set(values)<=set(vertices):raise GraphInputError('此边含完整顶点列表中没有的标签。',number)
        key=tuple(values) if directed else frozenset(values)
        if key in seen:raise GraphInputError(f'与第{seen[key]}行重复。',number)
        seen[key]=number
        if weight is not None and not weighted:raise GraphInputError('此行指定了边权，请勾选“带权”。',number)
        try:
            w=1 if weight is None else strict_json(weight.strip());real,imag=weight_parts(w)
            if kind=='hypergraph' and (imag or real<=0):raise GraphInputError('超边权须为正实数。')
        except GraphInputError as error:raise GraphInputError(str(error),number) from None
        edges.append({'vertices':values,'weight':w});locations.append(number)
        inferred.extend(v for v in values if v not in inferred)
        if len(edges)>(128 if kind=='hypergraph' else 1024) or len(inferred)>128:raise GraphInputError('超过图输入点/边预算。',number)
    return document(vertices or inferred,edges,graph_type=kind,directed=directed,weighted=weighted,name=name)


def _matrix(text):
    if text.lstrip().startswith('['):rows=strict_json(text)
    else:
        rows=[]
        for number,line in enumerate(text.splitlines(),1):
            if line.strip():
                try:rows.append([strict_json(value) for value in re.split(r'[\s,]+',line.strip())])
                except GraphInputError as error:raise GraphInputError(str(error),number) from None
    if not isinstance(rows,list) or not 1<=len(rows)<=128 or any(not isinstance(row,list) or not 1<=len(row)<=128 for row in rows) or len({len(row) for row in rows})!=1:raise GraphInputError('矩阵须为不超过128×128的非空矩形数组。')
    for row in rows:
        for value in row:weight_parts(value)
    return rows


def _matrix_document(text,vertices,kind,directed,weighted,name,incidence):
    rows=_matrix(text);n=len(rows);m=len(rows[0]);edges=[]
    if vertices and len(vertices)!=n:raise GraphInputError('完整顶点列表长度须等于矩阵行数。')
    vertices=vertices or list(range(n))
    if incidence:
        if kind!='hypergraph' or directed:raise GraphInputError('关联矩阵请选无向超图：行是顶点、列是超边。')
        if any(type(value) not in (int,float) or value not in (0,1) for row in rows for value in row):raise GraphInputError('关联矩阵仅接受0/1；超边权请通过带权边表或图JSON填写。')
        for j in range(m):
            members=[vertices[i] for i in range(n) if rows[i][j]==1]
            if len(members)<2:raise GraphInputError(f'第{j+1}列不足2个关联点。')
            edges.append({'vertices':members,'weight':1})
    else:
        if kind!='graph' or n!=m:raise GraphInputError('邻接矩阵须为普通图的方阵。')
        for i in range(n):
            for j in range(n):
                real,imag=weight_parts(rows[i][j])
                if i==j and (real or imag):raise GraphInputError(f'第{i+1}个对角元不为0；当前不支持自环。')
                if not weighted and (imag or real not in (0,1)):raise GraphInputError('无权邻接矩阵仅接受0/1；其他值请勾选带权。')
                if not directed:
                    opposite=weight_parts(rows[j][i])
                    if (real,-imag)!=opposite:raise GraphInputError(f'第{i+1}行、第{j+1}列：无向邻接矩阵须对称，复权须共轭对称。')
                if (real or imag) and (directed or i<j):edges.append({'vertices':[vertices[i],vertices[j]],'weight':weight_value(real,imag)})
    return document(vertices,edges,graph_type=kind,directed=directed,weighted=weighted,name=name)


def _graph6(text,vertices,name):
    data=text.strip().encode('ascii',errors='strict')
    if data.startswith(b'>>graph6<<'):data=data[10:]
    if not data or any(value<63 or value>126 for value in data):raise GraphInputError('graph6必须是单张图的有效ASCII编码。')
    values=[value-63 for value in data];header=1
    if values[0]<63:n=values[0]
    else:
        if len(values)<4:raise GraphInputError('graph6头不完整。')
        if values[1]<63:n=(values[1]<<12)+(values[2]<<6)+values[3];header=4
        else:
            if len(values)<8:raise GraphInputError('graph6头不完整。')
            n=0
            for value in values[2:8]:n=(n<<6)+value
            header=8
    if n>128 or len(values)!=header+(n*(n-1)//2+5)//6:raise GraphInputError('graph6超过128顶点或数据长度与头部不符。')
    if vertices and len(vertices)!=n:raise GraphInputError('graph6的标签数与顶点数不符。')
    labels=vertices or list(range(n));g=nx.from_graph6_bytes(data)
    return document(labels,[{'vertices':[labels[u],labels[v]],'weight':1} for u,v in g.edges()],name=name)


def parse_graph(text,format='edge_list',graph_type='graph',vertices_text='',directed=False,weighted=False,name='未命名图'):
    """Explicit edge/adjacency/incidence/graph6/JSON grammar, with no inference of direction.

    Adjacency zero means absence, so zero-weight edges require edge-list/JSON.
    Incidence is unweighted 0/1; each column is one hyperedge. JSON documents
    preserve their own flags and complete vertex order, irrespective of UI flags.
    """
    if not isinstance(text,str) or len(text)>MAX_TEXT or not isinstance(vertices_text,str) or len(vertices_text)>32768:raise GraphInputError('输入文件最多1MB，顶点列表最多32KB。')
    if graph_type not in ('graph','hypergraph') or type(directed) is not bool or type(weighted) is not bool:raise GraphInputError('图类型或开关无效。')
    vertices=_vertex_text(vertices_text)
    if format=='edge_list':return _edge_text(text,vertices,graph_type,directed,weighted,name)
    if format in ('adjacency','incidence'):return _matrix_document(text,vertices,graph_type,directed,weighted,name,format=='incidence')
    if format=='graph6':
        if graph_type!='graph' or directed or weighted:raise GraphInputError('graph6只表示无向无权普通图。')
        try:return _graph6(text,vertices,name)
        except UnicodeEncodeError:raise GraphInputError('graph6必须是ASCII编码。') from None
    if format!='json':raise GraphInputError('未知图输入格式。')
    data=strict_json(text)
    if isinstance(data,dict) and data.get('format')==FORMAT:return GraphDocument(data)
    if not isinstance(data,dict):raise GraphInputError('图JSON须为对象。')
    if data.get('format')=='graph-research-layout':
        if not isinstance(data.get('vertices'),list) or len(data['vertices'])>128 or not isinstance(data.get('edges'),list) or len(data['edges'])>128 or any(not isinstance(e,list) for e in data['edges']) or sum(map(len,data['edges']))>2048:raise GraphInputError('旧布局超过128顶点/128边/2048关联限制，或边表格式无效。')
        from graph_research.rendering.editor import validate_layout
        h,pos=validate_layout(data)
        kind='hypergraph' if any(len(e)>2 for e in h.Edges) else graph_type
        return document(h.vertices(),[{'vertices':list(e),'weight':float(w)} for e,w in zip(h.Edges,h.weights)],graph_type=kind,
                        weighted=any(w!=1 for w in h.weights),positions=[pos[v].tolist() for v in h.vertices()],name=name)
    if 'kind' in data:
        if set(data)-{'kind','n','edges'}:raise GraphInputError('普通图参数JSON只接受kind/n/edges。')
        from graph_research.graphs import make_graph
        if type(data.get('n')) is not int or not 1<=data['n']<=128:raise GraphInputError('图参数JSON须明确1..128的n。')
        g=make_graph(**data)
        return document(list(g),[{'vertices':list(e),'weight':1} for e in g.edges()],name=name)
    if set(data)-{'edges','vertices','weights','directed','weighted','name'} or not isinstance(data.get('edges'),list):raise GraphInputError('请导入统一图对象，或含edges/vertices/weights的图参数JSON。')
    edges=data['edges']
    if len(edges)>1024 or any(not isinstance(edge,list) or not 2<=len(edge)<=128 for edge in edges):raise GraphInputError('JSON边表每条边须为2..128个标签的列表，且至多1024条。')
    for edge in edges:
        for value in edge:_label(value)
    labels=data.get('vertices',vertices or list(dict.fromkeys(v for e in edges for v in e)))
    weights=data.get('weights',[1]*len(edges))
    if not isinstance(weights,list) or len(weights)!=len(edges):raise GraphInputError('weights须与边表等长。')
    return document(labels,[{'vertices':edge,'weight':w} for edge,w in zip(edges,weights)],graph_type=graph_type,
                    directed=data.get('directed',directed),weighted=data.get('weighted',weighted or 'weights' in data),name=data.get('name',name))


def graph_family(graph_type,family,n=5,m=3,k=3):
    """Bounded native constructors reused by the graphical form."""
    if graph_type=='graph':
        if type(n) is not int or not 1<=n<=128:raise GraphInputError('顶点数须为1..128。')
        from graph_research.graphs import make_graph
        g=make_graph(family,n)
        return document(list(g),[{'vertices':list(edge),'weight':1} for edge in g.edges()],name=f'{family}({n})')
    if graph_type!='hypergraph' or type(m) is not int or type(k) is not int or not 1<=m<=32 or not 2<=k<=8 or m*(k-1)+1>128:raise GraphInputError('超图边数1..32、一致度2..8，结果至多128顶点。')
    from graph_research.hypergraphs import HyperPath,HyperStar,HyperCycle
    functions={'path':HyperPath,'star':HyperStar,'cycle':HyperCycle}
    if family not in functions:raise GraphInputError('未知超图族。')
    h=functions[family](m,k)
    return document(h.vertices(),[{'vertices':list(edge),'weight':1} for edge in h.Edges],graph_type='hypergraph',name=f'{family}({m},{k})')
