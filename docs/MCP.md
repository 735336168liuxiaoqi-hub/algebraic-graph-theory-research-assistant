# MCP接入与任务协议

同一个图论计算核心提供本地STDIO MCP服务，供支持MCP的主agent连接。独立桌面、离线工具与API对话入口继续保留。当前不提供HTTP监听或公网服务，也不自动修改宿主配置文件。

## 安装与启动

本项目环境已安装并验证官方MCP Python SDK。其他Python环境安装发行包的`[mcp]`依赖；绘图使用`[mcp,visual]`，全部功能可用`[all]`。模型规划另需`[assistant]`，已有工具计算无需模型API。

```powershell
python -m pip install ".[mcp,visual]"
python -m graph_research mcp --root C:/Research/graph-state --user local-researcher
```

服务的标准输入/输出专用于MCP消息，手动启动后等待客户端输入属于正常情况。通常由主agent按连接配置自动启动，无需用户另外保留终端。请使用安装了本项目的Python解释器；状态目录建议短路径。计算仍使用现有Windows受限执行后端，其他系统没有未保护执行回退。

## 生成连接配置

在希望运行科研助手的Python环境中执行，输出使用该环境解释器的绝对路径：

```powershell
# 通用连接信息JSON
python -m graph_research mcp-config --root C:/Research/graph-state --user local-researcher

# Codex配置片段（TOML）
python -m graph_research mcp-config --root C:/Research/graph-state --user local-researcher --format codex

# DeepSeek Harness配置片段（YAML插件条目）
python -m graph_research mcp-config --root C:/Research/graph-state --user local-researcher --format dsh
```

把输出放入对应客户端的MCP配置位置。生成命令只输出配置，不创建状态目录、不连接服务、不读取API密钥，也不会覆盖原客户端文件。服务标识为`graph_research`；DSH使用官方`@deepseek-ai/dsh-mcp-client`插件。客户端的MCP权限选择仍由其宿主负责。

