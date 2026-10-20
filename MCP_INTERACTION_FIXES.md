# MCP 交互修复（2026-10-20）

> 这是rc2交互修复的历史验收记录。当前公开版本为0.36.0rc3，沿用这些修复；当前版本、核心指纹和发布验收以RELEASE_0.36.0rc3.md为准。

## 已处理

| 外部测试反馈 | 当前行为 |
| --- | --- |
| 恢复失败被任务原来的 cancelled / waiting 状态掩盖 | operation 单独给出后台操作状态和错误；SDK isError 正确报告失败，原任务和有效交互保留 |
| 重复取消生成不同 ZIP、交互编号变化 | 已取消且后台停止时直接复用持久化响应，保留 revision、interaction、原 ZIP 和 SHA256；锁内再次检查完成状态 |
| 恢复启动时新取消可能被清除 | 发布恢复作业前清理旧标记；启动后的新取消传递到执行器，不被恢复流程清除；提交/取消使用同一调度锁 |
| 重复提交显示历史 steps_recomputed，容易当成本次重算 | 保留旧字段兼容，补 cumulative、request_effect 和 operation.usage 三个明确作用域；重复提交不启动新作业，当前请求新增调用为0 |
| 目录缺少版本和核心标识 | 总目录、单工具契约和哈希命中响应均给出 service.version/core_manifest_sha256/core_verified |
| 样式参数失败时缺少修正位置 | FieldValidationError 提供 style 字段路径、允许类型/范围/枚举；受保护进程、回执、逐步结果和 MCP 返回保留这些元数据，诊断不回显原值 |
| 数字和数字字符串顶点视觉上相同 | 共用默认标签规则：1 与 "1" 分别显示；原标识、数学数据与用户自定义文字保持原样；覆盖 Qt、通用和原有静态图/TikZ |
| 布局支撑图转换容易被当作原图丢失 | normalization 说明仅布局使用无向无权支撑结构；完整图仍保存在 graph_document |
| 重结果如何进一步读取不够统一 | 成功结果均附 read_more 入口，inspect 路径默认 []；扫描与批量汇总的正确路径写入模型调用指南 |
| 普通步骤预算策略与验收预期不一致 | 保留默认执行到预算用尽，以及 fail_fast=true 预算不足预先拒绝；目录与结果明确策略，修正外部测试计划 M12 |

## 使用

重新建立 MCP 连接，使服务载入当前源码。已运行的旧进程不会自动热更新。无需配置助手模型API。

先查询 research_catalog 核对 service；不要只用相同版本号判断是否为同一份源码。实际数学结果仍须检查任务 status、逐步 results 和验证证据，operation.status=succeeded 不代表已经证明数学命题。

默认已有任务和宿主配置保留。建议外部验收使用独立 --root、--results-root、--user，详见 MCP_INTEGRATION.md。之前已交付的 rc2 源码 ZIP 保持原样，本文件描述当前工作区修复。

## 验证记录

- 针对 MCP / subagent / 图形 / 诊断：79 项通过，outputs/mcp-interaction-focused-r2.log。
- 随后补充取消调度锁、Schema 字段提示及原有绘图入口验证：3 项通过。
- Ruff 与生成文档一致性检查通过。
- 完整验收：692项，691通过、1跳过、0失败/错误/未运行；测试801.010秒，全闸门810.652秒。
- 跳过项：当前Windows环境不允许普通用户创建符号链接；test_result_cleanup中相应符号链接清理用例未执行，不计入通过数。
- 依赖检查、严格依赖锁、Ruff、199文件核心完整性、生成文档、git diff --check均通过。
- 执行期间源码未变化；源码指纹163bafb0796b96875d5491985583612419f5434f4cc5076a21d61dde5bc2a613。
- 核心清单SHA256：3b661197153693d861da7a9c3fc46919b438391ff5867a5eb25e08103257fd7c。
- 可核对记录：outputs/mcp-interaction-final-acceptance/checks-summary.json、test-inventory.json、test-results.json、test-progress.jsonl；完整日志为 outputs/mcp-interaction-final-acceptance.log。
- 静态图已实际渲染并查看：outputs/mcp-interaction-visual-qa/vertex-identities.png；同目录保留TeX源码，未宣称实际编译TeX。

首轮针对性测试发现标签导入的语法错误，已经修复；首轮失败日志保留，不作为通过依据。以上完整验收是最终源代码的验证记录。
