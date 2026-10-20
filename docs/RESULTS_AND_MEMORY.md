# 成果管理与用户记忆

## 查看与导出一轮研究

本地工具和 API 对话将多次计算保留在同一会话中。“导出结果包”保存截至导出时的会话成果，包括输入、计算记录、结构化数据和已登记的图片/TeX等附件。后来继续计算，需要重新导出才能包含新增结果。

结果页可看概览、表格、图形与原始数据。MCP用 `research_get` 查看任务摘要，`research_inspect_result` 分字段读取完整结果，`research_read_artifact` 读取已核验附件；不能把摘要截断当作数据缺失。

终端对话可用 `/查看` 打开结果页、`/导出` 再打包，不调用模型。结果包的范围、清单与校验值决定实际内容；导出失败和数学计算失败分别报告，不能仅因ZIP不存在就否定已完成计算。

## 成果中心与清理

顶部“成果 → 成果中心”统一管理会话/任务结果，支持课题、备注、快照、保留标记、清理预览及回收区恢复。实际根目录以窗口显示为准；MCP可用 `--results-root D:/Research/results` 显式指定。

建议把正在研究的结果按课题归类并标记保留，关键结论保存快照并另做备份。先看清理预览再确认；运行中、等待用户或审批中的任务不能清理。回收恢复不会重新计算，也不会重置预算；永久清理后仍保留最小任务状态，不能借旧request_id重新运行。

稳定的result_id/artifact_id用于任务关联，附件按SHA256核验；不要在运行期间手工移动内部文件。只复制程序源码不会带走研究数据，换电脑需另行导出需要的成果、图对象和扩展库，并重新配置路径。

## 用户偏好与使用习惯

为同一个用户使用稳定的 `--user` 标识，并指向同一记忆目录。记录明确的语言、详略、图片格式、布局与标签偏好，以及工具成功使用次数。不会从频次推断α、权重、容差等科学参数；当前请求优先于历史偏好。

记忆使用本机SQLite，默认在账户主目录的 `.graph_research/user_memory/memory.sqlite3`。可用 `--memory-dir` 选择目录。不指定用户时默认不启用记忆；用户标识用于本地分区，不是登录认证，也没有自动云同步。

```powershell
python -m graph_research memory show --user researcher
python -m graph_research memory set language zh-CN --user researcher
python -m graph_research memory set figure_format svg --user researcher
python -m graph_research memory forget figure_format --user researcher
python -m graph_research memory disable --user researcher
python -m graph_research memory enable --user researcher
```

当前会话可用 `--no-memory` 停止读取和积累。`memory clear --user researcher` 清空该用户的偏好、频次、经验与去重记录，保留启用选择；不删除会话、成果和审批记录。

对话仅识别完整、明确的记忆表达，例如“记住：以后用中文回答”“记住：以后默认导出SVG”。一次任务的临时选择不自动变为永久偏好。不能把自动批准、增加预算等规则写入偏好。

## 经审阅的科研经验

经验候选从可核验的执行记录提取，审阅后才作为后续任务的历史参考。查询时核对来源、版本、适用条件和已有证据；历史案例不能代替本次计算，也不是一般数学证明。这是记录与检索，不是训练或更新模型权重。

MCP 的 `research_memory` 和 `research_experience` 只读。审阅与遗忘由可信本机用户操作，主agent不能自行批准经验、选择他人身份或变更长期偏好。具体CLI选项可运行 `python -m graph_research experience --help`。

读取与管理记忆不调用模型；API任务附带的记忆文本会占该请求上下文。偏好库不保存原始问题、图数据或密钥；会话本身仍保存研究输入与结果，二者需分别管理。
