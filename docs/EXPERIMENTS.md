# 通用科研实验工作流

已实现阶段1～7的有限研究流程：问题准备、图／一般超图评价、受保护分段搜索、可选CPU CEM、受控调度、反馈微调和有证据的结构观察／假设检验。超图允许含环，超树是可选条件。传统计算无需PyTorch；CEM使用可选PyTorch环境，不引入Java、SageMath、WSL或CUDA要求。当前不自动证明一般定理；桌面专用实验界面与第8阶段统一验收另行推进。

## 三种操作

| 操作 | 输入 | 行为 |
| --- | --- | --- |
| `prepare` | 结构化问题；参数可只声明含义而暂不指定值 | 返回至多32组建议采样点、必要条件检查、能力缺口及静态内存估计。草案始终`executable=false, approved=false`，不计算 |
| `execute` | 同一问题协议、全部参数实例、明确候选对象、分段设置和预算 | 先暂停展示范围预算；可信用户确认后，在受保护进程分段评价、独立核验、保存结果及消耗 |
| `study` | 问题、预算、方法／种子／轮数；可省略cases由规则提出采样点 | 先审阅有限计划，确认后搜索、学习、诊断、结构归纳与假设反驳；模型可选 |

准备仍保持`status=analysis_only`、`summary.preparation_complete=true`、`summary.execution_complete=false`，模型及工具调用数均为0。静态估计不是实际成本预测；小样本实测也须明确确认后另行提交execute。不会自动搜索文献、安装依赖或批准资源。

## 当前计算能力

| 对象／能力 | 已接入内容 |
| --- | --- |
| 普通无向简单图 | 邻接矩阵谱半径、`A_alpha=alpha*D_degree+(1-alpha)*A`谱半径、距离矩阵谱半径、边数 |
| 一般超图`hypergraph` | 超边可有不同大小、允许含环；关联度、超边数、连通性、距离矩阵谱半径及独立核验 |
| 一致超图`uniform_hypergraph` | 指定uniformity=k；超边均含k个顶点，允许含环，不默认要求为超树 |
| 一致超树`uniform_hypertree` | 兼容已有入口，额外要求关联图连通无环；原有输入和数学语义保持不变 |
| 约束组合 | all／any／not；连通性、边数、最大度、达到最大度的顶点个数；超图可加hypertree，普通图另支持禁团和匹配数 |
| 合法构造 | `generate_hypertree(k,m,seed=42,degree_cap=None)`：每步接入k−1个新顶点，保持关联图为树；degree_cap只是上限 |
| 独立核验 | 集合、BFS、并查集、位集禁团和匹配DP重建性质；不调用主评价器或特征值求解器。用有理数重算保存正向量的Rayleigh下界、Collatz上界 |

浮点特征值用于排序；证书给出严格有理数区间。区间重叠时不声称严格比较。即使`candidate_collection_optimum_certified=true`，也仅针对**明确提供的集合**，不代表穷尽图类或证明一般定理。没有可行候选也不证明该图类为空。

超图度按关联超边数计算，距离按经过的超边数计算。一致超树必有`N=1+(k-1)m`，一般超图不能据此推导阶数。q是达到最大度Delta的顶点数，不是N。K_r-free不静默限制为完全多部图。alpha=1可计算，含义为度对角矩阵端点。

一般超图需限制成超树时，加`{"predicate":"hypertree"}`，明确表示关联图连通且无环；`{"not":{"predicate":"hypertree"}}`表示排除超树。仅当超树条件必需、且一致度和超边数已知时，准备流程才推导上述N关系；any／not中的条件不会被误当成必需条件。

限制：每候选1～128顶点；普通图至多1024边；超图至多128边／2048次关联。当前超图表示无权、无重复超边，每条超边至少2顶点，不支持空超边或单点超边。每实例1～64候选，一任务至多32实例、256候选，每段1～16候选。独立匹配核验限16顶点；禁团核验设10万递归节点上限，超限拒绝出证。距离谱要求连通；不连通超图仍可统计超边及检查其他结构条件。超图不接受普通图禁团／匹配语义或普通图alpha矩阵，不代用邻接张量谱。张量研究的一致性范围不因结构／距离接口接受非一致超图而改变。

