# 代数图论科研助手：本地复验任务书（已配置 CPU PyTorch）

你是执行本次验收的主agent。请实际执行、保存证据并交付报告，不要只复述计划。不要修改科研助手源码或修复发现的问题；先给出可复现的测试结论。本任务只在本机执行，不触发GitHub Actions，不推送Git、不创建Release、不修改仓库可见性。

任务书更新：2026-10-24。适用基线：0.38.0a1，本项目当前源码与已配置的本地环境；产品仓库 Release 对应提交281b5a3。重点验收新通用实验prepare／execute／study和第4～7阶段能力，同时检查原有计算与MCP入口。默认执行第1～7节；第8节完整回归可选，避免无意义地重复耗时检查。

## 0. 本轮复验重点

更新补充：本地源码已修复原子写入后对不存在临时文件的无效删除，并增强启动错误分类、doctor宿主状态和图字段定位。请验收这些具体行为；外部宿主禁止标准库访问属于仍需在原宿主验证的兼容边界，不能因提示改进就声明宿主限制已解除。核心指纹以本次实测为准，不能沿用上一轮指纹。

先执行以下回归，保存原样输出：

```powershell
& $Py -X utf8 -m unittest tests.test_protection.StorageProtectionTests.test_consumed_atomic_temps_do_not_count_as_host_deletions tests.test_protection.StorageProtectionTests.test_real_leftover_cleanup_respects_host_deletion_policy tests.test_protection.WindowsExecutionTests.test_native_stdlib_denial_is_visible_and_never_retried_or_mislabelled tests.test_protection.WindowsExecutionTests.test_exit_code_alone_never_asserts_a_permission_or_configuration_cause tests.test_environment.EnvironmentTests.test_host_customization_diagnostic_is_read_only_and_never_echoes_env_values tests.test_experiment_execution.ExecutionTests.test_invalid_candidates_have_precise_paths_without_starting_a_worker tests.test_experiment_execution.ExecutionTests.test_schema_errors_choose_real_operation_branch_and_redact_values tests.test_experiment_execution.ExecutionTests.test_unsupported_hypergraph_metric_is_an_input_error_with_location -v
```

另需验证Windows新文件发布及并发防覆盖：

```powershell
& $Py -X utf8 -m unittest tests.test_protection.StorageProtectionTests.test_new_exports_need_no_cleanup_deletions_and_keep_complete_content tests.test_protection.StorageProtectionTests.test_atomic_publication_cannot_clobber_a_concurrently_created_output -v
```

此处命令应在第2节设置好Project/Py/Out后执行。与整模块重复的测试ID只计一次。

上一轮报告 `ra-local-20261024-020627-c2acc1` 的 CEM 项因缺少 torch 未执行；另外记录了宿主进程限制和 Python 注入干扰。现在本项目 `.venv` 已安装官方 CPU 版 `torch==2.14.0+cpu`，无需 GPU。本轮开发验证使用项目本地CPU环境；在新电脑执行本任务书前，请按使用指南安装项目及对应CPU依赖。

本轮必须实际执行 CEM，不得再把“缺可选依赖、跳过 CEM”作为整体通过的依据。其他功能继续复验，重点是正常宿主环境中的受保护运行、CEM、恢复、MCP 与结果包。准备此任务书时仅完成了安装后的两项针对性回归；这些历史结果不能替代你本轮的证据。用户把本文件交给你执行即授权下述隔离测试，不需要为每个固定小样本重复询问。

分开报告两个结论：①正常受保护执行环境能否工作；②产品数学与工作流功能在实际测试环境中的结果。进程环境阻断不能当数学功能失败，也不能用绕过保护后的结果声称集成问题已解决。

## 1. 执行范围与限制

