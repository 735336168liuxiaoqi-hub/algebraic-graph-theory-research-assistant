"""Chinese UI vocabulary. Display strings never replace tool argument values."""

PARAMETERS={
    'reference':'参考图','candidate':'待核验候选图','strategy':'搜索策略','candidates':'本轮候选上限','incumbent':'当前最好可行图','seen':'已访问图记录','cursor':'枚举续算游标',
    'graph_document':'完整图与绘图样式',
    'total_steps':'路径总步数','right_steps':'向右步序号','bounds':'矩形边界',
    'fill':'填充矩形','row_labels':'行标签','column_labels':'列标签','fixed_vertices':'固定顶点',
    'root':'根顶点','iterations':'布局迭代次数','angle':'逆时针旋转角度','scale':'等比例缩放倍数','offset':'平移向量',
    'board':'可放车棋盘','side':'凯莱图乘法侧',
    'diagram':'论文示意图',
    'tolerance':'相对残差目标','max_iterations':'最大迭代数','initial_vector':'正初始向量','method':'求解方法',
    'directed':'有向图','degree_mode':'加权度约定','exact':'精确多项式','graph_type':'构图对象','base':'初始图描述','steps':'构图步骤','assertions':'结构断言',
    'edge_indices':'有向超边序列','cases':'批量研究项目','calculations':'计算项目','plot':'输出图集','expression':'数学表达式','lower':'求和下界','upper':'求和上界',
    'center':'展开中心','order':'展开阶数','row_sizes':'行块尺寸','column_sizes':'列块尺寸','row_order':'行块排列','column_order':'列块排列',
    'polynomials':'多项式系数组','search_budget':'搜索状态上限','parameter':'研究参数名','values':'有限参数取值','digits':'初始隔离位数',
    'generators':'生成元置换','actions':'行列变换步骤','row_index':'拆分行序号','row_terms':'拆分行向量','replacement':'边的替换图','endpoints':'替换图端点','roots':'共享根集',
    'a':'区间左端点','alpha':'α参数','arcs':'有向边表','attachments':'附接配置','b':'区间右端点',
    'blocks':'分块划分','coefficients':'系数列表','core_k':'核心阶数','count':'操作数量','data':'张量数据',
    'degrees':'度序列','edge_index':'边序号','edge_labels':'显示边编号','edge_paths':'按主干边附接',
    'edges':'边表','edit_edges':'操作边表','end':'终点','estimate_only':'仅估计规模','exponent':'逐项幂指数',
    'family':'构造族','forcing':'递推右端项','groups':'顶点分组','initial_values':'连续初值','k':'参数k',
    'kind':'图类型','labels':'新顶点标签','layout':'布局方式','left':'左侧图','left_lengths':'左端路长',
    'legend':'显示图例','length':'路或圈长度','lengths':'路长列表','limit':'结果数量上限','m':'边数或主干边数',
    'matrix':'矩阵类型','n':'顶点数','operation':'操作','parameters':'整数参数名','parts':'分拆列表',
    'pendant_length':'悬挂路长','positions':'顶点坐标','power':'图幂次数','q':'字母表大小','query':'查询关键词',
    'rank':'张量阶数','rhs':'右端向量','right':'右侧图','right_lengths':'右端路长','seed':'随机种子',
    'start':'起点','subdivisions':'每边插入顶点数','symbolic_alpha':'符号α','terms':'输出项数','variable':'下标变量',
    'vertex':'目标顶点','vertex_degrees':'独立度对角','vertex_labels':'显示顶点标签','vertex_paths':'按共享顶点附接',
    'vertices':'顶点列表','weighted_incidence':'输出赋权关联矩阵','weights':'超边权重'}