能量等库级指标尚未接入执行器。study搜索会最终检查最大度及其个数等约束；构造器不承诺直接满足所有等式条件。已有超树生长器只用于明确的超树任务，一般超图另用允许含环的稀疏构造。study通过hypotheses检验明确数值界或结构命题，不把高分本身称为反例。

## 输入与命令

草案样例保持`examples/research-experiments/clique-free-request.json`、`hypertree-distance-request.json`。新增：

- `clique-free-execute-request.json`：比较C5、星图和违反禁三角条件的候选，n=5、r=3、alpha=1/2。
- `hypertree-distance-execute-request.json`：比较3一致星形超树与松路，m=3、Delta=3、q=1；松路被标为不满足最大度约束。
- `hypergraph-distance-execute-request.json`：比较含环的3一致超图，n=6、m=3。允许n不同于超树的7，不要求关联图无环。

`*-request.json`是CLI的`{operation:"submit",task:...}`封装；`*-prepare.json`／`*-execute.json`是Python、MCP接收的任务本体。在源码目录运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m graph_research subagent --root outputs/finite-experiments --user researcher --input examples/research-experiments/clique-free-execute-request.json
```

首次返回`waiting_for_user`／`experiment_review`，计算调用为0。核对`interaction.plan`中的问题、全部候选、段数和预算。用户决定执行后，在可信本机终端签发事件，用返回值替换占位符：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m graph_research subagent-user --root outputs/finite-experiments --user researcher --task TASK_ID --interaction INTERACTION_ID --revision REVISION --action continue
```

把返回的`host_user_event.event_id`写入resume.json：

```json
{"operation":"resume","task_id":"TASK_ID","event_id":"EVENT_ID"}
```

```powershell
.\.venv\Scripts\python.exe -X utf8 -m graph_research subagent --root outputs/finite-experiments --user researcher --input resume.json
```

样例设置`segment_chunks=1`，若有剩余候选会返回`experiment_continue`，需要再次选择继续、签发新事件。该设置控制每次运行段数，不提高总预算。查询／取消使用同一task_id的`{operation:"get"}`／`{operation:"cancel"}`封装。

实例须恰好赋值全部声明参数，满足固定值及values/上下界。有理数使用`"1/2"`，不接受代码或表达式。候选格式`{"n":4,"edges":[[0,1],[1,2],[2,3]]}`，顶点为0到n−1；声明n保留孤立点。重复边、自环、越界点视为输入错误；表示合法但不满足数学条件则记录为不可行。

## Python与MCP

```python
from graph_research.experiments import (
    prepare_experiment, evaluate_candidate, verify_evaluation,
    generate_hypertree, experiment_contracts,
)
```

Python函数供可信程序使用，本身不建立进程隔离、审批和任务持久化。模型委派使用子agent／MCP任务入口。`research_submit`接收任务本体，`execution.mode="experiment"`。execute首次等待审阅；可信宿主通过现有`SubagentUserPortal.continue_task`或本机`subagent-user`签发绑定task、revision、interaction的事件，再调用`research_resume(task_id,event_id)`。门户必须由真实用户操作驱动，不可注册成模型工具。JSON中的approved或主agent自行推测不能代替确认。改变条件、候选或预算须取消并新建任务。

契约见`experiment_contracts()`和`graph-research://contracts`的同名字段。`experiment_evaluate`是固定受保护内部操作，不是公开ToolRegistry工具；配置allowed_tools白名单时须显式包含它。现有47项公开计算工具保持不变。

`research_get(detail="full")`取得完整数据；`research_inspect_result`按call_id读取逐次结果。MCP摘要只显示前8组实例简要统计，省略原始候选及完整尝试账本；审批交互保留完整范围。

## 预算、恢复与证据

execute必须声明`budget.max_evaluations`、`wall_seconds`、`cpu_seconds`、`memory_mb`，同时服从宿主工具调用及单次进程上限。调用数按每次分段尝试计，评价数按候选尝试计；一段多个候选不隐藏评价数量。初始段数超过调用预算时整体拒绝。

