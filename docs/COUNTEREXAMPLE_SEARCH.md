# 反例搜索与独立核验

适用开发版 `0.37.0a2`。这是一个专用研究子任务：反驳“参考图在相同顶点数、边数的连通简单图中邻接谱半径最大”。目前支持 **2..128 个顶点、至多1024条边、无向、无权、连通简单图**。

只验证这些明确条件，不支持任意自然语言猜想、额外禁子图、度序列、带权/有向图或超图。专用任务拒绝非空 `definitions` 和不支持的字段，避免把较宽图类的反例用于较窄图类。定义不清时，由主 agent 或现有 API 对话先向用户澄清。

## 一次完整任务

1. 固定参考图及 n/m，校验图类型、预算、工具白名单。
2. 数值筛选候选。可分段枚举、谱向量引导换边、随机换边、随机重新构图；规则策略按停滞反馈切换，模型策略只选择允许的策略或停止。
3. 有更大数值候选时，12点以内从原始边表重算精确特征多项式并核验实根；较大图采用独立有理数Rayleigh下界与Collatz上界。
4. 候选谱半径下界严格大于参考图上界，才返回已核验反例。区间重叠时精化，仍不分离就保留未核验状态。
5. 保存执行回执、决策记录和结果包。失败与取消不会重置预算；未找到不能宣称猜想成立。

`summary.counterexample.outcome`：

| 值 | 含义 |
| --- | --- |
| `counterexample_found` | 存在满足本接口全部约束的严格改进，已独立核验 |
| `not_found_within_budget` | 本次有限范围/预算未找到已核验反例，不证明最优 |
| `candidate_unverified` | 有候选但精确核验失败、未分离或无核验预算 |
| `search_incomplete` | 正在运行、取消或异常中断，不能视为最终科研结论 |

任务 `status` 和科研 `outcome` 分开看：正常结束但没找到反例也可为 `completed`；核验失败为 `partial`；搜索计算故障为 `failed`；取消为 `cancelled`。先检查状态和 `stop_reason`，再解释结果。

## 不配置 API 的首个例子

在源码目录用本项目的 Python 运行：

```powershell
.\.venv\Scripts\python.exe -m graph_research subagent --root outputs/counterexample-state --user researcher --input examples/counterexamples/path4-request.json
```

也可以通过 MCP 的 `research_submit` 传入 [path4-task.json](../examples/counterexamples/path4-task.json) 的任务对象，`wait_seconds=5` 短等，随后保存 `task_id` 用 `research_get` 查询。相同逻辑任务重复提交时保留原 `request_id` 和完全相同输入，不创建新编号逃避预算。

```json
{
  "version": 1,
  "request_id": "counterexample-path4-v1",
  "objective": "反驳P4在四顶点三边连通简单图中邻接谱半径最大的猜想",
  "execution": {
    "mode": "counterexample",
    "counterexample": {
      "reference": {"kind": "path", "n": 4},
      "planner": "rules",
      "max_rounds": 4,
      "candidates_per_round": 12,
      "seed": 42,
      "digits": 12
    }
  },
  "constraints": {"max_tool_calls": 8, "max_model_calls": 0, "allow_extensions": false}
}
```

这个小例应找到与 `K1,3` 同构的星图。P4 的特征多项式是 `x^4-3*x^2+1`，星图为 `x^4-3*x^2`；反例结果包含严格为正的有理数谱半径差区间。这里反驳的是上述固定条件的猜想，不宣布星图在任意其他条件下最优。

## 模型策略子 agent

将 `planner` 改为 `model`，并由可信宿主按原有模型配置方式启用模型、提供正的 `max_model_calls`。MCP 服务若没有显式启用模型，会在注册任务前拒绝；不偷偷切换或调用外部 API。

模型每轮只接收明确图定义、剩余预算和搜索反馈，返回 `{"strategy":"rewire","reason":"..."}` 等选择；可选 `stop`。它不能提交代码、候选图、核验结论、批准或新预算。数值搜索与精确核验都由原生工具在受保护进程中执行。策略模型使用本助手配置的 API；若希望完全由主 agent 决策，也可由主 agent 组合下方两个工具，无需内部 API。

## 两个可直接组合的工具