- 允许读取项目、运行现有测试和计算，并在本次新建的测试目录内写入请求、测试驱动、结果和报告。
- 不改graph_research、tests、tools、完整性清单、依赖锁、宿主MCP配置、生产会话、既有结果或用户记忆；不重封核心、不清理历史成果。
- 不自动安装／升级依赖，不复制其他环境、不创建依赖路径注入。不调用科研助手的真实模型API，不读出密钥、不联网搜索论文。模型规划仅用ScriptedModel测试。
- 主agent自身的token／费用由宿主统计；取不到则填null／unknown，不能把它与助手内部model_calls=0混淆。
- 不引入Java、SageMath、WSL或GPU要求。CEM是本轮必测项；已配置CPU PyTorch。若实际导入失败或选错解释器，标记BLOCKED_ENVIRONMENT并保留错误，不能跳过后宣布整体验收通过。不要自行安装／升级来掩盖环境差异。
- 默认整轮墙钟上限30分钟。新增手工功能任务每个最多10次内部工具尝试、64次候选评价、120秒工作进程墙钟／CPU、1024MiB内存；不得自动提高预算或无限重试。现有自动测试中声明的专门资源限制按原夹具执行。
- 发生完整性错误、系统保护无法启动或版本不匹配时，停止依赖该条件的测试，标记BLOCKED，保留诊断；不能放宽保护来得到绿色结果。
- 不使用WMI、计划任务或其他进程树外启动方式规避宿主限制；不卸载、删除或禁用宿主的安全shim／sitecustomize，不移除其注入路径、不改ACL、不提升权限。若正常执行受阻，只运行本任务指定的保留保护的诊断；请用户在正常可信终端另行运行受阻命令。另一个环境的结果必须单独注明，不能覆盖原失败。

本任务书被用户明确交办执行后，允许在**全新、隔离的测试root/user**中，使用现有自动测试夹具模拟范围确认、继续和反馈。该授权仅适用于下文固定小样本、预算和故障注入验证，不是批准任意实际科研任务。生产MCP中的用户事件仍须来自真实用户；不能把portal或subagent-user注册成模型工具，不能伪造已有生产任务的授权。

## 2. 定位版本和创建目录

优先使用用户指定的项目目录。该电脑常见位置为`C:/path/to/project`；也可能使用独立Git检出。检查pyproject.toml、graph_research及examples/research-experiments是否存在，再选择解释器。

注意：开发目录可能保留旧仓库的Git历史；实际加载文件路径、包版本、核心指纹及实验契约，比单独的git log更能说明本次运行的是哪个副本。不要自行重置／替换Git历史。

PowerShell准备命令；把项目路径换成实际值：

```powershell
$Project = 'C:/path/to/project'
Set-Location -LiteralPath $Project
$Py = Join-Path $Project '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $Py)) { throw '请先选择已安装本项目依赖的Python解释器，不要混用环境。' }
$RunId = 'ra-cpu-retest-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,6)
$Out = Join-Path $env:TEMP $RunId
if (Test-Path -LiteralPath $Out) { throw '测试目录已存在，请换一个运行编号。' }
New-Item -ItemType Directory -Path $Out | Out-Null
$env:PYTHONUTF8 = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
```

测试根目录宜短，例如`D:/RA-Test/运行编号`或系统临时目录。不要把任务root放在多层长报告目录下。报告里记录实际Project、Py、Out、RunId；本轮所有请求使用新的request_id，重放测试才复用同一个ID。

按顺序执行并保存标准输出、错误和退出码：

```powershell
& $Py -X utf8 -m graph_research doctor
& $Py -m pip check
& $Py -X utf8 -m graph_research protect check
& $Py -X utf8 -c "import sys,json,importlib.util,graph_research; print(json.dumps({'python':sys.executable,'package':graph_research.__file__,'version':graph_research.__version__,'torch_available':importlib.util.find_spec('torch') is not None},ensure_ascii=False))"
& $Py -X utf8 -c "from graph_research.experiments import experiment_contracts; c=experiment_contracts(); print(c['phase'],c['operations'])"
```

通过标准：依赖无冲突、核心ok=true、实际版本支持study，操作至少包含prepare／execute／study。必须执行以下真实导入与CPU计算，不能仅靠find_spec判断：

```powershell
& $Py -X utf8 -c "import json,pathlib,sys,torch; p=pathlib.Path(torch.__file__).resolve(); assert p.is_relative_to(pathlib.Path(sys.prefix).resolve()); assert torch.__version__=='2.14.0+cpu'; assert torch.version.cuda is None; values=torch.linalg.eigvalsh(torch.tensor([[2.,1.],[1.,2.]],dtype=torch.float64)).tolist(); assert values==[1.,3.]; print(json.dumps({'python':sys.executable,'torch':torch.__version__,'torch_path':str(p),'cpu_eigenvalues':values},ensure_ascii=False))"
& $Py -X utf8 tools/check_dependency_lock.py
& $Py -X utf8 -c "import json,os,sys; print(json.dumps({'pythonpath_present':bool(os.getenv('PYTHONPATH')),'sitecustomize_loaded':'sitecustomize' in sys.modules}))"
```