计算前先持久化调用计数、候选及时间预留。成功用回执中的实际进程墙钟／CPU结算时间；候选尝试不退还。缺可靠测量的失败／中断保留时间上限作为保守消耗，重试另扣预算。内存为每Job上限；时间口径是活动工作进程，暂停等待及宿主验证／导出的额外开销不在该测量中。启动清理及系统强制执行可能短暂越过截止点；超支后不启动下一段。

Windows建议把`--root`放在较短路径。工作进程下还要创建任务与临时子目录，过深的路径可能触发系统WinError206；返回的`error_details`含错误码／阶段／diagnostic_id，实际已写入的失败回执保留为`failed_execution`证据。不放宽进程保护或自动重试以绕过启动失败。

恢复校验定义、预算、核心版本、输入／结果哈希及独立数学证据。已完成分段复用；计算完成后、写入观察前崩溃，只有宿主事先持久化回执校验值才可复用。无固定值的文件不能自动视为完成；前次预留保留，用户确认后重试。记录／回执改变则阻止恢复，不静默重算。恢复、重启或新交互编号都不能重置预算。

暂停／结束时导出结果包：execute包括`experiment-input.json`、`experiment-results.json`、`experiment-ledger.json`、通用报告及逐次参数／结果／回执证据。导出失败会反映在返回中。`completed`表示明确集合已评价；历史失败后重试成功时顶层可为`partial`，看`summary.experiment.collection_complete`区分集合是否完成。prepare仍保存问题与草案。

## study：搜索、调度、微调与反驳

新任务使用`execution={"mode":"experiment","experiment":{"operation":"study",...}}`。普通图、一致／非一致超图共用接口；旧prepare和execute行为保持不变。新增内部保护操作experiment_search，不增加公开计算工具数量。

| 方法 | 当前实现与范围 |
| --- | --- |
| enumerate | 按编号枚举有标号图／超图，支持固定边数；潜在边位置上限20。保存精确游标，只有完整覆盖所声明构造域才标记finite_coverage |
| random | 带种子的候选采样；固定边数优先构造保证；一般超图允许环，必需超树条件才使用生长构造 |
| local | 从当前候选进行受限局部改边／接枝，结合随机重启；所有候选仍做正式约束检查 |
| cem | CPU自回归神经策略、精英训练及保留、探索混合、带动量的优化更新。普通图逐边决策；超图使用边槽及顶点选择，不默认展开全部k元组；超树使用合法生长动作 |

