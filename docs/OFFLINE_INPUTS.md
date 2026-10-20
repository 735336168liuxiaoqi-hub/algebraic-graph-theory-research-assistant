# 各工具输入说明与例子

选中工具后，终端会显示同源说明；每个参数前还会显示格式和输入例子。方式4粘贴完整单行JSON，方式3导入UTF-8 JSON文件；方式1/2逐项填写时只输入当前值。

下面的单字段例子仅说明格式，不会自动填入，不能随意拼成一组。完整示例取自已有工具的验收说明；数学前提和规模限制仍然适用。

目录：

- [generate_hypergraph](#generate_hypergraph)：构造基础一致超图族及六类悬挂路径研究图族，返回显式结构。
- [hypergraph_spectrum](#hypergraph_spectrum)：一致超图α谱半径：稳定幂迭代、保正Newton–Noda、度对角端点及独立证据复核。
- [graph_spectrum](#graph_spectrum)：计算普通无向简单图的矩阵和完整数值特征值列表。
- [graph_invariants](#graph_invariants)：计算图的基本结构不变量。
- [graph_characteristic_polynomial](#graph_characteristic_polynomial)：计算普通图整系数矩阵的精确特征多项式。
- [matching_polynomial](#matching_polynomial)：计算普通图匹配数生成多项式sum(m_j*x^j)。
- [matrix_analysis](#matrix_analysis)：分析有限数值矩阵的秩，方阵另给行列式和特征值。
- [polynomial_roots](#polynomial_roots)：统计并隔离闭区间内的不同实根。
- [quotient_matrix](#quotient_matrix)：按索引划分求平均商矩阵，并检查等价划分。
- [tensor_spectrum](#tensor_spectrum)：求非负立方张量的谱半径和一个Perron向量。
- [combinatorial_calculation](#combinatorial_calculation)：精确组合计数、棋盘车多项式、有限群循环指标及Cayley有向图。
- [graph_edit](#graph_edit)：普通图结构变换，包括批量用图替换边及局部笛卡尔积，返回可联动的新图描述。
- [exact_matrix_operation](#exact_matrix_operation)：有理数矩阵的精确代数、行列变换及行列式拆行。
- [tensor_operation](#tensor_operation)：执行小稠密张量的基本逐项和结构操作。
- [graph_construction](#graph_construction)：构造theta、毛毛虫、仙人掌、Hamming或指定圈秩随机图。
- [graph_symmetry](#graph_symmetry)：按自同构顶点轨道计算平均商矩阵并检查等价划分。
- [graph_spectral_analysis](#graph_spectral_analysis)：计算图能量、谱投影、图角或精确alpha特征多项式。
- [compare_graphs](#compare_graphs)：比较同构、邻接同谱或非诱导子图份数。
- [graph_enumeration](#graph_enumeration)：有预算地枚举简单路、圈、Hamilton圈或度序列实现。
- [hypergraph_structure](#hypergraph_structure)：计算超图关联、距离、带权线图、轨道、方程或匹配多项式。
- [hypergraph_transform](#hypergraph_transform)：返回添加路径、扩边、克隆、合并、剖分或诱导子超图后的结构。
- [hypergraph_quotient_spectrum](#hypergraph_quotient_spectrum)：以顶点轨道商算子约化alpha特征方程并比较Perron谱半径。
- [directed_graph_spectrum](#directed_graph_spectrum)：计算有向简单图的Hermitian或非对称矩阵及完整复数谱。
- [linear_recurrence](#linear_recurrence)：求正则线性递推的精确序列项与可验证闭式。
- [integer_linear_system](#integer_linear_system)：用Smith分解返回整数线性方程Ax=b的解族或无解/有条件状态。
- [hypergraph_tensor_charpoly](#hypergraph_tensor_charpoly)：精确Macaulay消元求一般一致超图A/L/Q/alpha的普通张量特征多项式。
- [tensor_charpoly](#tensor_charpoly)：对已有立方张量求精确普通特征多项式。
- [hypergraph_plot](#hypergraph_plot)：普通图与超图结构绘图；完整图对象保留方向、原权重和样式。
- [hypergraph_editor](#hypergraph_editor)：生成可离线使用的拖动顶点布局编辑器。
- [hypergraph_tikz](#hypergraph_tikz)：将当前超图布局导出为TikZ片段和完整.tex文档。
- [graph_tikz](#graph_tikz)：普通图TikZ导出；完整图对象支持有向、实/复权图及绘图样式。
- [hypergraph_schematic](#hypergraph_schematic)：论文示意图：符号/省略超路、花括号、TeX与SVG，或明确整数展开。
- [weighted_graph_spectrum](#weighted_graph_spectrum)：带权及复权图的矩阵与全谱。
- [graph_recipe](#graph_recipe)：用参数和现有操作组合构造图，并核验结构断言。
- [hypergraph_path_analysis](#hypergraph_path_analysis)：按起终点分析超图内部松路及关联子矩阵。
- [graph_batch_study](#graph_batch_study)：批量构图、计算与对照导出。
- [symbolic_analysis](#symbolic_analysis)：受控符号求和和局部级数。
- [block_matrix_analysis](#block_matrix_analysis)：精确分块操作及多项式伴随块。
- [graph_class_certificate](#graph_class_certificate)：广义线图判定及可复核证书。
- [graph_energy_study](#graph_energy_study)：有限整数参数域的精确能量比较。
- [research_environment](#research_environment)：只读检测三维绘图与TeX可选环境。
- [combinatorial_plot](#combinatorial_plot)：绘制格路径、矩形或数值矩阵棋盘，导出PNG/SVG/PDF。
- [graph_layout](#graph_layout)：普通图自动布局、固定顶点重排与坐标变换，导出预览及完整坐标。

## generate_hypergraph

构造基础一致超图族及六类悬挂路径研究图族，返回显式结构。

前提：无单点边；cycle在k=2时需m>=3，k>=3时需m>=2。

工具限制：m<=32、k<=8及lengths逐项/数量限制见Schema；构造族另有组合条件。；六类研究图族严格保留请求的k；根点不足报错，不隐式增加一致度；输出至多128顶点和128边。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 基础族用m/k或lengths；gee/gev/gvv用left_lengths/right_lengths；ca/cva用pendant_length；gwg用edge_paths/vertex_paths。所有长度按边数，定制族保持k。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| family | 选择构造族；各族参数含义见variants。 path: m条超边的松路。; star: m条超边的超星。; cycle: m条超边的松圈。; vertex_starlike: lengths各支路共用一个根顶点。; edge_starlike: lengths支路附在中心边的不同顶点。; bicyclic_c1: 三条路径构成的C1双圈；lengths需3项。; bicyclic_c2: C2双圈；lengths需3项。; bicyclic_c3: C3双圈；lengths需2项。; gee: 主干松路两端边，各指定1度点分别附一条悬挂路。; gev: 左端各不同1度点各附一条；右端同一1度点附多条。; gvv: 主干左右各选一个不同的端叶，各自附若干悬挂路。; gwg: 按edge_paths和vertex_paths指定主干上的悬挂路分布。; ca: 在松圈的1度点附一条路，须k>=3。; cva: 在松圈的2度交点附一条路，支持k=2普通圈。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, star, cycle, vertex_starlike, edge_starlike, bicyclic_c1, bicyclic_c2, bicyclic_c3, gee, gev, gvv, gwg, ca, cva | 必填，不能留空；从示例开始时可回车保留已填值。 | `path` |
| m | path/star/cycle及gee/gev/gvv/gwg/ca/cva的主干边数；其他family由lengths决定。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤32。 | 可选；未填写过时回车使用默认值3；从示例开始时优先保留示例中的值。 | `2` |
| k | 请求的一致度；C1/C2需>=3，C3需>=4。edge_starlike的实际一致度至少为支路数量，可能高于k。 | 填写一个整数，不填单位或Python表达式。 范围：≥2，≤8。 | 可选；未填写过时回车使用默认值3；从示例开始时优先保留示例中的值。 | `3` |
| lengths | 像星超树各支路的边数，或双圈构造的路径长度参数。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[2,2,2]` |
| left_lengths | gee/gev/gvv左端各悬挂路的边数列表；0不增加边。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,2]` |
| right_lengths | gee右端不同叶根各一条；gev/gvv右端同根多条悬挂路的长度列表。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1]` |
| pendant_length | ca/cva在圈上附接的一条悬挂路的边数。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤16。 | 可选；未填写过时回车使用默认值1；从示例开始时优先保留示例中的值。 | `2` |
| edge_paths | gwg的记录列表，如[{"edge_index":0,"lengths":[1,2]}]，依次附在该主干边的不同1度点。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：最多32项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[{"edge_index":0,"lengths":[1]}]` |
| vertex_paths | gwg的记录列表，如[{"vertex":1,"lengths":[1,2]}]，全部附在该主干共享顶点；输入顶点须度>1。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：最多32项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[{"vertex":1,"lengths":[1,2]}]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"family":"path","m":2,"k":3}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"family":"gee","m":2,"k":3,"left_lengths":[1,2],"right_lengths":[1]}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"family":"gwg","m":3,"k":3,"edge_paths":[{"edge_index":0,"lengths":[1]}],"vertex_paths":[{"vertex":1,"lengths":[1,2]}]}
```

完整例子 4（可直接粘贴到方式4）：

```json
{"family":"ca","m":3,"k":3,"pendant_length":2}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/generate_hypergraph.json)

## hypergraph_spectrum

一致超图α谱半径：稳定幂迭代、保正Newton–Noda、度对角端点及独立证据复核。

前提：非空、一致、正边权；alpha<1要求连通；alpha=1不承诺严格正向量。

工具限制：浮点求值使用logsumexp和系统缩放；Newton–Noda按需标准库Decimal 60位精化，最终向量仍为binary64。独立有理数复核针对明确的binary64输入模型；不能由谱半径精度推断向量相对误差或极小差值符号。；weighted_incidence在alpha=1不适用；与单独vertex_degrees不一致的关联标号仍不支持（只容许浮点舍入量级的差异）。赋权矩阵保留原公式，使用对数计算且不强制行归一化；严格正条目无法用binary64表示时明确失败。；Newton–Noda使用n×n缩放系统，不构造n^k张量；全部内部阶段共享单次工具的CPU、用时、内存与总迭代预算，不增加宿主工具或模型调用。未认证候选不作为成功结果。newton_noda自v0.31提供；v0.31.1补齐赋权矩阵对数计算，验收范围见发行说明。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- edges每条边大小相同、超图连通；alpha取0≤alpha≤1，1为度对角端点。weights按边顺序，vertex_degrees按顶点顺序，长度必须匹配；不填写时使用默认权和度。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多8项。 每项填写整数。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2]]` |
| alpha | αD+(1−α)A参数，0到1；1为独立度对角端点，不输出正向量。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，≤1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0.3` |
| seed | 可复现的随机种子；用于随机构造、初始向量或自动布局，不是计算精度。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤4294967295。 | 可选；未填写过时回车使用默认值42；从示例开始时优先保留示例中的值。 | `42` |
| weighted_incidence | 是否同时返回由Perron向量构造的赋权点边关联矩阵；单独指定的D若不同于加权度，此输出暂不支持。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `false` |
| weights | 按输入超边顺序排列的边权，一边一项。数值谱要求有限正权；精确消元的系数规则另见工具说明。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多256项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1]` |
| vertex_degrees | 独立指定D的对角，数值谱中须逐点有限非负，按工具返回的顶点顺序排列；不是任意顶点权乘入邻接项。省略时由边权求加权度。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多256项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,1,1]` |
| tolerance | 迭代收敛判据（相对方程残差低于它即停止），不是误差界；1e-13至0.01；默认1e-11。实际残差看返回的achieved_tolerance；可信区间看verification.lower/upper（有理数证书），不要用tolerance推断结果离真值多远。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥1e-13，≤0.01。 | 可选；未填写过时回车使用默认值1e-11；从示例开始时优先保留示例中的值。 | `1e-11` |
| max_iterations | 所有幂迭代、Newton–Noda、辅助α延拓及失败重试共享的总迭代上限，1至20000；不自动增加。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤20000。 | 可选；未填写过时回车使用默认值20000；从示例开始时优先保留示例中的值。 | `20000` |
| initial_vector | 可选严格正初值，按vertex_order顺序，长度等于顶点数；会归一化。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0.3333333333333333,0.3333333333333333,0.3333333333333333]` |
| method | 默认auto：先尝试两块等价划分；α>0.8使用Newton–Noda，普通区域先稳定幂法，128步预算内未收敛则切换。newton_noda显式使用保正Newton–Noda（高α自适应延拓、按需60位精化）；iteration仅使用稳定移位幂法。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：iteration, auto, newton_noda | 可选；未填写过时回车使用默认值"auto"；从示例开始时优先保留示例中的值。 | `auto` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2]],"alpha":0.3}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2],[2,3,4]],"alpha":1}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_spectrum.json)

## graph_spectrum

计算普通无向简单图的矩阵和完整数值特征值列表。

前提：无自环、无重边；D/DL要求连通。

工具限制：工具入口n<=128；使用双精度稠密矩阵。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `path` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `3` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2]]` |
| matrix | A邻接、L度减邻接、Q度加邻接、D距离、DL距离Laplacian、N归一化Laplacian、ABC度指数矩阵、S=J-I-2A、alpha混合矩阵。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：A, L, Q, D, DL, N, ABC, S, alpha | 可选；未填写过时回车使用默认值"A"；从示例开始时优先保留示例中的值。 | `A` |
| alpha | A_alpha=alpha*D+(1-alpha)*A中的参数；仅选择相关阵型/分支时使用。允许范围按Schema，数值Perron要求0<=alpha<1。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，≤1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |

完整例子 1（可直接粘贴到方式4）：

```json
{"kind":"path","n":3}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_spectrum.json)

## graph_invariants

计算图的基本结构不变量。

前提：普通无向简单图。

工具限制：工具入口n<=128。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `path` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `3` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2]]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"kind":"path","n":3}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_invariants.json)

## graph_characteristic_polynomial

计算普通图整系数矩阵的精确特征多项式。

前提：普通无向简单图；D/DL要求连通。

工具限制：n<=24，可能因符号规模受限。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `path` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `3` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2]]` |
| matrix | 支持A/L/Q/D/DL/S；不提供alpha、N或ABC分支。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：A, L, Q, D, DL, S | 可选；未填写过时回车使用默认值"A"；从示例开始时优先保留示例中的值。 | `A` |

完整例子 1（可直接粘贴到方式4）：

```json
{"kind":"path","n":3,"matrix":"A"}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_characteristic_polynomial.json)

## matching_polynomial

计算普通图匹配数生成多项式sum(m_j*x^j)。

前提：普通无向简单图。

工具限制：计算内核至多24顶点，指数复杂度。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `path` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `4` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2]]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"kind":"path","n":4}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/matching_polynomial.json)

## matrix_analysis

分析有限数值矩阵的秩，方阵另给行列式和特征值。

前提：非空、矩形、有限数值；方阵才有行列式和特征值字段。

工具限制：至多128行、256列；双精度。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- matrix按行输入；各行长度一致。可填0.5等小数，不使用Python表达式或分数字符串。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| matrix | 二维数值行列表，各行等长。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行最多256项。 每项填写整数或小数。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[1,2],[2,1]]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"matrix":[[1,2],[2,1]]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/matrix_analysis.json)

## polynomial_roots

统计并隔离闭区间内的不同实根。

前提：最高次系数非0，a<=b。

工具限制：最高32次；隔离默认eps=1e-10；不是任意精度特征值求解器。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- coefficients按最高次到常数项填写，中间缺项补0；例如[1,0,-1]表示x²-1，区间端点需a≤b。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| coefficients | 单变量多项式系数，从最高次到常数项；首项不得为0，小数按十进制有理数处理。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少2项，最多33项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[1,0,-1]` |
| a | 实根搜索闭区间的左端点，必须a<=b。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `-1` |
| b | 实根搜索闭区间的右端点，两个端点的根均包含在内。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `1` |

完整例子 1（可直接粘贴到方式4）：

```json
{"coefficients":[1,0,-1],"a":-1,"b":1}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/polynomial_roots.json)

## quotient_matrix

按索引划分求平均商矩阵，并检查等价划分。

前提：有限方阵；blocks完整划分0..n-1。

工具限制：输入矩阵Schema限制；等价检查使用浮点容差。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- blocks是从0开始的矩阵行列索引分组，必须构成完整划分；不等价时不能把商谱视为原谱的可靠子集。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| matrix | 待约化的有限数值方阵，不是图的边列表。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行最多256项。 每项填写整数或小数。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1],[1,0]]` |
| blocks | 行列索引0..n-1的不重不漏划分，每块非空；整数值浮点数如1.0会规范化为整数，不接受小数索引或布尔值；不是顶点显示标签列表。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少1项。 每项填写整数。 范围：至少1项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0],[1]]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"matrix":[[0,1],[1,0]],"blocks":[[0],[1]]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/quotient_matrix.json)

## tensor_spectrum

求非负立方张量的谱半径和一个Perron向量。

前提：有限非负立方张量，阶数>=2；可约非对角张量可能不收敛。

工具限制：至多100000项、阶数<=6；默认20000次迭代，不收敛报错。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- data是稠密非负立方张量，每个轴的长度相同；不要直接把超边列表放入data。二维例子代表二阶张量。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| data | 稠密张量的嵌套数组，不是超边列表；要求各维长度一致。数值谱和精确消元的系数规则不同。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1],[1,0]]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"data":[[0,1],[1,0]]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/tensor_spectrum.json)

## combinatorial_calculation

精确组合计数、棋盘车多项式、有限群循环指标及Cayley有向图。

前提：具体参数依operation。

工具限制：Schema中n/k<=32。；群计算至多8个作用点、8个生成元、128个群元素；先用SymPy检查群阶，超限不展开。有向谱入口另限64顶点，较大Cayley图仅返回结构。；棋盘车多项式每维至多10；矩形、0/1含义与绘图棋盘一致，空棋盘不进入本入口。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 分拆等原有分支使用n/k/parts。cycle_index/cayley_graph用generators：每行是一个0起始置换像列表，先生成完整群；Cayley可选side左乘、右乘或双侧，结果n/arcs可联动有向谱工具。rook_polynomial使用board矩形0/1矩阵：1可放车，0禁用，每维至多10。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 partition_number: 把n分成恰好k个正整数的无序分拆数；返回result整数。; divisibility_matrix: 整除关系矩阵；返回result。; mobius_matrix: 整除关系的Mobius逆矩阵；返回result。; cycle_type_count: 给定轮换类型的置换个数；返回result整数。; cycle_index: 先生成完整有限置换群，再对全部群元素计算标准循环指标。; cayley_graph: 生成左乘、右乘或双侧Cayley简单有向图，返回arcs、n和编号对应的置换列表；重复弧合并，自环省去。; rook_polynomial: 计算0/1棋盘的车多项式，x^k系数是不同行且不同列放置k个车的方案数；返回精确多项式和升幂系数。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：partition_number, divisibility_matrix, mobius_matrix, cycle_type_count, cycle_index, cayley_graph, rook_polynomial | 必填，不能留空；从示例开始时可回车保留已填值。 | `partition_number` |
| n | 分拆/整除矩阵使用的整数或阶数；群计算分支忽略n，作用点数由generators的长度确定。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤32。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `8` |
| k | partition_number的分拆份数，其他分支忽略。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤32。 | 可选；未填写过时回车使用默认值2；从示例开始时优先保留示例中的值。 | `3` |
| parts | cycle_type_count的轮换长度列表，例如[2,1]表示一个2轮换与一个不动点。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多32项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[2,1]` |
| generators | cycle_index/cayley_graph的生成元置换像列表，0起始。例如[[1,0,2],[1,2,0]]生成S3；不是只对这两个生成元求平均。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少1项。 每行最多8项。 每项填写整数。 范围：至少1项，最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[1,0,2],[1,2,0]]` |
| board | rook_polynomial专用的矩形0/1棋盘，1格可放置车，0格禁用；每维至多10。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少1项。 每行最多10项。 每项填写整数。 范围：至少1项，最多10项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[1,1],[1,1]]` |
| side | cayley_graph的乘法侧：right为g→g·s，left为g→s·g，twosided同时使用两侧。默认right；循环指标不使用该参数。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：right, left, twosided | 可选；未填写过时回车使用默认值"right"；从示例开始时优先保留示例中的值。 | `left` |

完整例子 1（可直接粘贴到方式4）：

```json
{"operation":"partition_number","n":8,"k":3}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"operation":"cycle_index","generators":[[1,0,2],[1,2,0]]}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"operation":"cayley_graph","generators":[[1,0,2],[1,2,0]]}
```

完整例子 4（可直接粘贴到方式4）：

```json
{"operation":"rook_polynomial","board":[[1,1],[1,1]]}
```

完整例子 5（可直接粘贴到方式4）：

```json
{"operation":"cayley_graph","generators":[[1,0,2],[1,2,0]],"side":"left"}
```

完整例子 6（可直接粘贴到方式4）：

```json
{"operation":"cayley_graph","generators":[[1,0,2],[1,2,0]],"side":"twosided"}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/combinatorial_calculation.json)

## graph_edit

普通图结构变换，包括批量用图替换边及局部笛卡尔积，返回可联动的新图描述。

前提：普通无向简单图；新增边的端点须已存在。

工具限制：输入n<=128；结果可能更大，例如稠密图的线图。；replace_edge结果至多128顶点；只接受无向简单图。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。
- core用core_k；relabel用labels；subdivide_edges用edit_edges/subdivisions；replace_edge用恰好一条edit_edges、replacement和endpoints；replace_edges可给多条边，每条使用独立替换图副本；partial_product用vertices选择顶点，replacement为笛卡尔积另一因子。返回graph_spec可联动整数编号工具。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `path` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `4` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2],[2,0],[2,3]]` |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 complement: 同一顶点集取补图。; line_graph: 边变顶点的线图，并重新编号为整数。; power: 将最短路距离不超过power的不同顶点连边；例如power=2连接两步以内的顶点。; delete_vertices: 删除vertices中的点及其关联边。; delete_edges: 删除edit_edges。; add_edges: 添加edit_edges，不允许新端点。; seidel_switch: 在vertices与其补集之间翻转邻接关系。; core: 反复删除度小于core_k的顶点；core_k=2会剥叶并去掉孤立点，结果可为空。; relabel: 按labels重编号，不允许标签冲突导致顶点合并。; subdivide_edges: 在指定边上各插入subdivisions个新顶点，保留孤立点。; replace_edge: 将edit_edges中恰好一条边替换为replacement，识别endpoints与原边两端，保留孤立点。; replace_edges: 将edit_edges中多条不同的已有边分别替换为replacement的独立副本；endpoints为每个副本的两个粘合端点，保留原图孤立点。; partial_product: 对vertices诱导子图与replacement作笛卡尔积，外部顶点不动；每个积顶点连接原顶点的全部外部邻点。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：complement, line_graph, power, delete_vertices, delete_edges, add_edges, seidel_switch, core, relabel, subdivide_edges, replace_edge, replace_edges, partial_product | 必填，不能留空；从示例开始时可回车保留已填值。 | `complement` |
| vertices | delete_vertices或seidel_switch的操作顶点选集，不是完整顶点表。 partial_product使用此列表选取参与局部笛卡尔积的原顶点，必须非空互异。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1]` |
| edit_edges | delete_edges/add_edges的边表；subdivide_edges中指定需剖分的边，省略表示全部边，空列表表示不改。 replace_edges可给多条不同的已有边，各自使用独立替换图副本。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1]]` |
| power | power分支的图幂次数，即最短路距离不超过该值的顶点连边。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤8。 | 可选；未填写过时回车使用默认值2；从示例开始时优先保留示例中的值。 | `2` |
| core_k | core分支的k-core阶数，默认2，结果可为空；2-core同时去掉孤立点并反复剥叶。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤128。 | 可选；未填写过时回车使用默认值2；从示例开始时优先保留示例中的值。 | `2` |
| labels | relabel分支按原顶点0..n-1顺序提供完整、唯一的新整数或字符串标签。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `["a","b","c"]` |
| subdivisions | subdivide_edges分支每条指定边插入的新顶点数，0表示不改。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤16。 | 可选；未填写过时回车使用默认值1；从示例开始时优先保留示例中的值。 | `2` |
| replacement | replace_edge/replace_edges的替换图，或partial_product的另一图积因子；填写{kind,n,edges}，例如{kind:"path",n:3}。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `{"kind":"path","n":3}` |
| endpoints | replace_edge中替换图的两个不同端点，按顺序对应edit_edges中的原边两端。新内部顶点使用无冲突整数编号。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少2项，最多2项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,2]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"operation":"complement","kind":"path","n":4}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"kind":"edges","n":5,"edges":[[0,1],[1,2],[2,0],[2,3]],"operation":"core"}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"kind":"path","n":3,"operation":"relabel","labels":["a","b","c"]}
```

完整例子 4（可直接粘贴到方式4）：

```json
{"kind":"path","n":3,"operation":"subdivide_edges","subdivisions":2,"edit_edges":[[0,1]]}
```

完整例子 5（可直接粘贴到方式4）：

```json
{"operation":"replace_edge","kind":"path","n":3,"edit_edges":[[0,1]],"replacement":{"kind":"path","n":3},"endpoints":[0,2]}
```

完整例子 6（可直接粘贴到方式4）：

```json
{"operation":"replace_edges","kind":"path","n":3,"edit_edges":[[0,1],[1,2]],"replacement":{"kind":"path","n":3},"endpoints":[0,2]}
```

完整例子 7（可直接粘贴到方式4）：

```json
{"operation":"partial_product","kind":"path","n":3,"vertices":[1],"replacement":{"kind":"path","n":2}}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_edit.json)

## exact_matrix_operation

有理数矩阵的精确代数、行列变换及行列式拆行。

前提：矩形数值输入；determinant/inverse/charpoly需方阵，inverse还须非奇异。

工具限制：至多12行、12列。；至多32个变换步骤；行列序号须在矩阵内。交换或加倍数需不同源/目标。允许数乘0，但此时操作不可逆。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- matrix按行输入整数或小数；elementary用actions步骤列表，split_row用row_index/row_terms并自动补余项。矩阵不接受分数字符串、符号或复数，小数按精确十进制有理数解释。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| matrix | 数值行列表，小数以其十进制文本转成Rational，不代表输入误差被消除。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行最多256项。 每项填写整数或小数。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[1,2],[3,4]]` |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 rref: 行最简形，返回matrix和pivot_columns。; inverse: 精确逆，返回matrix。; determinant: 精确行列式，返回determinant字符串。; charpoly: 精确特征多项式，返回polynomial字符串。; elementary: 依次交换、数乘或加倍数操作行/列；返回精确矩阵及LaTeX过程，不改变输入。; split_row: 将方阵某行拆成若干给定行向量及精确余项，返回各项矩阵与行列式。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：rref, inverse, determinant, charpoly, elementary, split_row | 可选；未填写过时回车使用默认值"rref"；从示例开始时优先保留示例中的值。 | `inverse` |
| actions | elementary分支的步骤记录列表。kind选swap_rows/scale_row/add_row或swap_columns/scale_column/add_column；target是0起始目标行列，交换需source，数乘需factor，加倍数需两者。例如[{"kind":"add_row","target":1,"source":0,"factor":-3}]。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：最多32项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[{"kind":"add_row","target":1,"source":0,"factor":-3}]` |
| row_index | split_row分支的0起始拆分行序号。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤11。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| row_terms | split_row分支给定的拆分行向量列表；会自动添加原行减去这些行之和的余项，确保行列式线性展开完整。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少1项。 每行最多12项。 每项填写整数或小数。 范围：最多12项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[1,0]]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"matrix":[[1,2],[3,4]],"operation":"inverse"}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"operation":"elementary","matrix":[[1,2],[3,4]],"actions":[{"kind":"add_row","target":1,"source":0,"factor":-3}]}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"operation":"split_row","matrix":[[1,2],[3,4]],"row_index":0,"row_terms":[[1,0]]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/exact_matrix_operation.json)

## tensor_operation

执行小稠密张量的基本逐项和结构操作。

前提：有限、形状规则的数值嵌套数组；对称化要求立方张量。

工具限制：至多10000项、阶数<=6。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- data每层数组对应一个轴；exponent仅在entrywise_power分支读取，不表示张量矩阵乘法。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| data | 稠密张量的嵌套数组，不是超边列表；要求各维长度一致。数值谱和精确消元的系数规则不同。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[1,2],[3,4]]` |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 symmetrize: 对所有轴置换取平均，返回tensor。; transpose: 反转所有轴顺序，返回tensor。; entrywise_power: 每个元素分别取exponent次幂，返回tensor。; properties: 返回shape、symmetric、diagonal。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：symmetrize, transpose, entrywise_power, properties | 可选；未填写过时回车使用默认值"symmetrize"；从示例开始时优先保留示例中的值。 | `symmetrize` |
| exponent | 逐项幂的非负整数指数，不是Shao广义张量乘积。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤8。 | 可选；未填写过时回车使用默认值2；从示例开始时优先保留示例中的值。 | `2` |

完整例子 1（可直接粘贴到方式4）：

```json
{"data":[[1,2],[3,4]],"operation":"symmetrize"}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/tensor_operation.json)

## graph_construction

构造theta、毛毛虫、仙人掌、Hamming或指定圈秩随机图。

前提：路径长度、圈长和阶数须满足对应图族定义。

工具限制：结果至多128点，总路径/圈长度<=128，参数范围另见Schema。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 先选family，再按该族含义填写：theta用三条路径长度lengths；caterpillar用主干长度n和attachments；cactus用圈长列表lengths及seed；hamming用k和q；random_k_cyclic用n、k、seed。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| family | 选择构造族。 theta: 至少两条路径连接同一对端点；至多一条长1的路径。; caterpillar: 主干松路加叶子；n是主干边数。; cactus: 按lengths附接圈，圈长至少3。; hamming: q^k个顶点的Hamming图。; random_k_cyclic: n点连通图，圈秩恰为k。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：theta, caterpillar, cactus, hamming, random_k_cyclic | 必填，不能留空；从示例开始时可回车保留已填值。 | `theta` |
| lengths | theta的各路径边数，或cactus各圈的边数；省略时内部回退[2,2,2]，因此cactus必须显式提供>=3的圈长。其他族不使用此列表构图。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[2,2,2]` |
| n | caterpillar的主干边数(主干有n+1点)；random_k_cyclic的总顶点数；其他族忽略。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤64。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `5` |
| k | hamming的正维数(k>=1)；random_k_cyclic的圈秩m-n+1；不是超图一致度。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤16。 | 可选；未填写过时回车使用默认值2；从示例开始时优先保留示例中的值。 | `2` |
| q | hamming每个坐标的字母数，阶数为q^k。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤8。 | 可选；未填写过时回车使用默认值2；从示例开始时优先保留示例中的值。 | `2` |
| attachments | caterpillar的[主干顶点,悬挂叶子数]列表，不是超边。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,3]]` |
| seed | 可复现的随机种子；用于随机构造、初始向量或自动布局，不是计算精度。 | 填写一个整数，不填单位或Python表达式。 范围：≥0。 | 可选；未填写过时回车使用默认值42；从示例开始时优先保留示例中的值。 | `42` |

完整例子 1（可直接粘贴到方式4）：

```json
{"family":"theta","lengths":[2,2,2]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_construction.json)

## graph_symmetry

按自同构顶点轨道计算平均商矩阵并检查等价划分。

前提：普通简单图；D要求连通。

工具限制：n<=24；同构检查和数值求谱均有规模限制。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `star` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `5` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2]]` |
| matrix | A/L/Q/alpha/D；只有alpha时读取alpha。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：A, L, Q, alpha, D | 可选；未填写过时回车使用默认值"A"；从示例开始时优先保留示例中的值。 | `A` |
| alpha | A_alpha=alpha*D+(1-alpha)*A中的参数；仅选择相关阵型/分支时使用。允许范围按Schema，数值Perron要求0<=alpha<1。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，<1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |

完整例子 1（可直接粘贴到方式4）：

```json
{"kind":"star","n":5}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_symmetry.json)

## graph_spectral_analysis

计算图能量、谱投影、图角或精确alpha特征多项式。

前提：普通无向简单图。

工具限制：alpha_charpoly至多12点；其他分支n<=128。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。
- 先选operation。alpha_charpoly分支可选symbolic_alpha=true；其他谱分析分支使用其对应数值输入。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `path` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `3` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2]]` |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 energy: 返回energy=sum\|lambda_i\|和estrada_index=sum exp(lambda_i)。; angles: 返回distinct_eigenvalues与angles，后者按不同特征值和顶点排列。; projectors: 返回decomposition；每项含eigenvalue、multiplicity、basis、projector。; alpha_charpoly: 返回精确polynomial和arithmetic='exact'；可选符号alpha。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：energy, angles, projectors, alpha_charpoly | 必填，不能留空；从示例开始时可回车保留已填值。 | `alpha_charpoly` |
| alpha | A_alpha=alpha*D+(1-alpha)*A中的参数；仅选择相关阵型/分支时使用。允许范围按Schema，数值Perron要求0<=alpha<1。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，<1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| symbolic_alpha | 仅alpha_charpoly分支：true返回符号alpha，false使用alpha的精确十进制值。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `true` |

完整例子 1（可直接粘贴到方式4）：

```json
{"operation":"alpha_charpoly","kind":"path","n":3,"symbolic_alpha":true}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_spectral_analysis.json)

## compare_graphs

比较同构、邻接同谱或非诱导子图份数。

前提：left/right均为合法普通图描述。

工具限制：同谱比较最多24点；子图计数宿主<=24、模式<=8、映射预算100000。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- left和right各填一个图的JSON对象，例如{"kind":"path","n":3}；不是直接填边表。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| left | 左侧普通图描述{kind,n,edges}；子图计数时是宿主图。自定义图需kind='edges'并显式n。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `{"kind":"path","n":3}` |
| right | 右侧普通图描述{kind,n,edges}；子图计数时是模式图，不是宿主图。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `{"kind":"star","n":3}` |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 isomorphic: 返回isomorphic布尔值。; cospectral: 按精确邻接特征多项式比较，返回cospectral。; subgraph_count: left为宿主、right为模式；返回除去模式自同构后的非诱导份数non_induced_copies。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：isomorphic, cospectral, subgraph_count | 可选；未填写过时回车使用默认值"isomorphic"；从示例开始时优先保留示例中的值。 | `isomorphic` |

完整例子 1（可直接粘贴到方式4）：

```json
{"left":{"kind":"path","n":3},"right":{"kind":"star","n":3}}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/compare_graphs.json)

## graph_enumeration

有预算地枚举简单路、圈、Hamilton圈或度序列实现。

前提：普通简单图；路径端点存在；度序列满足图化条件，否则实现列表为空。

工具限制：路/圈最多16点，度序列最多9点；limit<=1000；Hamilton与度序列分支另限100000搜索状态。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。
- paths填写start/end/length；cycles填写length；degree_realizations填写degrees。达到limit不代表已经枚举完整。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `cycle` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `4` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2]]` |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 paths: 长度恰为length条边的简单路，读取start/end。; cycles: 长度恰为length的圈，按旋转和反向去重。; hamilton: 所有Hamilton圈；忽略start/end/length。; degree_realizations: 按degrees枚举非同构简单图；忽略kind/n/edges/start/end/length。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：cycles, paths, hamilton, degree_realizations | 必填，不能留空；从示例开始时可回车保留已填值。 | `cycles` |
| start | 路枚举的起点标签，须属于所构造普通图。 | 填写一个整数，不填单位或Python表达式。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| end | 路枚举的终点标签，须属于所构造普通图。 | 填写一个整数，不填单位或Python表达式。 | 可选；未填写过时回车使用默认值1；从示例开始时优先保留示例中的值。 | `1` |
| length | 枚举的路/圈长度，按边数计，不是内部顶点数。Hamilton分支忽略它。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤16。 | 可选；未填写过时回车使用默认值3；从示例开始时优先保留示例中的值。 | `4` |
| degrees | 非负度序列；只供degree_realizations分支使用，枚举按同构去重。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多9项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[2,2,2]` |
| limit | 允许返回的枚举结果数上限；超出时明确报错，不声称截断列表是完整枚举。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤1000。 | 可选；未填写过时回车使用默认值1000；从示例开始时优先保留示例中的值。 | `1000` |

完整例子 1（可直接粘贴到方式4）：

```json
{"operation":"cycles","kind":"cycle","n":4,"length":4}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_enumeration.json)

## hypergraph_structure

计算超图关联、距离、带权线图、轨道、方程或匹配多项式。

前提：结构分支可非一致；distances需连通；equations和matching_poly需非空一致；matching_poly使用未加权定义。

工具限制：orbits最多24点；matching_poly最多40点且有100000状态预算；边列表限制见Schema。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- incidence等结构分支可使用非一致边表；equations只生成方程，不自动求解。涉及张量的分支仍需检查一致性。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多8项。 每项填写整数。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2],[2,3]]` |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 incidence: 返回vertices、edges、incidence(行顶点列超边)、degrees、cycle_rank(关联图的圈秩)。; distances: 返回vertices、distances；距离为最少经过的超边数。; line_graph: 每条超边变一个点，边权是两超边交集大小；返回nodes、weighted_edges。; orbits: 返回vertex_orbits。; equations: 返回alpha_equations表达式字符串和variables；未求解特征值或特征向量。; matching_poly: 返回matching_polynomial及区别说明；定义为覆盖匹配的带符号n次多项式。; laplacian_equations: 生成一致超图Laplacian张量特征方程λx^(k−1)−Lx^(k−1)=0；不是求解器，忽略alpha。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：incidence, distances, line_graph, orbits, equations, matching_poly, laplacian_equations | 可选；未填写过时回车使用默认值"incidence"；从示例开始时优先保留示例中的值。 | `incidence` |
| alpha | A_alpha=alpha*D+(1-alpha)*A中的参数；仅选择相关阵型/分支时使用。允许范围按Schema，数值Perron要求0<=alpha<1。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，<1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2],[2,3]],"operation":"incidence"}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2]],"operation":"laplacian_equations"}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_structure.json)

## hypergraph_transform

返回添加路径、扩边、克隆、合并、剖分或诱导子超图后的结构。

前提：输入为合法简单超图；不能合并到单点边。

工具限制：count*max(1,原边数)*rank<=256；合并/剖分还有结构约束。；attach_star根集大小必须小于目标边大小；结果至多128顶点和128边。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 先选operation；attach_path用vertex/count/rank，attach_star用roots/count/rank（新边共享根集），expand_edges用count，clone_all/clone_cartesian用vertex/count，merge用groups，subdivide用edge_index/count，induced用vertices。参数的具体含义和限制以各字段说明为准。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多8项。 每项填写整数。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2]]` |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 attach_path: 在vertex附接count条边，rank控制新边大小。; expand_edges: 每条边加count个新叶子。; clone_all: 以count个克隆替换vertex，全部克隆同处原边，会改变秩。; clone_cartesian: 每条相关边各选择一个克隆作笛卡尔展开，保持原边大小，结果重新编号。; merge: 合并groups后重新编号；重复边按简单超图规则处理。; subdivide: 将edge_index指定边替换为count条松边；只支持合适的非叶锚点结构。; induced: 保留完全包含于vertices选集中的边。; attach_star: 按roots附接count条共享根集的新边，边大小取max(原最大边大小,rank)，新边权为1。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：attach_path, expand_edges, clone_all, clone_cartesian, merge, subdivide, induced, attach_star | 必填，不能留空；从示例开始时可回车保留已填值。 | `expand_edges` |
| vertex | 当前操作针对的已有顶点标签。 | 填写一个整数，不填单位或Python表达式。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| count | 分支相关：attach_path为新边数；expand_edges为每边增加的叶子数；clone_all/cartesian为克隆总数；subdivide为替换后的松路边数。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤16。 | 可选；未填写过时回车使用默认值1；从示例开始时优先保留示例中的值。 | `1` |
| rank | attach_path的目标边大小；实际取max(原最大边大小,rank)。也参与保守展开预算，其他分支不据它改变秩。 | 填写一个整数，不填单位或Python表达式。 范围：≥2，≤8。 | 可选；未填写过时回车使用默认值3；从示例开始时优先保留示例中的值。 | `3` |
| edge_index | 输入edges中的零起始边序号，不是某个端点标签。 | 填写一个整数，不填单位或Python表达式。 范围：≥0。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| groups | 合并顶点的分组列表，各组是已有顶点的子集，组间不能重叠。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每项填写整数。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1]]` |
| vertices | induced分支保留的顶点选集，不是输入超图的完整顶点表。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,1,2]` |
| roots | attach_star分支的共享根顶点集；省略用[vertex]。count条新边始终共享这些根，每条边的其余顶点互不相同；不同于attach_path的链式附接。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,1]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2]],"operation":"expand_edges","count":1}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"operation":"attach_star","edges":[[0,1,2]],"roots":[0,1],"count":2,"rank":3}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_transform.json)

## hypergraph_quotient_spectrum

以顶点轨道商算子约化alpha特征方程并比较Perron谱半径。

前提：连通、非空、一致、未加权模型输入，0<=alpha<1。

工具限制：最多24顶点、16超边；约化向量会展开回原图作残差检查。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多8项。 每项填写整数。 范围：至少1项，最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2],[0,3,4]]` |
| alpha | A_alpha=alpha*D+(1-alpha)*A中的参数；仅选择相关阵型/分支时使用。允许范围按Schema，数值Perron要求0<=alpha<1。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，<1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0.3` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2],[0,3,4]],"alpha":0.3}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_quotient_spectrum.json)

