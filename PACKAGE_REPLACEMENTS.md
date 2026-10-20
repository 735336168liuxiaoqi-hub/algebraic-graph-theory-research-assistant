# 继续用Python包替代Sage功能（v0.22）

科研功能验收以[能力覆盖表](FUNCTIONAL_COVERAGE.md)为准，整体用途可实现即可；无需逐个兼容旧函数。旧定义及每项用途保存在[追溯台账](SAGE_REMAINING_REVIEW.md)。本轮为53条旧定义记录补上实现或复用映射，同时修正3条原有误判；待迁移记录由180条变为130条。两份超图文件含重复用途，类与方法也分别计数，这些数值不是独立算法数或Sage等价性百分比。

本轮使用已安装的NetworkX、SymPy、NumPy及可选Matplotlib，无需新增安装依赖、Sage或WSL。旧源文件不执行、不修改。Windows安装器开发继续搁置。

## 无API桌面与模型工具入口

该阶段保留32个工具名及153项参数；后续v0.23新增9个[科研工作流](RESEARCH_WORKFLOWS.md)，当前总计41个工具和202项参数。下列新分支与旧分支共用输入说明、中文名称和悬停提示，模型也读取同一份契约。

| 工具 | 新选项 | 功能 |
| --- | --- | --- |
| 图结构变换 `graph_edit` | `replace_edge` | 用另一个图替换一条边，按指定端点粘合，保留孤立点 |
| 精确矩阵计算 `exact_matrix_operation` | `elementary` | 交换、数乘、加倍数操作行或列，返回精确矩阵及LaTeX过程 |
| 精确矩阵计算 | `split_row` | 拆分某行并自动补余项，返回行列式的线性展开 |
| 组合计算 `combinatorial_calculation` | `cycle_index` | 由生成元建立完整置换群，再计算标准循环指标 |
| 组合计算 | `cayley_graph` | 生成右Cayley简单有向图，附编号与群元素对应表 |
| 超图变换 `hypergraph_transform` | `attach_star` | 新超边共享同一个根顶点集，其余顶点分别新建 |
| 超图结构分析 `hypergraph_structure` | `laplacian_equations` | 生成一致超图L张量特征方程，不求解方程 |

### 用三点路替换一条边

```json
{"operation":"replace_edge","kind":"path","n":3,"edit_edges":[[0,1]],"replacement":{"kind":"path","n":3},"endpoints":[0,2]}
```

替换图的0、2号点分别识别为原边两端，产生一个新内部顶点。结果是4顶点路径图。新图仍可用返回的 `graph_spec` 联动图谱等工具；结果最多128顶点。

### 精确初等变换与拆行

```json
{"operation":"elementary","matrix":[[1,2],[3,4]],"actions":[{"kind":"add_row","target":1,"source":0,"factor":-3}]}
```

第二行减去三倍第一行，结果为 `[[1,2],[0,-2]]`。行列序号均从0开始；操作支持 `swap_rows`（交换行）、`scale_row`（数乘行）、`add_row`（加行倍数），以及对应的 `swap_columns/scale_column/add_column`。

矩阵最多12×12，最多32步。输入仍为整数或小数，按十进制转精确有理数；字符串代码、任意表达式不进入该工具。允许数乘0，但这种操作不可逆；不能因此声称矩阵保持行等价。

```json
{"operation":"split_row","matrix":[[1,2],[3,4]],"row_index":0,"row_terms":[[1,0]]}
```

原第一行 `[1,2]` 拆为 `[1,0]` 与自动补入的 `[0,2]`，两项行列式为4和−6，和为原行列式−2。这里利用的是行列式对单行的线性性，**不是说原矩阵等于各项矩阵之和**。

### 循环指标和Cayley图

```json
{"operation":"cycle_index","generators":[[1,0,2],[1,2,0]]}
```

生成元分别为换位和三循环，生成6阶群S3。标准循环指标为 `(x1^3+3*x1*x2+2*x3)/6`。必须对完整群求平均，不能只对输入的两个生成元平均。

把操作改为 `cayley_graph` 即得到6个顶点的右Cayley有向图。可提取结果中的 `n/arcs` 传给 `directed_graph_spectrum`，`matrix="A"` 得到谱半径2。这里 `n` 是群阶，不是置换的作用点数。

群分支限8个作用点、8个生成元、128个群元素，先判断群阶再展开。有向谱工具另限64个顶点；更大的Cayley图只保证可返回结构，不会把顶点数偷偷截断。

### 共享根集附边

```json
{"operation":"attach_star","edges":[[0,1,2]],"roots":[0,1],"count":2,"rank":3}
```

得到边 `[0,1,2]、[0,1,3]、[0,1,4]`。新增的两条边始终共享0、1两个根点；这与逐边延伸的 `attach_path` 不同。新边权为1，保留旧边权和孤立点；结果限128顶点、128边，根集必须小于目标边大小。

