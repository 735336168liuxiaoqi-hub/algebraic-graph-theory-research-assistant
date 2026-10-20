# Newton–Noda 与高 α 稳定计算（v0.31.1）

v0.31外部pilot的NNI/auto各288点及共同检查器通过，受保护执行在该次环境退出107。v0.31.1补齐启动日志、阶段诊断和稳定赋权矩阵；本机验收记录见V031_ACCEPTANCE_PROGRESS.md（历史开发记录）。未读取holdout或A组算法答案，未覆盖外部pilot文件。

## 使用方法

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

## 数值实现与边界

- 采用Guo论文Algorithm 1：解Newton–Noda线性系统、保持正方向，按式(3)取eta=1并折半步长。内部用L2归一化，输出转换为原有L1约定。
- 用log(x)、logaddexp（logsumexp的稳定累加形式）计算边贡献和Collatz比值，不在双精度中先形成可能下溢的整条边乘积。幂迭代更新也在对数域归一化。
- Newton系统按行与列缩放，表示为非负非对角模值与非负行和；采用避免近等数相减的消去。只分配n×n系统，不分配n^k张量；当前不是大型稀疏线性求解后端。
- 浮点回溯允许8个机器精度的舍入余量；这不是对实际浮点实现普遍全局收敛的证明。最终接受依赖独立残差和区间检查。
- 赋权点—边关联矩阵使用居中对数、logaddexp和原有公式，避免整条边乘积或顶点幂下溢；不强制行归一化。严格正条目无法用binary64表示时明确失败。独立D仅容许与实际加权度存在舍入量级差异。
- α>0.8时，从辅助参数0.5开始，按1−α最多缩小5倍推进。阶段在128步内未解决时，将−log(1−α)步长减半；同一轮最多32次阶段重试。已满足目标的热启动向量可直接进入目标求解。
- 停滞、缩放导数下溢或线性系统数值问题触发标准库Decimal 60位精化，仍用同一NNI更新及回溯。高精度不需要额外Python依赖；输出向量仍为binary64，无法表示时明确失败。
- 每个辅助阶段在独立检查器规模允许时复核；现有精确有理数检查预算为顶点和边各≤128、阶数≤8。严格区间对应明确的binary64输入模型，不保证逐分量向量相对误差，也不保证极小谱差的符号可判断。

数学依据：[Guo, A note on Newton–Noda iteration for computing the Perron pair of a weakly irreducible nonnegative tensor](https://uregina.ca/~chguo/Note_NNI.pdf)。理论假设、精确算术结论与本实现的有限精度/资源限制应区别解释。

## 预算及诊断

一次hypergraph_spectrum工具调用仍计一次宿主工具尝试；内部线性求解、延拓、失败重试和精化属于该次计算的数值工作，全部受同一个CPU、墙钟、内存及max_iterations上限约束。没有额外模型调用，没有自动增加工具额度。MCP scan中每个用户请求的α仍各计一次工具尝试。

iterations包含全部阶段及失败阶段。solver_diagnostics保留linear_solves、backtracks、precision_switches、continuation_stages、failed_stages、向量对数动态范围及有限长度的残差历史。失败抛出带诊断的PerronConvergenceError，标记certified=false；扫描将其记为unresolved，不当作反例或成功值。

## 用户后续可运行的验证

以下命令也可由用户独立复跑。请先在项目目录中运行；如安装元数据与源码版本不同，先更新当前开发环境的项目安装（不安装新依赖）：

```powershell
.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e .

# 新算法、稳定计算、预算及接入回归
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_newton_noda -v

# 原始28个缺失点；每次创建新目录，保留失败和全部成本
.venv/Scripts/python.exe -X utf8 tools/benchmark_newton_noda.py --cases unresolved

# 全部264个固定点，额外单列24个α=1端点
.venv/Scripts/python.exe -X utf8 tools/benchmark_newton_noda.py --cases pilot --include-endpoint

# 如需同时验证Windows资源保护，追加 --protected
# 完整旧功能、桌面中文和保护回归
$env:RESEARCH_PYTHON = (Resolve-Path '.venv/Scripts/python.exe').Path
.venv/Scripts/python.exe -X utf8 tools/launch_checks.py --full --strict-lock
```

benchmark输出report.json（含所有成功/未解决点及成本）和submissions.json（独立检查器格式）。默认直接调用可信Python库；--protected模式另有受限进程回执。直接模式记录的process_time仅为该宿主进程CPU，不能冒充受限进程树CPU成本。

外部共同检查器可由用户在自己的测试目录运行，指定本次生成的submissions.json。保留原版B/run01记录；修复版另用新目录。完成pilot、冻结算法及预算后，再由独立试验进入未使用的holdout；本实现和基准脚本均不读取它。
