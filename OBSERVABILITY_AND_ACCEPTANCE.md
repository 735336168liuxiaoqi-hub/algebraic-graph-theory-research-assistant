# 阶段1：统一验收、执行耗时和诊断（v0.35.2）

本阶段增加观测能力，不增加数学算法、不启用任务内批处理、不复用工作进程或增加计算缓存。工具契约仍为42项，MCP接口仍为13项；旧回执和历史快照可继续读取。现有v0.35.1发行副本保留，不修改实际宿主连接。

## 一、统一测试清单

质量闸门使用tests/gates.json统一选择测试模块，root字段显式登记项目根目录的test_workflow。fast/full都包含已登记根目录测试，新增而未登记的模块会失败。原来的623与630分别来自只收集tests/和另加根目录7项；本阶段另加16项观测回归，当前完整清单为646项，其中tests/639项、根目录7项。最终以实际生成的清单和逐项结果为准。

项目根目录执行（Python可换成自己的、已安装本项目及测试依赖的环境）：

```powershell
$researchPy = (Resolve-Path -LiteralPath '.venv\Scripts\python.exe').Path
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)

# 只收集，不执行计算和模型请求。
& $researchPy -X utf8 tools/run_test_suite.py --profile full --collect-only --output "outputs/inventory-$stamp"

# 完整质量闸门：环境、依赖锁、静态检查、保护、生成文档、统一测试。
& $researchPy -X utf8 tools/checks.py --full --strict-lock --report-dir "outputs/acceptance-$stamp"
Write-Host "退出码：$LASTEXITCODE"
```

checks.py不指定report-dir时自动创建outputs/checks下的新目录。严格锁用于发行验收；进阶用户的兼容依赖环境可省略--strict-lock，必须在报告中记录未启用严格锁。

每轮生成：

- test-inventory.json：完整测试ID、模块数量、tests/与根目录分项、源码/测试/驱动文件SHA、核心清单SHA、版本和真实Python。
- test-progress.jsonl：每项结束即追加状态与耗时；中断时可判断已完成哪些项，缺失部分不能算通过。
- test-results.json：通过、断言失败、错误、跳过、预期失败、意外成功、未执行分别计数；类级初始化错误和子测试失败另列。
- checks-summary.json：各检查命令的退出码/耗时及整条链的状态。受保护预检的环境阻塞仍退出2，不输出绿色成功。

执行前核对已收集清单及源码指纹，测试结束再次检查源码；测试期间改源码会让验收失败，即使断言全部通过。原始stdout/stderr继续输出到终端，外部执行者应另外保存日志。所有文件写在新的验收目录，不覆盖旧报告。

## 二、阶段计时是什么

成功或失败的受保护execution.json增加diagnostic_id及timings。数学结果仍在result.json的result内，计时作为独立诊断信封保存，不混入rho、多项式等数学字段。

| 层次 | 主要阶段 |
| --- | --- |
| 宿主 | 完整性前检、请求准备、受保护启动、等待工作进程、关闭进程、读取结果、完整性后检、回执证据准备 |
| Windows启动细分 | 保护文件检查、工作区准备、受限令牌、Job配置、标准句柄、创建进程、分配Job、恢复运行 |
| 工作进程 | bootstrap到entry的导入、guard、完整性、读请求、工具模块导入、工具注册、扩展发现、参数校验、工具函数、结果转换/序列化/发布 |
| 重点业务内部 | 超图构造、谱复核及独立有理数证书、批量CSV/JSON/Markdown发布、结构图与TikZ文件导出 |
| 成果包 | MCP任务metrics中保留累计verification_and_export_seconds，并增加last_export_timings细分包导出/包校验 |

seconds是含子阶段的时间；exclusive_seconds扣除了同一观测器记录的子阶段，合计时应使用后者。宿主worker_wait包含子进程全部工作，不能与worker阶段相加。Windows启动细分也包含在宿主启动范围内，不能重复加总。

host.process_startup测量限制建立至恢复进程运行，不能等同于整个Python冷启动。Python到达bootstrap前的时间仍包含在宿主等待中；worker.entry_import只测bootstrap开始后到entry的导入。宿主快照中的未覆盖时间单列unattributed_seconds；工作进程可用elapsed_seconds减各阶段exclusive_seconds之和检查未覆盖量。缺少某阶段表示未观测，不补造0。