两类环境干扰只记录是否存在及最小必要的已脱敏来源，不输出完整环境变量或密钥。当前配置期望导入来自本项目 `.venv/Lib/site-packages/torch`。若版本或路径不同，标记环境差异，不自动切换到别的环境。

若受保护工作进程启动失败，只执行一次以下固定诊断，并保留其非零退出码、JSON、stdout/stderr、bootstrap-stderr.log和diagnostic_id：

```powershell
& $Py -X utf8 tools/diagnose_protected_startup.py --output "$Out/startup-diagnostics"
```

此诊断保留原保护，不是计算回退。若受阻，停止后续依赖同一受保护执行条件的测试，不重复制造几十个相同错误。其他不依赖该条件的纯校验可继续，逐项记录未覆盖范围。

记录初始完整性指纹，结束时再次比较。当前基线应有47项公开计算工具；内部experiment_evaluate／experiment_search不算第48／49项。版本不同须说明差异，不能篡改清单来对齐数字。

## 3. 默认自动回归：先验证现有实现

先运行之前跳过的两项 CEM 测试，以便尽早发现环境是否仍阻断：

```powershell
& $Py -X utf8 -m unittest tests.test_experiment_study.SearchTests.test_cpu_cem_json_checkpoint_preserves_weights_momentum_and_trajectory_sequence tests.test_experiment_study.StudyEntryTests.test_actual_protected_cem_round_and_restart -v
```

两项必须实际执行，不能是skipped；第一项验证普通图、一致超图、超树的JSON状态往返与下一轮一致性，以及不同torch版本断点拒绝；第二项验证真实受保护CEM分段运行及重新创建入口后的恢复。它们不调用真实模型API。

然后运行以下命令，分别保存日志和退出码；不要因为一个失败就漏报后续独立模块。项目测试已经包含隔离目录、脚本模型和可信用户事件模拟。

```powershell
& $Py -X utf8 -m unittest tests.test_experiment_preparation tests.test_experiment_evaluation tests.test_experiment_execution tests.test_experiment_study -v
& $Py -X utf8 -m unittest tests.test_release_candidate tests.test_documentation tests.test_package_structure -v
& $Py -X utf8 -m unittest tests.test_mcp_integration.SDKTests.test_real_stdio_handshake_async_execution_and_cross_connection_reuse -v
& $Py -X utf8 tools/check_generated.py
```

把每条命令的原样输出写入Out/logs下的独立文件。可用你编写在Out里的小型subprocess驱动，以UTF-8保存stdout／stderr和returncode；不要修改项目测试来便于通过。

以实际收集结果为准，不硬凑数量。先跑的两项CEM与后面的整模块有重叠：按完整测试ID去重，分别记录执行次数与唯一用例数，不能重复计通过数。分别统计passed、failed、error、skipped、blocked、not_run；统计总数须能与逐项列表核对。CEM若仍跳过，本轮CEM验收即未完成。现有脚本模型通过不等于真实模型服务商已验收。

若一个模块因环境问题无法导入，标记该模块BLOCKED，不把未执行用例算通过。SDK缺失时，MCP线协议测试标记SKIP_DEPENDENCY，其余CLI／数学检查继续。

## 4. 真实功能冒烟：不以单测绿色代替实际任务

以下通过CLI任务入口执行。MCP另见第6节。复制现有例子到Out/requests，修改副本中的request_id，加上RunId前缀；不要编辑原例子。

**首次提交前**把每个副本的constraints设为max_model_calls=0、allow_extensions=false，max_tool_calls不高于10；experiment含budget时，max_evaluations不高于64、wall_seconds／cpu_seconds不高于120、memory_mb不高于1024，已有更低值保留。先用契约核对缩小后的预算仍覆盖计划；不够时缩小测试案例／方法组合，不提高上限。prepare的工具预算继续为0。提交后不更改同request_id的输入；重放只能使用完全相同的副本。

