# 0.36.0rc1候选版验收

> 历史候选版记录：文中授权待确认/仅本地交付描述的是当时状态。2026-10-20项目所有者已确认授权并选择MIT；当前发布以0.36.0rc3和LICENSE-STATUS.md为准。

项目：Algebraic Graph Theory Research Assistant（代数图论科研助手）。完成时间：2026-10-20 00:50（Asia/Shanghai）。

本记录说明本地技术验收，不代表原始代码已获得公开授权；当前状态仍为pending_authorization，未创建公开仓库、未上传代码、未授予统一开源许可。

## 技术结果

- 完整检查链通过：660项收集并执行，659通过、1跳过，0失败、0错误、0未执行。
- 跳过项为宿主不允许普通账户创建符号链接的清理防跟随测试；未修改宿主权限，未将跳过计为通过。
- Python 3.13.9、Windows；环境诊断、76项依赖锁、pip check、Ruff、195文件核心完整性及生成文档一致性均通过。
- 测试耗时778.401秒，检查链786.777秒，执行期间源码指纹未变。
- 当前43个内置工具、234项参数说明、42个桌面条目；旧参考查询及分类已移除，计算工具保留。
- wheel经独立解包验证：数值、符号、绘图、保护、恢复、API适配模拟、真实MCP/子agent、批量工作流、记忆及桌面表单等均通过；包内无运行时迁移目录或Sage桥接源码。
- 实际wheel生成的固定运行副本健康检查通过，使用自己的195文件核心，依赖齐全、model_calls=0、state_created=false。
- 来源记录移至docs/provenance，原迁移JSON SHA256保持不变：de79544c115abf3c986559db54e62cb516740e4c66f5982f48a2b82c5bdcdab3。
- 来源授权未确认时公开发布检查返回allowed=false；原作者署名、迁移哈希和映射保留。

## 校验标识

核心清单SHA256：13648746f344fac0202fafbb78ef541d13865ea9bce46487875b2b2aa2a6ee9d。

测试源码指纹：2974588f5f677e23c620bd0139cd45701b60ddbc92997b58d4cb35e23a382758。

wheel SHA256：a9d5ceee13d071176e37c5f2fe56388bebf0d5e3662b88b7f5dfded253e68d8a。源码ZIP、wheel及交付文件的完整SHA256以同目录SHA256SUMS为准。

## 复核方式与范围

从源码目录运行`python tools/checks.py --full --strict-lock --report-dir outputs/your-verification`。构建后运行`python tools/verify_release.py`核验独立wheel。维护者变更核心需审阅并重新封存，不能为掩盖损坏而改写清单。

本机原始证据保存在outputs/open-source-v036-rc1/final-acceptance及对应日志，个人实验结果和完整私有Git历史不随候选源码归档提供。

未运行远端GitHub矩阵或真实付费服务商API；授权未明确，不公开发布。完整隐式三维绘图、自动TeX编译和Windows安装器不属于本候选版。
