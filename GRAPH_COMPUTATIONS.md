# 图论计算功能与验证范围

验收以[科研能力覆盖表](FUNCTIONAL_COVERAGE.md)为准：完成整体科研用途即可，不要求保留旧Sage函数名、类或显示钩子。已有工具能够组合完成的任务，优先补衔接和统一入口。

实现按[功能分包](PACKAGE_LAYOUT.md)组织，计算定义与工具名保持不变；基础数学依赖和绘图/模型可选依赖分离。

新增基础图操作、线性递推、整数线性方程与六类研究超图，见[新增功能及限制](RESEARCH_TOOLS.md)。输入、返回和分支条件见[自动生成工具手册](docs/model/TOOL_REFERENCE.md)，模型接入与维护见[MODEL_TOOL_GUIDE.md](MODEL_TOOL_GUIDE.md)。

目标是承接原Sage包的计算用途，提供无需Sage/WSL的Python实现。图和超图对象使用NetworkX或本项目的Hypergraph；数值数组使用NumPy，精确多项式和方程使用SymPy。

本轮继续替代的图操作、矩阵变换、有限群及共享根集超边见[替代说明](PACKAGE_REPLACEMENTS.md)，全部剩余定义与用途见[逐项审计](SAGE_REMAINING_REVIEW.md)。

## 可用计算

| 类别 | 主要功能 | 入口示例 |
| --- | --- | --- |
| 普通图矩阵与谱 | A/L/Q/距离/距离Laplacian/归一化Laplacian/Seidel/ABC矩阵，数值谱、精确特征多项式、符号α矩阵 | `graphs.get_Matrix`、`exact_characteristic_polynomial` |
| 有向图 | Hermitian邻接矩阵、普通邻接/出度Laplacian/α矩阵及复数谱 | `hermitian_adjacency_matrix`、`directed_graph_spectrum`工具 |
| 谱分析 | 谱投影、图角、图能量、Estrada指数、同谱分组、Perron向量排序 | `spectral_projectors`、`angle`、`findCospe` |
| 对称性与商矩阵 | 精确顶点轨道、自动同构映射、平均商矩阵、等价划分检查、H联图符号平均商矩阵 | `orbit_subdivision`、`equitable_quotient`、`HJQM` |
| 构图 | theta、毛毛虫、仙人掌、Hamming、随机给定圈秩图、H联、根积、冠积、部分联、顶点粘合 | `theta_graph`、`H_join`、`rooted_product`、`corona_graphs` |
| 图变换 | 添加悬挂星/内部路、逐边剖分、顶点吹胀、边移动、补图、线图和Seidel切换 | `add_stars`、`add_innerPaths`、`K_subdivide_graph`、`Blowup` |
| 有限枚举 | 简单路、指定长度圈、Hamilton圈、给定度序列的非同构简单图 | `All_Paths`、`findCycles`、`Graphs_WithDegreeSequence` |
| 图多项式 | 特征多项式、系数绝对值、反转、路的递推、剖分后多项式、普通图匹配数 | `abscharpoly`、`gen_poly`、`matching_generating_function` |
| 超图构造与变换 | 松路/超星/松圈、点心/边心像星超树、三类双圈；悬挂路、内部路、粘合、根积、剖分、顶点分裂和两种克隆 | `HyperPath`、`VStarLike`、`Bicyclic_C1`、`Add_innerPath`、`Blow_Up` |
| 超图结构 | 关联阵、距离、交图/带权线图、同构、顶点轨道、圈秩、简单路 | `Hypergraph.incidence_matrix`、`orbit_subdivision`、`IsIsomorphic` |
| 超图谱 | α谱半径与Perron向量、正边权、独立D对角、全精度赋权关联矩阵、A/L/Q/α张量、符号特征方程和轨道约化方程 | `alpha_spectrum`、`WeightIncidenceMatrix`、`alpha_eigen_equations` |
| 超图商与多项式 | 顶点轨道商算子、展开向量的原图残差检查、精确匹配多项式 | `Quotient_Graph`、`Matching_Polynomial` |
| 一般张量特征多项式 | 精确Macaulay消元、普通张量代数重数、A/L/Q/α、符号参数、有理权、非对称张量和不连通分量 | `characteristic_polynomial`、`charpoly_H`；见TENSOR_ELIMINATION.md（历史开发记录） |