## directed_graph_spectrum

计算有向简单图的Hermitian或非对称矩阵及完整复数谱。

前提：顶点0..n-1，无自环；反向弧可以同时存在。

工具限制：n<=64、弧数<=1024；双精度稠密求解。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- arcs中的[u,v]表示u→v，顺序有意义；n给出总顶点数，标签为0..n-1。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| n | 有向图总顶点数，包含孤立点。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤64。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `3` |
| arcs | 有向弧[u,v]列表，方向从u到v。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1],[1,2],[2,0]]` |
| matrix | H中单向弧使用正负i、双向弧使用1；A为有向邻接，L为出度D-A，alpha为混合矩阵。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：H, A, L, alpha | 可选；未填写过时回车使用默认值"H"；从示例开始时优先保留示例中的值。 | `H` |
| alpha | A_alpha=alpha*D+(1-alpha)*A中的参数；仅选择相关阵型/分支时使用。允许范围按Schema，数值Perron要求0<=alpha<1。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，<1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |

完整例子 1（可直接粘贴到方式4）：

```json
{"n":3,"arcs":[[0,1],[1,2],[2,0]]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/directed_graph_spectrum.json)

## linear_recurrence

求正则线性递推的精确序列项与可验证闭式。

前提：coefficients从a(n)到a(n+r)；阶数r=1..8；提供从start起连续r个有理数初值。