| ID | 输入／操作 | 必须检查 |
| --- | --- | --- |
| F01 | tools模式调用graph_invariants，kind=path、n=3 | P3直径2、边数2；内部模型调用0；有真实执行回执 |
| F02 | clique-free-request.json，operation=prepare | 草案executable=false、approved=false；工具及模型调用0；不出现“实验已完成” |
| F03 | hypergraph-distance-execute-request.json | 首次等待审阅且工具调用0；确认后2个候选均可行，均不是超树；允许n=6、k=3、m=3，不套用N=7 |
| F04 | 自建非一致超图execute，见下文 | 接受非一致结构、计算距离谱；独立重建距离矩阵与谱值吻合 |
| F05 | clique-free-study-request.json | 无API完成；可行候选确实无三角形；原始目标与训练分数分列；有限范围声明保留 |
| F06 | hypergraph-distance-study-request.json | 一致、连通、3条超边及含环语义正确；一般超图未限制成超树 |
| F07 | hypertree-distance-study-request.json | 可行候选满足k=3、m=3、Delta=3、q=1；q为最大度顶点个数；允许部分候选不可行 |
| F08 | 自建有限枚举与假设检验，见下文 | 完整覆盖8个有标号3顶点图；数值界及结构命题有真实反例，候选模式冲突不升级为定理反例 |
| F09 | 自建两轮分段任务，见第5节 | 暂停、跨进程恢复、反馈和回执复用正确，预算不清零 |
| F10 | clique-free-cem-study-request.json，必测，按下文缩小并固定实例 | CPU训练、精英／动量／RNG检查点及跨进程恢复证据存在；不强求启发式找到理论最优图 |

CLI的`*-request.json`是`{"operation":"submit","task":...}`封装；Python／MCP接收对应的任务本体`*-study.json`或`*-execute.json`，不要混用。

### F01最小任务

保存为Out/requests/F01-request.json，替换request_id前缀：

```json
{
  "operation": "submit",
  "task": {
    "version": 1,
    "request_id": "RUNID-F01",
    "objective": "计算P3直径",
    "execution": {"mode":"tools","steps":[{"id":"structure","tool":"graph_invariants","arguments":{"kind":"path","n":3}}]},
    "constraints": {"max_model_calls":0,"max_tool_calls":1,"allow_extensions":false}
  }
}
```

执行模板；为每个功能任务使用不同root，防止互相污染：

```powershell
& $Py -X utf8 -m graph_research subagent --root "$Out/F01-state" --user $RunId --input "$Out/requests/F01-request.json"
```

### 等待审阅／分段继续的处理

必须先保存首次返回，核对interaction.plan的题目、实例、方法、轮数和预算。自动测试的事件模拟只可用于本任务书授权的新测试root/user。若使用真实生产MCP连接，必须交给真实用户，不可自行签发。

隔离测试中的CLI继续命令：

```powershell
& $Py -X utf8 -m graph_research subagent-user --root "该功能任务的独立root" --user $RunId --task TASK_ID --interaction INTERACTION_ID --revision REVISION --action continue
```

取返回的host_user_event.event_id，保存Out中的resume.json，再执行subagent：

```json
{"operation":"resume","task_id":"TASK_ID","event_id":"EVENT_ID"}
```

每次读取最新revision和interaction_id；不能复用旧交互号。最多处理5次预期的分段暂停；多于此值停止并报告，不无限循环。取消、失败、预算耗尽、等待用户都不能强行当作completed。

### F04非一致超图

使用与F03相同的execute外层协议，替换experiment为：

```json
{
  "operation":"execute",
  "problem":{
    "version":1,"question":"非一致含环超图的距离谱评价","intent":"parameterized_extremum",
    "object":{"type":"hypergraph","order":5},"parameters":{},
    "constraints":{"predicate":"connected"},
    "objective":{"metric":"distance_spectral_radius","direction":"maximize"}
  },
  "cases":[{"id":"mixed","parameters":{},"candidates":[{"n":5,"edges":[[0,1,2],[1,3],[2,3,4]]}]}],
  "chunk_size":1,"segment_chunks":1,
  "budget":{"max_evaluations":4,"wall_seconds":60,"cpu_seconds":60,"memory_mb":1024}
}
```

任务constraints设max_model_calls=0、max_tool_calls=2、allow_extensions=false。应返回feasible=true、uniform=false、hypertree=false，超图度为[1,2,2,2,1]。