- `graph_counterexample_round`：一次有界候选生成和数值筛选，返回最好图、`promising`、近期已访问图的SHA256、枚举游标和实际评价数；`counterexample_verified` 固定为 false。
- `graph_counterexample_verify`：从参考图和候选的原始结构重新计算，返回 `counterexample_found` / `not_counterexample` / `candidate_unverified`、小图多项式根区间或大图严格有理谱界证据。

可通过原工具目录获取完整参数。离线桌面中，两项位于普通图工具分类，已补中文/英文名称和参数说明。完整自动搜索当前入口为 MCP/子 agent 任务接口，未另加桌面专用搜索向导。

## 预算、恢复与边界

- 默认最多4轮，每轮最多12个可行新候选；可配置最多8轮、每轮24个。生成尝试另有每轮 `max(64,16*candidates)` 上限。
- 每轮搜索和每次独立核验各消耗一次工具尝试，候选评价数量另报；并非一个调用就无限计算。始终为发现候选预留核验尝试，失败和中断也计数。
- `enumerate` 仅在有标号边组合数不超过20000时可用，逐段续算；近期缓存按有标号边表SHA256去重，最多512项；旧项淘汰后可能重访，不声称全局去重或非同构枚举。穷尽数值筛选也不作为最优性证明。
- 随机/换边搜索不保证找到存在的反例；数值筛选阈值可能漏掉很小的改进，因此未找到不证明猜想。
- 12点以内根隔离初始精度6..24位，最多48位；较大图用正向量和有理谱界，必要时最多512步正向量求精。界未分离仍为未核验，digits不是大图的误差保证。进程资源限制继续生效。
- 暂停后须由真实用户在可信门户选择继续。可能已执行但缺回执的步骤，明确告知用户后才重试，前次预算保留；不允许模型伪造恢复事件。
- 新需求超出四种搜索策略或当前数学目标时，应走原有独立开发评估/审批，不在搜索中自动生成和安装代码。

结果包新增 `counterexample-summary.json`，`results.json` 内也保存同一结构；完整多项式、图及回执保留在计算结果中，MCP 摘要裁剪时按 `research_inspect_result` 取完整证据。

## English summary

`execution.mode="counterexample"` searches for a connected unweighted simple graph with the reference graph's vertex/edge counts and a strictly larger adjacency spectral radius. The first version supports 2..128 vertices and at most 1024 edges only. Nonempty `definitions` and unsupported constraints are rejected.

`planner="rules"` needs no model. `planner="model"` requires explicit host configuration and a positive model budget. The model can choose a bounded search strategy or stop; it cannot change graphs, budgets, approvals or verification outcomes. Screening is numerical. Up to 12 vertices, verification uses exact characteristic-polynomial root intervals; larger graphs use independently checked rational Rayleigh/Collatz bounds. A positive strict difference is required in both cases. The recent SHA256 cache holds up to 512 labelled graphs and can evict older entries.

Outcomes distinguish a verified counterexample, no witness within the search budget, and an unverified candidate. No-witness results never prove optimality. Existing task IDs, replay handling, cancellation, trusted resume and result bundles are reused. The source development version is not yet a GitHub release; reconnecting an old installed runtime alone will not update its code.


## 扩容后的严格核验

搜索支持2..128顶点、最多1024边。12点是精确多项式核验的分界，不再是搜索总上限。

对无向无权邻接矩阵A及正向量x，有：

- Rayleigh下界：xᵀAx/(xᵀx) ≤ ρ(A)。
- Collatz上界：ρ(A) ≤ maxᵢ (Ax)ᵢ/xᵢ。

大图先生成近似正向量，再将实际存储的binary64向量逐项精确转为有理数，从原始边表重算上下界，不信任浮点谱值或“已收敛”标志。候选下界大于参考上界才确认反例；比较不清时继续求精或明确返回未核验。`isolation_digits`为null，`verification_method`为`exact_rational_rayleigh_collatz`。

结果保存正向量、图SHA256和有理界，可独立调用`graph_research.workflows.graph_spectral_certificate.verify_adjacency_certificate(n, edges, certificate)`复核，不重新求特征值。可用新增`examples/counterexamples/path128-task.json`通过MCP测试128点任务。
