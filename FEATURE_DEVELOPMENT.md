# 用户确认后的独立功能扩展（v0.10）

本版将功能增加分成：现有工具复用、需求澄清、缺口分析、消耗评估、宿主用户确认、受限算法生成、验收和独立封包。新功能不会自动写进原有数学包。

## 一次完整交互

1. 用户提出目标。能用已有工具联动、整理结果或简单算术完成时，直接继续会话，不保存新工具。
2. 缺少输入、数学定义、约束、规模或验收标准时，模型提出1至3个具体问题；状态为`awaiting_clarification`，停止并等待回复。
3. 真缺算法时，提交评估：需求、核对过的工具及不足、新算法步骤、输入Schema、至少两个有依据的验收样例和复杂度。此阶段不生成源码。
4. 宿主生成评估卡：预计后续调用量、token范围、时间范围、测试预算及可选金额，状态为`awaiting_approval`。未经用户确认，不调用模型生成代码，也不跑开发测试。
5. 用户可以批准、拒绝或修改需求。批准只绑定当前评估的名称、输入约定、验收样例及预算；修改范围要重新评估确认。
6. 批准后生成纯JSON算法，在独立Python进程中验收；通过后封包并登记为`fixture_tested_experimental`，再供后续调用。失败不会冒充可用工具。

模型返回`approved:true`或伪造approval字段不能批准。批准由宿主API/CLI完成，不在模型计算工具中。评估/审批记录保存在会话目录，重启后仍能恢复；核心包或工具目录变化会使尚未执行的评估失效。

按用户记忆仅保存展示偏好和成功工具频次，不能记住“以后默认同意开发”或代替本次审批。清空记忆不会删除审批审计；详见[用户记忆](USER_MEMORY.md)。

## CLI操作

```powershell
python -m graph_research ask "我希望增加一个图论计算功能"

# 根据模型的问题补充需求：
python -m graph_research resume "会话目录" --reply "输入、数学定义、输出及规模要求"

# 阅读评估卡后，由用户明确指定评估ID：
python -m graph_research resume "会话目录" --approve 评估ID
python -m graph_research resume "会话目录" --reject 评估ID

# 对评估有修改意见，重新澄清和评估，不能视为批准：
python -m graph_research resume "会话目录" --reply "请改变输出形式，另做一份评估"

# 网络中断后在剩余预算内继续，已完成节点及审批记录保留：
python -m graph_research resume "会话目录" --continue
```

拒绝不需要模型密钥，不会继续消耗模型调用。旧`extend source-proposal.json`直接安装入口已关闭；现在`extend requirements.json`只准备需求评估，仍要用`resume --approve`确认后才开发。旧版会话记录可读取；已有旧扩展保留并标为`legacy_unreviewed`，不会自动删除或升级。

## Python宿主接入

```python
from graph_research.assistant import ResearchSession, ConfiguredModel

model = ConfiguredModel()  # 密钥仅在本机环境变量配置
session = ResearchSession('outputs/my-session', 'tool_packages')
state = session.ask('用户的研究需求', model)

# UI显示state['questions']，用户提交答案后：
state = session.reply('用户实际补充的需求', model)

# UI显示state['assessment']及消耗；只有用户点击确认按钮才调用：
state = session.approve(state['assessment_id'], model)
# 用户拒绝时：session.reject(state['assessment_id'])，不再调用model。
```

这几行分别代表不同的用户交互事件，不能在生产中看到`awaiting_approval`就自动调用`approve`。`ResearchSession`逐节点保存状态；模型响应不能修改宿主审批记录。

## 消耗估计与边界

- 小任务最多4次、一般任务最多6次批准后的模型调用尝试，包含代码生成、重试及后续结果整理；开发尝试最多2次。
- 每个开发版本用批准的2至12项样例验收，每项15秒超时，单次解释执行50000指令预算，源码最多20000字符。
- token估计结合工具目录、需求和当前上下文的文本规模；时间包含模型与测试的保守估计。它们是启发式范围，不是服务商的计费/时长保证。
- 未配置模型单价时，金额明确为未知。可以在`ask --pricing 本机价格.json`提供`input_per_million`、`output_per_million`和`currency`，按你所选模型的实际单价计算区间；不内置或猜测市场价格。
- 澄清/评估本身已发生的模型使用不包含在“批准后的开发”估算内。审计记录中的`model_calls_used`表示调用尝试数，不是服务商账单tokens。
- 预算用尽会停止，不能偷偷增加重试或调用次数。继续开发应重新评估确认。

## 如何保护原包

新扩展存放在原包目录之外，目录构造会拒绝指向`graph_research`内部。模型源码只能由AST解释器运行，不允许导入、属性访问、文件/网络操作、eval/exec。验收前后核对原包源码和资源哈希；名称不能覆盖原工具。

通过验收的每个扩展单独保存：

```text
tool_packages/新算法名/
  tool.py             # 仅供受限解释器执行，不自动import
  tool.json           # 接口、源码校验值、验收结果与审批关联
  assessment.json     # 需求、缺口、资源评估
  approval.json       # 批准范围及记录
  tests.json          # 实际验收结果
  README.md
  ready.json          # 本机发布完成标记
tool_packages/新算法名.zip
```

失败的准备目录不会被自动加载；ZIP是独立交付物，故意不携带本机自动启用标记，跨环境导入需要重新审批。新的包不修改原库，不自动pip安装，也不自动获得任意Python权限。

## 工具联动与新算法的区别

例如“图结构 → 谱 → TikZ”直接分步调用原工具；图密度可由已有顶点数、边数算出，不新增密度包装包。

真正的新算法可接收旧工具的结果作为JSON输入。例如先用`graph_invariants`得到度序列，再由独立的新算法计算某个原工具没有提供的不变量。新包内禁止`call_tool`，从架构上把编排留在会话层。

是否存在数学上的能力缺口仍需要模型分析与用户审阅；系统不能证明任意程序的语义新颖性，也不能凭有限验收样例证明一般正确性。自动开发目前只覆盖受限纯计算算法；需要新依赖、UI或不受限Python执行的功能应转人工开发，不能伪称已自动实现。

`examples/governed_extension_demo.py`提供离线演示；不使用真实模型，默认只到评估，`--simulate-approval`才模拟用户确认。该选项用于测试，不能替代生产用户确认。

## 持久工具库与主agent开发（v0.35）

新增工具跨会话复用、中文元数据、版本并存及可信用户启停/回退见[TOOL_LIBRARY.md](TOOL_LIBRARY.md)。同名升级需在评估中给出replaces当前package_id，独立保存新版本，不覆盖原生工具。核心/目录指纹现包含扩展版本；验收证据保留保护后端、环境及请求/结果哈希。

主agent可通过MCP的research_development申请并提交开发，无需助手内部模型；由--allow-development显式启用，真实用户确认和受限验收保留。宿主模型消耗由宿主控制，本服务不计量外部模型token或费用。本机验收尝试和预算单独记录，重试/中断不能重置。旧独立API模式保持原审批流程。
