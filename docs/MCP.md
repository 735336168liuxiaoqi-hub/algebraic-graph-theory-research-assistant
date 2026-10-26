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

服务对外提供13个调度／集成入口，47个内置计算工具通过按需目录发现，不同时展开全部Schema占用上下文。

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

### 通用实验入口

当前main的`execution.mode="experiment"`支持prepare／execute／study。已有工具、明确候选评价及rules规划的study无需本助手API；`planner="model"`才需要宿主开启内部模型。study在确认后的有限参数网格、方法、种子及预算内运行枚举／随机／局部／可选CPU CEM，内部experiment_evaluate和experiment_search不是额外的公开计算工具。

先从`graph-research://contracts`读取experiment_contracts；以`examples/research-experiments/clique-free-study.json`任务本体提交research_submit。CLI的`*-request.json`带submit外层，不能直接当作MCP task。默认按宿主预算直接执行；require_review只控制一次初审，pause_at_checkpoints才控制科研反馈。确实等待用户时可在桌面确认，原服务自动接收事件，主agent继续查询同一task_id，模型仍无签发权限。原有可信宿主事件接口保持兼容。

指南、完整例子、CEM依赖和研究边界见[通用实验](EXPERIMENTS.md)。按每轮保护进程扣工具尝试，另计候选评价和时间预算；失败／重启／恢复不清零。CEM需可选search依赖，`[all]`不含torch。一般超图允许含环，张量目标不由普通图矩阵替代。升级后须更新实际启动副本并重连以加载新契约。

首版同一状态目录、同一用户同时接受一个后台任务。另一新任务返回`mcp_busy`且不创建额外任务；同request_id查询继续幂等。已有步骤可以在一个任务中连续执行。

后台任务有固定的宿主进程入口，计算仍使用受保护子进程。STDIO断开不主动取消计算；若客户端终止整个进程树，记录仍保留。重新连接后先查询；显示worker中断时，使用`research_recover`恢复记录。它不重算；之后需要真实用户选择继续并签发事件，再调用`research_resume`。已有有效回执的固定步骤会复用；失败或不确定的尝试仍消耗预算。

取消后不会自动继续。主agent需要把暂停原因和用户可选操作展示出来。任务无法证明进程存活时，新启动进程有最多15秒保守观察窗口，避免把正在启动的worker误判为崩溃。

## 用户回复与审批

### 默认自主执行

本地a9将审批从普通计算主流程移除：输入、宿主权限与预算校验通过后直接运行。实验账本仅记录范围、核心/策略身份、资源和执行证据，不再维护approved或host_authorization。没有另外一套4096评价、300秒、1GiB等“自动批准”门槛；真正的每worker资源限额、总调用数和任务累计预算始终保留。

默认CLI、MCP和Python接口行为一致。`constraints.require_review=true`或宿主`--confirm-experiments`可主动要求一次初审；只有这时创建真实用户确认记录。科研反馈单独用实验`pause_at_checkpoints=true`，按segment_rounds/segment_chunks暂停；它不要求初审，也不代表资源批准。仅分段和保存检查点不会暂停。

宿主已启用模型并授权调用额度后，planner=model也可直接执行，不因为“用了模型”再次审批。附加definitions仍须在execute/study前形式化到problem，模型可以自行处理；无法判断的数学歧义才询问用户。超出宿主硬限额直接拒绝，点击确认不能抬高权限；主agent可选预算内等价计划，或请求用户调整授权。

新增工具、不可逆操作及不确定执行的重试仍保留必要交互。确定的启动前失败返回blocked和诊断，不弹无意义的继续确认。真实确认仍经签名事件绑定task/revision/interaction，模型没有签发能力。

旧review-policy参数只在入口转换成一次初审选项，不再是计算引擎的两套执行模式；旧核心实验只读，不强制迁移账本。配置可直接保存UTF-8，避免PowerShell 5.1管道损坏中文路径：

```powershell
python -m graph_research mcp-config --root C:/Research/agt-state --user researcher --output C:/Research/mcp.json
```

已有文件不覆盖。安装/注册及升级连接是一次性操作，日常预算内计算不要求用户开终端或复制事件编号。阈值按已授权预算处理，主agent不能通过拆单或换request_id扩大授权。

MCP不暴露签发用户回复、批准、拒绝或继续事件的方法；`approved: true`、`actor: user`和任意回复文本不能通过MCP参数代签。