工具限制：表达式≤1024字符/128语法节点；系数分子分母次数≤8；仅受控算术，不执行输入代码。；原生JSON入口经受限计算进程执行，受30秒等默认预算限制。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- coefficients[i]乘a(n+i)，等号右端为forcing；初值从start起连续给出且数量等于阶数。例如[-1,-1,1]和[0,1]是Fibonacci递推。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| coefficients | JSON列表，从a(n)系数到a(n+r)系数；可填数值或如"-(n+1)"、"1/(n+1)"的算式字符串。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少2项，最多9项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[-1,-1,1]` |
| initial_values | 从a(start)开始的连续初值，数量等于阶数；如[0,1]或["1/3"]。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多8项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[0,1]` |
| forcing | 等号右端，默认0；支持n的多项式、有理函数及2^n、factorial(n)、binomial(n,2)等超几何项之和。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥-1000000000000，≤1000000000000。 或 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 范围：最多1024字符。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `2*n+1` |
| variable | 递推下标符号，默认n；不用于声明其他参数。 | 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 | 可选；未填写过时回车使用默认值"n"；从示例开始时优先保留示例中的值。 | `n` |
| start | 递推成立的最小整数下标，默认0；系数在其后的整数点须无极点且最高移位系数非零。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤128。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| terms | 返回从start起的精确序列项数，1..64。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤64。 | 可选；未填写过时回车使用默认值12；从示例开始时优先保留示例中的值。 | `10` |

