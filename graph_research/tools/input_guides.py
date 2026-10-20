"""Human input help derived from the live tool schemas and reviewed examples.

Field examples illustrate one parameter's format. Only complete examples are
presented as callable parameter sets; unrelated field examples must not be
combined blindly. No tool or model is executed to produce this help.
"""
import copy
import json
import math

import jsonschema


NOTES={
    'combinatorial_plot':'先选择操作。逐步格路径steps中0向上、1向右；按步序号生成时right_steps从0计数。棋盘matrix按行输入，非零格着色，行号沿y轴自下向上；矩形bounds为[xmin,ymin,xmax,ymax]。',
    'graph_layout':'坐标positions为[{"vertex":0,"xy":[0,0]},...]，填写时须覆盖全部顶点。固定弹簧布局还需fixed_vertices；对齐用vertices选择部分顶点。坐标变换顺序为绕原点缩放、逆时针旋转（度）、最后平移。结果可继续拖动编辑或传入TikZ。',
    'linear_recurrence':'coefficients[i]乘a(n+i)，等号右端为forcing；初值从start起连续给出且数量等于阶数。例如[-1,-1,1]和[0,1]是Fibonacci递推。',
    'integer_linear_system':'matrix*x=rhs，未知量与parameters都取整数；conditional必须检查conditions，不能直接当作无条件有解。',
    'generate_hypergraph':'基础族用m/k或lengths；gee/gev/gvv用left_lengths/right_lengths；ca/cva用pendant_length；gwg用edge_paths/vertex_paths。所有长度按边数，定制族保持k。',
    'hypergraph_spectrum':'edges每条边大小相同、超图连通；alpha取0≤alpha≤1，1为度对角端点。weights按边顺序，vertex_degrees按顶点顺序，长度必须匹配；不填写时使用默认权和度。',
    'graph_edit':'core用core_k；relabel用labels；subdivide_edges用edit_edges/subdivisions；replace_edge用恰好一条edit_edges、replacement和endpoints；replace_edges可给多条边，每条使用独立替换图副本；partial_product用vertices选择顶点，replacement为笛卡尔积另一因子。返回graph_spec可联动整数编号工具。',
    'graph_construction':'先选family，再按该族含义填写：theta用三条路径长度lengths；caterpillar用主干长度n和attachments；cactus用圈长列表lengths及seed；hamming用k和q；random_k_cyclic用n、k、seed。',
    'graph_spectral_analysis':'先选operation。alpha_charpoly分支可选symbolic_alpha=true；其他谱分析分支使用其对应数值输入。',
    'graph_enumeration':'paths填写start/end/length；cycles填写length；degree_realizations填写degrees。达到limit不代表已经枚举完整。',
    'compare_graphs':'left和right各填一个图的JSON对象，例如{"kind":"path","n":3}；不是直接填边表。',
    'directed_graph_spectrum':'arcs中的[u,v]表示u→v，顺序有意义；n给出总顶点数，标签为0..n-1。',
    'hypergraph_transform':'先选operation；attach_path用vertex/count/rank，attach_star用roots/count/rank（新边共享根集），expand_edges用count，clone_all/clone_cartesian用vertex/count，merge用groups，subdivide用edge_index/count，induced用vertices。参数的具体含义和限制以各字段说明为准。',
    'hypergraph_structure':'incidence等结构分支可使用非一致边表；equations只生成方程，不自动求解。涉及张量的分支仍需检查一致性。',
    'hypergraph_tensor_charpoly':'只研究一致超图张量。空边表时必须另外给出n和rank；有边时可推断rank。matrix=alpha时可输入分数alpha或选symbolic_alpha；estimate_only=true只估计规模，不返回已计算的多项式。',
    'tensor_charpoly':'data是按各轴嵌套的立方张量数据，不是超边表；例如二维2×2数组代表二阶张量。estimate_only=true只估计规模。',
    'tensor_spectrum':'data是稠密非负立方张量，每个轴的长度相同；不要直接把超边列表放入data。二维例子代表二阶张量。',
    'tensor_operation':'data每层数组对应一个轴；exponent仅在entrywise_power分支读取，不表示张量矩阵乘法。',
    'matrix_analysis':'matrix按行输入；各行长度一致。可填0.5等小数，不使用Python表达式或分数字符串。',
    'exact_matrix_operation':'matrix按行输入整数或小数；elementary用actions步骤列表，split_row用row_index/row_terms并自动补余项。矩阵不接受分数字符串、符号或复数，小数按精确十进制有理数解释。',
    'quotient_matrix':'blocks是从0开始的矩阵行列索引分组，必须构成完整划分；不等价时不能把商谱视为原谱的可靠子集。',
    'polynomial_roots':'coefficients按最高次到常数项填写，中间缺项补0；例如[1,0,-1]表示x²-1，区间端点需a≤b。',
    'combinatorial_calculation':'分拆等原有分支使用n/k/parts。cycle_index/cayley_graph用generators：每行是一个0起始置换像列表，先生成完整群；Cayley可选side左乘、右乘或双侧，结果n/arcs可联动有向谱工具。rook_polynomial使用board矩形0/1矩阵：1可放车，0禁用，每维至多10。',
}


