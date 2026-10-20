# 基础图操作、递推与研究图族（v0.21）

这些功能共用现有计算内核、保护进程和结果包，无需模型 API。桌面「本地工具」中可选择「图结构变换」「线性递推」「整数线性方程」或「超图构造」；接入模型后使用同一份工具契约。每项均提供可编辑的输入示例，详见[全部输入说明](docs/OFFLINE_INPUTS.md)。

## NetworkX 基础图操作

`graph_edit` 新增 `core`、`relabel`、`subdivide_edges`，继续支持补图、线图、子图等已有操作。

```json
{"operation":"core","kind":"edges","n":5,"edges":[[0,1],[1,2],[2,0],[2,3]],"core_k":2}
```

反复去掉度小于 2 的顶点，得到三角形；孤立点也会删除。`core_k` 可修改核心阶数。树的 2-core 为空，这是正确结果。

```json
{"operation":"relabel","kind":"path","n":3,"labels":["甲","乙","丙"]}
```

新标签按原顶点顺序给出，必须完整、互不重复，不合并顶点。剖分示例：

```json
{"operation":"subdivide_edges","kind":"path","n":3,"edit_edges":[[0,1]],"subdivisions":2}
```

在指定边上插入两个新顶点；省略 `edit_edges` 对所有边操作。结果中的 `graph_spec` 可直接传给普通图谱、图不变量等工具；`graph_spec_labels` 给出重新编号与输出标签的对应关系，保留孤立点。空图的 `n=0` 不适用于要求至少一个顶点的谱工具。

Python 还提供 `graphs.BaseGraph`、`Relabel`、`sorted_label`、`generalized_line_graph`、`subdivide_edges`。`BaseGraph` 明确采用 2-core；重编号返回副本，不修改传入图或映射。旧 GF(2) 关联矩阵公式在简单图上等于普通线图，保留函数名不代表新增广义线图识别算法。此次边剖分也不替代旧 Sage 中同名的矩阵分块函数 `subdivide`。

## SymPy 线性递推

选择 `linear_recurrence`，约定方程为：

`coefficients[0]*a(n) + ... + coefficients[r]*a(n+r) = forcing(n)`。

```json
{"coefficients":[-1,-1,1],"initial_values":[0,1],"forcing":0,"start":0,"terms":12}
```

这是 Fibonacci 递推，返回 `0,1,1,2,3,5,8,13,21,34,55,89`。长度为 r 的初值依次对应 `a(start)` 至 `a(start+r-1)`。例如 `[-1,1]`、初值 `[0]`、右端项 `"2*n+1"` 得到平方数序列。分数请写成 `"1/3"`，避免预先使用浮点近似。

支持 1 至 8 阶、有理函数系数，系数分子分母次数不超过 8；右端项支持超几何项及有限和，例如 `n`、`2^n`、`factorial(n)`。最高移位系数在整数定义域内变零、系数或右端项存在已检出的极点等情形会拒绝求解，需单独分析。最多输出 64 项。

| 状态 | 含义 |
| --- | --- |
| `verified_closed_form` | 闭式已通过递推恒等式及全部初值校验 |
| `unverified_closed_form` | 有闭式候选，但尚未通过校验，不能当作已证明的解 |
| `terms_only` | 未找到闭式，仍返回独立递推得到的精确项；不表示无解 |

Python 入口为 `algebra.recurrences.solve_linear_recurrence`。此接口处理上述正则线性递推，不能替代所有 Maxima/Sage 递推功能。

## SymPy 整数线性方程

选择 `integer_linear_system`，求 `A*x=b` 的整数解。使用 SymPy 1.14+ 的 Smith 分解及整数变换，返回特解、完整整数零空间基和自由整数参数，不用有理数解冒充整数解。

```json
{"matrix":[[2,4]],"rhs":[6]}
```

例如 `x+2y=3` 有无穷多整数解；返回基可能采用不同但等价的整数参数化方式。`{"matrix":[[2]],"rhs":[1]}` 返回 `no_solution`。

```json
{"matrix":[[2]],"rhs":["n"],"parameters":["n"]}
```

返回 `conditional`，要求 `Mod(n,2)=0` 才有整数解。输入参数和自由参数都取整数；所有条件必须同时成立。`solved` 表示不附加条件即有整数解。符号条件不会自动化简成所有参数的显式取值列表。

系数矩阵为 1 至 12 行、1 至 12 列的常整数矩阵，元素绝对值至多 10^9；右端项为整数，或至多 8 个已声明整数参数的整系数多项式，次数至多 8。暂不支持符号系数矩阵、不等式或非线性丢番图方程。Python 入口为 `algebra.integer_systems.solve_integer_linear_system`，`algebra.linear` 中的旧名 `solve_linear_system` 也返回该结构化结果。

## 六类定制超图

统一放入 `hypergraphs.research_families`，使用已有松路、松圈和附接路径操作组合。`generate_hypergraph` 可选以下族；`m` 为主干边数，`k` 为一致度，所有路长都以边数计，0 表示不附接。

| family / Python 函数 | 结构 |
| --- | --- |
| `gee` / `Gee` | 松路两端边上，各条悬挂路使用不同的 1 度根点 |
| `gev` / `Gev` | 左端各路使用不同根点，右端各路共用一个根点 |
| `gvv` / `Gvv` | 左右端各自共用一个根点，左右根点不同 |
| `gwg` / `GWG` | 按主干边序号和共享顶点指定悬挂路分布 |
| `ca` / `Ca` | 松圈的一个 1 度点附一条路，需要 k≥3 |
| `cva` / `Cva` | 松圈的一个 2 度交点附一条路，可取 k=2 |

```json
{"family":"gee","m":3,"k":3,"left_lengths":[1,2],"right_lengths":[1]}
```

```json
{"family":"gwg","m":3,"k":3,"edge_paths":[{"edge_index":0,"lengths":[1,2]}],"vertex_paths":[{"vertex":1,"lengths":[2]}]}
```

`edge_index` 从 0 开始，`vertex` 必须是主干上度大于 1 的现有顶点。`ca/cva` 使用 `pendant_length` 指定附接路长。每组至多 8 条路，各长至多 32；工具构造预算为 128 个顶点及 128 条边。

保留指定 k，不照搬旧程序自动增大 k 的行为。根点不足时明确报错；通过度和关联关系选择根点，顶点编号不保证与旧 Sage 完全一致，应比较结构同构关系。构造结果可继续交给结构分析、绘图、TikZ 和符合前提的谱工具；联动已有工具不会创建扩展包。

本轮没有迁移所有历史定制图族，`HyperTree1`、`U1/U2`、`LinkG` 等仍需分别核对。[迁移清单](MIGRATION_STATUS.md)记录接口映射，不是与 Sage 全部参数逐项等价的证明。Windows 安装包开发继续搁置。
