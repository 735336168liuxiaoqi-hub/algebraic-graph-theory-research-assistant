# 批量任务与工具联动

主agent一次提交多组输入和步骤模板，科研助手按依赖执行，统一返回进度、逐步结果和可校验成果包。固定批量计算无需助手另配模型API。原tools、scan、agent入口保留。

完成情况以实际展开步骤和输出路径核验，不再由`partial`状态推断完成。失败或跳过使`computed_outputs_complete=false`；`summary.batch.steps/counts`保留逐步状态，跳过不伪造调用或收费。已有`batch.outputs`继续检查每个案例的路径；顶层`expected_outputs`若为文本，只表示未自动核验的交付意图。简单固定tools入口也可使用`execution.on_error="continue_independent"`，无需为少量独立步骤重复构造批量案例模板。

## 直接使用

examples/batch_workflow/paths.task.json计算P3/P4的邻接谱，再将矩阵绑定给matrix_analysis求秩，共2案例×2步骤=4次工具尝试。

- MCP：paths.mcp.json是research_submit的完整参数。之后沿用task_id调用research_get，建议wait_seconds=2、until=terminal。
- 本机CLI：`python -m graph_research subagent --root C:/Research/batch --user local --input examples/batch_workflow/paths.cli.json`。
- Python：`create_subagent(..., limits=SubagentLimits(max_model_calls=0,max_tool_calls=15,allow_extensions=False))`返回的parent直接submit任务JSON，不需要主agent或模型。
- failure-branches.task.json演示无效圈图输入的依赖分支跳过、独立步骤和其他案例继续。

本机subagent CLI沿用默认宿主预算10次；较大批次可用Python的SubagentLimits或MCP启动参数配置。示例任务自身设为4次，若中断后需要重算，原上限不变；可在首次提交前为重试预留预算。

核心结构：

```json
{
  "version": 1, "request_id": "batch-paths-001", "objective": "批量计算图性质",
  "execution": {"mode": "batch", "batch": {
    "cases": [{"id":"P3","inputs":{"n":3}}, {"id":"P4","inputs":{"n":4}}],
    "steps": [{"id":"graph","tool":"graph_invariants","arguments":{"kind":"path"},
               "bindings":{"n":{"case":["n"]}}}],
    "outputs":{"diameter":{"step":"graph","path":["diameter"]}},
    "on_error":"continue_independent"
  }},
  "constraints":{"max_model_calls":0,"max_tool_calls":2,"allow_extensions":false}
}
```

## 输入和依赖

inputs为共享输入，cases[].inputs为该案例输入；bindings中的input/case分别读取两者。省略cases时执行一次default案例。arguments填写常量，同一参数不能同时来自常量与绑定。

多组同构流程使用cases；异构工具联动可省略cases，直接在steps中分别声明工具、参数和依赖。

前序结果使用`{"step":"spectrum","path":["matrix"]}`绑定；depends_on可声明额外先后依赖。可前后声明步骤，执行器稳定拓扑排序；引用范围仅当前案例模板，重复ID、未知依赖、循环和跨案例引用均拒绝。只读JSON对象键或数组下标，不执行表达式、字符串插值或Python文本。

返回步骤ID为案例ID::模板步骤ID。两类ID只能用ASCII字母数字、下划线、点或横线，最长48字符，不含冒号。outputs按模板步骤及path选择最多32个汇总字段。

## 预检、预算和执行

最多64案例、展开100步，请求最多256KiB，展开输入最多1MiB。宿主--max-tool-calls和任务constraints均须足够，预算不足时整批拒绝，不自动提高上限。开始前检查所有工具、白名单和已知参数格式；依赖值产生后，实际调用前再次校验完整参数。数学可解性仍由工具判断，例如圈图n=2会实际失败。

每个真正尝试的步骤分别预扣一次，失败/中断也计数。依赖跳过、绑定字段不存在或绑定类型不符而未启动工具的步骤不扣计算预算。因此summary.batch中的失败步骤数可能高于failed_calls；判断完成应同时看整体status及案例状态。

执行为串行、每步独立受保护进程，沿用原单步时间/CPU/内存上限。主要改善主agent往返、重复编排和结果整理，进程启动次数仍按实际步骤统计。一个超图的alpha扫描继续可用scan模式，保留已有热启动。

## 失败、取消和恢复

- on_error默认stop：首个失败后停止整个批量任务，剩余步骤标记skipped。
- continue_independent：跳过失败步骤的依赖分支，独立步骤和其他案例继续。失败不自动重试。
- 案例未完整成功或所选输出字段不存在，整体返回partial/failed，不把已有部分结果当作全部完成。
- research_cancel取消整个任务，保留结果；重启不自动继续。可信宿主取得真实用户确认后签发continue事件，再调用research_resume。
- 恢复先核验已完成步骤的参数及回执，成功步骤复用，预算不重置。不确定步骤重算仍需用户确认；损坏回执拒绝恢复和结果读取。
- 相同request_id只能重放相同JSON，返回已有任务，不新增计算。修改输入、输出列或预算须使用新请求编号。

## 进度和成果

summary.batch包括总步骤、完成数、各状态计数、案例行、依赖、call_id和已用时间。MCP摘要默认8案例/20步骤，优先显示执行中/失败步骤，并标注省略量。detail=full或结果包可读全表。

所选标量直接显示；较大对象或长文本提供定位，用行内call_id和summary.batch.output_definitions里对应path调用research_inspect_result读取。原始精度仍保留在逐步结果中。

统一成果包增加report.html案例汇总、batch-results.csv标量表、batch-summary.json逐步状态、batch-plan.json原始计划，同时保留results.json、reproduce.json、calls/内的完整参数、结果、回执和附件。CSV文本有公式注入转义；计划文件只作为数据保存，不会自动执行。

成果包沿用现有256MiB总量等限制；超大输出仍可从保存的逐步记录按字段读取。若打包未完成，返回会明确标记partial并保留计算记录，不会报告不存在的完整ZIP。

## 单工具批量导出

graph_batch_study在一次受保护调用内计算多案例，与execution.mode=batch的逐步编排不同。必须检查calculation_status、export_status和rows.errors；可恢复导出失败保留数值，files只登记已发布文件，summary.output_complete=false及export_failures会提示。未发布暂存文件不作为附件。路径及固定运行副本说明见[DEVELOPMENT.md](DEVELOPMENT.md)。
