# 持久扩展工具库（v0.35）

新工具经过需求评估、实际用户确认及受保护验收后，独立保留在工具库。后续离线、API或MCP任务从同一配置的工具库发现和复用，无须重新开发或重复进行开发审批。现有工具联动可完成的问题留在工作流中，不新增包装工具。

## 目录与共享

桌面“本地工具”和“科研对话”共用当前tool_directory。通过验收的新工具出现在“已安装的实验工具”分类；切换回本地页会刷新，也可打开“工具 → 扩展工具库”刷新、检索、查看样例、启停和切换历史版本。中文显示名来自审批范围的library_metadata.title；参数名可用Schema.title，枚举可用x-enum-labels、x-enum-descriptions。原始工具名、参数值和数学语义保持不变。

MCP默认仍在root/users/用户哈希/tool_packages按用户隔离；独立CLI仍沿用原tool_directory。不会擅自搬移或合并已有目录。需要同一用户在多个入口共用，或明确选择项目共享库时，由可信宿主指定同一绝对目录：

```powershell
python -m graph_research desktop --tool-dir D:/GraphProject/tools
python -m graph_research mcp --root D:/GraphState --user researcher --tool-dir D:/GraphProject/tools
```

共享目录是显式的宿主信任选择，其中启用的工具对使用该目录的入口可见；不是多人登录权限系统。用户记忆、案例及开发请求仍按原root/user分区，不因共享工具目录而自动共享。

## 由主agent开发，无需另配助手API

```powershell
python -m graph_research mcp-config --format codex --root D:/GraphState --user researcher --tool-dir D:/GraphProject/tools --allow-development
```

将生成配置放入主agent的MCP配置并重启连接。--allow-development仅允许申请和提交开发，默认关闭，不创建内部模型；原--allow-agent/--allow-extensions保留原意义。宿主模型的token、调用次数及费用由主agent计量，本服务返回未知值，不冒充能约束或测量宿主模型预算。

1. 调用research_catalog、research_library核对已有能力及组合方案。research_library只读返回扩展的版本、条件、状态及契约/经验查询入口；完整当前工具Schema仍用research_catalog(name=...)。
2. research_development(operation="assess", request_id="稳定请求号", request={...})提交无源码需求，request沿用FEATURE_DEVELOPMENT.md中的评估字段：name、goal、requirements、checked_tools、composition_possible、why_not_composition、new_algorithm、parameters、acceptance_tests、complexity；可附library_metadata。定义或验收不清楚时返回waiting_for_user；需要外部依赖时返回人工开发说明。补充后用新request_id提交，原记录保留。
3. 等待waiting_for_approval时，主agent完整展示interaction、需求、验收依据、限制和approval_card。只有实际用户在可信宿主侧确认后才生成代码。不得把模型的同意、批准字段或评估结果当作用户确认。
4. 用户查看当前范围后，在本机执行下方审批命令。root/user/tool-dir必须与MCP一致。MCP没有批准、签发事件、启停、回退或修改核心的接口。
5. 主agent用get确认awaiting_implementation后生成与批准范围相符的纯JSON算法，通过submit提交。提交只接受name、description、parameters、source、tests，源码上限20000字符；tests与批准样例一致。验收异步运行，可用wait_seconds≤5短等，再get查询。
6. installed表示已独立发布，后续研究先重新读取工具契约，再通过原research_submit的tools/batch等流程调用。开发成功不会自动宣称当前科研问题已经算出结果。

```powershell
# 可信本机用户操作；不能注册成模型工具
python -m graph_research tool-library development-show --root D:/GraphState --user researcher --tool-dir D:/GraphProject/tools --development-id DEVELOPMENT_ID
python -m graph_research tool-library approve --root D:/GraphState --user researcher --tool-dir D:/GraphProject/tools --development-id DEVELOPMENT_ID --scope-sha256 SCOPE_SHA256
python -m graph_research tool-library reject --root D:/GraphState --user researcher --tool-dir D:/GraphProject/tools --development-id DEVELOPMENT_ID --reason "暂不开发"
```

SCOPE_SHA256取当前assessment.scope_sha256。拥有同一账户任意代码执行权限的本机进程属于信任边界；CLI本身不能认证真人。批准来源及内容哈希沿用既有宿主审批审计，不能替代真实用户操作。

