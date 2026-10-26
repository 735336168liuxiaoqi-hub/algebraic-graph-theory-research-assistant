# 代数图论科研助手

**Algebraic Graph Theory Research Assistant** · 预发布 **0.38.0a2** · [Apache-2.0](LICENSE) · [English user guide](docs/QUICKSTART.md)

面向图与超图科研的Python计算工具、桌面应用和MCP服务。支持谱与符号计算、鼠标绘图、论文图形导出，以及有限预算内的科研搜索。可以独立使用，也可以接入主agent。无需Java、SageMath或WSL；完整桌面和受保护执行目前在Windows验证。

本地开发版 **0.38.0a10** 沿用预算内直接执行和可选初审／反馈，修正失败后的逐步覆盖与交付核验，并将一致超图邻接／α张量谱接入有限实验搜索。普通任务无批准状态，也不创建事件签名存储。资源保护、多代训练、完整候选证据和必要的真实用户确认保留；当前Release仍为a2，尚未发布本地改动。配置见[MCP](docs/MCP.md#默认自主执行)和[通用实验](docs/EXPERIMENTS.md)。

## 下载与安装

| 下载方式 | 版本与用途 |
| --- | --- |
| [v0.38.0a2最新修复版（推荐）](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.38.0a2) | 包含最新修复的源码ZIP、wheel、中英文安装指南、验收任务书和校验清单；旧Release已下架 |
| [main分支源码ZIP](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/archive/refs/heads/main.zip) | 后续开发源码，可能继续更新；使用时核对版本及核心指纹 |

仓库当前为私有，需要获授权的GitHub账号。空电脑先按[新电脑安装步骤](使用指南.md#new-pc-setup)下载并安装64位Python 3.13，再解压完整源码ZIP，在包含`pyproject.toml`的目录打开PowerShell：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[all]"
.\.venv\Scripts\python.exe -m graph_research doctor
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m graph_research protect check
.\.venv\Scripts\python.exe -m graph_research desktop
```

首次安装需联网下载依赖，不要求安装Git。以后可双击`start-desktop.cmd`；同目录`.exe`也是使用Python环境的启动器，需要保留整个项目目录。已有Conda/venv、wheel安装、升级和换电脑见[使用指南](使用指南.md)。CEM另需可选CPU PyTorch，安装与导入检查见[CPU配置步骤](使用指南.md#cpu-cem-setup)；`[all]`不强制安装它。

## 选择使用方式

| 入口 | 适合的任务 | 模型要求 |
| --- | --- | --- |
| 桌面本地工具 | 选择函数、填参数、查看结果、绘图和导出 | 无需API |
| 桌面科研对话 | 自然语言澄清、组合工具、正式计划和反馈 | 配置兼容模型服务 |
| MCP子agent | 主agent理解需求，本服务负责计算、核验和结果交付 | 固定工具和规则实验无需本助手另配API |

桌面顶部“语言 / Language”可切换简体中文与English。三种入口共用**47个内置计算工具**；桌面将绘图、布局和LaTeX操作放在对应图旁。MCP对外提供13个调度／集成入口，按需发现计算契约。

![三种模式与成果流程](docs/diagrams/workflow-overview.svg)

## 当前能力

| 领域 | 支持内容 |
| --- | --- |
| 普通图 | 构造、结构变换、不变量、同构与对称性、商矩阵、数值／精确谱、多项式、能量、带权和有向矩阵 |
| 超图 | 一般超图结构与距离、一致超图α谱及Perron向量、赋权关联矩阵、张量方程和有界精确消元 |
| 代数与组合 | 矩阵及分块、递推、整数线性方程、符号求和／级数、有限置换群、Cayley图、车多项式 |
| 图形 | 鼠标构图、拖动布局、保存坐标、PNG/SVG/PDF和TikZ、含不确定长度超路的论文示意图、整图标签和坐标显示 |
| 科研管理 | 批量步骤、结果包、成果清理与恢复、用户偏好、经审阅经验、审批后的独立扩展工具包 |
| 通用实验 | 有限候选评价、枚举／随机／局部搜索、可选CPU CEM、规则／模型调度、反馈微调、结构观察及明确假设的反驳 |

### 如何开始一次研究

普通计算直接使用已有工具；多案例／多步骤用[批量任务](docs/BATCH.md)。桌面“科研实验”开关使用[模型科研计划](docs/RESEARCH_PLANNING.md)。更复杂的有限搜索使用[通用实验工作流](docs/EXPERIMENTS.md)：

| 操作 | 用途 |
| --- | --- |
| `prepare` | 明确数学问题、建议参数实例和能力缺口；只准备草案，不执行计算 |
| `execute` | 预算内直接评价明确候选，可选一次初审 |
| `study` | 固定范围和预算内分段搜索、可选CEM、诊断及假设检验；反馈暂停可选 |

study可由规则提出初始参数实例，无需先给出所有数值；规则调度不需要API，内部模型调度可选。支持允许含环的一般／一致超图，超树是可选条件。当前study的超图指标为距离谱和超边数；已有张量工具另有一致性与核验要求。通用study目前通过CLI、Python和MCP使用，桌面专用表单尚未提供。

所有结果都有适用范围：数值观察、候选模式、有限扫描及“未找到反例”不能代替一般性证明。规模、预算、审批和可恢复边界见具体契约。完整Windows安装器、完整隐式三维绘图及自动TeX编译尚未提供。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [使用指南](使用指南.md) / [English guide](docs/QUICKSTART.md) | 安装、三种入口、首次计算、通用实验、升级及常见问题 |
| [功能与边界](docs/FEATURES.md) | 计算能力、数学条件和规模限制 |
| [通用实验](docs/EXPERIMENTS.md) | 搜索、CEM、规划、可信反馈、假设检验与可运行JSON例子 |
| [MCP接入](docs/MCP.md) | 连接主agent、工具预算、后台任务和用户交互 |
| [工作流程图](docs/WORKFLOW.md) | 三种入口、LangGraph计划与study闭环 |
| [专题目录](docs/README.md) | 图形、API、成果、记忆、扩展和Python接口 |
| [版本与验证](docs/releases/CURRENT.md) | 开发源码与历史Release的范围区别 |
| [贡献指南](CONTRIBUTING.md) | 开发检查、核心保护和提交流程 |

## 文件放在哪里

日常只需桌面启动入口、使用指南和需要时的测试任务书：

| 需要做什么 | 位置 |
| --- | --- |
| 启动程序 | 根目录`start-desktop.cmd`或同目录`.exe` |
| 安装及使用 | [使用指南](使用指南.md)，专题从[文档目录](docs/README.md)进入 |
| 交给主agent全面测试 | 本机`outputs/test-plans/全面测试-交给主agent.md` |
| 查结果、绘图与本机记录 | 本机`outputs/README.md`；正式成果在桌面“成果中心”管理 |
| 取已发布安装材料 | `dist/latest/`，与本地开发版分别核对版本 |
| 开发维护 | `graph_research/`源码、`tests/`回归、`tools/`维护脚本，见[开发说明](docs/DEVELOPMENT.md) |

历史验收、构建和临时探针集中在项目旁的“科研助手历史归档”，不混入当前使用材料；目录对照从outputs说明进入。`.venv`、`tool_packages`和带回执的任务目录由程序管理。

许可及来源见[LICENSE](LICENSE)、[NOTICE](NOTICE.md)和[授权记录](LICENSE-STATUS.md)。[源码迁移记录](docs/provenance/README.md)用于维护追溯；研究数据、密钥、虚拟环境及本地过程记录不随源码分发。
