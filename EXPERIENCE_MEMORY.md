# 只读记忆与经审阅科研案例（v0.34）

主agent通过research_memory读取明确偏好和成功调用频次，通过research_experience检索经用户审阅的历史案例。输入、身份、目录由原MCP宿主固定；两个接口均不写记忆、不计算、不扣任务内部数学工具预算，不调用模型。

## 案例积累与审阅

新子agent任务的已完成调用会在收尾时尝试生成候选，包括tools、scan、batch和agent模式的实际工具调用。只接受可核验的执行回执；失败案例还须有带执行版本的失败回执。候选使用固定规则提取条件与标量事实，不从模型回答归纳结论。没有受支持标量事实的成功调用会跳过，不把图像或符号推导强行归纳成案例。

记录包括工具/实验状态、alpha、容差、方法、图的阶/边数/一致度等已知条件，实际rho/残差/迭代数或失败类别，以及原始任务、调用、请求/结果/回执哈希和执行环境版本。矩阵秩与超图一致度分开处理。原始图、矩阵、问题、源码、路径和密钥不自动写入经验内容；输入仅保留哈希及有限条件。用户自己填写的审阅注释会保存。

默认状态为candidate，主agent不能检索为推荐。用户查看候选及对应结果后，可信本机CLI/宿主接口按当前content_sha256批准或拒绝。注释不能改变已捕获事实或扩大已测试条件；审阅不是数学证明，也不能替代新工具开发审批。

MCP没有捕获、批准、修改、遗忘或清空经验的方法。拥有同一系统账户任意代码执行权限的宿主属于本地信任边界，CLI本身不证明真人身份，不能注册成模型工具或用模型推测代替实际用户审阅。

## 主agent读取

```json
{}
```

以上是research_memory的完整参数；返回available、enabled、preferences、frequently_used_tools和experience_counts，最多10种常用工具，不返回其他用户或数据库路径。

research_experience按条件查找，例如：

```json
{"query":"高α","tool":"hypergraph_spectrum","outcome":"success","method":"newton_noda","rank":3,"alpha":0.999,"limit":5}
```

或传`{"id":"32位经验编号"}`读取一条。候选、已拒绝和已遗忘的记录不开放给主agent。每页最多20条，返回total/next_offset；过滤是关键词及结构化条件匹配，不是语义搜索或适用性证明。

- source_state=verified：原始输入、结果和回执仍与捕获时一致。
- source_state=unavailable：原任务/文件已清理或不可访问，仅保留经审阅的历史事实及哈希快照，不能当作本次计算证据。
- 原始来源已变化的记录会排除，并给出excluded_changed_sources。
- current_core_matches=false：当前代码清单与当时不同，需要留意版本差异；历史经验不自动作废，也不会被当作当前版本的保证。

记录及审阅文字都作为数据处理，优先级低于当前请求；不改alpha、精度、图结构或权重，不签发审批，不训练模型权重，不自动修改基础算法。条件只记录部分特征，相同阶数/边数/一致度不等于同构图。

## 本机管理

使用与你的MCP配置完全相同的--root和--user；示例路径和标识需替换为自己的配置。

```powershell
python -m graph_research experience list --root C:/Research/graph-state --user local-researcher --status candidate
python -m graph_research experience show --root C:/Research/graph-state --user local-researcher --id EXPERIENCE_ID
python -m graph_research experience review --root C:/Research/graph-state --user local-researcher --id EXPERIENCE_ID --content-sha256 CONTENT_SHA256 --decision approve --note "只适用于记录中的条件，其他图需重算"
python -m graph_research experience review --root C:/Research/graph-state --user local-researcher --id EXPERIENCE_ID --content-sha256 CONTENT_SHA256 --decision reject --note "不作为参考"
python -m graph_research experience forget --root C:/Research/graph-state --user local-researcher --id EXPERIENCE_ID
```

EXPERIENCE_ID和CONTENT_SHA256取自show的当前输出。content_sha256不匹配时拒绝审阅。单条遗忘擦除事实及审阅注释，保留最小事件去重标记，避免同一调用再次自动生成。

`experience clear --root ... --user ...`只清除该用户科研经验；`memory clear --user ... --memory-dir C:/Research/graph-state/memory`清除该目录下该用户的偏好、频次和经验，保留启用/停用开关。两者都不删除原会话、成果包或扩展。

`memory disable --user ... --memory-dir ...`同时停止该用户记忆读取及候选积累；重新启用不挖掘停用期间旧调用。清空后恢复旧任务也只积累新完成的调用。旧版本任务不自动回溯，用户可以显式用`experience capture --root ... --user ... --task TASK_ID --call call-0001`导入仍可核验的历史调用；旧失败记录缺少版本时会拒绝导入。

存储沿用--root/memory/memory.sqlite3，按用户哈希分区，与其他入口的默认记忆目录不自动同步。数据为本机明文，user是分区键而非登录认证。记忆异常不改变已完成计算的成功状态；summary.experience_collection会说明候选未写入，缺失案例可由用户稍后显式导入。

本版入口为MCP、子agent及CLI/宿主接口，桌面未增加统一经验管理页。偏好模型上下文沿用原行为；主agent需要实际调用只读接口后才取得这些记忆。

升级到v0.34.0后重启MCP服务，并在主agent客户端刷新工具列表。无需另配科研助手模型API。

新增扩展的数字/布尔输出最多记录16个标量候选，不保存任意返回文字或数组；工具版本记入证据。当前启用版本改变时，current_tool_package_matches=false提示差异。工具库可通过research_library关联本用户已审阅案例，详见TOOL_LIBRARY.md。