完整例子 1（可直接粘贴到方式4）：

```json
{"coefficients":[-1,-1,1],"initial_values":[0,1],"terms":10}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"coefficients":["-(n+1)",1],"initial_values":[1],"terms":6}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"coefficients":[-1,1],"forcing":"2*n+1","initial_values":[0]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/linear_recurrence.json)

## integer_linear_system

用Smith分解返回整数线性方程Ax=b的解族或无解/有条件状态。

前提：A为常数整数矩阵；rhs长度等于行数；所有声明参数和自由参数取整数。

工具限制：A为1..12行列，绝对值≤10^9；右端整系数多项式次数≤8，至多8个参数。；原生JSON入口受限运行；参数解仅在列出的整除和零行条件成立时有效。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- matrix*x=rhs，未知量与parameters都取整数；conditional必须检查conditions，不能直接当作无条件有解。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| matrix | 按行给出常数整数矩阵，至多12×12；整数值浮点数如1.0可规范化。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少1项。 每行最多12项。 每项填写整数。 范围：至少1项，最多12项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[2,4],[0,6]]` |
| rhs | 右端列表，例如[2,6]或["n-1","2*n"]。字符串仅按受控算术解析。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多12项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[2,6]` |
| parameters | rhs中允许的整数参数名列表，例如["n","d1"]；使用字符串符号时必须声明。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `["n"]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"matrix":[[2,4],[0,6]],"rhs":[2,6]}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"matrix":[[2]],"rhs":[1]}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"matrix":[[2]],"rhs":["n"],"parameters":["n"]}
```

完整例子 4（可直接粘贴到方式4）：

```json
{"matrix":[[1,1]],"rhs":[3]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/integer_linear_system.json)