独立检查不能只调用科研助手的同一评价／验证函数：用原始超边构造BFS，距离等于路径经过的超边数，得到D；用NumPy的eigvalsh独立计算最大特征值，与结果相对误差不超过1e-8。另用有理数重算保存向量的Rayleigh／Collatz界，核对区间：保存向量的浮点数应用Fraction.from_float还原其实际IEEE值，不要以四舍五入的十进制字符串冒充同一个精确向量。该检查证明具体实例，不证明一般定理。

### F08明确假设与覆盖

study.problem使用simple_graph、order=3、parameters={}、objective=edge_count/maximize，不加禁团或连通约束；cases为一个空参数实例。methods=["enumerate"]、seeds=[11]、rounds=1、batch_size=8、max_edges=3、planner=rules、adaptive=false；预算max_evaluations=8、wall_seconds=60、cpu_seconds=60、memory_mb=1024，任务工具上限2。

hypotheses使用：

```json
[
  {"id":"bound","type":"metric_bound","relation":"le","value":1},
  {"id":"structure","type":"universal_structure","property":"bipartite","expected":true},
  {"id":"pattern","type":"candidate_pattern","property":"bipartite","expected":true}
]
```

预期8个不同有标号图被评价。bound及structure应有verified_counterexample见证；pattern只报pattern_contradicted。独立确认见证的边数／奇环，finite_coverage仅对应n=3的声明域；general_theorem_proved=false，确定性枚举的重复不能计作独立随机种子证据。

### F10 CPU CEM 独立功能验收（必测）

从 `examples/research-experiments/clique-free-cem-study-request.json` 复制生成新请求。保持原问题与两组alpha实例，把experiment修改为：

```json
{
  "cases": [
    {"id":"alpha025","parameters":{"n":5,"r":3,"alpha":"1/4"}},
    {"id":"alpha075","parameters":{"n":5,"r":3,"alpha":"3/4"}}
  ],
  "methods":["cem"],"seeds":[11],"rounds":2,"batch_size":4,
  "segment_rounds":1,"planner":"rules","adaptive":false,"max_edges":8,
  "budget":{"max_evaluations":16,"wall_seconds":120,"cpu_seconds":120,"memory_mb":1024}
}
```

这段仅列修改字段，`operation=study`、`problem`保留源例子；不要把它当作完整请求覆盖其他必需字段。任务constraints固定为max_model_calls=0、max_tool_calls=4、allow_extensions=false。每次request_id使用新前缀。先调用compile_study检查计划应为2个run、4轮、16个候选评价，再通过CLI任务入口执行，不用直接函数替代受保护执行。

1. 首次submit应等待范围审阅且工具调用0；核对两个alpha、种子、轮数和预算。
2. 在授权的全新测试root中签发continue事件；第一轮完成后应暂停。保存task_id、revision、interaction、首个回执的SHA256。
3. 结束CLI调用，再启动新的CLI进程读取同task_id；签发当前交互的新事件继续。总共最多处理4个计算段；每段后读取最新状态，不复用旧interaction_id。
4. 最终应completed，training_performed=true，累计16个候选评价、4次工具尝试、真实模型调用0。若失败，保留实际预算与失败回执，不能自动重试把累计数字凑到上述预期。
5. 只读检查每次受保护结果中的checkpoint：应有neural.weights、neural.momentum、neural.updates、torch_version，以及RNG、elites、round等；至少一个updates>0。只在报告输出检查结果、数量和哈希，不把完整权重或动作序列塞回主agent上下文。不要使用torch.load或pickle反序列化断点。
6. 每个可行候选都用原始边表独立查三角形；用NumPy自行构造A与度对角阵D，计算`alpha*D+(1-alpha)*A`最大特征值。与原始目标值相对误差不超过1e-8。不可行候选可以出现，应如实统计，不能当整体失败或静默剔除；训练分数不能冒充原始谱半径。若没有可行候选，不能据此认定数学错误，也不能声称已验证谱值；独立谱核验标记未覆盖并保留采样事实，不增预算反复抽样。
7. 验证结果包SHA256与manifest，检查原始参数、分段回执、训练与消耗记录。仅发现training_performed文字标志不足以通过训练验收。
8. 连续运行与JSON断点恢复后下一轮完全一致，由第3节第一项专项测试验证；CLI跨进程恢复由本项验证。两者分列，不把“能够读取断点”当作“恢复轨迹一致”。

