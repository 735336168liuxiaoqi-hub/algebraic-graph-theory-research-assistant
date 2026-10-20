# 代数图论科研助手

**Algebraic Graph Theory Research Assistant** 面向图与超图的谱计算、符号分析和科研绘图。

当前为 **0.36.0rc4候选版，采用MIT许可证**。项目所有者已于2026-10-20确认原始代码公开授权，并明确选择MIT；保留原作者署名和源码迁移记录。参见[许可证](LICENSE)、[许可记录](LICENSE-STATUS.md)和[来源署名](NOTICE.md)。

仓库为private时，请先使用获授权GitHub账号登录，再下载附件。

## 下载并使用（Windows）

**推荐先下载[源码运行包 ZIP](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/algebraic-graph-theory-research-assistant-0.36.0rc4-source-candidate.zip)**。包内含桌面启动器和完整程序，需要电脑先装有64位Python 3.11或更高版本（建议3.13）。

| 下载 | 适合谁 | 安装方式 |
| --- | --- | --- |
| [源码运行包 ZIP（推荐）](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/algebraic-graph-theory-research-assistant-0.36.0rc4-source-candidate.zip) | 第一次使用、希望以后双击启动 | 解压后按下方三条命令安装 |
| [Python安装包 wheel](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/graph_research_assistant-0.36.0rc4-py3-none-any.whl) | 已有Python/Conda环境的用户 | 用pip安装，再运行模块 |
| [发布页与全部附件](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.36.0rc4) | 查看版本、校验值及验证记录 | 页面底部展开Assets |

1. 解压ZIP，进入同时包含`pyproject.toml`、`graph_research`和`start-desktop.cmd`的项目目录。
2. 在这个目录打开PowerShell，依次运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[all]"
.\.venv\Scripts\python.exe -m graph_research desktop
```

3. 出现桌面窗口后，选择“本地工具”即可开始，无需模型API。首次安装需要联网下载依赖。
4. 以后双击同目录的`start-desktop.cmd`或`图论科研助手.exe`启动，保留整个项目目录。

已有Conda/venv用户可激活自己的环境，用`python -m pip install ".[all]"`和`python -m graph_research desktop`启动。wheel安装步骤及三种模式见[完整使用指南](使用指南.md)。当前包需要Python和依赖，.exe是使用项目环境的启动器。

## 当前能力

- 普通图构造、变换、谱、能量、精确多项式、对称与商矩阵；带权、复权及有向图矩阵。
- 一致超图α谱半径、Perron向量、赋权关联矩阵、张量方程和有规模限制的精确消元。
- 递推、整数线性方程、分块矩阵、有限群、符号求和/级数和车多项式。
- 图/超图绘图、拖动布局、保存坐标、PNG/SVG/PDF、TikZ及论文符号示意图。
- 批量实验、结果包、可选API对话、受评估审批的新工具开发、用户记忆和MCP子agent接入。

桌面与模型共用43个内置工具、238项参数说明；当前工作版桌面显示37项，绘图、布局和LaTeX整合到对应图旁，简单图结果可直接预览。每项工具保留中文名称、悬停说明、完整参数例子和结果导出。

## 工作流程

三种入口共用本地计算核心、执行证据和成果管理。按分类手动调用选择本地工具；自然语言研究选择API对话；由其他agent委派计算使用MCP。

![三种模式工作流程](docs/diagrams/workflow-overview.svg)

查看[完整工作流程图](docs/WORKFLOW.md)：模式总览、API对话、MCP委派、新工具评估与审批。图中只包含当前已实现流程；A/B测试后讨论的性能优化继续作为后续工作。

## 本候选版移除的内容

旧代码查找工具、旧Sage桥接脚本、桌面“旧代码迁移参考”分类及migration-status命令已移除。迁移记录、原文件哈希、函数映射、历史源码摘录和原作者署名保存在[源码追溯目录](docs/provenance/README.md)，不进入运行时wheel。

用于数学回归的已知数值结果仍保留。现有Python导入名称graph_research及命令保持兼容，数学计算功能不因移除参考模块而减少。

## 使用

安装到新电脑及本地工具、API科研对话、MCP子agent三种方式，先看[完整使用指南](使用指南.md)。

需要Python 3.11或更新版本。当前在Windows验证原生桌面及受保护计算；本地工具无需Sage、WSL或模型API。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[all]"
.\.venv\Scripts\python.exe -m graph_research desktop
```

也可使用自己激活的Python/Conda环境，按[环境说明](ENVIRONMENT.md)安装。根目录.exe是使用已有Python环境的启动器，尚非包含依赖的Windows安装器。

- 本地工具：分类选择函数，查看[输入说明与例子](docs/OFFLINE_INPUTS.md)，填写或导入JSON数据后计算。
- API对话：在[模型设置](MODEL_SELECTION.md)中本机配置；不要把密钥提交到仓库。
- [MCP接入](MCP_INTEGRATION.md)：主agent可委派工具计算；默认不需要另配本助手模型API。
- [功能覆盖与数学边界](FUNCTIONAL_COVERAGE.md)、[图计算](GRAPH_COMPUTATIONS.md)、[布局与组合绘图入口](LIBRARY_ENTRIES.md)。

完整隐式三维绘图、自动TeX编译及Windows安装器不在本次发布范围。MCP包含工具发现、保护执行和成果处理开销，不能保证比直接Python更快或更省模型token。数值结果和样例验证不等于一般数学证明。

项目仓库：[algebraic-graph-theory-research-assistant](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant)。查看[本版发布说明](RELEASE_0.36.0rc4.md)、[参与开发](CONTRIBUTING.md)和[英文快速开始](docs/QUICKSTART.md)。提交问题请带版本、核心指纹、最小输入与脱敏日志。