## hypergraph_tensor_charpoly

精确Macaulay消元求一般一致超图A/L/Q/alpha的普通张量特征多项式。

前提：非空边列表须一致；无边时必须给出n和rank；给rank时必须匹配每条边的大小。

工具限制：n<=32、rank<=5；默认Macaulay阶<=4096、SCC块<=256、多项式次数<=4096；符号alpha限512/64；原生Python子进程20秒硬超时。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 只研究一致超图张量。空边表时必须另外给出n和rank；有边时可推断rank。matrix=alpha时可输入分数alpha或选symbolic_alpha；estimate_only=true只估计规模，不返回已计算的多项式。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多5项。 每项填写整数。 范围：最多64项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2]]` |
| n | 总顶点数，给出时顶点为0..n-1并保留孤立点；省略时只按出现的标签推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤32。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `3` |
| rank | 张量阶数/一致度k；有边时可推断，无边时必填。 | 填写一个整数，不填单位或Python表达式。 范围：≥2，≤5。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `3` |
| matrix | A邻接张量、L=D-A、Q=D+A或alpha*D+(1-alpha)*A。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：A, L, Q, alpha | 可选；未填写过时回车使用默认值"A"；从示例开始时优先保留示例中的值。 | `A` |
| alpha | 仅matrix='alpha'读取；可用整数、小数、分数字符串；symbolic_alpha=true时改为符号alpha，不受数值Perron的[0,1)限制。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 或 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 范围：最多128字符。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| symbolic_alpha | true将alpha作为精确符号处理；必须选用本工具的alpha特征多项式分支。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `false` |
| weights | 按边顺序的精确系数，允许带符号或分数字符串；不同于正权数值谱工具。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多64项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1]` |
| vertex_degrees | 独立D的精确对角；省略时使用精确边权度，不是逐点乘邻接项。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多32项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,1,1]` |
| estimate_only | true只返回计算规模估计，不进行消元，不返回已计算的多项式或特征值。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `true` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2]]}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2]],"estimate_only":true}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_tensor_charpoly.json)

## tensor_charpoly

对已有立方张量求精确普通特征多项式。

前提：阶数>=2，各维长度相同；系数可用有限数值或分数字符串。

工具限制：顶层维数<=8，实际限稠密项数20000、Macaulay4096、块256、次数4096及20秒硬超时。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- data是按各轴嵌套的立方张量数据，不是超边表；例如二维2×2数组代表二阶张量。estimate_only=true只估计规模。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| data | 规则的嵌套数组；允许负系数、非对称张量和如'1/3'的字符串。小数视为精确十进制数。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多8项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1],[1,0]]` |
| estimate_only | true只返回计算规模估计，不进行消元，不返回已计算的多项式或特征值。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `false` |

完整例子 1（可直接粘贴到方式4）：

```json
{"data":[[0,1],[1,0]]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/tensor_charpoly.json)

## hypergraph_plot

普通图与超图结构绘图；完整图对象保留方向、原权重和样式。

前提：每边至少两点，无重复边；显式vertices须包含全部成员；每边恰为两点时按简单图绘制黑色直线边。

工具限制：至多128点、128边、2048点边关联；复杂图可能需要手动调布局。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 边表每项列出该边的成员；如需孤立点，vertices填写全部顶点。绘图/导出可以使用字符串标签。
- 简单图的每条边写成两个顶点，例如[[0,1],[1,2]]；绘图后可在结果中调整布局。
- positions可省略使用自动布局；手填时每项为{"vertex":标签,"xy":[x,y]}，必须覆盖全部顶点且坐标不能全相同。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| graph_document | 可选完整图对象，format=graph-research-graph、version=1。保留原标签、孤立点、graph_type、方向、权重、坐标及style；须与外层结构/坐标参数一致。样式包括字号、颜色、线型、标签显示及pt偏移。布局按无向无权支撑结构，不修改方向/权重。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `{"format":"graph-research-graph","version":1,"graph_type":"hypergraph","directed":false,"weighted":true,"vertices":[0,1,2],"edges":[{"vertices":[0,1],"weight":2}],"positions":[[0,0],[1,0],[0,1]],"style":{"weight_labels":true,"font_size":10}}` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2],[2,3]]` |
| vertices | 完整顶点表，必须包含全部边端点；可包含孤立点。不提供时从超边成员推断。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,1,2,3,4]` |
| positions | 可选完整顶点坐标记录[{vertex,xy:[x,y]}]；提供时按此布局绘制PNG/SVG，优先于自动layout/seed。标签须完整互异，坐标有限且不重合。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[{"vertex":0,"xy":[1.0,0.0]},{"vertex":1,"xy":[0.309,0.9511]},{"vertex":2,"xy":[-0.809,0.5878]},{"vertex":3,"xy":[-0.809,-0.5878]},{"vertex":4,"xy":[0.309,-0.9511]}]` |
| layout | spring使用关联图的弹簧布局并排列连通分量；circular按顶点顺序排在圆周。不用于谱计算。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：spring, circular | 可选；未填写过时回车使用默认值"spring"；从示例开始时优先保留示例中的值。 | `spring` |
| seed | 可复现的随机种子；用于随机构造、初始向量或自动布局，不是计算精度。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤4294967295。 | 可选；未填写过时回车使用默认值42；从示例开始时优先保留示例中的值。 | `42` |
| edge_labels | 是否显示或导出超边编号e0,e1,...，不是给边设置数学权重。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值true；从示例开始时优先保留示例中的值。 | `true` |
| legend | 静态图中是否附带超边成员图例。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值true；从示例开始时优先保留示例中的值。 | `true` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2],[2,3]],"vertices":[0,1,2,3,4]}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"edges":[[0,1],[1,2]],"vertices":[0,1,2,3]}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"edges":[[0,1]],"graph_document":{"format":"graph-research-graph","version":1,"graph_type":"hypergraph","directed":false,"weighted":true,"vertices":[0,1,2],"edges":[{"vertices":[0,1],"weight":2}],"positions":[[0,0],[1,0],[0,1]],"style":{"weight_labels":true,"font_size":10}},"vertices":[0,1,2]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_plot.json)

## hypergraph_editor

生成可离线使用的拖动顶点布局编辑器。

前提：整数或字符串标签，整数绝对值<=2^53-1；合法简单超图，可非一致或为空。

工具限制：至多128点、128边、2048点边关联；不增删超边；坐标文件<=2MB。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 边表每项列出该边的成员；如需孤立点，vertices填写全部顶点。绘图/导出可以使用字符串标签。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2],[2,3]]` |
| vertices | 完整顶点表，必须包含全部边端点；可包含孤立点。不提供时从超边成员推断。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,1,2,3]` |
| seed | 可复现的随机种子；用于随机构造、初始向量或自动布局，不是计算精度。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤4294967295。 | 可选；未填写过时回车使用默认值42；从示例开始时优先保留示例中的值。 | `42` |
| layout | spring使用关联图的弹簧布局并排列连通分量；circular按顶点顺序排在圆周。不用于谱计算。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：spring, circular | 可选；未填写过时回车使用默认值"spring"；从示例开始时优先保留示例中的值。 | `spring` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2],[2,3]]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_editor.json)

## hypergraph_tikz

将当前超图布局导出为TikZ片段和完整.tex文档。

前提：合法超边列表，可含孤立点；positions提供时必须完整且不重合。

工具限制：至多128点、128边、2048点边关联；默认等比例归一化最长控制点跨度10cm，保持形状但不保留原坐标数值；中文完整文档用ctex/XeLaTeX。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 边表每项列出该边的成员；如需孤立点，vertices填写全部顶点。绘图/导出可以使用字符串标签。
- positions可省略使用自动布局；手填时每项为{"vertex":标签,"xy":[x,y]}，必须覆盖全部顶点且坐标不能全相同。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| graph_document | 可选完整图对象，format=graph-research-graph、version=1。保留原标签、孤立点、graph_type、方向、权重、坐标及style；须与外层结构/坐标参数一致。样式包括字号、颜色、线型、标签显示及pt偏移。布局按无向无权支撑结构，不修改方向/权重。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `{"format":"graph-research-graph","version":1,"graph_type":"hypergraph","directed":false,"weighted":true,"vertices":[0,1,2],"edges":[{"vertices":[0,1],"weight":2}],"positions":[[0,0],[1,0],[0,1]],"style":{"weight_labels":true,"font_size":10}}` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2],[2,3]]` |
| vertices | 完整顶点表，必须包含全部边端点；可包含孤立点。不提供时从超边成员推断。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,1,2]` |
| positions | 按vertex标识的二维坐标记录列表，每项{vertex:标签,xy:[x,y]}；必须覆盖全部顶点，标签不可重复，坐标有限且不完全重合。x向右、y向上。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[{"vertex":0,"xy":[1.0,0.0]},{"vertex":1,"xy":[0.0,1.0]},{"vertex":2,"xy":[-1.0,0.0]},{"vertex":3,"xy":[-0.0,-1.0]}]` |
| edge_labels | 是否显示或导出超边编号e0,e1,...，不是给边设置数学权重。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `false` |
| vertex_labels | 是否导出顶点的显示标签；关闭时仍保留顶点和曲线。模型工具中仅支持布尔值。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值true；从示例开始时优先保留示例中的值。 | `true` |
| seed | 可复现的随机种子；用于随机构造、初始向量或自动布局，不是计算精度。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤4294967295。 | 可选；未填写过时回车使用默认值42；从示例开始时优先保留示例中的值。 | `42` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2],[2,3]]}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"edges":[[0,1]],"graph_document":{"format":"graph-research-graph","version":1,"graph_type":"hypergraph","directed":false,"weighted":true,"vertices":[0,1,2],"edges":[{"vertices":[0,1],"weight":2}],"positions":[[0,0],[1,0],[0,1]],"style":{"weight_labels":true,"font_size":10}},"vertices":[0,1,2]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_tikz.json)

## graph_tikz

普通图TikZ导出；完整图对象支持有向、实/复权图及绘图样式。

前提：每边恰为两个不同顶点，边不可重复。

工具限制：至多128点、128边；默认等比例归一化到10cm跨度。导出代码不依赖TeX，编译另需LaTeX环境。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 边表每项列出该边的成员；如需孤立点，vertices填写全部顶点。绘图/导出可以使用字符串标签。
- positions可省略使用自动布局；手填时每项为{"vertex":标签,"xy":[x,y]}，必须覆盖全部顶点且坐标不能全相同。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| graph_document | 可选完整图对象，format=graph-research-graph、version=1。保留原标签、孤立点、graph_type、方向、权重、坐标及style；须与外层结构/坐标参数一致。样式包括字号、颜色、线型、标签显示及pt偏移。布局按无向无权支撑结构，不修改方向/权重。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `{"format":"graph-research-graph","version":1,"graph_type":"graph","directed":true,"weighted":true,"vertices":[0,1,2],"edges":[{"vertices":[0,1],"weight":2}],"positions":[[0,0],[1,0],[0,1]],"style":{"weight_labels":true,"font_size":10}}` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1],[1,2]]` |
| vertices | 完整顶点表，必须包含全部边端点；可包含孤立点。不提供时从超边成员推断。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,1,2,3]` |
| positions | 按vertex标识的二维坐标记录列表，每项{vertex:标签,xy:[x,y]}；必须覆盖全部顶点，标签不可重复，坐标有限且不完全重合。x向右、y向上。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[{"vertex":0,"xy":[1.0,0.0]},{"vertex":1,"xy":[0.0,1.0]},{"vertex":2,"xy":[-1.0,0.0]},{"vertex":3,"xy":[-0.0,-1.0]}]` |
| edge_labels | 是否显示或导出超边编号e0,e1,...，不是给边设置数学权重。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `false` |
| vertex_labels | 是否导出顶点的显示标签；关闭时仍保留顶点和曲线。模型工具中仅支持布尔值。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值true；从示例开始时优先保留示例中的值。 | `true` |
| seed | 可复现的随机种子；用于随机构造、初始向量或自动布局，不是计算精度。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤4294967295。 | 可选；未填写过时回车使用默认值42；从示例开始时优先保留示例中的值。 | `42` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1],[1,2]],"vertices":[0,1,2,3]}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"edges":[[0,1]],"graph_document":{"format":"graph-research-graph","version":1,"graph_type":"graph","directed":true,"weighted":true,"vertices":[0,1,2],"edges":[{"vertices":[0,1],"weight":2}],"positions":[[0,0],[1,0],[0,1]],"style":{"weight_labels":true,"font_size":10}},"vertices":[0,1,2]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_tikz.json)