## Python库中的其他替代

以下函数已进入库，但没有为每个旧函数额外创建模型工具名。模型只调用工具目录中的名字。

| 入口 | 功能与边界 |
| --- | --- |
| `graphs.set_edge_weight / weight_edges / complex_weight` | 按边或同权边组赋权、生成加权矩阵、构造i/−i方向矩阵；默认复制或返回数组，不隐式修改原图 |
| `graphs.edge2graph / replace_edges_by_graph` | 单边或批量替换，内部顶点独立编号，保留孤立点与边属性 |
| `graphs.PartProduct` | 在选定子图上作图积并接回外部邻接；遇到顶点标签碰撞明确报错 |
| `graphs.pick_vertices / list2dict / Index` | 按度分组、按二元记录分组、读取显式边序号 |
| `graphs.Cycle / mygraphmul / mygraphsub` | 按顶点顺序成圈、不交并复制或笛卡尔积、保留顶点的删边 |
| `graphs.random_symmetric_matrix / AMdb` | 区间随机整数对称矩阵、以端点度倒数之和赋权的矩阵，孤立点给零行列 |
| `graphs.checksign1` | 非零多项式系数的符号集合；未知符号保持符号形式，不自动当作可比性证明 |
| `graphs.polynomials_for_addstarsgraph` | 对附叶图计算L/Q特征多项式Schur表达式；原图无权简单、至多12原顶点，数值叶数合计至多256；符号叶数需非负整数假设且不能叫x。旧A分支公式错误，明确拒绝 |
| `algebra.groups.cayley_graph` | Python接口还支持左/右/双侧、带标签重边和自环，以及显式有限半群元素与生成元；默认上限4096元素 |
| `combinatorics.getCycleIndex1` | 保留旧函数的“循环分拆直接作为指数”编码；**不是标准循环指标**。Pólya计数请用 `getCycleIndex` 或工具 `cycle_index` |
| `linear_algebra.el_rop2/3、el_cop2/3、do_Actions` | SymPy行列变换；`repl=True`需可变SymPy矩阵，全部步骤成功后才提交原地改动 |
| `linear_algebra.split_row / split_vector` | 行列式拆行及单非零分量向量分解 |
| `linear_algebra.lst2ltx / sum_hold / Op_links / do_show_ops / show_equtions` | 返回显式LaTeX，不修改全局打印器，不调用Sage富显示 |
| `linear_algebra.stdequs / Mat2PR` | 线性方程标准化、多项式系数域DomainMatrix转换；后者基础域支持ZZ/QQ |
| `linear_algebra.matrix_round / map_round` | 只有候选舍入误差在eps以内时才替换，保留精确值和大整数 |
| `combinatorics.getGridPath / gridPath / lattice_path / rectangle / chess_board` | 用Matplotlib画格路径、矩形和矩形棋盘，返回Figure；可选返回格路径坐标 |

```python
import networkx as nx
from graph_research import graphs

g = nx.path_graph(3)
weighted = graphs.set_edge_weight(g, {(0, 1): 2, (1, 2): 3})
matrix = graphs.weight_edges(weighted)
```

普通 `graph_spectrum` 现有接口仍按无权图处理，不会因为图有weight属性就改变数学约定。要使用上面的权重应直接使用返回的加权矩阵进行相应计算；不要将仅有结构信息的 `graph_spec` 当成带权图。

## 目录修正与剩余差距

原目录会在缺失类上继续查找 `__init__/__repr__`，意外找到None对象的方法，已修复。三个误判是 `MyIdentity.__init__`、`MyIdentity.__repr__`、`TCBSpline.__init__`，已恢复待迁移；现有可用目录逐条核对实际可调用路径。

源码提取也修复了TeX多行字符串导致的函数截断，保留了带字符串默认参数的真实定义。原始811条定义记录仍全部保留。

后续已补齐明确定义的研究超图族、内部路分析、广义线图有界证书、分块与有限参数能量工作流，当前边界以[科研能力覆盖表](FUNCTIONAL_COVERAGE.md)为准。[Python库入口整合](LIBRARY_ENTRIES.md)另接通格路径/棋盘绘图、布局与坐标调整、车多项式、Cayley乘法侧、批量替换边和局部笛卡尔积。完整隐式三维绘图及TeX编译仍未接通，不以旧函数数量评价功能完成率。

实现依据可查 [NetworkX边属性](https://networkx.org/documentation/stable/reference/generated/networkx.classes.function.set_edge_attributes.html)、[SymPy精确矩阵](https://docs.sympy.org/latest/modules/matrices/matrices.html)、[SymPy置换群](https://docs.sympy.org/latest/modules/combinatorics/perm_groups.html)。数学结果以本项目独立断言和适用范围为准，不以函数名字相同代替验证。
