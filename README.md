# 代数图论科研助手

用同一套计算工具构造图与超图、计算谱和多项式、绘制论文插图，或在有限预算内搜索候选与反例。可在 Windows 桌面直接操作，也可从 Python 或主 agent 调用。数值观察和有限搜索的结果不能代替一般性证明。

**首次使用：** 从 [v0.38.0a11 发布页](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.38.0a11) 下载源码 ZIP，按[中文安装指南](使用指南.md#new-pc-setup)或 [English user guide](docs/QUICKSTART.md) 配置环境。验证安装后，双击 `start-desktop.cmd`，打开“本地工具”计算 5 个顶点的路径图：应得到 4 条边、直径 4。此例不需要模型 API。

## 选择入口

| 想做什么 | 从哪里开始 |
| --- | --- |
| 自己输入图、计算指标或导出论文插图 | 桌面“本地工具”；见[图输入与绘图](docs/GRAPHICS.md) |
| 用自然语言安排计算，查看计划与结果 | 桌面“科研对话”；先[配置模型](docs/API.md)，需要多步研究时启用[科研实验](docs/RESEARCH_PLANNING.md) |
| 让自己的主 agent 提交计算 | [MCP 接入](docs/MCP.md)；固定工具与规则搜索无需另配助手模型 |
| 用 Python 调用函数或做有限搜索 | [Python 接口](docs/reference/PYTHON_API.md)；多案例用[批量任务](docs/BATCH.md)，比较或搜索候选用[通用实验](docs/EXPERIMENTS.md) |

桌面、科研对话和 MCP 共用 47 个内置计算工具；MCP 另提供 13 个调度接口。各工具的数学条件和规模限制见[功能与边界](docs/FEATURES.md)，其他专题见[文档目录](docs/README.md)。

## 维护与本机文件

| 需要做什么 | 位置 |
| --- | --- |
| 修改代码、运行检查 | `graph_research/` 放程序，`tests/` 放回归测试，`tools/` 放维护脚本；从[开发说明](docs/DEVELOPMENT.md)和[贡献指南](CONTRIBUTING.md)开始 |
| 核对交付内容或验收 | [当前版本与验证记录](docs/releases/CURRENT.md)及[随源码提供的本地验收任务书](docs/reference/LOCAL_ACCEPTANCE.md)；维护工作区的本地发布索引在 `dist/README.md` |
| 找到或导出研究结果 | 在桌面打开“成果中心”，见[成果与记忆](docs/RESULTS_AND_MEMORY.md)；维护工作区的本机记录索引是 `outputs/README.md` |

根目录的启动器、命令脚本、`assistant.py` 与 `test_workflow.py` 均有固定用途。调整这些入口时需同步核对发布清单、测试分组及对应文档；运行环境、工具包和带回执的任务目录保留在原位。

项目采用 [Apache-2.0](LICENSE)；署名、授权和历史来源见 [NOTICE](NOTICE.md)、[授权记录](LICENSE-STATUS.md)与[源码迁移记录](docs/provenance/README.md)。