模型可通过41个受控工具入口调用这些功能族，包括超图绘图、交互编辑器及简单图/超图TikZ代码导出，仍保持可配置API，不默认使用任何付费模型。库级API比模型工具更细。绘图说明见[HYPERGRAPH_PLOTTING.md](HYPERGRAPH_PLOTTING.md)，拖动和坐标往返见[HYPERGRAPH_EDITOR.md](HYPERGRAPH_EDITOR.md)，代码导出见[TIKZ_EXPORT.md](TIKZ_EXPORT.md)。

## 示例

```python
import networkx as nx
import sympy as sp
from graph_research import graphs as gg
from graph_research import hypergraphs as hg

# 符号α特征多项式与轨道商矩阵
alpha = sp.Symbol('alpha')
print(gg.exact_characteristic_polynomial(nx.path_graph(3), 'alpha', alpha))
print(gg.equitable_quotient(nx.star_graph(4)))

# 根据原包功能构图并计算谱
h = hg.VStarLike(1, 2, 3, rank=3)
print(h.alpha_spectrum(0.3))

# 超图商返回算子；不要当作普通简单超图
quotient = hg.Quotient_Graph(h)
print(quotient.blocks)
print(quotient.terms())
print(quotient.alpha_spectrum(0.3))

# 精确匹配多项式，不是一般张量特征多项式
print(hg.Matching_Polynomial(h, sp.Rational(3, 10)))
```

运行综合演示：

```powershell
.\.venv\Scripts\python.exe -X utf8 examples/graph_calculations.py
```

## 数学与接口约定

- 保留原包核心归一化：k一致超图的邻接张量排列位置取`w_e/(k-1)!`。
- 超图谱默认要求连通、一致、正边权、0≤α<1。`vertex_degrees`直接指定D的对角，不是乘到邻接项的任意顶点权。
- 新版`Quotient_Graph`是顶点轨道商算子，逐块验证特征方程系数相同，约化向量会展开回原图检查。它不是普通简单超图，返回类型有意改变。旧边轨道代表元构造保留为`edge_representative_quotient`，不能保证保持谱半径：三边3一致松路在α=0时原谱半径约1.3782407725，旧代表边图约1.2599210499。
- `HJQM`返回按块平均的符号矩阵；只有替换块正则等满足等价划分条件时，才能把它作为谱约化依据。普通图工具会返回`equitable`检查。
- `blowup_vertex`把全部克隆放入同一条边，会改变秩；`Blow_Up`对克隆作笛卡尔展开，保持秩。这两种操作不能混用。
- `add_path`的长度是新超边数；普通图`add_innerPaths`的参数是内部顶点数。函数名保留，但计数约定明确写在文档中。
- 普通图`Count_Subgraph`计算非诱导子图份数。度序列枚举按同构去重；枚举超过预算会报错，不返回声称完整的截断结果。
- `HyperMatrix`加减法现在严格检查形状并返回HyperMatrix，不再隐式广播。`Tensor.tensordot(other)`恢复原方法的矩阵乘法行为，真正张量收缩使用`Tensor.contract(other, axes=...)`。
- Khatri–Rao名称按原包的分块Kronecker积语义实现，分块大小需显式传入；不分块时为Kronecker积。列式Khatri–Rao另用`columnwise_khatri_rao`。
- 超图剖分按“将一条边替换成松路”的定义实现；原旧函数单个非叶锚点的分支并不总是得到这一路径结构，新实现已用同构算例核对。
- `Energy_Diff`直接计算图能量差，不复现旧积分式的归一化或积分误差输出。

## 验证与边界

测试使用已知谱公式、精确多项式恒等式、谱投影重构、图同构、NetworkX预存graph atlas、圈秩和原图展开残差，避免仅检查函数名存在。

枚举是指数规模问题：度序列枚举限9顶点，并有搜索状态上限；模型工具的同构、轨道、符号多项式、稠密张量等也有各自规模限制。超过限制会给出明确错误。

超图绘图已加入：不填充插值曲线、非一致结构及PNG/SVG/PDF；简单图和超图的TikZ代码导出也已加入。结构图已兼容普通简单图；批量图集、参数化构图及结构断言见[科研工作流](RESEARCH_WORKFLOWS.md)。自动TeX编译、三维隐式面、超大规模穷举仍不在本轮实现范围；不以逐项复刻旧定制图族名称验收。一般一致超图张量特征多项式现有精确消元，计算范围由资源上限决定。匹配多项式仍不能代替张量特征多项式。