参考[上游CEM项目](https://github.com/dragance106/cema-for-graphs)的逐步构图、精英选择与探索机制，本后端独立实现；未复制其源码或引入Java奖励层。与原实现不同：小型共享特征网络、动作序列重建观察、64步微批训练、JSON安全张量编码、CPU确定性设置及完整状态版本检查。网络／优化器参数不是用pickle反序列化，检查点不携带代码或文件路径。算法参考和差异另见[来源说明](provenance/CEM_REFERENCE.md)。

默认设置：methods=random/local，seeds=[42]，rounds=2，batch_size=8。每个方法／种子／参数实例为一个run；总轮数和最大候选评价数在确认前列出。每段候选2～16个，总run上限32；每run最多16轮，仍受宿主最多100次工具尝试限制。CEM单条动作序列默认最多1024步，可显式提高到2048；检查点JSON上限180KiB。大图可改用随机／局部后端，不把某个CEM表示的上限冒充整个工具库的图阶上限。

一般非一致超图默认边大小范围为2到min(n,3)，可以用edge_sizes显式修改。max_edges默认128；没有固定边数条件时，它限定本次搜索空间。**这些构造限制都属于有限实验域，不能据此宣称研究了所有一般超图或所有边数。** 非一致超树专用生成器尚未接入，会明确拒绝该组合；一般非一致超图搜索可用。

### 规划与反馈

cases可省略：规则根据自由参数的含义和范围提出有限实例，随后由用户审阅。未指定具体n/r/k/m不必先手填取值，但需要明确参数数学含义和目标；歧义、未知指标或无界解释不会被静默改写。

planner=rules无需API，优先安排未测实例、不同方法及种子，再重复；可在已审阅的alpha网格上优先安排疑似结构变化区间中的实例。planner=model复用现有模型配置，宿主须启用模型预算；模型读取能力、批准的run、阶段诊断及资源反馈，只返回结构化动作。可选run、停止或请求范围变化，不能提交代码、临时工具、新参数值或更高预算。当前加密是**预授权有限网格内的调度**；网格外扩域需要新任务确认，不是无限自主扩张。

模型调用也先扣尝试数，失败不自动重试；候选／工具预算不足时不再为下一轮额外调用规划模型。脚本化模型验收不等于实际服务商效果评测。所有真实API密钥仍只配置在本机环境，测试不调用付费模型。

adaptive=true允许在已展示的区间调整exploration(0.01～0.5)、elite_fraction(0.1～0.75)、penalty_weight(0.1～10)。正式排序始终先区分可行性，再看原始目标；训练引导分数另存，不能把约束惩罚降低当成谱指标改善。奖励版本改变后缓存精英重新评分，原始数值和证据保留。每次决策保存原因、旧配置、新配置、检查点及反馈；恢复旧配置可通过可信反馈提交原值，不删除历史或退还预算。

segment_rounds控制何时暂停，默认128。在experiment_continue处，用户可继续，也可通过可信门户`study_feedback`调整已有run的优先级、上述参数或明确假设。扩大数学范围、种子清单、方法或总预算需取消并新建审阅；主agent不能伪造用户反馈。

### 结构与命题

汇总包括每run的可行率、原始最佳目标、有标号结构多样性和执行消耗；这些量用于同预算多种子比较，不预设CEM比传统搜索更好。结构分析包括度分布、分部识别、超图关联圈秩、悬挂结构、最大度顶点距离及压缩骨架。小实例同构分类提供经过边映射核对的见证；超过12顶点／16边或8个代表的分析限制时标为未分类，不凭度序列断言同构。

识别出完全多部图时，可给出该实例的精确商矩阵及特征多项式（分部数至多8）。它们属于具体实例的符号证据，不自动推出整类图的极值定理。

hypotheses支持：

- metric_bound：明确的数值上／下界。只有独立谱区间完整越过边界才给出反例见证；区间重叠标为不确定。
- universal_structure：声明所有可行对象具有regular/bipartite/complete_multipartite/hypertree中的某项性质，找到经过约束核验的相反实例即可反驳该明确命题。
- candidate_pattern：关于搜索所得优秀候选的模式，只能标为“观测模式被否定”，不能冒充已反驳最优结构定理。

假设可附statement和source，保留用户提供的来源。系统未自动检索文献，不将已有结果包装为新发现。报告保留独立种子和方法支持度、候选猜想及后续反驳方向；“未反驳”不等于证明，“没有可行候选”不等于数学上无解。

### 可运行样例

`examples/research-experiments/`新增clique-free-study-request.json、hypergraph-distance-study-request.json、hypertree-distance-study-request.json和clique-free-cem-study-request.json。前三者无需PyTorch，最后一个需要可选依赖；各样例适配默认10次宿主工具预算。开始一个较短路径的任务：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m graph_research subagent --root outputs/study --user researcher --input examples/research-experiments/clique-free-study-request.json
```

首次只返回审阅计划；后续continue签发及resume与前文完全相同。暂停时调整参数：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m graph_research subagent-user --root outputs/study --user researcher --task TASK_ID --interaction INTERACTION_ID --revision REVISION --action study-feedback --feedback examples/research-experiments/study-feedback.json
```

此命令仅签发真实用户反馈事件，仍需把返回event_id交给resume。结果包增加study-plan-and-decisions.json与study-interpretation.json；逐轮原始结果保存检查点、精英、动作序列和版本。MCP摘要省略权重、检查点和完整结构表；使用detail=full、research_inspect_result或结果包读取。核心／题目／预算／检查点版本或回执改变时阻止恢复。

启用CEM可在当前Python环境安装项目的`search`可选依赖；只需CPU时，按[PyTorch官方安装选择器](https://pytorch.org/get-started/locally/)选Windows／Pip／Python／CPU，再安装本项目。普通桌面、传统搜索和all依赖不强制安装torch。不同PyTorch版本的训练检查点不可混用；同一环境下的连续／恢复一致性已单独验证。

## English

Phases 1–7 support model-free preparation, reviewed evaluation/search, optional CPU CEM, bounded scheduling, feedback, structural observations and formal hypothesis checks. Hypergraphs may contain cycles. Traditional backends need no torch; CEM requires the optional search environment. No Java/SageMath/WSL or CUDA setup is required. General theorem proving and the dedicated desktop study UI are outside this delivery.

`prepare` returns an unapproved draft with exploratory parameters and performs no calculation. `execute` takes the same problem, fully assigned parameter cases, explicit `{n,edges}` candidates, chunk settings and finite budgets. See the `*-execute.json` task examples and `*-execute-request.json` CLI envelopes above.

Execute first returns `waiting_for_user` / `experiment_review` with zero computation calls. An authenticated host user reviews scope and budget, then issues a task/revision/interaction-bound continue event via the trusted portal or local command. The parent passes it to `research_resume`. Do not expose the portal to a model or synthesize consent. Segment pauses and uncertain retries require fresh events; budgets never reset.

Ordinary graphs support adjacency, alpha and distance matrix spectral radii plus edge count. `hypergraph` permits nonuniform edges and cycles; `uniform_hypergraph` additionally requires uniformity=k. Both support distance spectral radius, hyperedge count and incidence degrees. Distance requires connectivity; counting does not. The optional `hypertree` predicate means a connected acyclic incidence graph. The legacy `uniform_hypertree` type retains that requirement. N=1+(k−1)m is inferred only when a uniform hypertree is unconditionally required, never for general hypergraphs or a negated/disjunctive tree condition. Tensor metrics are not silently substituted with ordinary matrix metrics.

Boolean constraints cover connectivity, size, maximum degree and its multiplicity; ordinary graphs also support clique-free and matching predicates. Vertex labels are0..n−1, with at most128 vertices; matching verification is limited to16. Hypergraphs are unweighted, with distinct edges of at least2 vertices. The existing growth helper only generates hypertrees, not arbitrary hypergraphs, and guarantees neither exact degree/multiplicity conditions nor optimality. The new `hypergraph-distance-execute-request.json` CLI example evaluates cyclic 3-uniform hypergraphs with n=6 and m=3.

Independent verification rebuilds structure and rational spectral enclosures without an eigensolver. Numerical ranking is not a theorem; certified optimality applies only to the explicit collection. No exhaustive graph-class coverage or counterexample claim is inferred.

Persistent accounting includes failed/uncertain reservations. Successful receipts settle active worker wall/CPU usage; missing measurements retain conservative limits. Paused time and additional host validation/export overhead are excluded from these worker measurements. Only valid host-pinned evidence is reused; altered inputs, budgets, evidence or core versions block continuation. Bundles preserve input, results, ledger and receipts. Use `detail="full"` for all data; MCP summaries are bounded. Public tools remain47, with a separate internal protected evaluation operation.

Prefer a short Windows task root: very deep protected-worker paths can hit WinError206. Structured errors and available failure receipts identify the startup problem; protection is not weakened and retries are never automatic.

`study` adds interchangeable enumerate/random/local backends and optional CPU PyTorch CEM. Cases may be proposed from exploratory parameters, then reviewed as a finite scope. Rules or a configured model schedule approved runs, seeds and bounded guidance changes. Model decisions cannot inject code, enlarge the parameter grid or raise budgets. Refinement prioritizes points within the reviewed finite grid; expansion requires a new review.

CEM reconstructs observations from action sequences, uses small training microbatches, and checkpoints policy weights, momentum, elites, exploration state and RNG state in bounded JSON, without pickle, Java or CUDA. Normal installation does not require torch; select the optional search environment when needed. Continuous and resumed CPU runs are checked under the same runtime version.

Trusted `study_feedback` events may change exploration, elite fraction, penalty guidance, approved-run priorities and explicit hypotheses. Guidance scores never replace raw objectives or feasibility. Changing reward versions re-scores stored elites; failed attempts retain reservations. Existing checkpoints and previous settings remain available for audit.

Reports include structural features, witnessed small-instance isomorphisms, multipartite quotient matrices, finite labelled coverage, candidate conjectures and formal hypothesis checks. Numeric bounds require certified interval violations for counterexamples. A contradicted candidate pattern is not a refuted extremal theorem. Sampling consistency and heuristic failure never establish a general proof or nonexistence. Four study request examples and a feedback JSON are provided above; dedicated desktop study controls and stage8 acceptance remain separate.