## hypergraph_schematic

论文示意图：符号/省略超路、花括号、TeX与SVG，或明确整数展开。

前提：锚点唯一且有有限坐标；中心超边不同连接顶点数不超过数值k；符号路长只接受单个参数加减整数。

工具限制：最多128锚点、128中心边、64路段，展开最多128顶点/128超边。具体完整绘制每路最多16边，超过请省略。；路中省略号表示未展开超边；边内省略点表示未展示顶点，不表示恰好省略三个。符号图的首尾示意边段不限制实际参数最小值；展开长度须为正整数。；压缩仅支持完整无权一致超图中的无外部分支松路。展开生成的新内部顶点标签可能与源图不同，源快照不变。图形表示不承诺像素级复刻参考稿。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| diagram | 独立示意图JSON：vertices为{id,xy}列表；edges为中心边；paths为{start,end,length,brace,...}列表。可从桌面鼠标绘制获得。 可含style的线色、点色、底色、线宽、顶点半径；颜色为#RRGGBB。source_graph仅用于来源快照，不作为展开算法输入。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `{"format":"graph-research-schematic","version":1,"name":"E型论文示意图","rank":"k","vertices":[{"id":"v","xy":[0.0,0.0]},{"id":"a","xy":[0.0,2.5]},{"id":"b","xy":[-2.165,-1.25]},{"id":"c","xy":[2.165,-1.25]}],"edges":[],"paths":[{"start":"v","end":"a","length":"a","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true},{"start":"v","end":"b","length":"b","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true},{"start":"v","end":"c","length":"c","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true}],"style":{"line_color":"#161616","vertex_color":"#c03036","edge_fill":"#eeeeee","line_width":0.018,"vertex_radius":0.03}}` |
| operation | export导出示意图；expand在参数明确赋值后生成新超图。 export: 生成TeX完整文档、tikzpicture片段、SVG和可重新编辑的示意图JSON；不执行TeX编译。; expand: 显式替换k和路长参数，补齐私有顶点并生成独立GraphDocument/hypergraph_spec；后续可绑定计算工具。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：export, expand | 可选；未填写过时回车使用默认值"export"；从示例开始时优先保留示例中的值。 | `expand` |
| parameters | 仅expand使用的整数赋值，如{"k":3,"a":4,"b":2,"c":3}；不使用eval，不接受代码。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `{"k":3,"a":3,"b":2,"c":4}` |
| vertex_labels | 是否在预览/TeX中显示锚点标签，默认false；不影响路长数学标签。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `false` |

完整例子 1（可直接粘贴到方式4）：

```json
{"diagram":{"format":"graph-research-schematic","version":1,"name":"E型论文示意图","rank":"k","vertices":[{"id":"v","xy":[0.0,0.0]},{"id":"a","xy":[0.0,2.5]},{"id":"b","xy":[-2.165,-1.25]},{"id":"c","xy":[2.165,-1.25]}],"edges":[],"paths":[{"start":"v","end":"a","length":"a","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true},{"start":"v","end":"b","length":"b","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true},{"start":"v","end":"c","length":"c","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true}],"style":{"line_color":"#161616","vertex_color":"#c03036","edge_fill":"#eeeeee","line_width":0.018,"vertex_radius":0.03}}}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"diagram":{"format":"graph-research-schematic","version":1,"name":"E型论文示意图","rank":"k","vertices":[{"id":"v","xy":[0.0,0.0]},{"id":"a","xy":[0.0,2.5]},{"id":"b","xy":[-2.165,-1.25]},{"id":"c","xy":[2.165,-1.25]}],"edges":[],"paths":[{"start":"v","end":"a","length":"a","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true},{"start":"v","end":"b","length":"b","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true},{"start":"v","end":"c","length":"c","brace":"left","first_edges":1,"last_edges":1,"ellipsis":true,"label_offset":0.28,"vertex_ellipsis":true}],"style":{"line_color":"#161616","vertex_color":"#c03036","edge_fill":"#eeeeee","line_width":0.018,"vertex_radius":0.03}},"operation":"expand","parameters":{"k":3,"a":3,"b":2,"c":4}}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_schematic.json)

## weighted_graph_spectrum

带权及复权图的矩阵与全谱。

前提：显式指定权重约定；无向复权矩阵是厄米阵。

工具限制：显式指定权重约定；无向复权矩阵是厄米阵。；数值n≤128；精确n≤8；权实虚部绝对值≤10^6。；rho取模，残差使用对应特征值本身；数值计算不构成证明。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| n | 总顶点数1..128，编号0..n-1，保留孤立点。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `3` |
| edges | 赋权记录列表，每项{"u":0,"v":1,"weight":2}；复权如{"real":0,"imag":1}。不接受字符串复数、重复边或自环。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：最多2048项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[{"u":0,"v":1,"weight":{"real":0,"imag":2}}]` |
| directed | false时反向取共轭；true时只写u→v，反向弧须另填。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `false` |
| matrix | A邻接；L=D-A；Q=D+A；alpha=αD+(1−α)A。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：A, L, Q, alpha | 可选；未填写过时回车使用默认值"A"；从示例开始时优先保留示例中的值。 | `A` |
| alpha | A_alpha=alpha*D+(1-alpha)*A中的参数；仅选择相关阵型/分支时使用。允许范围按Schema，数值Perron要求0<=alpha<1。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，≤1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| degree_mode | absolute将逐点出边权模之和放入D；sum将逐点实边权之和放入D，仅接受实权。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：absolute, sum | 可选；未填写过时回车使用默认值"absolute"；从示例开始时优先保留示例中的值。 | `absolute` |
| exact | true额外输出精确矩阵及特征多项式（权的十进制部分按有理数，复权绝对度可能为代数数），仅限n≤8。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `true` |

完整例子 1（可直接粘贴到方式4）：

```json
{"n":3,"edges":[{"u":0,"v":1,"weight":{"real":0,"imag":2}}],"exact":true}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/weighted_graph_spectrum.json)

## graph_recipe

用参数和现有操作组合构造图，并核验结构断言。

前提：根必须已存在且互异；结构选择器按当时的图及边序解析。

工具限制：根必须已存在且互异；结构选择器按当时的图及边序解析。；结果≤128顶点；普通图≤1024边、超图≤128边；16步骤；不求符号图对象。；普通图附接单根；超图内部路按端点组共享根；现有操作不支持的输入明确拒绝。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| graph_type | graph普通无向图；hypergraph结构超图，允许非一致。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：graph, hypergraph | 必填，不能留空；从示例开始时可回车保留已填值。 | `graph` |
| base | 普通图{kind,n,edges}；超图{family,m,k,...}或{edges,vertices,weights}。尺寸n/m/k/lengths等可用已声明参数算式，如"t+2"。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `{"kind":"path","n":"t+2"}` |
| steps | 至多16个对象。operation=attach_star用roots/count；attach_path用roots/length；connect用left/right/length；disjoint_copies用copies；subdivide_edge用edge_index/count。count为新增段数（超图替换为count+1条松路边），length为边数。rank为超图目标边大小（不得小于现有最大边）。根可为标签或{"kind":"leaf","edge":0,"index":0}、{"kind":"joint","index":0}；所有索引从0起，index可负。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[{"operation":"attach_star","roots":[0],"count":"t"}]` |
| parameters | 命名整数参数对象，例如{"t":2}；至多8个，每值0..128。仅支持有界算术，不运行Python。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `{"t":2}` |
| assertions | 可选结构断言对象：order/size/cycle_rank为整数或尺寸算式；connected/bipartite为布尔；degree_sequence为完整度列表。超图另支持rank/uniform/linear（两边交≤1点）。超图cycle_rank和bipartite针对关联图。失败直接报错。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `{"order":"2*t+2","size":"2*t+1","connected":true,"cycle_rank":0}` |

完整例子 1（可直接粘贴到方式4）：