参考：[Codex官方MCP说明](https://developers.openai.com/codex/mcp)、[DSH官方MCP客户端](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)、[官方Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0)。配置格式经过解析与官方SDK客户端验证；生成配置不等于已在目标电脑完成宿主安装；应在目标客户端重连后验证。

## 主agent如何调用

服务对外只提供少量调度工具，计算函数通过按需目录发现。现有43个内置工具不会同时展开全部Schema占用上下文。

| MCP工具 | 功能 |
| --- | --- |
| `research_catalog` | 无name返回精简目录与宿主限额；指定name返回工具完整参数、中文说明及示例 |
| `research_submit` | 提交统一任务，快速返回task_id；后台执行 |
| `research_get` | 查询状态、结果、预算和交互；wait_seconds最多10秒 |
| `research_list_tasks` | 当前宿主用户最近任务，最多50条 |
| `research_cancel` | 请求取消，保留已保存结果 |
| `research_resume` | 传递可信宿主已签发的event_id，异步继续 |
| `research_recover` | 将确认已中断的任务恢复为待用户继续的状态；不重算 |
| `research_inspect_result` | 按call_id和JSON字段路径查询，数组分页，每次最多256KiB |
| `research_read_artifact` | 核验SHA256后按附件编号分块读取，单次最多64KiB，返回base64 |
| `research_library` | 只读检索已安装扩展及版本、状态、适用条件；启停及切换仅供可信本机用户 |
| `research_development` | 主agent提交无源码评估、查询及取消；用户确认后提交实现，后台受保护验收并持久封包 |
| `research_memory` | 只读获取当前宿主用户的明确偏好、常用工具及案例状态数量 |
| `research_experience` | 只读检索已审阅历史案例，按工具、方法、alpha和一致度等条件过滤，核验来源及版本 |

先调用`research_catalog(name="graph_invariants")`，再向`research_submit`提交：

```json
{
  "task": {
    "version": 1,
    "request_id": "study-p3-001",
    "objective": "计算P3的直径",
    "definitions": ["普通无向简单图"],
    "execution": {
      "mode": "tools",
      "steps": [
        {"id": "structure", "tool": "graph_invariants", "arguments": {"kind": "path", "n": 3}}
      ]
    },
    "constraints": {"max_model_calls": 0, "max_tool_calls": 1, "allow_extensions": false}
  }
}
```

返回task_id后调用`research_get(task_id="返回的编号",wait_seconds=2)`；读取`results`中的真实计算结果和`artifacts`结果包。多步工具间数据使用原子agent协议的`bindings`，见[完整任务协议](reference/SUBAGENT.md)。重复提交必须沿用request_id和同一份输入；不因为等待较久就改ID提交。

结果为`queued/running`时仍未完成。后台执行状态在`transport.worker_state/active`中；任务状态、修订、剩余预算和终止标记沿用原协议。`get`可能短暂重读并发更新的JSON文件，不会因此重新执行计算或请求模型。

## 长计算、取消和恢复

首版同一状态目录、同一用户同时接受一个后台任务。另一新任务返回`mcp_busy`且不创建额外任务；同request_id查询继续幂等。已有步骤可以在一个任务中连续执行。

后台任务有固定的宿主进程入口，计算仍使用受保护子进程。STDIO断开不主动取消计算；若客户端终止整个进程树，记录仍保留。重新连接后先查询；显示worker中断时，使用`research_recover`恢复记录。它不重算；之后需要真实用户选择继续并签发事件，再调用`research_resume`。已有有效回执的固定步骤会复用；失败或不确定的尝试仍消耗预算。

取消后不会自动继续。主agent需要把暂停原因和用户可选操作展示出来。任务无法证明进程存活时，新启动进程有最多15秒保守观察窗口，避免把正在启动的worker误判为崩溃。

## 用户回复与审批

MCP不暴露签发用户回复、批准、拒绝或继续事件的方法；`approved: true`、`actor: user`和任意回复文本不能通过MCP参数代签。

可信宿主按[子agent用户门户](reference/SUBAGENT.md)取得用户实际操作，使用相同root/user签发绑定当前任务、revision和interaction_id的事件，然后把event_id交给主agent调用`research_resume`。已有本机`subagent-user`命令继续可供可信宿主使用，不应注册成模型工具。

本机身份与目录属于可信宿主配置；user不是登录认证。拥有同一账户任意本机代码执行权限的进程不在这条审批隔离边界内。

## 可选启用内部模型与扩展

默认`execution.mode="agent"`明确拒绝，不构造模型适配器，不请求模型。主agent完成任务拆解后，可直接委派固定工具步骤。

确需助手自主分析时，由宿主显式增加：

```powershell
python -m graph_research mcp --root C:/Research/graph-state --user local-researcher --allow-agent --model-config C:/Research/model.json --max-model-calls 8
```

公开配置来自既有模型设置；密钥只通过其中指定的环境变量提供，没有终端隐藏输入回退。worker只接收明确选定的密钥变量，其他服务商密钥会被滤除。模型地址、模型和思考强度按公开配置快照使用。

允许申请实验扩展时再加`--allow-extensions`；实际开发仍要求范围评估、用户批准和原受限验证，基础包不会开放给模型修改。单独启用agent不会默认开放扩展。`mcp-config`接受相同启动选项；需要认证时仅生成环境变量名及宿主转发规则，不输出变量值。

宿主可用`--max-tool-calls`、重复的`--allowed-tool`及`--tool-seconds/--tool-cpu-seconds/--tool-memory-mb`限制能力。任务约束只能降低上限。调用计数与已有工作流预算持续保留，连接重建、回复和审批不能重置。

## 成果保存与清理

默认结果包进入公共[成果中心](RESULTS_AND_MEMORY.md)，可用`--results-root D:/研究成果`显式指定。桌面可按课题归类、保留或清理MCP结果；返回的result_id和artifact_id保持稳定，改名后仍按原SHA256读取。已缓存回执引用的ZIP不自动删除。

整任务清理后，相同request_id返回终态`cleared`及原已用预算，不会再次计算；原始结果须在成果中心回收区恢复后再取。永久清理保留最小任务状态，需重新研究时使用新请求编号。恢复不会重置预算，运行及等待用户/审批的任务不能清理。

## 结果与附件

### 操作结果与任务状态

`status`是持久化任务状态；`operation`是最近一次后台start/resume操作的结果。恢复失败时，原任务可以继续保持`cancelled`或`waiting_for_user`，同时`operation.status=failed`、`operation.error.code=event_not_found`等。MCP调用返回`isError=true`，不能仅凭task_id存在或任务状态未变化宣称恢复成功。保留旧的`transport.error`以兼容既有宿主。

`operation.status=succeeded`只说明后台调度已完成；科研结论仍须检查任务status、逐步results、验证证据和导出状态。`cancel`、`recover`当前请求的成功不受上次后台操作失败影响。

`request_effect`说明本次请求：重复submit/resume为`reused`，查询为`read_only`，均不会新建后台计算，新增工具/模型调用为0；已有后台任务可以独立继续运行。首次submit/resume为`launched`，新增调用暂为null，完成后的实际量看`operation.usage`。这里不是宿主模型token或费用。

`budget.used`和`summary.reuse.cumulative`是整任务累计量；旧字段`steps_recomputed`仍保留，但表示历史已执行观察数，不能解释成本次重复计算。`operation.usage`是自本次后台作业启动以来的尝试增量，失败也计入；旧作业未保存基线时不猜测该增量。

任务已经取消且后台停止后，重复取消保留原revision、interaction、artifact_id、ZIP路径与SHA256，不生成新成果包。后台尚在停下时，取消仍可能返回原运行状态；继续按原task_id查询到`transport.active=false`。

`research_catalog`及按名/哈希查询均包含`service.version`、`service.core_manifest_sha256`和`service.core_verified`。不同核心指纹说明实际代码清单不同；只看版本号不能证明代码一致。校验失败时停止并报错，不自动封存。

普通`tools`步骤默认执行到预算用尽；希望预算不足时整任务不开始，可设置`constraints.fail_fast=true`。`scan`与`batch`总是预检展开预算。目录的`budget_policies`和任务的`budget.admission_policy`给出当前政策。

样式字段错误通过逐步结果的`error_details.field_path`与`validation`给出位置和修正规则。例如`["style","font_size"]`配合minimum=6、maximum=36。不会在诊断元数据中回显原始输入值。MCP外层Schema错误也会提供可用的字段路径和规则。

每条成功结果可用`read_more.call_id`调用`research_inspect_result`，path默认`[]`；大结果需选择具体字段并分页。谱扫描的标量汇总在`summary.scan.points`，批量编排汇总在`summary.batch`；不要把工具内部graph_batch_study返回当作编排器字段。

布局用无向无权支撑结构计算坐标，其`normalization`说明转换用途；`graph_document`保留原图方向和权重，后续原图计算使用该字段。数字顶点1与字符串顶点"1"的数据身份保持独立，默认图标签显示为1和带引号的"1"；显式自定义标签按用户文本显示。

### 使用独立验收连接

在外部agent测试时，另设MCP服务名，并给`--root`、`--results-root`、`--user`指定测试专用目录/用户，例如`--root C:/graph-tests/state --results-root C:/graph-tests/results --user acceptance-local`。复用已安装的Python入口与宿主限额即可，无需助手API。避免用生产用户测试记忆、取消或清理；不要自动覆盖原连接配置。

静态资源：`graph-research://guide`、`graph-research://contracts`。
任务资源：`graph-research://tasks/{task_id}`。
附件资源：`graph-research://tasks/{task_id}/artifacts/{index}`。

资源附件只读取该任务已登记的ZIP，并核验SHA256；整资源读取最大1MiB。更大附件使用分块工具按offset拼接，每次最多64KiB；默认服务只处理总量不超过256MiB的单个登记附件，更大的保留本机路径供宿主处理。不接受任意文件路径或外部URL，不能用于读取宿主密钥或其他用户文件。

DSH等客户端对二进制资源的展示支持各不相同，通用路径和分块工具仍可使用。计算里的图像、TikZ等成果继续包含在结果包内，主agent也可按其宿主能力读取已返回的本机成果路径。

## 验证边界

官方SDK客户端验证新协议与传统initialize握手、STDIO多进程调用、真实本地多步计算、结果字段查询、ZIP读取、重复请求与跨连接恢复。模型参与的交互使用脚本模型与可信门户模拟，不调用付费API。目标宿主的安装、原生审批界面和权限选择由宿主负责；当前不提供远程HTTP服务。

## 查询、扫描与契约缓存

默认精简返回，full/inspect保留完整证据；提交可短暂等待，查询可等待终态；工具契约提供缓存指纹，相同schema_hash可复用已读取契约。scan模式一次提交固定图的α扫描，构图与每点分别计预算。11点加构图需要宿主显式配置至少12次尝试，默认10不会自动提高。成本日志只记本机已采集的工具RPC，不代替主模型usage。
