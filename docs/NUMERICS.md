# α谱数值算法与张量精确消元

## Newton–Noda 与高 α 稳定计算

v0.31外部pilot的NNI/auto各288点及共同检查器通过，受保护执行在该次环境退出107。v0.31.1补齐启动日志、阶段诊断和稳定赋权矩阵；本机验收记录见[releases/CURRENT.md](releases/CURRENT.md)。未读取holdout或A组算法答案，未覆盖外部pilot文件。

### 使用方法

Python：

```python
from graph_research.hypergraphs import Hypergraph

h = Hypergraph([[0, 1, 2], [2, 3, 4], [4, 5, 6]])
result = h.alpha_spectrum(alpha=0.999, method="newton_noda")
print(result["rho"], result["relative_residual"])
print(result["verification"])
print(result["solver_diagnostics"])
```

工具参数、API 与 MCP 固定步骤共用同一设置：

```json
{
  "edges": [[0, 1, 2], [2, 3, 4], [4, 5, 6]],
  "alpha": 0.999,
  "method": "newton_noda",
  "tolerance": 1e-11,
  "max_iterations": 20000
}
```

桌面“超图数值谱”中选择“保正牛顿–Noda迭代”；悬停可查看说明。保存的旧参数若仍指定iteration，则仍运行幂法；换成auto或newton_noda才会启用新增路线。Codex/WorkBuddy重连本地MCP服务后读取新契约，不能继续用旧schema_hash解释新配置。

| method | 行为 |
| --- | --- |
| auto（新默认值） | 先尝试经验证的两块等价划分；不适用且α>0.8时使用Newton–Noda；普通区域先稳定幂法，128步预算内未收敛则用剩余预算进入Newton–Noda |
| newton_noda | 显式使用保正Newton–Noda；高α配合有记录的自适应延拓，数值停滞时按需60位精化 |
| iteration | 仅使用移位幂法；底层已改为对数求值和稳定归一化，保留其独立比较用途 |

α=1始终是D对角端点，不使用迭代、不输出严格正向量；不把这个值代替α<1的谱半径。仍要求一致、非空、正边权；α<1要求连通。邻接张量归一化和向量L1输出约定不变。

### 数值实现与边界

- 采用Guo论文Algorithm 1：解Newton–Noda线性系统、保持正方向，按式(3)取eta=1并折半步长。内部用L2归一化，输出转换为原有L1约定。
- 用log(x)、logaddexp（logsumexp的稳定累加形式）计算边贡献和Collatz比值，不在双精度中先形成可能下溢的整条边乘积。幂迭代更新也在对数域归一化。
- Newton系统按行与列缩放，表示为非负非对角模值与非负行和；采用避免近等数相减的消去。只分配n×n系统，不分配n^k张量；当前不是大型稀疏线性求解后端。
- 浮点回溯允许8个机器精度的舍入余量；这不是对实际浮点实现普遍全局收敛的证明。最终接受依赖独立残差和区间检查。
- 赋权点—边关联矩阵使用居中对数、logaddexp和原有公式，避免整条边乘积或顶点幂下溢；不强制行归一化。严格正条目无法用binary64表示时明确失败。独立D仅容许与实际加权度存在舍入量级差异。
- α>0.8时，从辅助参数0.5开始，按1−α最多缩小5倍推进。阶段在128步内未解决时，将−log(1−α)步长减半；同一轮最多32次阶段重试。已满足目标的热启动向量可直接进入目标求解。
- 停滞、缩放导数下溢或线性系统数值问题触发标准库Decimal 60位精化，仍用同一NNI更新及回溯。高精度不需要额外Python依赖；输出向量仍为binary64，无法表示时明确失败。
- 每个辅助阶段在独立检查器规模允许时复核；现有精确有理数检查预算为顶点和边各≤128、阶数≤8。严格区间对应明确的binary64输入模型，不保证逐分量向量相对误差，也不保证极小谱差的符号可判断。

