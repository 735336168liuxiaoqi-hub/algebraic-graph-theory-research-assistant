# 科研实验规划与执行

通用科研实验已提供prepare／execute／study三类操作，见[通用科研实验工作流](EXPERIMENTS.md)：prepare只准备草案；execute评价明确候选；study在审阅后的有限范围内搜索、可选CEM、反馈及假设检验。规则调度无需模型。下文research模式使用模型制定可检查的已有工具计划，两种工作流共享保护、预算和结果接口，但配置及执行范围不同。

开发源码0.38.0a1。此模式复用现有LangGraph、工具契约、受保护执行、预算、可信交互及结果包，增加可检查的科研计划与执行反馈。它不限于图性质遍历，也可安排已有构图、矩阵、批量计算和比较工具。

实际节点与分支见[当前LangGraph状态图](WORKFLOW.md#0-当前langgraph状态图)，可编辑源码见[langgraph-research.mmd](diagrams/langgraph-research.mmd)。独立核验是计划中的工具调用，范围/预算/覆盖检查位于相应节点及宿主治理层。

## 两种使用方式

桌面科研对话：在**新对话开始前**勾选“科研实验 / Research experiment”，配置现有模型服务后描述研究目标。“先查看计划”可先展示范围、前提、步骤、核验方式和资源上界，再点击开始。对话开始后模式固定；另一个独立目标可新建对话。一个对话后续的新请求使用新的实验统计边界，不合并先前任务的覆盖计数。

MCP/结构化子任务：提交`execution.mode="research"`，由助手的已配置模型拆解目标；宿主须显式启用模型并给出正的模型预算。只配置主agent自己的模型，并不会自动给本服务提供内部规划模型。若希望完全由主agent规划，无需另配助手API，使用普通`tools`/`batch`任务组合下方原生工具即可。

```json
{
  "version": 1,
  "request_id": "research-atlas6-v1",
  "objective": "完整统计6阶连通简单图的邻接单谱性、全一输入可控性和Wronskian顶点，独立复核一个样例",
  "execution": {
    "mode": "research",
    "research": {
      "require_review": false,
      "max_plans": 3,
      "verification": "independent",
      "scope": {"source":"atlas","orders":[6],"matrix":"A","filters":{"connected":true}}
    }
  },
  "constraints": {"max_model_calls": 6,"max_tool_calls": 8,"allow_extensions": false,
    "allowed_tools":["graph_property_scan","graph_property_verify"]}
}
```

可导入示例见`examples/research/atlas6-task.json`。CLI使用同目录`atlas6-request.json`。模型可先inspect工具契约、澄清数学歧义，随后一次安排多步工具计划，根据错误和结果有界重规划。用户不需逐次指定函数，但当前系统不自动证明任意自然语言猜想。

## 计划是可校验的数据

科研计划必须包含`research={question,scope,assumptions,expected_outputs,validation,completion}`及原有steps/bindings。

- `completion`为`finite_enumeration`、`fixed_computation`或`bounded_search`。
- 每份计划最多10步；max_plans为1至8，默认4。失败与澄清不重置宿主总预算。
- 模型不能绕过计划直接计算。任务显式提供scope时，计划scope须一致；图性质扫描参数还须匹配已固定的source/orders/matrix/filters等原值。当前不自动理解或验证任意额外文字条件，重要条件应落实到受支持的参数，存在缺口则澄清或走独立开发。
- 工具尝试数及进程资源上界由程序计算；时间字段不是实际耗时预测，模型金额未知时保留null。超预算计划在执行前拒绝。
- require_review=true或桌面“先查看计划”要求确认。MCP返回当前plan及interaction，可信用户通过原UserPortal回答“确认/yes/按计划执行”；模型不能铸造事件。修改需求会使待确认计划失效并记录为superseded。
- 缺少工具时继续使用现有assess、用户审批和独立扩展流程。联动已有工具不创建新包；本功能不自动把成功实验写成新原生算法。

## 首批图性质工具

`graph_property_scan`按确定的生成器位置分批处理，batch_size为1至128。来源有：

| 来源 | 范围和完整性 |
| --- | --- |
| atlas | 1至7阶完整非同构简单图谱，可用connected等条件筛选 |
| trees | 1至12阶非同构树 |
| provided | 1至128张明确输入的图，每张最多12顶点；仅声明该输入集合，不保证非同构或涵盖全部图 |

支持connected、bipartite、边数和度数范围；select可组合simple_spectrum、controllable、has_wronskian_vertex，标记目标图，但总体计数仍覆盖所有通过结构条件的图。

矩阵支持A、L、Q=D+A、alpha=(1−α)A+αD以及U=aA+dD。系数采用有理数，建议分数字符串如"1/3"。单谱判定用特征多项式与导数互素；可控性用全一向量Krylov矩阵的精确秩，字段表示矩阵对(M,e)，图类连通性由filters.connected明确。Wronskian顶点按原矩阵主子式多项式与完整多项式互素判定，不重建删点图的度矩阵。单顶点图按空主子式多项式为1的约定处理；复现论文中额外排除单顶点的计数时，应明确该约定。

`graph_property_verify`从原始图和完整certificate独立复核，使用Fraction特征多项式递推、精确多项式欧几里得算法和有理数消元，不调用主计算的SymPy特征多项式/秩例程。单例复核不表示所有图均已独立复核。

这不是128顶点反例搜索上限的扩展：此工具提供小规模精确性质遍历，非同构枚举仍有独立的规模限制。没有接入geng或进行8、9阶一般图的完整生成；外部集合只能作为明确输入范围处理。

## 结果与恢复

summary.research由程序统计计划、失败、分页范围和独立复核样例。source_id绑定来源、阶数、矩阵和条件；cursor须连续。不允许把不同范围、重叠页或缺页拼成完整计数。结果区分completed、partial和in_progress；enumeration_complete只针对支持的有限生成器/输入集合，不是无限图类定理。verification=independent要求至少一个属于本次扫描的样例通过复核，不是全部统计的独立认证。

结果包新增research-summary.json、research-plans.json和research-counts.csv，并保留每次调用的原始输入、结果和执行回执。汇总前核对执行证据；损坏结果不能沿用。取消、进程中断和不确定执行沿用可信用户继续/重试及累计预算，已完成步骤复用有效回执。

现有经审核经验仍用于工具使用参考；计划及反馈随结果包保存，本版未自动建立可执行的方法模板库，也不把模型文字或一次实验观察写成定理。

## English

Development source0.38.0a1 adds a governed research profile to the existing LangGraph workflow. Select **Research experiment** before starting a new desktop chat, or submit execution.mode="research" with an explicitly enabled internal model. The host may instead compose the scan/verify tools without an assistant model.

Research plans declare question, scope, assumptions, outputs, validation and completion type. Calls must match an active validated plan; explicit structured scope cannot change silently. Plans are bounded by max_plans and existing total budgets. Review, clarification, cancellation, uncertain retry, receipts and result bundles use the trusted host mechanisms.

Graph property scans support non-isomorphic atlas graphs through7 vertices, non-isomorphic trees through12, or a bounded supplied collection. They compute exact simple spectrum, all-ones controllability and Wronskian vertices for explicit rational matrices. Independent Fraction-based verification checks selected certificates. Continuous scope-bound pages determine finite coverage; incomplete coverage is not a completed enumeration and finite experiments are not general proofs.

Model planning is tested with scripted adapters; no paid provider is exercised by local automated tests. Existing reviewed tool-use memory remains advisory. This version archives plans but does not automatically install executable method templates.