不要求CEM在这个极小预算内优于random/local，也不要求找出理论最优图。此处验收可用性、训练、数学语义、预算和证据，不证明搜索效果优势。

## 5. 审批、恢复、预算与负向测试

F09建议从F08修改：n=4、methods=["random"]、seeds=[11]、rounds=2、batch_size=4、segment_rounds=1、adaptive=false；删除hypotheses，cases仍为一个空参数实例，max_edges=6。总预算max_evaluations=16、墙钟／CPU各120秒、内存1024MiB，任务工具上限4、模型上限0。

1. 首次submit必须在审阅处暂停，未计算。
2. 在隔离测试中确认，完成第一轮后应暂停；工具尝试1，评价4。保存第一个成功回执SHA256。
3. 结束本次CLI进程后重新调用查询，结果和预算应保留。
4. 通过study-feedback提交`{"knobs":{"exploration":0.3,"penalty_weight":2},"focus_runs":["run1"],"note":"测试授权范围内的反馈"}`，再用其event_id恢复。
5. 最终两轮累计8个评价、2次工具尝试；第一个成功回执不变，奖励版本变化、反馈和配置变化有记录。
6. 重放同一submit输入和同一已完成事件，不新增计算、不重置计数。同request_id改输入应拒绝。

以下可靠性检查优先复用项目已有夹具，不手工破坏真实数据：

```powershell
& $Py -X utf8 -m unittest tests.test_experiment_execution.ExecutionTests.test_cancel_between_chunks_keeps_first_evidence tests.test_experiment_execution.ExecutionTests.test_changed_receipt_rejects_resume_without_recomputation tests.test_experiment_study.StudyEntryTests.test_failed_attempt_budget_is_retained_on_retry tests.test_experiment_study.StudyEntryTests.test_pinned_search_receipt_survives_crash_before_observation_save tests.test_experiment_study.StudyEntryTests.test_resource_budget_blocks_extra_planning_call_after_failed_round tests.test_experiment_study.StudyEntryTests.test_scripted_model_can_select_runs_but_cannot_enlarge_scope -v
```

如果第3节已经执行了这些用例，引用已有逐项证据即可，不重复运行凑数量。检查负向输入：approved=true、feedback抬高预算、exploration=0.9、重复边、自环、越界顶点、对非一致超图套普通图alpha矩阵等，均应拒绝或明确标为不可行，不执行任意代码、不悄悄改题。结构合法但不满足研究条件与协议输入无效要区分。

负向测试分两层记录：N-MESSAGE验证未知字段／伪造approved等在消息层被拒；N-FIELD使用结构正确的完整任务封装，分别只改一个候选字段触发自环、重复边、顶点越界，或使用不适用的数学对象／目标组合。保存原始error code、字段路径或详细原因及工具调用数。消息层拒绝只能证明消息校验，不能替代字段层用例；若错误封装导致先被消息层拒绝，应在新request_id下纠正测试驱动再执行，保留首次输入，不修改产品。信息过于笼统记录体验问题，数学约束误判另记功能缺陷。

## 6. MCP／主agent入口

先通过当前连接research_catalog读取service.version、core_manifest_sha256和capabilities。若连接仍指向旧封存副本，记录VERSION_MISMATCH，**不替用户改宿主配置**；CLI测试继续，MCP实测标记BLOCKED。

版本匹配时，至少实际委派F01一次，并读取结果字段及一个登记结果包。调用顺序为catalog → submit → 同task_id的get → inspect_result／read_artifact。按实时契约构造参数，不猜字段。单个任务查询间隔2～5秒、总查询上限30次；没完成就保留状态，不换request_id另起计算。

可读取F03/F05首次审阅计划验证模型不能批准自己。生产连接需要真实用户事件才能继续；没有该事件时把其后半段标为WAITING_USER，而不是假装跑完。完整自动MCP协议验证使用第3节的SDK隔离测试；也可在Out内创建独立HostConfiguration／SDK STDIO服务，不修改真实客户端配置。

必须检查：