def compact(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def _valid(value,schema):
    try:return jsonschema.Draft202012Validator(schema).is_valid(value)
    except (ValueError,TypeError,jsonschema.SchemaError):return False


def _minimal(schema):
    if 'const' in schema:return schema['const']
    if 'enum' in schema:return schema['enum'][0]
    if 'default' in schema and _valid(schema['default'],schema):return schema['default']
    for branch in schema.get('anyOf',schema.get('oneOf',[])):
        value=_minimal(branch)
        if _valid(value,schema):return value
    kind=schema.get('type')
    if isinstance(kind,list):return _minimal({**schema,'type':kind[0]})
    if kind=='boolean':return True
    if kind in ('integer','number'):
        value=max(1,schema.get('minimum',1))
        if 'exclusiveMinimum' in schema:value=max(value,schema['exclusiveMinimum']+1)
        if 'maximum' in schema:value=min(value,schema['maximum'])
        return value
    if kind=='string':return '示例'
    if kind=='array':return [_minimal(schema.get('items',{})) for _ in range(max(1,schema.get('minItems',1)))]
    if kind=='object':return {key:_minimal(schema['properties'][key]) for key in schema.get('required',[]) if key in schema.get('properties',{})}
    return None


def _vertices(arguments):
    if 'vertices' in arguments:return arguments['vertices']
    if 'edges' in arguments:return list(dict.fromkeys(v for edge in arguments['edges'] for v in edge))
    return list(range(min(arguments.get('n',3),16)))


def field_example(definition,name):
    schema=definition['parameters']['properties'][name]
    examples=definition.get('documentation',{}).get('examples',[])
    for example in examples:
        if name in example['arguments'] and _valid(example['arguments'][name],schema):return copy.deepcopy(example['arguments'][name])
    base=examples[0]['arguments'] if examples else {};vertices=_vertices(base)
    positions=[{'vertex':v,'xy':[round(math.cos(2*math.pi*i/max(1,len(vertices))),4),round(math.sin(2*math.pi*i/max(1,len(vertices))),4)]} for i,v in enumerate(vertices)]
    hints={'initial_vector':[1/max(1,len(vertices))]*len(vertices),'edges':[[0,1],[1,2]],'arcs':[[0,1],[1,2]],'vertices':vertices,'vertex':vertices[0] if vertices else 0,
           'graph_document':{'format':'graph-research-graph','version':1,'graph_type':'graph','directed':True,'weighted':True,'vertices':[0,1,2],'edges':[{'vertices':[0,1],'weight':2}], 'style':{'font_size':10,'weight_labels':True}},
           'weights':[1]*len(base.get('edges',[[0,1]])),'vertex_degrees':[1]*len(vertices),
           'positions':positions,'labels':['a','b','c'],'left_lengths':[1],'right_lengths':[1],'edge_paths':[{'edge_index':0,'lengths':[1]}],'vertex_paths':[{'vertex':1,'lengths':[1]}],'lengths':[2,2,2],'groups':[[0,1]],'blocks':[[0],[1]],
           'attachments':[[0,3]],'edit_edges':[[0,2]],'degrees':[2,2,2],'parts':[2,1],
           'data':[[0,1],[1,0]],'matrix':[[1,2],[3,4]],'left':{'kind':'path','n':3},'right':{'kind':'star','n':3},
           'n':len(vertices) or 3,'rank':len(base['edges'][0]) if base.get('edges') else 3}
    candidates=[]
    if 'default' in schema:candidates.append(schema['default'])
    if name in hints:candidates.append(hints[name])
    candidates.append(_minimal(schema))
    return next((copy.deepcopy(value) for value in candidates if _valid(value,schema)),None)


def format_hint(schema):
    """Describe the exact terminal grammar, not just the JSON type name."""
    if 'enum' in schema:return '填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：'+', '.join(str(v) for v in schema['enum'])
    if 'anyOf' in schema or 'oneOf' in schema:return ' 或 '.join(format_hint(s) for s in schema.get('anyOf',schema.get('oneOf',[])))
    kind=schema.get('type')
    if isinstance(kind,list):return ' 或 '.join(format_hint({**schema,'type':v}) for v in kind)
    if kind=='boolean':return '填写 是/否 或 true/false；逐项填写也支持1/0。'
    if kind=='integer':text='填写一个整数，不填单位或Python表达式。'
    elif kind=='number':text='填写整数或小数，不填单位、算式、NaN或Infinity。'
    elif kind=='string':text='填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。'
    elif kind=='object':text='填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。'
    elif kind=='array':
        child=schema.get('items',{});child_kind=child.get('type')
        if child_kind=='array' and child.get('items',{}).get('type') in ('integer','number'):
            text='填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。'
            if 'minItems' in child:text+=' 每行至少'+str(child['minItems'])+'项。'
            if 'maxItems' in child:text+=' 每行最多'+str(child['maxItems'])+'项。'
            text+=' 每项填写'+('整数。' if child['items']['type']=='integer' else '整数或小数。')
        elif child_kind in ('integer','number'):
            text='填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。'
        elif child_kind=='object':text='填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。'
        else:text='填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。'
    else:text='填写符合此工具参数定义的JSON数据。'
    constraints=[]
    for key,label in [('minimum','≥'),('exclusiveMinimum','>'),('maximum','≤'),('exclusiveMaximum','<')]:
        if key in schema:constraints.append(label+str(schema[key]))
    if 'minItems' in schema:constraints.append('至少'+str(schema['minItems'])+'项')
    if 'maxItems' in schema:constraints.append('最多'+str(schema['maxItems'])+'项')
    if 'maxLength' in schema:constraints.append('最多'+str(schema['maxLength'])+'字符')
    if constraints:text+=' 范围：'+'，'.join(constraints)+'。'
    return text


def input_guide(definition):
    parameters=definition['parameters'];required=set(parameters.get('required',[]));fields=[]
    for name,schema in parameters.get('properties',{}).items():
        example=field_example(definition,name)
        if name in required:omission='必填，不能留空；从示例开始时可回车保留已填值。'
        elif 'default' in schema:omission='可选；未填写过时回车使用默认值'+compact(schema['default'])+'；从示例开始时优先保留示例中的值。'
        else:omission='可选，无值时可留空；某些操作分支仍需要此项，见用途说明。'
        fields.append({'name':name,'required':name in required,'description':schema.get('description',''),
                       'format':format_hint(schema),'omission':omission,'example':example,
                       'input_example':example if isinstance(example,str) else compact(example) if example is not None else None})
    notes=[];properties=parameters.get('properties',{});name=definition['name']
    if 'kind' in properties and 'edges' in properties:
        notes.append('标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。')
    if name in NOTES:notes.append(NOTES[name])
    if name in ('hypergraph_plot','hypergraph_editor','hypergraph_tikz','graph_tikz'):
        notes.append('边表每项列出该边的成员；如需孤立点，vertices填写全部顶点。绘图/导出可以使用字符串标签。')
    if name=='hypergraph_plot':notes.append('简单图的每条边写成两个顶点，例如[[0,1],[1,2]]；绘图后可在结果中调整布局。')
    if 'positions' in properties:notes.append('positions可省略使用自动布局；手填时每项为{"vertex":标签,"xy":[x,y]}，必须覆盖全部顶点且坐标不能全相同。')
    complete=copy.deepcopy(definition.get('documentation',{}).get('examples',[]))
    for example in complete:jsonschema.validate(example['arguments'],parameters)
    documentation=definition.get('documentation',{})
    return {'name':name,'summary':documentation.get('summary',definition['description']),
            'preconditions':copy.deepcopy(documentation.get('preconditions',[])),
            'limits':copy.deepcopy(documentation.get('limits',[])),
            'fields':fields,'notes':notes,'examples':complete,
            'field_example_scope':'单字段例子仅说明输入格式，不会自动填入，也不能把各字段例子随意拼成一组；完整参数例子可直接作为调用输入。'}


def show_input_guide(definition,print_fn=print):
    guide=input_guide(definition)
    print_fn('\n输入说明：'+guide['summary'])
    print_fn(definition['description'])
    print_fn('前提：'+'；'.join(guide['preconditions']))
    print_fn('限制：'+'；'.join(guide['limits']).replace('模型入口','工具入口'))
    print_fn('返回：'+definition.get('documentation',{}).get('returns','以实际结果为准'))
    for note in guide['notes']:print_fn('注意：'+note)
    for field in guide['fields']:
        print_fn(field['name']+'：'+field['format']+' '+field['omission'])
    if guide['examples']:
        print_fn('完整参数输入例子（方式4可直接粘贴为一行；方式3保存为UTF-8 JSON文件）：')
        for index,example in enumerate(guide['examples']):print_fn(f'例{index+1}：'+compact(example['arguments']))
    print_fn('逐项填写时只输入当前参数的值，不要输入参数名或整组对象。示例不会自动执行。')


def render_manual(definitions):
    parts=['# 各工具输入说明与例子','',
           '选中工具后，终端会显示同源说明；每个参数前还会显示格式和输入例子。方式4粘贴完整单行JSON，方式3导入UTF-8 JSON文件；方式1/2逐项填写时只输入当前值。',
           '', '下面的单字段例子仅说明格式，不会自动填入，不能随意拼成一组。完整示例取自已有工具的验收说明；数学前提和规模限制仍然适用。','',
           '目录：','']
    for definition in definitions:parts.append(f'- [{definition["name"]}](#{definition["name"]})：'+definition['documentation'].get('summary',definition['description']))
    for definition in definitions:
        guide=input_guide(definition);name=guide['name']
        parts.extend(['',f'## {name}','',guide['summary'],''])
        parts.extend(['前提：'+'；'.join(guide['preconditions']),'',
                      '工具限制：'+'；'.join(guide['limits']).replace('模型入口','工具入口'),
                      '', '字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。',''])
        for note in guide['notes']:parts.append('- '+note)
        parts.extend(['','| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |','| --- | --- | --- | --- | --- |'])
        def cell(text):return str(text).replace('|','\\|').replace('\n',' ')
        for field in guide['fields']:
            example=field['input_example']
            parts.append('| '+' | '.join(cell(v) for v in [field['name'],field['description'],field['format'],field['omission'],('`'+example+'`') if example is not None else '参考该工具定义'])+' |')
        for i,example in enumerate(guide['examples']):
            parts.extend(['',f'完整例子 {i+1}（可直接粘贴到方式4）：','', '```json',compact(example['arguments']),'```'])
        parts.extend(['','可导入参数文件：'+f'[第一个完整例子](../examples/offline-inputs/{name}.json)'])
    return '\n'.join(parts)+'\n'