OPTIONS={
    'enumerate':'分段枚举','edge_move':'谱向量引导换边','rewire':'随机换边','random':'随机重新构图',
    'grid_path':'逐步格路径','lattice_path':'按步序号生成格路径','rectangle':'矩形绘图','chessboard':'矩阵棋盘',
    'spectral':'谱布局','tree':'树形层次布局','transform':'旋转缩放和平移','align_horizontal':'水平对齐','align_vertical':'竖直对齐',
    'rook_polynomial':'棋盘车多项式','right':'右乘','left':'左乘','twosided':'双侧乘法',
    'replace_edges':'批量用图替换边','partial_product':'局部笛卡尔积',
    'export':'导出示意图','expand':'展开具体超图',
    'iteration':'移位幂迭代','auto':'自动选择求解方法','newton_noda':'保正牛顿–Noda迭代',
    'graph':'普通图','hypergraph':'超图','absolute':'边权模之和','sum':'实边权之和','summation':'符号求和','series':'局部级数展开',
    'extract':'提取全部分块','permute':'行列块重排','multiply':'按块求和乘积','companion_blocks':'多项式伴随块构造',
    'cycle_index':'置换群循环指标','cayley_graph':'凯莱有向图','elementary':'初等行列变换','split_row':'行列式拆行','replace_edge':'用图替换边','attach_star':'共享根集附超边','laplacian_equations':'拉普拉斯张量特征方程',
    'path':'路径图','cycle':'圈图','complete':'完全图','star':'星图','empty':'无边图','edges':'自定义边表',
    'spring':'弹簧布局','circular':'圆周布局',
    'A':'邻接矩阵','L':'拉普拉斯矩阵','Q':'无符号拉普拉斯矩阵','D':'距离矩阵',
    'DL':'距离拉普拉斯矩阵','N':'归一化拉普拉斯矩阵','ABC':'原子键连通矩阵','S':'塞德尔矩阵','alpha':'α矩阵','H':'厄米邻接矩阵',
    'partition_number':'整数分拆数','divisibility_matrix':'整除矩阵','mobius_matrix':'莫比乌斯矩阵','cycle_type_count':'指定循环型的置换数',
    'complement':'补图','line_graph':'线图','power':'图的幂','delete_vertices':'删除顶点','delete_edges':'删除边','add_edges':'添加边',
    'seidel_switch':'塞德尔切换','core':'核心子图','relabel':'顶点重编号','subdivide_edges':'指定边剖分',
    'rref':'行最简形','inverse':'逆矩阵','determinant':'行列式','charpoly':'特征多项式',
    'symmetrize':'张量对称化','transpose':'张量转置','entrywise_power':'张量逐项幂','properties':'张量性质',
    'theta':'西塔图','caterpillar':'毛毛虫图','cactus':'仙人掌图','hamming':'汉明图','random_k_cyclic':'随机指定圈秩图',
    'energy':'图能量','angles':'图角','projectors':'谱投影','alpha_charpoly':'α特征多项式',
    'isomorphic':'图同构判断','cospectral':'同谱判断','subgraph_count':'子图份数',
    'cycles':'枚举圈','paths':'枚举简单路','hamilton':'枚举哈密顿圈','degree_realizations':'给定度序列的非同构实现',
    'incidence':'关联矩阵','distances':'距离矩阵','orbits':'顶点轨道','equations':'张量特征方程','matching_poly':'匹配多项式',
    'attach_path':'附接悬挂路','expand_edges':'超边扩张','clone_all':'顶点克隆到原边','clone_cartesian':'顶点克隆组合展开',
    'merge':'合并顶点','subdivide':'超边剖分','induced':'诱导子超图',
    'vertex_starlike':'点心像星超树','edge_starlike':'边心像星超树','bicyclic_c1':'第一类双圈超图',
    'bicyclic_c2':'第二类双圈超图','bicyclic_c3':'第三类双圈超图',
    'gee':'双端分根悬挂路族','gev':'左分根右共根悬挂路族','gvv':'双端共根悬挂路族',
    'gwg':'指定分布悬挂路族','ca':'圈叶点附路族','cva':'圈交点附路族'}

HINTS={
    'iteration':'使用稳定对数求值的移位幂迭代，可按顶点顺序指定正初值。','auto':'先尝试两块等价划分；高α使用Newton–Noda，普通区域先幂迭代，预算内停滞时切换。',
    'newton_noda':'保持向量为正的Newton–Noda迭代；结合对数求值、系统缩放、高α延拓与按需60位精化，共享总迭代预算。',
    'path':'构造路径图，相邻顶点依次连接。','cycle':'构造闭合的圈图。','complete':'每两个不同顶点之间都有一条边。',
    'star':'一个中心顶点连接所有叶顶点。','empty':'只含指定顶点，不含任何边。','edges':'使用填写的边表和顶点总数，保留孤立点。',
    'spring':'使用关联图的弹簧布局，分别排列连通分量。','circular':'按顶点顺序排列在圆周上。',
    'A':'邻接关系对应的矩阵。','L':'顶点度对角矩阵减去邻接矩阵。','Q':'顶点度对角矩阵加上邻接矩阵。',
    'D':'顶点间最短路距离组成的矩阵，需要连通图。','DL':'传输度对角矩阵减距离矩阵，需要连通图。',
    'N':'按顶点度归一化的拉普拉斯矩阵，孤立点对应行列为零。',
    'ABC':'按端点度赋权的原子键连通邻接矩阵。','S':'非对角元在相邻时为−1、非相邻时为1，主对角为0。',
    'alpha':'α倍度对角矩阵与(1−α)倍邻接矩阵之和。',
    'H':'以复数记录有向邻接关系，得到厄米矩阵。'}