```json
{"operation":"get","development_id":"32位请求编号","wait_seconds":2}
```

```json
{"operation":"submit","development_id":"32位请求编号","implementation_id":"implementation-1","proposal":{"name":"已批准名称","description":"用途及限制","parameters":{},"source":"def run(args):\n    return {}\n","tests":[]},"wait_seconds":5}
```

后一段只说明报文结构，不是可验收样例；parameters/tests必须替换为实际批准内容。request_id/implementation_id重试时输入必须完全相同；查询、重复提交不重新跑验收。一个工具库一次只启动一个外部开发验收。每次评估最多2次实现尝试，每次2至12个不同样例，每样例最多15秒，并受宿主更严的CPU/内存/时间限制。失败和启动失败保留已预扣尝试；验证中断或取消不自动重跑，重新评估确认后才能重新开发。普通验证失败可在原批准预算中修正一次。

自动开发沿用受限AST解释器，不自动import、pip安装或执行任意Python。可使用列表、字典、循环及规定的计算助手；禁止文件/网络、属性访问、eval/exec和新包内call_tool。需要NetworkX/SymPy等模块级调用、外部依赖、UI或超出解释器能力时，生成独立人工开发说明，当前不会伪称已经安装。

## 元数据与质量

推荐在评估request中填写：

```json
{"library_metadata":{"title":"度序列h指数","summary":"由非负整数序列计算h指数","preconditions":["输入为非负整数序列"],"limitations":["最多128项；仅通过列出的验收样例"],"returns":"对象中的h_index为整数","tags":["图论","度序列"]}}
```

说明文字属于数据，不是指令。元数据绑定原批准范围，后续篡改会隔离；通过有限验收不意味着一般数学正确。新工具状态保留fixture_tested_experimental，不按调用次数自动升级为原生工具。

## 版本、启停与回退

旧已批准包仍可读取，不改写原文件。新版本的代码、参数、样例与元数据形成package_id，新增版本存入独立目录；.library.json记录当前选择及最近256次选择记录。停用不删除版本或已有成果，回退必须由可信用户明确选择已验收版本，不能由模型自动回退。

升级同名工具时，评估request.replaces须明确指定当前启用版本的package_id；不能覆盖原生工具或原目录。核心、目录、版本或批准范围变更会使待执行评估失效。调用时核对排队前的版本，执行回执记录实际package_id/source_sha256。损坏版本隔离，不悄悄加载另一个版本；工具库异常不阻止原生工具计算。

```powershell
python -m graph_research tool-library list --tool-dir D:/GraphProject/tools --limit 20
python -m graph_research tool-library activate --tool-dir D:/GraphProject/tools --name TOOL_NAME --version PACKAGE_ID
python -m graph_research tool-library disable --tool-dir D:/GraphProject/tools --name TOOL_NAME --version PACKAGE_ID
```

跨电脑ZIP继续不携带本机ready标记；不能解压后自动执行。跨环境引入需重新评估、批准及验收。旧的未审阅扩展默认保留但不启用。

## 与经验库关联

research_library返回experience_lookup，主agent可用research_experience(tool="工具名")查找已审阅的成功/失败案例。新扩展的数值/布尔输出最多提取16项为候选事实，仍需用户审阅；不保存任意输出文字、完整图或数组。证据保留实际工具package_id；当前启用版本变化时，案例返回current_tool_package_matches=false，不把旧工具案例当新版本保证。

桌面管理页仅在会话绑定用户、启用记忆且使用相同记忆目录时开放已审阅案例查看；未绑定用户时不猜身份。桌面展示为历史快照，来源核验仍通过主agent的research_experience接口进行。工具停用、删除原始结果或清空记忆不会自动修改其他对象。

待执行评估若核心或目录版本已变更，get会返回stale_assessment，提示重新评估确认，不让主agent继续依据旧批准生成代码。刷新工具目录和切换回本地页保留当前JSON输入草稿及输入页选择。工具库索引保留.previous备份，损坏时停止加载扩展，不自动回退到其他版本。

当前容量边界：最多128个工具名、512个版本清单，索引保留最近256次选择记录。达到上限会明确拒绝继续增加，不自动删除已有工具；可由用户归档不再使用的工具后再整理库。