### 桌面任务审批

本地a4提供原生窗口；**a5在交互式Windows默认自动打开／复用窗口并定位新待办**，旧下载包尚无这些功能。优先复用用户会话中已打开的主桌面程序，避免每次由临时agent工具进程启动GUI。没有主窗口时，由持久MCP服务启动精简窗口，不使用breakaway／detached／WMI等方式绕过宿主进程限制。

1. 完成正在运行的旧版任务，更新后重启MCP连接及桌面程序。旧服务没有事件投递循环，窗口不能替旧服务执行计算。
2. 新任务需要确认时，窗口自动显示并连接提交它的root/user，用户不需要额外打开终端或点击连接。手动查看时仍可打开桌面“任务审批”；身份取MCP的`--user`，不是users下的目录哈希。未知用户会明确报错而不创建空用户。连接设置保留在本机。
3. 选择任务，查看数学对象、实例／方法／种子、预算、已用调用和提示；“查看完整计划与当前记录”可检查准确输入与评估。
4. 默认仅列待处理任务，可按标题／request_id／task_id搜索，关闭过滤查看历史（最多最近1000条）。初次点击“确认并开始”；取消按钮明确显示“不执行”。study暂停后改探索／精英／惩罚／优先run或反馈说明，主按钮会自动变为“应用参数并继续”；没有改动才沿用原参数继续。撤销本次修改不会执行计算。
5. 无需PowerShell签发、复制event_id或让主agent再次resume。窗口只签名并保存用户操作；**原MCP进程**接收后沿用自己的模型配置、环境和限额启动后台任务。主agent按原task_id查询结果。窗口的自动刷新只读状态，不自动批准或重试。

也可单独打开精简窗口（运行一次即可，之后在窗口操作）：

```powershell
python -m graph_research approvals --root D:/Research/mcp-state --user researcher
```

GUI仍需安装`desktop`可选依赖。此窗口仅管理指定root/user下有MCP宿主记录的任务；不接管独立CLI任务，也不接管`research_development`的独立工具开发申请，后者继续使用[扩展开发的可信审批入口](EXTENSIONS.md)。任务协议内的`waiting_for_approval`可以在窗口处理。

“等待对应MCP服务接收”表示签名操作尚未交付；确认该配置的MCP服务已经更新并重启，root/user及宿主配置一致。此时不要反复点击或换request_id。连接关闭时操作会保留；事件过期、任务版本变化或恢复失败都会显示原因，未核验计算不自动重试。失败后的继续会明确提示旧预算保留、重试另计。关闭窗口不会取消已确认执行的MCP任务。

正常study的`segment_rounds`默认128个计算分段；worker_rounds=1时每段一代，增大worker_rounds可在同一保护进程内连续多代。segment_rounds=1用于每段后反馈。窗口不会暗改计划或扩预算。旧核心任务只供查看，新版用新任务验证，不改旧检查点。

同一交互不会反复弹窗，用户正常关闭后不会因轮询重新弹出；后续新交互仍可自动显示。检测到异常退出只尝试一次界面重开，不重试计算。新窗口的自动启动仍服从实际宿主策略：宿主若连持久MCP子进程也回收，先由正常用户会话打开主程序，后续待办会自动切到审批页；应用不会越过该策略。无桌面依赖或headless/offscreen环境不自动弹窗，MCP任务继续等待真实用户。

界面回调错误、Qt消息和原生崩溃信息写入`~/.graph_research/logs/desktop.log`；无法写入时尝试TEMP中的进程日志，不因日志失败关闭窗口。MCP的`users/<摘要>/mcp/approval-ui-bootstrap.log`保留启动输出，`approval-ui-notified.json`记录打开／复用情况。排障只读这些诊断，不读事件密钥、不代签或修改队列。外部agent临时进程退出造成窗口消失，不能简单归为Qt崩溃；两类原因应分别报告。

### 科研资源配置

标准档位保持30秒／1GiB／1数值线程。一次性在MCP启动配置选择research档位，可生成可审阅配置：

```powershell
python -m graph_research mcp-config --root D:/Research/agt-state --results-root D:/Research/results --user researcher --resource-profile research
```

research默认允许1000次工具尝试、每段900秒墙钟；数值线程采用逻辑CPU数减1（至少1，最多128），CPU秒=900×线程数，内存为约75%物理内存（最多64GiB）的进程树总上限；无法探测内存时按8GiB的75%计算。它只配置宿主上限，不分配内存、不开始训练，也不增加模型API预算。实际用量取决于图阶、批量和算法。