def parameter_title(definition,name):
    """Translate reviewed native names, or use the extension's explicit title."""
    if definition.get('documentation',{}).get('coverage')!='reviewed_native':
        return definition.get('parameters',{}).get('properties',{}).get(name,{}).get('title',name)
    if definition.get('name')=='hypergraph_schematic' and name=='parameters':return '展开赋值'
    tool=definition.get('name','')
    if tool=='combinatorial_plot':
        special={'matrix':'棋盘数值矩阵','steps':'路径步序列'}
        if name in special:return special[name]
    if tool=='graph_layout' and name=='vertices':return '参与对齐的顶点'
    if tool=='graph_recipe' and name=='parameters':return '整数参数值'
    if tool=='symbolic_analysis':
        special={'parameters':'符号参数名','variable':'求和或展开变量'}
        if name in special:return special[name]
    if tool=='block_matrix_analysis':
        special={'matrix':'左侧矩阵','right':'右侧矩阵','parameters':'整数符号参数名'}
        if name in special:return special[name]
    if tool=='linear_recurrence':
        special={'start':'起始下标','coefficients':'递推系数','variable':'下标变量'}
        if name in special:return special[name]
    if name=='k' and tool=='generate_hypergraph':return '一致度'
    if name=='k' and tool=='graph_construction':return '圈秩或汉明维数'
    if name=='k' and tool=='combinatorial_calculation':return '分拆份数'
    if name=='rank' and tool=='hypergraph_transform':return '新边目标大小'
    if name=='matrix' and tool in ('matrix_analysis','exact_matrix_operation','quotient_matrix','integer_linear_system'):return '矩阵'
    if name=='matrix' and tool=='hypergraph_tensor_charpoly':return '张量类型'
    if name=='n' and tool=='combinatorial_calculation':return '整数参数n'
    if name=='n' and tool=='graph_construction':return '顶点数或主干长度'
    return PARAMETERS.get(name,name)


def option_presentation(definition,parameter,value):
    """Return contextual label and brief help, reusing reviewed branch contracts."""
    tool=definition.get('name','');key=str(value);title=OPTIONS.get(key,key)
    documentation=definition.get('documentation',{})
    if documentation.get('coverage')!='reviewed_native':
        field=definition.get('parameters',{}).get('properties',{}).get(parameter,{})
        labels=field.get('x-enum-labels',{});descriptions=field.get('x-enum-descriptions',{})
        title=labels.get(key,key) if isinstance(labels,dict) else key
        hint=descriptions.get(key,field.get('description','')) if isinstance(descriptions,dict) else field.get('description','')
        return str(title),str(hint or key).replace('\n',' ')[:220]
    branch=documentation.get('operations' if parameter=='operation' else 'variants',{})
    description=branch.get(key) if parameter in ('operation','family') else None
    if parameter=='matrix' and tool in ('hypergraph_tensor_charpoly',):
        title={'A':'邻接张量','L':'拉普拉斯张量','Q':'无符号拉普拉斯张量','alpha':'α张量'}.get(key,title)
        formula={'A':'超边邻接对应的张量','L':'度对角张量减去邻接张量','Q':'度对角张量加上邻接张量','alpha':'α倍度对角张量加(1−α)倍邻接张量'}
        description=formula.get(key,title)+'；仅适用于一致超图，精确消元受规模限制。'
    if parameter=='matrix' and tool=='directed_graph_spectrum':
        title={'A':'有向邻接矩阵','L':'出度拉普拉斯矩阵','alpha':'有向α矩阵'}.get(key,title)
        description={'H':'单向弧使用±i、双向弧使用1，构造厄米邻接矩阵。',
                     'A':'按弧的方向构造邻接矩阵，可返回复特征值。',
                     'L':'出度对角矩阵减去有向邻接矩阵。',
                     'alpha':'α倍出度对角矩阵加(1−α)倍有向邻接矩阵。'}.get(key,title)
    if tool=='hypergraph_structure' and key=='line_graph':title='超图线图'
    if tool=='combinatorial_calculation' and parameter=='side':
        description={'right':'对每个群元素g添加g→g·s，s遍历生成元；省去重边和自环。',
                     'left':'对每个群元素g添加g→s·g，s遍历生成元；省去重边和自环。',
                     'twosided':'同时加入左乘和右乘生成的弧；重复弧合并，自环省略。'}[key]
    if tool=='generate_hypergraph' and key in ('path','star','cycle'):
        title={'path':'松路','star':'超星','cycle':'松圈'}[key]
    hint=description or HINTS.get(key) or definition.get('parameters',{}).get('properties',{}).get(parameter,{}).get('description','')
    return title,str(hint or title).replace('\n',' ')[:220]