tool_function的exclusive_seconds是扣除已细分阶段后的工具函数逻辑，不承诺全部为纯数学运算。采样会捕获异常阶段；failed_stage可能是已经处理的异常（如某格式导出失败后保留结果），不能据此把成功计算改判为执行失败。当前精细覆盖集中于上述路径，其他工具逻辑仍计入通用工具函数时间。

宿主回执中的计时快照止于回执发布前，避免为了把回执自己的写入耗时写回自己而反复改写。调用者记录的端到端时间还包含回执最终发布等收尾成本。旧host_elapsed_seconds口径保留，新旧字段不可混用为同一指标。

MCP默认summary只返回少量阶段独占时间及诊断编号；detail=full及结果包保留完整计时。幂等重放返回的仍是原执行时间，不能把它当成新的一次计算；复用计数及预算语义保持。

## 三、实际采样命令

```powershell
# 四类实际任务，各5次；全部为新受保护进程，固定参数、无模型API。
& $researchPy -X utf8 tools/benchmark_execution.py --case all --repeats 5 --output "outputs/profile-$stamp"
Write-Host "退出码：$LASTEXITCODE"

# 也可只采样高alpha计算。
& $researchPy -X utf8 tools/benchmark_execution.py --case high-alpha --repeats 5 --output "outputs/high-alpha-$stamp"
```

输出report.json、samples.json、原始结果及SHA绑定的执行回执。报告保存每个样本，按阶段计算中位数及nearest-rank P95；样本少时P95接近最大值，不能视为总体性能保证。首个样本与后续样本分开观察：后续可能受系统文件缓存影响，但没有复用工作进程。失败样本和未执行样本仍留在分母中，成功样本的耗时统计不能代替完成率。

阶段1只建立可审计基线，不宣称已经提速，也不把采样结果当成未实施的批处理收益。

## 四、错误编号与查询

错误详情保留phase、exception_type、可取得的errno/winerror、原因码及diagnostic_id；文件错误可提供路径UTF-16长度，不返回新增的完整私有路径或凭据。原始错误消息仍保留在相应的本机执行证据中；MCP的机器诊断字段不复制原始输入、密钥或整段异常文本。

示例：

```json
{
  "code": "io_path_missing",
  "phase": "development.spawn",
  "exception_type": "FileNotFoundError",
  "errno": 2,
  "diagnostic_id": "32位十六进制编号"
}
```

编号关联工作进程信封、宿主回执、失败工具观察、MCP返回及本用户rpc-metrics.sqlite3中的安全诊断记录。MCP开发提交额外区分读取申请、检查批准、预扣尝试和启动进程。该机制提供定位依据，不宣称已找出旧版那次未复现提交异常的原因。

用已有服务的相同root和user查询（不启动stdio服务或数学计算）：

```powershell
& $researchPy -I -X utf8 -m graph_research mcp --root 'C:/YourExistingMcpState' --user 'YourExistingUser' --metrics
& $researchPy -I -X utf8 -m graph_research mcp --root 'C:/YourExistingMcpState' --user 'YourExistingUser' --metrics --diagnostic-id '替换成实际32位编号'
```

诊断数据库兼容旧calls表，新建单独的diagnostics表；不重写历史任务。记录是尽力保存：如果文件系统/SQLite本身不可写，MCP原计算结果不因写诊断失败而改为成功或重算，编号也不保证已落盘。成功计算的编号主要在执行回执中，错误编号可由--metrics查询。

写失败回执时发生第二个错误会附为failure_receipt_error，不能覆盖原始计算异常。完整性/保护/预算的错误仍停止执行，不能通过重封存、放宽权限或改普通进程来消除错误。实际API/离线/MCP调用链均透传失败元数据。

## 五、版本使用

需要重新启动调用该源码的科研助手，或重新连接新版本MCP，才会加载新字段。本轮不修改实际宿主配置，不替换已发布v0.35.1副本。上轮v0.35.1测试材料仍固定用于该版本；A/B业务任务清单可继续复用，阶段1验收使用本页新入口。