可用`--tool-memory-mb`、`--tool-threads`、`--tool-seconds`、`--tool-cpu-seconds`和`--max-tool-calls`覆盖；**旧配置里显式写着30秒／1024MiB的参数会继续优先，需删除或改大，不能只追加档位名**。人工确认并重启MCP连接后生效，既有任务不据此升级权限。

协议时间上限7天墙钟／365天累计CPU、内存上限1TiB、工具尝试上限10000只是可表达范围；宿主仍可更低，任务不能抬高。study总预算可设数小时，worker_rounds安排多代连续训练；每段仍由宿主的单次上限保护。CPU累计时间与实际经过时间分别配置，多核运行需要相应CPU预算。详情见[连续训练](EXPERIMENTS.md#长时间研究与连续训练)。

`--approval-ui auto`为默认，`--approval-ui off`供无桌面的集成或测试使用。关闭自动窗口不代表同意任务，仍需原有可信用户入口。变更宿主配置后重新连接；不自动修改其他应用的配置文件。

### 兼容已有宿主

可信宿主仍可按[子agent用户门户](reference/SUBAGENT.md)取得用户实际操作，使用相同root/user签发绑定当前任务、revision和interaction_id的事件，再由主agent调用`research_resume`。本机`subagent-user`命令保留供可信宿主使用，不应注册成模型工具。使用桌面审批时无需重复这条路径。

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

`status`是持久化任务状态；`operation`是最近一次后台start/resume操作的结果。恢复前同步校验事件、范围、版本及宿主策略，无效事件直接返回错误，不启动后台作业或消耗预算。后台获得任务锁后仍调用同一套校验，处理过期或状态变化等竞态；此时原任务可保持`cancelled`或`waiting_for_user`，同时`operation.status=failed`、`operation.error.code`给出原因。MCP调用返回`isError=true`，不能仅凭task_id存在或任务状态未变化宣称恢复成功。保留旧的`transport.error`以兼容既有宿主。

`operation.status=succeeded`只说明后台调度已完成；科研结论仍须检查任务status、逐步results、验证证据和导出状态。`cancel`、`recover`当前请求的成功不受上次后台操作失败影响。

`request_effect`说明本次请求：重复submit/resume为`reused`，查询为`read_only`，均不会新建后台计算，新增工具/模型调用为0；已有后台任务可以独立继续运行。首次submit/resume为`launched`，新增调用暂为null，完成后的实际量看`operation.usage`。这里不是宿主模型token或费用。

`budget.used`和`summary.reuse.cumulative`是整任务累计量；旧字段`steps_recomputed`仍保留，但表示历史已执行观察数，不能解释成本次重复计算。`operation.usage`是自本次后台作业启动以来的尝试增量，失败也计入；旧作业未保存基线时不猜测该增量。

任务已经取消且后台停止后，重复取消保留原revision、interaction、artifact_id、ZIP路径与SHA256，不生成新成果包。后台尚在停下时，取消仍可能返回原运行状态；继续按原task_id查询到`transport.active=false`。

`research_catalog`及按名/哈希查询均包含`service.version`、`service.core_manifest_sha256`和`service.core_verified`。不同核心指纹说明实际代码清单不同；只看版本号不能证明代码一致。校验失败时停止并报错，不自动封存。

普通`tools`步骤默认执行到预算用尽；希望预算不足时整任务不开始，可设置`constraints.fail_fast=true`。`scan`与`batch`总是预检展开预算。目录的`budget_policies`和任务的`budget.admission_policy`给出当前政策。

`tools`遇到执行失败默认停止；需要继续独立步骤时设置`execution.on_error="continue_independent"`。它与预算`fail_fast`分别控制不同事项。失败不会自动重试，依赖失败结果的步骤标为`skipped`并说明原因，不计预算、不伪造`call_id`。`summary.steps`列出计划覆盖与逐步状态；缓存复用按已有证据计覆盖，不要求调用次数等于步骤数。

`execution_complete`要求全部固定步骤已处理且无跳过；它不代表全部成功。`computed_outputs_complete`要求全部计算和导出成功；`output_complete`还要求交付声明可核验并通过。旧的字符串`expected_outputs`保留为交付意图，返回`not_validated`且`output_complete=false`，不会把不存在的字段算成已交付。固定步骤可改用`"expected_outputs":[{"name":"order","step":"structure","path":["order"]}]`，按实际结果检查路径；批量任务也可使用已有`batch.outputs`。prepare用`preparation_complete`及`preparation_output_complete`表示草案，不声称计算完成。

无参`research_catalog`的`capabilities.experiment_preparation`列出对象、指标、约束、后端和张量定义域。未知ID返回`unknown`及候选建议；存在但不适用于该对象的ID才标`unsupported`。

上述a10语义用于新任务。历史任务的封存响应与回执保留原样，重用旧request_id仍返回旧快照，不会改写证据或重新计算。升级后重启MCP连接，验收使用新的request_id及输出目录，并按当前源码版本／核心指纹固定测试基线。

样式字段错误通过逐步结果的`error_details.field_path`与`validation`给出位置和修正规则。例如`["style","font_size"]`配合minimum=6、maximum=36。不会在诊断元数据中回显原始输入值。MCP外层Schema错误也会提供可用的字段路径和规则。

每条成功结果的`read_more`包含工具名和完整参数`task_id`、`call_id`、`path`。例如调用`research_inspect_result({"task_id":"返回的task_id","call_id":"call-0001","path":["spectrum"],"offset":0,"limit":100})`。path默认`[]`；大结果需选择具体字段并分页。谱扫描的标量汇总在`summary.scan.points`，批量编排汇总在`summary.batch`；不要把工具内部graph_batch_study返回当作编排器字段。

布局用无向无权支撑结构计算坐标，其`normalization`说明转换用途；`graph_document`保留原图方向和权重，后续原图计算使用该字段。数字顶点1与字符串顶点"1"的数据身份保持独立，默认图标签显示为1和带引号的"1"；显式自定义标签按用户文本显示。

### 使用独立验收连接

在外部agent测试时，另设MCP服务名，并给`--root`、`--results-root`、`--user`指定测试专用目录/用户，例如`--root C:/graph-tests/state --results-root C:/graph-tests/results --user acceptance-local`。复用已安装的Python入口与宿主限额即可，无需助手API。避免用生产用户测试记忆、取消或清理；不要自动覆盖原连接配置。

静态资源：`graph-research://guide`、`graph-research://contracts`。
任务资源：`graph-research://tasks/{task_id}`。
附件资源：`graph-research://tasks/{task_id}/artifacts/{index}`。

资源附件只读取该任务已登记的成果ZIP或scientific_evidence候选JSONL，并核验SHA256；整资源读取最大1MiB。更大附件使用分块工具按offset拼接，每次最多64KiB；默认服务只处理总量不超过256MiB的单个登记附件，更大的保留本机路径供宿主处理。不接受任意文件路径或外部URL，不能用于读取宿主密钥或其他用户文件。

DSH等客户端对二进制资源的展示支持各不相同，通用路径和分块工具仍可使用。计算里的图像、TikZ等成果继续包含在结果包内，主agent也可按其宿主能力读取已返回的本机成果路径。

## 验证边界

官方SDK客户端验证新协议与传统initialize握手、STDIO多进程调用、真实本地多步计算、结果字段查询、ZIP读取、重复请求与跨连接恢复。模型参与的交互使用脚本模型与可信门户模拟，不调用付费API。目标宿主的安装、原生审批界面和权限选择由宿主负责；当前不提供远程HTTP服务。

## 查询、扫描与契约缓存

默认精简返回，full/inspect保留完整证据；提交可短暂等待，查询可等待终态；工具契约提供缓存指纹，相同schema_hash可复用已读取契约。scan模式一次提交固定图的α扫描，构图与每点分别计预算。11点加构图需要宿主显式配置至少12次尝试，默认10不会自动提高。成本日志只记本机已采集的工具RPC，不代替主模型usage。


开发版专用任务 `execution.mode=counterexample` 的输入、预算及科研结论边界见[反例搜索](COUNTEREXAMPLE_SEARCH.md)。

## 科研自主规划（开发源码0.38.0a1）

execution.mode=research将目标交给已显式配置的助手模型，支持正式计划、可选用户查看、预算估计、失败反馈和有界重规划。参数及例子见[科研实验说明](RESEARCH_PLANNING.md)。仅使用主agent模型时，由主agent规划并通过固定tools/batch调用graph_property_scan/verify，无需本助手另配API。