```json
{"graph_type":"graph","base":{"kind":"path","n":"t+2"},"parameters":{"t":2},"steps":[{"operation":"attach_star","roots":[0],"count":"t"}],"assertions":{"order":"2*t+2","size":"2*t+1","connected":true,"cycle_rank":0}}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"graph_type":"hypergraph","base":{"family":"path","m":2,"k":3},"steps":[{"operation":"attach_path","roots":[{"kind":"leaf","edge":0}],"length":1}],"assertions":{"uniform":true,"rank":3,"linear":true,"cycle_rank":0}}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_recipe.json)

## hypergraph_path_analysis

按起终点分析超图内部松路及关联子矩阵。

前提：结构支持非一致超图；相邻边恰交1点，非相邻边不交，主干点不能重复。

工具限制：结构支持非一致超图；相邻边恰交1点，非相邻边不交，主干点不能重复。；内部交点全图度须2，私有点全图度须1；不满足时仍返回路线但internal_loose_path=false。；至多128顶点/128边；赋权子矩阵不在路径上重新归一化。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多128项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[[0,1,2],[2,3,4]]` |
| start | 已有起点标签。 | 填写一个整数，不填单位或Python表达式。 或 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `0` |
| end | 不同于起点的已有终点。 | 填写一个整数，不填单位或Python表达式。 或 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `4` |
| edge_indices | 按起点到终点顺序的0起始超边编号，1..64且互异；省略时仅接受关联图中的唯一通路。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多64项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1]` |
| weights | 按输入超边顺序排列的边权，一边一项。数值谱要求有限正权；精确消元的系数规则另见工具说明。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,1]` |
| weighted_incidence | true从原始完整超图Perron解提取赋权关联子矩阵；此时要求连通一致、正权及0≤α<1。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `true` |
| alpha | A_alpha=alpha*D+(1-alpha)*A中的参数；仅选择相关阵型/分支时使用。允许范围按Schema，数值Perron要求0<=alpha<1。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥0，<1。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |

完整例子 1（可直接粘贴到方式4）：

```json
{"edges":[[0,1,2],[2,3,4]],"start":0,"end":4,"weighted_incidence":true}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/hypergraph_path_analysis.json)

## graph_batch_study

批量构图、计算与对照导出。

前提：至多12项、累计≤512顶点，单图≤128；精确多项式≤8顶点。

工具限制：至多12项、累计≤512顶点，单图≤128；精确多项式≤8顶点。；单项失败不覆盖其他结果；批次可返回partial/failed，必须检查rows.errors。；plot需[visual]依赖；输出当前任务outputs中的新目录，不覆盖输入。；必须检查calculation_status、export_status及rows.errors；已完成计算不因可恢复导出失败自动重算，安全边界/核心完整性失败仍停止。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| cases | 1..12个{name,graph_type,input或recipe}对象；name简短名称。graph_type为graph/hypergraph/weighted，默认graph。graph的input={kind,n,edges}；hypergraph为{edges,vertices,weights}；weighted为带权谱工具参数（不含exact）；recipe为参数化构图工具参数，graph_type须一致。每项单独填参数可作扫描。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：至少1项，最多12项。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `[{"name":"P3","input":{"kind":"path","n":3}},{"name":"K3","input":{"kind":"complete","n":3}}]` |
| calculations | 不重复列表：structure基本结构，spectrum邻接数值谱/超图Perron谱，charpoly普通图精确多项式。默认前两项。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多3项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `["structure","spectrum","charpoly"]` |
| plot | true同时排版普通图/超图为PNG、SVG、PDF；带权/有向图暂不绘制，记录说明而不丢弃方向/权重。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值false；从示例开始时优先保留示例中的值。 | `false` |
| seed | 可复现的随机种子；用于随机构造、初始向量或自动布局，不是计算精度。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤4294967295。 | 可选；未填写过时回车使用默认值42；从示例开始时优先保留示例中的值。 | `42` |

完整例子 1（可直接粘贴到方式4）：

```json
{"cases":[{"name":"P3","input":{"kind":"path","n":3}},{"name":"K3","input":{"kind":"complete","n":3}}],"calculations":["structure","spectrum","charpoly"]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_batch_study.json)

## symbolic_analysis

受控符号求和和局部级数。

前提：表达式≤1024字符/128语法节点；只解释数学白名单。

工具限制：表达式≤1024字符/128语法节点；只解释数学白名单。；阶乘/二项式数值参数≤128；符号计算仍受计算进程时间/内存上限。；所有条件分支保留；不自动将条件结论当无条件公式。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 summation: 在整数界限间进行符号求和，保留条件、未求值及发散状态；上界可为oo。; series: 在指定有限中心作局部展开，保留O项和截断式，不声明全局收敛。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：summation, series | 必填，不能留空；从示例开始时可回车保留已填值。 | `summation` |
| expression | 算式文本或数字；支持+−*/^、括号、声明变量、pi/E及sin/cos/tan/exp/log/sqrt/Abs/factorial/binomial。拒绝属性、导入、下标和代码。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥-1000000000000，≤1000000000000。 或 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 范围：最多1024字符。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `x^2` |
| variable | 求和下标或展开变量，默认x；不能与参数或数学函数重名。 | 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 范围：最多32字符。 | 可选；未填写过时回车使用默认值"x"；从示例开始时优先保留示例中的值。 | `x` |
| parameters | 符号名列表如["n"]，求和时全部声明为整数，展开时为一般符号；至多8个。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `["n"]` |
| lower | 包含在内的整数求和下界，可用整数参数。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥-1000000000000，≤1000000000000。 或 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 范围：最多1024字符。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| upper | 包含在内的整数求和上界，或字符串"oo"；数值跨度≤10000；符号界限在conditions中保留上界≥下界条件。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥-1000000000000，≤1000000000000。 或 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 范围：最多1024字符。 | 可选；未填写过时回车使用默认值10；从示例开始时优先保留示例中的值。 | `n` |
| center | 级数展开中心，有限实数算式如0或"pi"；不含变量。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥-1000000000000，≤1000000000000。 或 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 范围：最多1024字符。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `0` |
| order | 1..16，保留至O((x−center)^order)；可能出现负幂或分数幂，非全局收敛承诺。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤16。 | 可选；未填写过时回车使用默认值6；从示例开始时优先保留示例中的值。 | `5` |

完整例子 1（可直接粘贴到方式4）：

```json
{"operation":"summation","expression":"x^2","variable":"x","upper":"n","parameters":["n"]}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"operation":"series","expression":"exp(x)","order":5}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/symbolic_analysis.json)

## block_matrix_analysis

精确分块操作及多项式伴随块。

前提：所有矩阵元素通过受控算术解析，有限小数按有理数处理。

工具限制：所有矩阵元素通过受控算术解析，有限小数按有理数处理。；块尺寸不重不漏；右矩阵沿column_sizes切分，返回每个行块的各项乘积。；伴随块次对角为1，最后一列为负的升幂系数；先归一为首一，不以Jordan分解替代。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| operation | 运算分支。必须依据operations中的含义选择；不同分支会读取不同参数并返回不同字段。 extract: 按行块和列块尺寸提取所有子矩阵。; permute: 按给定完整排列重排行块、列块，同时返回实际行列索引。; multiply: 按块拆分乘法并累加，输出各贡献及与直接矩阵乘法的一致性。; companion_blocks: 将各首一多项式的伴随矩阵组成块对角矩阵并核验特征多项式乘积。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：extract, permute, multiply, companion_blocks | 必填，不能留空；从示例开始时可回车保留已填值。 | `multiply` |
| matrix | 按行填写≤16×16矩形数据，元素支持有理数算式与已声明整数参数。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[1,2],[3,4]]` |
| row_sizes | 正整数行块尺寸，如[1,2]；和必须等于左矩阵行数。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,1]` |
| column_sizes | 正整数列块尺寸，和等于左矩阵列数；乘法时同时划分右矩阵的行。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,1]` |
| row_order | permute使用的行块0起始完整排列；省略保持顺序。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1]` |
| column_order | permute使用的列块完整排列。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1]` |
| right | multiply右矩阵，行数等于左矩阵列数。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[2],[1]]` |
| polynomials | companion_blocks使用系数组列表，从最高次到常数。如[[1,0,-2],[1,"-t"]]；首项须显式非零有理数，每块次数1..8，总次数≤16。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：至少1项，最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[1,0,-2],[1,"-t"]]` |
| parameters | 整数符号名称列表，如["t"]；伴随块保留x为多项式变量。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多8项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `["t"]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"operation":"multiply","matrix":[[1,2],[3,4]],"row_sizes":[1,1],"column_sizes":[1,1],"right":[[2],[1]]}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"operation":"companion_blocks","polynomials":[[1,0,-2],[1,"-t"]],"parameters":["t"]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/block_matrix_analysis.json)

## graph_class_certificate

广义线图判定及可复核证书。

前提：普通无向简单图，至多10顶点。定义为根图线图加按根点连接的鸡尾酒会图。

工具限制：普通无向简单图，至多10顶点。定义为根图线图加按根点连接的鸡尾酒会图。；每个覆盖块为团减不交匹配，缺边配对顶点仅属于本块；其他点至多属2块，块间交至多1点。；正证书逐邻接验证；负证书通过确定性穷尽搜索复核。状态预算耗尽不输出证书或布尔结论。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `star` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤10。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `5` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1],[1,2]]` |
| search_budget | 有限精确覆盖搜索状态上限1..200000，默认100000；耗尽返回indeterminate，不能当作否定。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤200000。 | 可选；未填写过时回车使用默认值100000；从示例开始时优先保留示例中的值。 | `100000` |

完整例子 1（可直接粘贴到方式4）：

```json
{"kind":"star","n":5}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"kind":"star","n":6}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_class_certificate.json)

## graph_energy_study

有限整数参数域的精确能量比较。

前提：至多10顶点的有理数实对称矩阵；超图张量和一般复权/有向矩阵不适用。

工具限制：至多10顶点的有理数实对称矩阵；超图张量和一般复权/有向矩阵不适用。；先隔离全部实根并按重数累加绝对值；差区间不含0才能判严格大小。；同特征多项式可证能量相等；非同谱能量也可能相同，此时允许undetermined。；最多16个参数值；精确运算仍受外层时间/内存上限。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| left | 左图{kind,n,edges}，或{"recipe":构图配方对象}，或{"weighted":带权图参数（不含exact，matrix仅可选A）}。图能量仅取有理实对称邻接矩阵的特征值绝对值之和，不接受L/Q等其他阵型。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `{"recipe":{"base":{"kind":"path","n":"t+2"}}}` |
| right | 右图，输入格式同left。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 必填，不能留空；从示例开始时可回车保留已填值。 | `{"recipe":{"base":{"kind":"complete","n":"t+2"}}}` |
| parameter | 扫描整数参数名，默认t；注入两侧recipe的parameters。 | 填写文本原值；逐项填写不需要外层引号，完整JSON中必须加双引号。 范围：最多32字符。 | 可选；未填写过时回车使用默认值"t"；从示例开始时优先保留示例中的值。 | `t` |
| values | 1..16个互异整数，范围0..128；默认[0]。仅覆盖此显式有限域。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多16项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,2]` |
| digits | 初始根隔离十进制位数4..24，未分离时最多精化至48位。 | 填写一个整数，不填单位或Python表达式。 范围：≥4，≤24。 | 可选；未填写过时回车使用默认值12；从示例开始时优先保留示例中的值。 | `12` |

完整例子 1（可直接粘贴到方式4）：

```json
{"left":{"recipe":{"base":{"kind":"path","n":"t+2"}}},"right":{"recipe":{"base":{"kind":"complete","n":"t+2"}}},"values":[1,2]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_energy_study.json)

## research_environment

只读检测三维绘图与TeX可选环境。

前提：包可发现或程序在PATH中不等于实际计算/编译已验证。

工具限制：包可发现或程序在PATH中不等于实际计算/编译已验证。；不下载依赖，不调用模型/网络，不修改环境；Windows安装器开发仍搁置。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。


| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |

完整例子 1（可直接粘贴到方式4）：

```json
{}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/research_environment.json)

## combinatorial_plot

绘制格路径、矩形或数值矩阵棋盘，导出PNG/SVG/PDF。

