# 工作流程图素材

用户阅读入口：[工作流程](../WORKFLOW.md)。GitHub原生渲染入口：[Mermaid版本](MERMAID.md)。

| 文件前缀 | 内容 |
| --- | --- |
| workflow-overview | 中文三模式总览 |
| workflow-overview-en | 英文总览，节点/连线与中文相同 |
| workflow-api | API澄清、计划、本地执行与保存 |
| workflow-mcp | 主agent委派、异步查询、取消与用户事件 |
| workflow-extension | 复用、独立开发、范围评估与批准 |

每张图提供SVG、PNG、Mermaid源码（.mmd）。图示描述当前候选版已实现路径，不将拟议的性能优化画作已有能力。

## 更新图示

只修改workflows.json中的节点、连线、标签及排版，再在安装了项目desktop依赖的环境运行：

```powershell
python docs/diagrams/render_workflows.py
```

脚本仅生成本目录的SVG、PNG、.mmd和MERMAID.md，不访问模型、不启动MCP、不执行科研计算。SVG为静态矢量，无脚本、远程资源或个人绝对路径；PNG便于在不支持Mermaid的阅读器中查看。Mermaid自动布局与静态图可有不同排版，但节点、连线与标签相同。

渲染使用PySide6/Qt SVG与可用中文字体，Windows上优先Microsoft YaHei；其他环境需要有相应字体。脚本检查节点边界、节点重叠与文本宽度，更新后仍需查看图片确认连线和标签清楚。

发布时保留工作流程文档及本目录的引用素材。应用逻辑、核心完整性清单和运行预算不因重建文档而修改。