- 13个MCP调度入口与47个按目录发现的计算工具不是同一计数。
- summary精简返回不等于数据丢失；用detail=full／inspect读取完整结果，不把检查点塞满主agent上下文。
- `operation.status=succeeded`只表示后台操作成功，还要看task status、逐项结果和验证字段。
- request_effect、operation.usage与budget.used分别说明本次请求／后台增量／整任务累计；get和重放不新增计算。
- 默认内部模型调用0。主agent自身的模型消耗单独记录，未知写null。

## 7. 结果核对与交付

每个成功任务至少抽查一个ZIP结果包：核对实际SHA256，再用`graph_research.assistant.verify_bundle(path,sha256)`验证。只读解包内容，不运行包内文件。execute应有experiment-input.json、experiment-results.json、experiment-ledger.json；study另有study-plan-and-decisions.json、study-interpretation.json。参数、原始结果、执行证据和消耗能关联回本次task/request，摘要没有凭空补出结果。

独立数学抽查最低要求：P3直径；可行普通图的禁三角和A_alpha矩阵；F04超图距离矩阵；F07超图度及最大度顶点数；F08反例见证。原始边表与独立实现是依据，模型文字、相同函数自比对或“无异常退出”都不够。

结束再次执行protect check，核对核心指纹与初始值一致。不要删除测试目录；把报告放在Out/report，至少输出：

1. SUMMARY.md：总体结论、阻断项、主要缺陷及优先级，区分数学错误／流程错误／环境问题／体验建议。
2. REPORT.json：逐项状态、实际版本、解释器、核心指纹、请求／任务ID、预期与实际、证据路径、错误和未覆盖范围。
3. METRICS.csv：case_id、入口、方法、种子、评价数、可行数、原始最佳目标、工具／模型尝试、墙钟／CPU、峰值内存、结果包SHA256；不可用写空值。
4. requests/、responses/、logs/：实际执行输入和输出；失败必须保留最小复现输入及诊断编号。

REPORT.json可采用以下结构，填实际值，不把模板状态当执行结果：

```json
{
  "run_id":"实际编号",
  "version":"实际版本",
  "core_sha256_before":"实际值",
  "core_sha256_after":"实际值",
  "environment":{"python":"实际路径","torch":"实测版本","torch_path":"实际导入路径","pythonpath_present":null,"sitecustomize_loaded":null,"protected_execution":"NOT_RUN","mcp_sdk":null},
  "counts":{"passed":0,"failed":0,"errors":0,"skipped":0,"blocked":0,"waiting_user":0},
  "assistant_real_model_api_calls":0,
  "functional_task_model_calls":0,
  "scripted_model_calls":null,
  "main_agent_usage":null,
  "remote_ci_started":false,
  "source_modified":false,
  "cases":[
    {"id":"F01","status":"NOT_RUN","expected":"P3直径2","actual":null,"evidence":[],"issues":[]}
  ],
  "uncovered":[]
}
```

状态使用PASS／FAIL／ERROR／SKIP_DEPENDENCY／BLOCKED／BLOCKED_ENVIRONMENT／WAITING_USER／NOT_RUN，必须与证据一致。CEM是必测，无法执行时必须明确“CEM未验收、整体未全部通过”；少量样例、数值区间重叠、启发式未找到候选和单一方法／种子的结果，不得写成一般极值定理。发现缺陷先报告，不自行修复后隐藏原失败。

## 8. 可选完整本地检查

仅当用户要求完整回归，或默认验收发现需要扩大检查的未解决问题时运行；不要无理由重复已经完成的整套测试：

```powershell
& $Py -X utf8 tools/checks.py --full --strict-lock --report-dir "$Out/full-acceptance"
```

这是**本地命令**，不需要GitHub额度，不运行远端CI。当前基线收集842项，上次本机约22分钟，结果为839通过、3环境跳过；这些是历史参考，不能直接当本次结果。完整检查受实际机器影响，给本阶段单独最多45分钟。这个历史版本的3项跳过中含2项缺torch；本轮已安装torch，不应继续用历史跳过数作预期。strict-lock不匹配时标记环境差异，不自动改依赖；若经用户同意运行非strict-lock检查，须在报告注明降低了哪项环境约束。

最终回复用户时，给出报告目录和SUMMARY.md，概括已通过、实际失败、环境跳过及仍等待用户的部分；不得只回复“测试通过”。不提交Git、不触发Actions，也不增加付费模型调用。