前提：路径步仅为0/1；棋盘须为非空矩形有限数值矩阵，标签数量须匹配。

工具限制：需要[visual]依赖；路径至多2048步，棋盘每维至多32，标签最长80字符。；文件仅写入自动生成的任务输出目录，不接受模型指定路径，不覆盖研究成果。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 先选择操作。逐步格路径steps中0向上、1向右；按步序号生成时right_steps从0计数。棋盘matrix按行输入，非零格着色，行号沿y轴自下向上；矩形bounds为[xmin,ymin,xmax,ymax]。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| operation | 绘图种类；切换后按对应分支填写输入。 grid_path: 从原点按steps逐步绘图：0向上，1向右，返回全部路径坐标和终点。; lattice_path: 填写total_steps及0起始right_steps生成格路径；其余步向上。; rectangle: 按bounds=[xmin,ymin,xmax,ymax]绘制矩形；fill控制是否填充。; chessboard: 按matrix绘制矩形棋盘，非零格着色，零格留白；可设置行列标签。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：grid_path, lattice_path, rectangle, chessboard | 可选；未填写过时回车使用默认值"grid_path"；从示例开始时优先保留示例中的值。 | `grid_path` |
| steps | grid_path的0/1步序列；0向上、1向右，从原点出发。例如[1,0,1,0]。可为空，至多2048步。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多2048项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,0,1,0]` |
| total_steps | lattice_path的总步数0..2048；所有步序号均从0开始。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤2048。 | 可选；未填写过时回车使用默认值6；从示例开始时优先保留示例中的值。 | `4` |
| right_steps | lattice_path中向右移动的步序号，其余步向上；例如总步数4、[0,2]等价于[1,0,1,0]。不可重复，必须小于总步数；可为空。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多2048项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,2]` |
| matrix | chessboard的按行矩形数值矩阵；非零格着色、零格留白。行号沿y轴自下向上，列号从左向右；每维至多32。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少1项。 每行最多32项。 每项填写整数或小数。 范围：至少1项，最多32项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[1,0,1],[0,1,0]]` |
| bounds | rectangle的[xmin,ymin,xmax,ymax]，最小值不得大于对应最大值。例如[0,0,3,2]。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少4项，最多4项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,0,3,2]` |
| fill | rectangle是否填充内部；false仅保留矩形边框。 | 填写 是/否 或 true/false；逐项填写也支持1/0。 | 可选；未填写过时回车使用默认值true；从示例开始时优先保留示例中的值。 | `false` |
| row_labels | chessboard行标签，可用整数或普通文本；数量等于矩阵行数，按自下向上顺序显示；不是Python或LaTeX表达式。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多32项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `["下行","上行"]` |
| column_labels | chessboard列标签，数量等于矩阵列数，按从左向右顺序显示；省略时显示0起始列号。 | 填写完整JSON数组；嵌套层次、字符串双引号须保留。复杂张量或含字符串标签时不要使用数字简写。 范围：最多32项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `["甲","乙","丙"]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"operation":"grid_path","steps":[1,0,1,0]}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"operation":"lattice_path","total_steps":4,"right_steps":[0,2]}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"operation":"rectangle","bounds":[0,0,3,2],"fill":false}
```

完整例子 4（可直接粘贴到方式4）：

```json
{"operation":"chessboard","matrix":[[1,0,1],[0,1,0]],"row_labels":["下行","上行"],"column_labels":["甲","乙","丙"]}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/combinatorial_plot.json)

## graph_layout

普通图自动布局、固定顶点重排与坐标变换，导出预览及完整坐标。

前提：需要1..128顶点的无向简单图；树形布局必须为连通无圈的树。；填写positions时须覆盖全部顶点，每个顶点恰好出现一次；坐标必须有限。

工具限制：需要[visual]依赖，至多128点且绘图至多128边、2048点边关联。；结果坐标绝对值不得超过10^9；重合坐标按原值保存并明确不生成预览，绝不自动扰动数学结果。；该入口适用于普通图；超图布局与拖动继续使用现有超图结构图入口。

字段范围仅描述输入格式上限；还须满足上述工具限制及数学前提。

- 标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。
- 坐标positions为[{"vertex":0,"xy":[0,0]},...]，填写时须覆盖全部顶点。固定弹簧布局还需fixed_vertices；对齐用vertices选择部分顶点。坐标变换顺序为绕原点缩放、逆时针旋转（度）、最后平移。结果可继续拖动编辑或传入TikZ。
- positions可省略使用自动布局；手填时每项为{"vertex":标签,"xy":[x,y]}，必须覆盖全部顶点且坐标不能全相同。

| 参数 | 含义 | 输入方式与范围 | 留空规则 | 单字段输入例子 |
| --- | --- | --- | --- | --- |
| graph_document | 可选完整图对象，format=graph-research-graph、version=1。保留原标签、孤立点、graph_type、方向、权重、坐标及style；须与外层结构/坐标参数一致。样式包括字号、颜色、线型、标签显示及pt偏移。布局按无向无权支撑结构，不修改方向/权重。 | 填写JSON对象，字段名和字符串用英文双引号，例如{"kind":"path","n":3}。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `{"format":"graph-research-graph","version":1,"graph_type":"graph","directed":true,"weighted":true,"vertices":[0,1,2],"edges":[{"vertices":[0,1],"weight":2}],"positions":[[0,0],[1,0],[0,1]],"style":{"weight_labels":true,"font_size":10}}` |
| operation | 选择自动布局或已有坐标操作；spring可附加固定顶点，其余操作不使用fixed_vertices。 spring: 使用NetworkX弹簧布局；有positions时以此初始化；fixed_vertices指定的点保留原始坐标。; circular: 按顶点顺序排列到圆周，图的邻接关系保持不变。; spectral: 用NetworkX拉普拉斯谱坐标生成二维布局；重特征值或非连通图可能导致坐标不唯一或重合。; tree: 核验当前图是一棵树，再按root的广度优先层次生成二维坐标。; transform: 对完整positions依次作正等比例缩放、绕原点逆时针旋转angle度、平移offset。; align_horizontal: 将vertices选中的点移到相同y坐标，取其原y均值；其他点不动。; align_vertical: 将vertices选中的点移到相同x坐标，取其原x均值；其他点不动。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：spring, circular, spectral, tree, transform, align_horizontal, align_vertical | 可选；未填写过时回车使用默认值"spring"；从示例开始时优先保留示例中的值。 | `spectral` |
| kind | 普通无向简单图族。自定义图必须kind='edges'；此时给出n和edges。path/cycle/complete/star/empty直接按n构造。 | 填写选项原值（不加引号），或在逐项填写时输入从1开始的选项编号。可选：path, cycle, complete, star, empty, edges | 可选；未填写过时回车使用默认值"path"；从示例开始时优先保留示例中的值。 | `path` |
| n | 图的顶点数，显式包含孤立点；自定义普通图顶点为0..n-1。并非根据edges自动推断。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤128。 | 可选；未填写过时回车使用默认值5；从示例开始时优先保留示例中的值。 | `5` |
| edges | 超边/边列表，每项列出该边的成员。边内顶点不可重复，不接受重复边；具体边大小、标签类型和是否允许空列表以本工具Schema为准。 | 填写嵌套JSON数组（每行一项），例如[[0,1],[1,2]]；逐项填写也可用0,1;1,2，分号分行、逗号分项。 每行至少2项。 每行最多2项。 每项填写整数。 范围：最多1024项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[[0,1]]` |
| positions | 完整坐标记录[{vertex:0,xy:[0,0]},...]。spring可作为初始布局；transform和对齐必须提供；vertex使用0起始计算编号。 | 填写JSON对象列表，每项为一个记录；不要使用逗号/分号数字简写。 范围：至少1项，最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[{"vertex":0,"xy":[0,0]},{"vertex":1,"xy":[1,1]},{"vertex":2,"xy":[2,0]}]` |
| fixed_vertices | spring中保持坐标不变的顶点编号列表；须同时提供全部positions。其他顶点重新布局，固定点不重新缩放。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,2]` |
| vertices | 仅供水平/竖直对齐的顶点编号列表，省略为全部顶点；选中的点对齐到其对应坐标均值，未选顶点不动。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少1项，最多128项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[0,1]` |
| root | tree布局的根顶点，须属于当前树；根在上方，后续层向下排列。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤127。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `2` |
| iterations | spring布局的最大迭代次数1..5000。 | 填写一个整数，不填单位或Python表达式。 范围：≥1，≤5000。 | 可选；未填写过时回车使用默认值150；从示例开始时优先保留示例中的值。 | `30` |
| seed | spring布局的随机种子；相同图、输入及依赖环境可重现布局。 | 填写一个整数，不填单位或Python表达式。 范围：≥0，≤4294967295。 | 可选；未填写过时回车使用默认值42；从示例开始时优先保留示例中的值。 | `42` |
| angle | transform绕原点逆时针旋转的角度，单位为度。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：≥-360000，≤360000。 | 可选；未填写过时回车使用默认值0；从示例开始时优先保留示例中的值。 | `90` |
| scale | transform的正等比例缩放倍数；先缩放并旋转，最后平移，不表示图的幂。 | 填写整数或小数，不填单位、算式、NaN或Infinity。 范围：>0，≤1000000.0。 | 可选；未填写过时回车使用默认值1；从示例开始时优先保留示例中的值。 | `2` |
| offset | transform最后施加的二维平移向量[dx,dy]，省略为[0,0]。 | 填写JSON数字列表，例如[1,2,3]；逐项填写也可用1,2,3，逗号分项。 范围：至少2项，最多2项。 | 可选，无值时可留空；某些操作分支仍需要此项，见用途说明。 | `[1,0]` |

完整例子 1（可直接粘贴到方式4）：

```json
{"operation":"spectral","kind":"path","n":5}
```

完整例子 2（可直接粘贴到方式4）：

```json
{"operation":"tree","kind":"path","n":5,"root":2}
```

完整例子 3（可直接粘贴到方式4）：

```json
{"operation":"spring","kind":"path","n":3,"positions":[{"vertex":0,"xy":[0,0]},{"vertex":1,"xy":[1,1]},{"vertex":2,"xy":[2,0]}],"fixed_vertices":[0,2],"iterations":30}
```

完整例子 4（可直接粘贴到方式4）：

```json
{"operation":"transform","kind":"path","n":3,"positions":[{"vertex":0,"xy":[0,0]},{"vertex":1,"xy":[1,1]},{"vertex":2,"xy":[2,0]}],"angle":90,"scale":2,"offset":[1,0]}
```

完整例子 5（可直接粘贴到方式4）：

```json
{"operation":"align_horizontal","kind":"path","n":3,"positions":[{"vertex":0,"xy":[0,0]},{"vertex":1,"xy":[1,1]},{"vertex":2,"xy":[2,0]}],"vertices":[0,1]}
```

完整例子 6（可直接粘贴到方式4）：

```json
{"edges":[[0,1]],"graph_document":{"format":"graph-research-graph","version":1,"graph_type":"graph","directed":true,"weighted":true,"vertices":[0,1,2],"edges":[{"vertices":[0,1],"weight":2}],"positions":[[0,0],[1,0],[0,1]],"style":{"weight_labels":true,"font_size":10}},"kind":"edges","n":3,"operation":"circular"}
```

可导入参数文件：[第一个完整例子](../examples/offline-inputs/graph_layout.json)
