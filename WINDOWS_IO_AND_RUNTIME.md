# Windows 深目录导出与固定运行版本（v0.35.1）

本次修复针对外部v2批量报告：真实输出目录235字符，CSV目标250字符，而旧临时文件达到260字符，导致计算完成后导出失败。旧失败记录和预算保留，不自动重算或重新封存。

## 路径和导出

公共存储层将安全检查、记录展示用的逻辑路径与Windows实际I/O路径分开：安全检查统一处理盘符/UNC及扩展前缀，随后I/O使用扩展路径。核心写入、越界、符号链接/junction和设备命名空间继续拒绝。临时文件仍位于目标目录、同卷原子发布，名称固定短前缀.gr-，禁止覆盖语义保持。

graph_batch_study输出子目录缩短为16位随机标识；目录独占创建，碰撞不覆盖。PNG/SVG/PDF使用原子流式发布，JSON/CSV/Markdown使用同一存储层。执行清单扫描、文件读取、哈希、结果包及附件读取支持深目录。

- calculation_status：实际计算complete/partial/failed。
- export_status：请求文件导出的complete/partial/failed。
- status：总体完成情况；计算成功但导出失败为partial。
- rows：保留已实际计算的数值，不为补导出重新调用算法。
- export_errors：按格式给出code/phase/retryable/type。
- files：只登记实际成功发布的文件。

目录或全部导出写入失败时，rows仍通过受保护工作进程根目录的result.json回传。不能写出结果文件不等于没有计算数据；MCP summary.output_complete和export_failures及结果包部分状态会明确提示。若进程被终止、根结果文件也不可写等不可恢复情况，不能保证尚在内存的结果恢复，不会伪造完成回执。

## 错误与重试

| code | 含义 | 自动重试建议 |
| --- | --- | --- |
| core_integrity_failed | 已安装核心与清单不一致 | 不重试、不自动封存，恢复已验证版本 |
| sandbox_violation | 越界、核心写入或设备/链接别名被拒绝 | 不重试、不降级为普通导出警告 |
| path_too_long | 路径超出实际可支持范围 | 不重复同一路径 |
| mcp_busy / host_busy | 已知任务/会话锁占用 | 等待并查询原任务，不重复创建计算 |
| io_permission_denied | 文件权限拒绝 | 检查所选目录，不自动扩大权限 |
| io_temporarily_unavailable | 共享/锁冲突 | 有限等待，查询已有记录 |
| io_path_missing | 路径缺失 | 检查路径，不一概归因于杀毒软件 |
| host_runtime_error | 其他未归类宿主运行异常 | 保留记录，查看日志，不自动重算 |

atomic_text仅在临时文件已经成功创建、随后消失且父目录仍在时重建同一内容；创建阶段就失败不做六次无效重试。已知共享冲突保留原有限重试。重试只针对I/O，不重跑数学算法，也不冲销失败预算。

## 固定运行版本，开发与使用分离

建议开发继续使用源码目录，长期运行的MCP使用已验证wheel的独立副本。工具不会修改Codex/WorkBuddy配置、重启服务或安装依赖。先完成wheel验证，再执行：

```powershell
$releaseInfo = Get-Content dist/graph_research_assistant-0.35.1.release.json -Raw | ConvertFrom-Json
python tools/stage_runtime.py --wheel dist/graph_research_assistant-0.35.1-py3-none-any.whl --sha256 $releaseInfo.wheel_sha256 --destination D:/GraphRuntime/v0.35.1 --python C:/YourPython/python.exe
```

目标必须为新目录，现有运行版本永不就地覆盖。Python可选择专用环境或现有环境，须已安装对应依赖；本工具只隔离核心代码，不声称隔离或锁定所选Python环境的第三方依赖。

生成mcp.py、runtime.json、package/及connection-template.json。先用选定解释器检查：

```powershell
C:/YourPython/python.exe -I -B D:/GraphRuntime/v0.35.1/mcp.py --check
```

--check仅核对副本及依赖可发现性，不创建会话、调用模型或运行计算。每次正常启动也核对完整文件清单和核心清单，变化即拒绝启动，不自动重封存。校验值用于识别本机改动，不是对抗拥有本机任意代码执行权限者的身份认证。

将connection-template.json的command/args作为新连接入口，并在args末尾**原样追加现有--root、--user、--tool-dir、预算及其他启动参数**。不要因为升级换数据根目录或用户标识。配置片段需由宿主确认后切换；旧运行目录保留，让正在执行的任务先收尾，再重连新版本。

后续开发只改源码目录，不能就地修改这个运行副本。升级使用新版本目录；回退选择原版本入口，保留数据目录。两版对待执行开发审批的核心指纹不同，旧批准不能自动替代新确认。

本机已生成并实测的固定目录为`<LOCAL_PATH>`，其中`connection-template.json`提供现有项目Python的启动入口。尚未改动任何实际MCP配置；正在运行的旧进程需重连才能加载新代码。切换固定副本时仍须按上文保留原有身份、数据目录和预算参数。项目根目录可执行以下无计算自检：

```powershell
& .\.venv\Scripts\python.exe -I -B -X utf8 .\dist\runtimes\v0.35.1\mcp.py --check
```

完整验收与保留的中间失败记录见V0351_VALIDATION.md。

## 回归口径

测试覆盖250/259/260/280/320字符真实路径、中文路径、前缀/UNC形式、核心/越界/junction防护、临时文件消失及禁止覆盖。端到端在真实MCP深度的受保护进程完成12案例×3计算和图集导出，核对路图闭式谱、特征多项式递推、逐项顺序、附件及SHA。

不同运行的时间、随机目录与图文件元数据可能不同；比较数学字段和状态，不把整份JSON或ZIP跨运行哈希相同作为数学等价条件。每份实际产物仍独立核对其原始SHA256。
