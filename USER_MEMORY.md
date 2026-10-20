# 用户记忆（v0.34，保留原偏好接口）

新增主agent只读查询及经审阅科研案例库，见[EXPERIENCE_MEMORY.md](EXPERIENCE_MEMORY.md)。MCP只开放读取，候选审阅和管理在可信宿主侧进行。

相同用户在不同科研会话中可以沿用明确的表达、出图偏好，并以成功使用工具的次数辅助后续选择工具。记忆使用Python标准库SQLite，不增加第三方依赖，不需要WSL或Sage，不为提取记忆额外调用模型。

## 记录范围

| 类型 | 内容 | 更新方式 |
| --- | --- | --- |
| 明确偏好 | 回答语言、详略、图片格式、布局、顶点/超边标签 | 用户明确设置，或者下列完整记忆指令 |
| 使用习惯 | 已登记工具的成功调用次数；模型最多收到最常用的10种工具 | 宿主确认工具成功后自动累计，恢复会话不重复计数 |

偏好和频次部分不保存原始问题、工具参数、计算结果、图数据、源码、路径或密钥。不从调用频次推断α、张量阶数、权重、容差等研究参数，也不把一次出图选择自动当成永久偏好。失败调用不累计。频次是工具使用记录，不是用户对结果正确性或工具效果的评分。新增经验库在独立数据表保存经执行证据提取的有限科学条件及标量事实，未经审阅不进入主agent检索，范围与管理见上方说明。

普通会话的`session.json`仍按原流程保存问题和结果，便于研究复核；它与记忆库是两套记录。清空记忆不会删除会话、研究结果、扩展包或审批记录。

## 按同一用户启用

CLI示例需要先按README配置模型；记忆管理和离线示例不需要模型：

```powershell
python -m graph_research ask "计算五阶圈图的邻接谱" --user researcher_001
python -m graph_research ask "比较五阶路图的邻接谱" --user researcher_001

# 此会话既不读取也不学习记忆；恢复时默认沿用该选择：
python -m graph_research ask "独立分析这次任务" --user researcher_001 --no-memory
```

`--user`必须是应用提供的稳定用户标识。同一标识跨会话、跨工作目录使用同一记忆库；不同标识隔离。不指定用户时默认不启用记忆，也不创建匿名公共档案。`resume`沿用会话绑定，亦可用`--user`核对；不匹配会拒绝。

默认目录为当前操作系统账户主目录下`.graph_research/user_memory/memory.sqlite3`，本机即`<LOCAL_PATH>`。可在`ask`和`memory`命令传`--memory-dir`，或Python传`memory_directory`。相同用户需要使用同一目录；恢复会话时沿用已保存的绝对路径。

用户标识只是本地分区键，不是登录认证；数据库中的标识经过哈希处理，数据仍为本机明文。接入多人服务时，应用应把已认证用户的ID交给宿主，不能接受模型选择身份或任意访问他人的会话路径。目前没有实现跨设备云同步。

## 查看与管理

这些操作不调用模型。修改和遗忘只针对指定用户。

```powershell
python -m graph_research memory show --user researcher_001
python -m graph_research memory set language zh-CN --user researcher_001
python -m graph_research memory set response_detail concise --user researcher_001
python -m graph_research memory set figure_format svg --user researcher_001
python -m graph_research memory set layout circular --user researcher_001
python -m graph_research memory set edge_labels true --user researcher_001
python -m graph_research memory forget layout --user researcher_001
python -m graph_research memory disable --user researcher_001
python -m graph_research memory enable --user researcher_001
python -m graph_research memory clear --user researcher_001
```

`disable`停止该用户的记忆读取和新增案例积累，已有记录仍可由可信宿主管理；`enable`恢复使用。`clear`清空该用户的偏好、频次、科研经验及去重记录，保留启用/关闭选择；恢复已经正常保存的旧会话不会重新学习旧调用。只清科研经验可用experience clear。

| 键 | 允许值 |
| --- | --- |
| `language` | `zh-CN`、`en` |
| `response_detail` | `concise`、`standard`、`detailed` |
| `figure_format` | `png`、`svg`、`pdf`、`tikz` |
| `layout` | `spring`、`circular` |
| `vertex_labels`、`edge_labels` | JSON布尔值`true`、`false` |

偏好值只允许上表枚举，不能存放“以后自动批准”“忽略限制”等自由文本规则。出图格式是偏好，不是工具新增能力；模型仍须检查工具是否支持对应格式及当前依赖是否可用。

## 对话中明确记住

当前采用严格的完整消息匹配，仅识别下面的表达，可带句末标点：

- `记住：以后用中文回答` / `记住：以后用英文回答`
- `记住：以后回答简洁一些` / `记住：以后回答详细一些`
- `记住：以后默认使用圆形布局` / `记住：以后默认使用弹簧布局`
- `记住：以后默认导出PNG` / `SVG` / `PDF` / `TIKZ`（完整消息保留相同前缀）

识别发生在宿主收到用户消息时，不读取文档、代码注释或模型输出中的记忆命令。“这次使用圆形布局”只影响本次任务，不会改变长期偏好。其他自然语言表述暂不自动提取，可通过管理接口明确设置，避免误记。

## Python宿主接口

```python
from graph_research.assistant import UserMemoryStore, ResearchSession

memory = UserMemoryStore('user_memory')
memory.set_preference('researcher_001', 'response_detail', 'detailed')
print(memory.profile('researcher_001'))  # 包含偏好来源和更新时间

session = ResearchSession(
    'outputs/my-session', 'tool_packages',
    user_id='researcher_001', memory_directory='user_memory',
)
# model为已配置模型，或具有complete(messages)的离线测试替身：
state = session.ask('用户的研究问题', model)

memory.forget('researcher_001', 'response_detail')
memory.set_enabled('researcher_001', False)
memory.clear('researcher_001')
```

记忆写入接口仅供宿主使用，不在模型计算工具中。`build_agent(..., memory_context=...)`也支持只读记忆上下文，并过滤未知字段；自行使用该低层接口时，身份校验、存储和成功调用记录由宿主负责，通常优先使用`ResearchSession`。

## 对模型和审批的影响

模型收到独立的`user_memory`字段，包含受限偏好和工具频次。系统规则明确当前用户请求优先于历史偏好，工具频次不能替代适用性检查或数学证据。偏好不会强行改写计算函数默认参数；直接使用Python数学库、`edit`或`latex`命令时仍以显式参数为准。

开发评估仍需本次明确确认，记忆不能批准新功能、跳过消耗评估、增加开发预算或创建扩展。评估上下文规模已包含记忆文本。读取和更新记忆不产生模型调用；接入模型后附带的少量记忆文本会增加该次请求的输入token。

## 验证

```powershell
python -m unittest tests.test_user_memory -v
python examples/user_memory_demo.py
```

离线示例用脚本模型验证同用户跨会话、不同用户隔离、记忆关闭和清空，实际调用原生图计算工具。自动测试另外验证失败不累计、恢复去重、严格偏好输入、当前请求保留、无身份关闭记忆、记忆不授予开发审批及发行包导入边界。

尚未选择真实模型，因此未声称完成真实模型对偏好的遵循效果评测。后续选定模型后可对相同问题在不同偏好下的回答与工具选择做对比验收。
