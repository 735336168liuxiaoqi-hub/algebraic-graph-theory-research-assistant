# 对话计算结果包（v0.29）

一次对话内可以反复提问、计算、出图及消元。每次宿主执行结束，默认保存包含截至当时整次对话的结果ZIP；也可保存独立快照或只导出指定一轮。公共用户入口现统一使用[成果中心](RESULTS_CENTER.md)的短目录。打包不调用模型、不重新计算，不新增计算工具，不改变数学定义。

## 打开结果

CLI会在回答后打印结果包路径。现在可在无API模式输入`v`、模型对话输入`/查看`直接打开[新版结果页](RESULT_DISPLAY.md)；也可将ZIP完整解压到新目录，再打开`report.html`：

| 文件 | 用途 |
| --- | --- |
| `report.html` | 浏览器可离线阅读，按轮次显示请求、回答、计算和图表 |
| `report.md` | 可长期保存的文字报告 |
| `results.json` | 所有选中轮次的完整参数、原始结果、失败记录和执行版本 |
| `calculations.csv` | 每次计算的索引，以及参数、结果文件的相对位置 |
| `calls/calc-编号/` | 单次计算参数、结果或错误，以及可用的执行回执 |
| `artifacts/` | 实际生成的PNG、SVG、TikZ及布局编辑器等科研文件 |
| `reproduce.json` | 人工复核后可用于重算的工具名称、参数、版本和扩展源码哈希；不会自行执行 |
| `manifest.json` | 包内各文件的大小及SHA256清单 |

矩阵、向量和多项式按原工具返回值保留，不为了报告展示统一舍入；精确有理数和符号表达式仍保留字符串形式。CSV是计算索引，完整数学数据保存在JSON中。

附件路径转换为包内相对路径，复制ZIP到另一台电脑后仍可阅读。阅读报告不需要模型、Sage或科研计算库。重新计算则需要相应Python工具及兼容版本；实验性工具的源码包继续独立保存，不与研究结果包混装。

## 轮次与范围

每条`ask`或`reply`用户消息记为一轮，包括澄清补充；本轮可包含多次工具调用。`approve`、`reject`与中断后的`continue`属于当前轮，不新增用户请求轮次。继续执行不会重复收录已经保存的计算。

默认结果包汇总整个会话。手动快照始终独立保留。成果中心托管的自动包内容相同则复用，新累计包核验后会删除未被宿主回执引用的旧自动ZIP；原始请求、回答与计算回执仍保留。直接Python库调用未设置results_directory时仍采用旧版独立包规则。

```powershell
# 导出整次会话，不需要模型密钥：
python -m graph_research export "outputs/你的会话目录" --output "outputs/本次研究结果.zip"

# 只导出第2条用户请求及该轮的多次计算：
python -m graph_research export "outputs/你的会话目录" --turn 2 --output "outputs/第2轮结果.zip"

# 核验ZIP及其中的文件：
python -m graph_research verify-results "outputs/本次研究结果.zip" --sha256 "导出时记录的64位SHA256"
```

不指定`--output`时，受管理会话保存到成果中心指定目录；旧版未托管会话仍保存到`会话目录/exports/results_轮次数_随机标识.zip`。旁边提供`.zip.sha256`文件（导入旧包时可能只有已登记摘要）。已有同名输出不覆盖；基础包目录禁止写入。导出和验证不自动解压、运行、安装或恢复任何代码。

## “可靠”如何检查

新计算的宿主回执记录实际工具身份、基础包清单哈希、Python和依赖版本、执行时间、请求与原始结果文件哈希，以及生成附件的哈希。打包时验证：

1. 工具名和输入参数与实际执行请求相同。
2. 保存的结果与受限进程返回的完整结果相同。
3. 附件在本会话任务目录内，且大小、哈希与计算结束时的记录相同。
4. ZIP完成后再次检查文件清单与各成员哈希，通过后原子发布。

`verify-results`只读取和检查，拒绝越界文件名、重复名称、链接及超量文件。SHA256若没有可信的外部记录，只能核验包内部一致性，不能证明发行者身份；文件完整性与执行记录也不构成数学证明。模型回答和实际工具结果在报告中分开保留。

## 失败、取消与缺失附件

计算失败、取消、网络中断或尚待澄清/确认时仍可保存结果快照。报告明确标为`partial`，保留已经完成的计算，不把失败或未完成任务当成成功结果。仅模型分析而无计算的轮次标为`analysis_only`；旧轮次成功不会使新的空计算轮次冒充“本轮已计算”。

附件被删改、执行回执不一致时，默认停止打包，CLI显示具体原因；计算本身与已有快照仍保留，也不会将旧包标为本轮最新结果。需要接受缺失内容时明确选择：

```powershell
python -m graph_research export "outputs/你的会话目录" --allow-incomplete --output "outputs/部分结果.zip"
```

降级导出会在报告和JSON中注明未收录附件及验证问题，不会把它们标成已通过验证。新的或并发发生的附件变化会中止快照发布。

## Python应用接入

```python
from graph_research.assistant import ResearchSession, verify_bundle

session = ResearchSession('outputs/my-session', 'tool_packages')
state = session.ask('研究需求', model)
print(session.result_bundle)  # 自动生成的ZIP、SHA256、统计

state = session.reply('下一项计算需求', model)
all_results = session.export_results('outputs/whole-conversation.zip')
one_turn = session.export_results('outputs/turn-2.zip', turn=2)
verify_bundle(all_results['archive'], all_results['sha256'])
```

如需减少大规模对话反复打包的磁盘占用，可在创建/恢复会话时指定`auto_export=False`，需要时手工调用`export_results`；这不会关闭逐节点计算记录。成果中心的自动保留策略只删除可替代的旧自动ZIP；手动快照、被回执引用的版本及原始科学证据保留。当前单包限制为1000次计算、4096个成员、256MiB未压缩总量、单文件64MiB，超限时可按轮导出。

旧版会话缺少轮次边界和计算时的哈希回执，会作为明确标记的历史分组保存，不猜测轮次、不伪造原始执行版本。新增请求开始按新规则记录。缺少原始执行证明的旧数据标为`legacy_record`，与新记录的`verified_execution`区分。

结果包包含所选轮次的研究问题和实际计算数据，默认不复制用户记忆库、密钥、宿主配置、模型内部决策、扩展源码或可生效的审批文件。

## 离线示例

```powershell
python examples/results_bundle_demo.py
python -m unittest tests.test_results -v
```

示例包含三轮五次计算：P3结构和邻接谱、C4绘图与TikZ、一条三元超边的精确张量特征多项式；生成整个对话包、单轮包及可直接查看的HTML预览。不连接真实模型。