数学依据：[Guo, A note on Newton–Noda iteration for computing the Perron pair of a weakly irreducible nonnegative tensor](https://uregina.ca/~chguo/Note_NNI.pdf)。理论假设、精确算术结论与本实现的有限精度/资源限制应区别解释。

### 预算及诊断

一次hypergraph_spectrum工具调用仍计一次宿主工具尝试；内部线性求解、延拓、失败重试和精化属于该次计算的数值工作，全部受同一个CPU、墙钟、内存及max_iterations上限约束。没有额外模型调用，没有自动增加工具额度。MCP scan中每个用户请求的α仍各计一次工具尝试。

iterations包含全部阶段及失败阶段。solver_diagnostics保留linear_solves、backtracks、precision_switches、continuation_stages、failed_stages、向量对数动态范围及有限长度的残差历史。失败抛出带诊断的PerronConvergenceError，标记certified=false；扫描将其记为unresolved，不当作反例或成功值。

### 用户后续可运行的验证

以下命令也可由用户独立复跑。请先在项目目录中运行；如安装元数据与源码版本不同，先更新当前开发环境的项目安装（不安装新依赖）：

```powershell
.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e .

## 新算法、稳定计算、预算及接入回归
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_newton_noda -v

## 原始28个缺失点；每次创建新目录，保留失败和全部成本
.venv/Scripts/python.exe -X utf8 tools/benchmark_newton_noda.py --cases unresolved

## 全部264个固定点，额外单列24个α=1端点
.venv/Scripts/python.exe -X utf8 tools/benchmark_newton_noda.py --cases pilot --include-endpoint

## 如需同时验证Windows资源保护，追加 --protected
## 完整旧功能、桌面中文和保护回归
$env:RESEARCH_PYTHON = (Resolve-Path '.venv/Scripts/python.exe').Path
.venv/Scripts/python.exe -X utf8 tools/launch_checks.py --full --strict-lock
```

benchmark输出report.json（含所有成功/未解决点及成本）和submissions.json（独立检查器格式）。默认直接调用可信Python库；--protected模式另有受限进程回执。直接模式记录的process_time仅为该宿主进程CPU，不能冒充受限进程树CPU成本。

外部共同检查器可由用户在自己的测试目录运行，指定本次生成的submissions.json。保留原版B/run01记录；修复版另用新目录。完成pilot、冻结算法及预算后，再由独立试验进入未使用的holdout；本实现和基准脚本均不读取它。

## 一般一致超图与张量的精确特征多项式

本版实现Macaulay消元，不再仅能计算匹配多项式。支持一般k一致超图的A、L、Q、α张量，以及小规模非对称、带负系数的立方张量。只需Python依赖，不需要Sage/WSL。

### 计算的对象

计算普通张量特征多项式

`χ_T(λ) = Res(λ x_i^(k-1) - (T x^(k-1))_i, i=0,...,n-1)`。

次数应为`n*(k-1)^(n-1)`，结果首一，包含零根与全部代数重数。它不是E特征多项式、匹配多项式，也不是只保留不同根的平方自由多项式。超图邻接张量沿用原包约定：排列位置取`w_e/(k-1)!`，因此邻接作用中的每条边贡献为`w_e*prod(x_u, u∈e\{v})`。

参考：[Cooper–Dutle, Spectra of Uniform Hypergraphs，§2.1、§3.3、§4.2、§6](https://arxiv.org/pdf/1106.4856)。单超边闭式和完全超图低余次数系数用于独立校验；二变量任意张量另与一元Sylvester resultant比较。

### Python调用

```python
import sympy as sp
from graph_research import Hypergraph, HyperPath, Tensor

h = Hypergraph([[0, 1, 2]])
p = h.characteristic_polynomial()
print(sp.factor(p.as_expr()))
## lambda**3 * (lambda**3 - 1)**3（输出可能继续分解成不可约因子）

print(h.charpoly())  # 兼容入口，默认谱变量为x
print(h.characteristic_polynomial(matrix='L'))
print(h.characteristic_polynomial(matrix='Q'))

alpha = sp.Symbol('alpha')
print(h.characteristic_polynomial(matrix='alpha', alpha=alpha))
print(h.characteristic_polynomial(weights=['2/3']))

## 不限于单边/超树；完整三一致四顶点超图也可计算
from itertools import combinations
complete = Hypergraph(list(combinations(range(4), 3)))
print(sp.factor(complete.characteristic_polynomial().as_expr()))

## 任意立方张量（包括非对称张量）
print(Tensor([[[1,2],[3,4]], [[5,6],[7,8]]]).characteristic_polynomial())
```

`characteristic_polynomial(details=True)`返回多项式和计算记录；默认返回SymPy Poly。`charpoly_H`、`charpoly_system`、`comp_charpoly`也有原生Python入口。后者保留单点零块的λ因子，修正旧Sage辅助函数在全单点情形下可能遗漏零根重数的问题。

直接使用稀疏齐次作用而不构造稠密张量：

```python
from graph_research.elimination import action_characteristic_polynomial
## 每一行：幂指数tuple -> 系数；阶数为3，单项式总次数为2
rows = [{(2,0):1, (1,1):2, (0,2):3},
        {(2,0):4, (1,1):5, (0,2):6}]
p = action_characteristic_polynomial(rows, rank=3)
```

### Macaulay算法及检查

令`d=k-1`，临界次数`t=n*(d-1)+1`。枚举t次单项式，矩阵阶数是`binomial(n*d,n-1)`。每个单项式选择第一个能整除它的`x_i^d`，用对应的特征方程乘以余下单项式生成一行。

由于谱变量仅在`λx_i^d`中出现，分子是`det(λI-N)`；非约化单项式（至少被两个纯幂整除）对应主子矩阵给出分母。计算这两个矩阵的特征多项式并作精确除法。

- 按矩阵有向图的强连通分量拆解行列式，单点块仍保留`λ-N_ii`。
- 精确验证余式为零，不以近似商或无检查的整除替代。
- 验证结果次数`n*d^(n-1)`与首一性。
- 不连通超图按分量处理：ni维分量的多项式提升到`d^(n-ni)`次幂；孤立点同样保留相应重数。
- 整数、分数和符号参数均作精确运算。浮点输入按其十进制值作为精确有理数；例如已有浮点`1/3`不能恢复原始分数，应传`'1/3'`或`sp.Rational(1,3)`。由超图直接生成作用可以避免浮点`1/(k-1)!`误差。

原包的Macaulay构造是迁移参考；不使用SymPy实验性Macaulay类的系数位置推断，避免λ在多个方程中重复出现时误选分母行列。可对照[SymPy的Macaulay实现说明](https://github.com/sympy/sympy/blob/master/sympy/polys/multivariate_resultants.py)。

### 模型工具与规模估算

```powershell
.\.venv\Scripts\python.exe -X utf8 -m graph_research call hypergraph_tensor_charpoly '{"edges":[[0,1,2]]}'
.\.venv\Scripts\python.exe -X utf8 -m graph_research call hypergraph_tensor_charpoly '{"edges":[[0,1,2],[2,3,4]],"estimate_only":true}'
.\.venv\Scripts\python.exe -X utf8 -m graph_research call hypergraph_tensor_charpoly '{"edges":[[0,1,2]],"matrix":"alpha","symbolic_alpha":true}'
.\.venv\Scripts\python.exe -X utf8 -m graph_research call tensor_charpoly '{"data":[[0,1],[1,0]]}'
```

模型工具采用独立Python进程，20秒硬超时；超过上限会终止并报告失败，不接受部分多项式。`estimate_only`只估算规模，不是计算结果。

默认数值/有理系数限制：Macaulay矩阵阶≤4096、最大SCC块≤256、结果次数≤4096、稠密输入≤20000项。模型工具的符号α限制更保守：矩阵阶≤512、SCC块≤64。最终可计算范围也取决于稠密程度和系数复杂度，不能仅按顶点数保证成功。

直接库调用可传`EliminationLimits(...)`调整限制；其中时间预算是分阶段检查，不能中断单次SymPy调用。需要硬超时时使用上面的隔离工具接口。

目前已计算的例子：三一致单边（12次）、两条松边（80次）、三条松边（448次）、完整三一致四顶点（32次）、完整三一致五顶点（80次）、四一致单边（108次）、符号α与精确有理边权。完整算例：

```powershell
.\.venv\Scripts\python.exe -X utf8 examples/tensor_charpoly.py
```

### 边界

“一般”指在所选齐次张量定义下不限图形类别，并不表示任意规模都能完成符号消元。非一致超图没有在这里默认指定一种张量扩展，输入会明确拒绝。此版本也不计算E特征多项式或Cayley型超行列式。
