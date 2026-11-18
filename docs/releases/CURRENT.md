# 当前版本：0.38.0a11

[v0.38.0a11 预发布页](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.38.0a11) · [中文安装指南](../../使用指南.md) · [English user guide](../QUICKSTART.md)

a11 整理源码包和维护说明。已经使用 a10 的研究任务可继续用原环境完成；新建环境或验收这次整理时，选 a11 的源码 ZIP 或 wheel。

## 与 a10 相比

- 保留 Windows 桌面、本地工具、科研对话和 MCP 入口；两个命令行启动脚本共用一份环境检查，原入口仍可使用。
- 首页按研究任务导航，中英文指南保留安装和首个计算示例。[本地验收任务书](../reference/LOCAL_ACCEPTANCE.md)说明如何从新目录确认版本、运行计算并记录结果。
- [工作流程](../WORKFLOW.md)集中说明图示维护；默认保存 SVG 与 Mermaid 总览，独立 PNG 和 Mermaid 源文件可按需导出。离线工具的输入例子保留为可直接导入的 JSON，示例压缩包可按需生成。
- 源码导出现在还会排除编辑器配置、缓存、临时文件和常见密钥文件。授权、署名和历史验证记录继续保留；项目采用 [Apache-2.0](../../LICENSE)，原 Sage 文件的 MIT 署名见 [NOTICE](../../NOTICE.md)。

## 七个发布附件

| 需要做什么 | 附件 |
| --- | --- |
| 在新电脑安装，或取得完整源码 | [源码 ZIP](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.38.0a11/algebraic-graph-theory-research-assistant-0.38.0a11-source.zip) |
| 装入已有 Python 环境 | [Python wheel](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.38.0a11/graph_research_assistant-0.38.0a11-py3-none-any.whl) |
| 单独阅读操作步骤 | [中文安装说明](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.38.0a11/INSTALL_CN.md) · [English installation guide](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.38.0a11/INSTALL_EN.md) |
| 在自己的环境复验 | [本地验收任务书](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.38.0a11/LOCAL_TEST_PLAN_zh.md) |
| 查本版实际检查范围与附件哈希 | [验证记录](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.38.0a11/RELEASE_VALIDATION.json) · [SHA256 清单](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.38.0a11/SHA256SUMS.txt) |

安装需要 64 位 Python 和依赖，Windows 启动器不会自行安装 Python。运行 CEM 搜索时另装 CPU PyTorch。升级时在新目录安装，重启桌面并让 MCP 宿主指向新环境；不要用旧检查点强行续跑其他核心版本。有限搜索和数值观察不能替代一般性证明。

## 历史版本

[v0.38.0a10](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.38.0a10) 与 [v0.38.0a2](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.38.0a2) 保留原发布附件。[a10 验证摘要](0.38.0a10-validation.json)、[a2 验证摘要](0.38.0a2-validation.json)、[a1 验证摘要](0.38.0a1-validation.json)及[早期修复记录](0.38.0a1-feedback-validation.json)仅对应各自版本。a2 当时按 MIT 发布，其授权不随新版变更。
