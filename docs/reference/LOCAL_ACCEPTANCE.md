# 在新目录验收科研助手

这份任务书适用于当前源码包和维护工作树。请在项目根目录运行；源码包不需要包含作者的测试输出或旧运行环境。先按[安装指南](../../使用指南.md)准备环境。复现已发布版本时，使用与该版本一起发布的任务书和校验清单。

## 1. 确认运行的是这一份代码

在 Windows PowerShell 中执行：

```powershell
$Py = (Resolve-Path .venv/Scripts/python.exe).Path
& $Py -X utf8 -m graph_research doctor
& $Py -X utf8 -m graph_research protect check
```

使用其他虚拟环境时，将 `$Py` 指向该环境的解释器。核对版本、源码位置和核心完整性；不一致就记录并停止，不以旧版本的通过记录代替本次检查。

## 2. 检查用户实际能做的事

| 范围 | 操作与判定 |
| --- | --- |
| 桌面和离线计算 | 打开 `start-desktop.cmd`，进入本地工具，计算五个顶点的路图的图不变量。无需密钥；直径应为 4。 |
| 输入示例 | 从 `examples/offline-inputs/` 选一个与工具同名的 JSON 导入。核对界面显示的输入和计算结果，再试一个无效输入，确认能看出错在哪个字段。 |
| MCP（交付范围包含时） | 按 [MCP 接入](../MCP.md)连接，查询工具目录、提交一项小计算，用原任务编号查询结果。记录工具实际执行结果和任务状态。 |
| 研究流程或 CEM（交付范围包含时） | 按[实验说明](../EXPERIMENTS.md)选择小规模示例，记录候选、预算、独立核验结果。测试 CEM 需要另装 CPU PyTorch；只运行普通搜索不能算作 CEM 已验收。 |

使用新任务和合成输入，不复用正在进行的科研任务。桌面不能启动、缺少可选依赖或未连接 MCP，均记录为未验项目。

## 3. 维护者检查交付内容

在已装好开发依赖的环境中运行。第一条检查源码包和文档链接；第二条从训练和计算工具的实际输入定义重建预期值，核对手册及示例：

```powershell
& $Py -X utf8 -m unittest tests.test_release_candidate
& $Py -X utf8 tools/check_generated.py
```

正式发布前，按[开发维护说明](../DEVELOPMENT.md)准备锁定环境，在新的报告目录运行完整检查：

```powershell
$Report = Join-Path 'outputs/checks' ('release-' + [guid]::NewGuid().ToString('N'))
& $Py -X utf8 tools/checks.py --full --strict-lock --report-dir $Report
```

查看报告中的 `checks-summary.json` 和逐项结果，分别写明通过、失败、环境阻断及未执行的检查，并附失败步骤和原始错误。发布时的验证数字见[版本记录](../releases/CURRENT.md)，它们只对应当时的包。
