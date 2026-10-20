# 运行环境、核心保护与开发维护

普通安装见[使用指南](../使用指南.md)，无须安装开发依赖或运行整套测试。本页面向维护者和集成开发者。

## 环境与版本核对

使用目标环境自己的Python执行安装和命令，不混用系统、Conda和项目venv。源码目录的启动器固定寻找本项目`.venv`；已有环境可直接运行模块。

```powershell
python -m graph_research doctor
python -m pip check
python -m graph_research protect check
```

核对实际解释器、包版本、源码来源与核心指纹，MCP客户端升级后需重连并重新读取契约。已有固定运行副本保持自身封存版本，不会随工作目录更新。完整桌面及保护执行在Windows验证；其他系统不提供无保护回退来绕过限制。

## 开发检查

```powershell
python -m pip install -r requirements-lock.txt -r requirements-dev.txt
python -m pip install --no-deps --no-build-isolation -e .
python -X utf8 tools/checks.py --full --strict-lock
```

修改工具时同步契约、中文参数帮助、示例和生成手册；测试模块在tests/gates.json登记。完整工具文档由 `graph_research.tools.contracts.export_documentation` 导出；输入手册由 `tools/export_input_guides.py --overwrite` 更新。用 `tools/check_generated.py` 检查一致性。用户专题导航维护在[docs目录](README.md)，不要再在根目录新增分阶段进度说明。

纯文档维护校验相对链接、源码导出内容和生成记录；不需要重新封存数学核心。确实修改核心时，维护者审阅后才使用 `tools/seal_release.py` 更新清单，不可用重封存掩盖来源不明的损坏。

## 代码结构

`graphs`、`hypergraphs`、`tensors`和`algebra`存放计算；`rendering`与`schematics`负责图形；`tools`负责工具契约；`desktop`、`assistant`和`mcp`提供入口；`runtime`负责受保护执行与诊断。外部扩展和用户状态不放入基础包。

## 已实施的五项保护

| 保护 | 行为 |
| --- | --- |
| 核心只读 | Windows低完整性计算进程无法写入中/高完整性的基础包文件；宿主账户及源码目录权限不作永久修改 |
| 写入限制 | Python写入限于每次计算独立目录；禁止越界路径、符号链接/目录联接、任意命令和网络访问；直接导出拒绝写入包目录 |
| 完整性检查 | 发行清单覆盖包内源码及资源；CLI、工具注册、模型决策和受限计算执行检查修改、缺失及新增文件，异常停止 |
| 故障恢复 | 独立备份及固定SHA256恢复；会话原子保存、上一完整快照、并发锁和过期实例拒绝；审批损坏不自动回退 |
| 资源限制 | Windows Job限制CPU、内存和子进程数；宿主监控用时、结果大小及文件总量；超时/取消清理进程树 |

## 日常使用

```powershell
# 检查基础包（不调用模型）：
python -m graph_research protect check

# 正常调用已自动进入受限进程：
python -m graph_research call graph_invariants '{"kind":"path","n":5}'
python -m graph_research ask "计算五阶圈图的谱" --user researcher_001

# 在另一个终端请求取消该会话：
python -m graph_research cancel "outputs/你的会话目录"

# 查看已保存状态后继续：
python -m graph_research resume "outputs/你的会话目录" --continue
```

任务文件分别放在会话的`tasks/task_随机ID/`或`outputs/protected-tasks/task_随机ID/`。各任务保留`execution.json`，明确`complete`、`failed`或`cancelled`；失败留下的文件不作为成功结果。后台进程不继承模型密钥、其他账户凭据或用户个人配置目录。

v0.24起，终止请求后保留进程及Job句柄，最多等待5秒核验主进程和整个进程树退出，再释放资源；若未退出则明确报错。避免取消调用已经返回、任务目录仍被工作进程占用的时序问题，原计算预算和写入保护不变。

取消对正在运行的计算有效，并在模型调用之间检查。已经发给模型服务商的请求可能要等返回或网络超时，不能承诺立即中断远程计费。取消开发验收会阻止随后发布新扩展；已完成的审批及计算记录保留。

## 保护已有研究成果

直接保存坐标、TikZ、布局编辑器及静态图片时，默认拒绝覆盖已有文件；确需覆盖时显式指定：

```python
h.save_pos('outputs/layout.json', overwrite=True)
h.save_tikz('outputs/figure.tex', overwrite=True)
h.save_plot('outputs/figure.svg', overwrite=True)
h.edit_layout('outputs/editor.html', overwrite=True)
```

`edit`和`latex`命令相应提供`--overwrite`。显式覆盖也不能写入基础包目录。导出先完整写入临时文件，再发布，防止半份文件替换已有成果。直接Python导出允许宿主明确选择其他目录，模型计算进程仅能在自己的任务目录写入。

## 可信备份与恢复

```powershell
python -m graph_research protect backup --output "backups/core-0.12.0.zip"
```

备份前必须通过完整性检查；已有同名备份不覆盖。保留命令返回的SHA256，并将它与备份独立保管。恢复时指定该可信值，而不是临时接受未知文件计算出的值：

```powershell
python -m graph_research protect restore "backups/core-0.12.0.zip" --sha256 "备份时记录的64位SHA256" --destination "recovered-runtime"
```

如果基础包已经损坏到无法启动，使用发行包旁的独立维护脚本，不导入损坏包：

```powershell
python "dist/recover_graph_research_0.12.0.py" "backups/core-0.12.0.zip" --sha256 "原先记录的SHA256" --destination "recovered-runtime"
```

恢复先验证完整档案、清单和各文件哈希，拒绝越界路径、重复名称、链接及超量压缩包，然后只写入**全新目录**。不直接覆盖正在运行的安装，不删除损坏副本，也不修改实验数据、记忆、扩展或审批。恢复副本位于`recovered-runtime/graph_research`；检查后可在单独的启动配置中选择该运行时，或使用保留的可信wheel重新安装。

清单及备份采用哈希校验，没有引入发行者数字签名。它们用于发现意外变化；如果有权限的宿主同时修改程序、清单和备份，不能据此证明可信。不能在检查失败时自动重建清单。`tools/seal_release.py`只供维护者审查源码后制作新版本，不是修复命令，不提供给模型。

## 损坏扩展与保存中断

损坏、超量、接口与审批范围不符的扩展会逻辑隔离：保留原文件及错误信息，不登记执行，也不阻止基础工具加载。旧的`legacy_unreviewed`扩展默认停用，需要独立复核；已获批准且通过验收的扩展仍可正常加载。

会话主文件损坏时读取上一次完整快照，并显示`recovery_notice`，将本轮标为可恢复的中断状态。批准和预算记录不自动使用旧快照，防止重复使用授权。相同会话不允许两个实例同时运行；旧实例需要重新加载后再继续。

## Python应用接入

```python
from graph_research.runtime.runner import run_tool, TaskLimits
from graph_research.assistant import ResearchSession

result = run_tool(
    'graph_invariants', {'kind': 'path', 'n': 5}, 'tool_packages',
    directory='outputs/my-task',
    limits=TaskLimits(wall_seconds=30, cpu_seconds=30, memory_mb=1024),
)

# ResearchSession已使用同一受限执行入口：
session = ResearchSession('outputs/my-session', 'tool_packages')
# 另一宿主线程可以调用session.cancel()；桌面已有停止入口。
```

默认每进程内存上限1024MiB，进程树合计1536MiB，最多8个进程、CPU合计30秒、墙钟30秒；单份结果最多4MiB，任务文件总量监控默认64MiB。精确消元默认20秒，扩展单例验收15秒，仍受数学算法自身规模限制。文件总量通过轮询监控，短时间可能超出阈值后被终止，不是文件系统硬配额。

基础Python数学函数和`ToolRegistry.call`仍提供可信宿主的直接计算接口，便于纯Python研究和原有离线实验；直接调用不会自动进入操作系统隔离。应用接入及不确定规模任务优先用`run_tool`。普通用户在编辑器中拖动顶点、导出结果的流程保持一致。

当前操作系统隔离后端已在本机Windows实测，依赖Windows自带权限及Job机制，不需要管理员账户、WSL或新第三方包。其他系统尚无等价受限后端，受限入口明确拒绝执行；普通数学库仍可用。也不应把低完整性与Python审计钩子当作能对抗任意恶意本机程序的完整沙箱。系统权限依据：[Windows完整性控制](https://learn.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control)、[进程组资源限制](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。

## 验收

`tests/test_protection.py`覆盖真实系统写入拒绝、CPU/内存上限、子进程清理、超时和取消、核心误写、成果防覆盖、保存失败、快照恢复、并发冲突、扩展隔离及安全恢复。对核心损坏的测试只修改独立复制件，不修改实际基础包。

## 进程树退出确认

清理不仅等待Job活动计数归零，还在终止前用Job进程ID列表捕获SYNCHRONIZE句柄，终止后等待这些进程对象确认退出，再关闭句柄和返回宿主。这样避免任务目录清理与子进程退出的竞态；失败仍阻止接受计算结果。该列表API见[Microsoft官方说明](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list)。资源采集在退出确认之后进行。

CPU限制保留内核Job限额，并由宿主按Job累计CPU轮询检查；状态原子发布遇Windows短暂共享/锁冲突时，仅有界重试相同IO，不重做生成或计算、不改ACL、不放宽已有文件不覆盖规则。

## 启动诊断

工作进程使用STARTUPINFOEX与PROC_THREAD_ATTRIBUTE_HANDLE_LIST，仅继承NUL输入和任务目录的bootstrap-stdout.log、bootstrap-stderr.log三个标准句柄。这样能捕获venv启动器、Python导入等早于入口重定向的错误，也避免把宿主其他可继承句柄交给低完整性进程。保留原有低完整性令牌、Job资源及UI限制，不增加breakaway、不修改账户/源码ACL，不提供不受限回退。句柄列表规则见[Microsoft文档](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)。

Python入口另写startup-status.json阶段标记。execution.json保留进程是否创建并分配Job、退出码、阶段和每份最多4KiB的日志尾部；失败时仍保存实际可用的Job资源数据及任务目录。基准失败记录关联execution_directory和startup，便于外部复核。

CPython Windows venv启动器将107用于配置文件打开、读取、home字段或解码错误，见[CPython 3.13.9源码](https://github.com/python/cpython/blob/v3.13.9/PC/venvlauncher.c)。进程退出码不是Win32 API错误码；没有具体启动日志时，只给可能原因，不断言沙箱权限。新回归使用独立副本的坏配置复现107，不修改实际venv配置。

## 诊断与发布

受保护计算记录实际输入、耗时、预算、执行错误和诊断编号。MCP中区分任务状态、后台调度操作及导出状态；重用请求不应解释为重新计算。计时与本机RPC记录不等于宿主模型的token或费用。

源码导出运行 `tools/prepare_public_release.py --output 新目录`，只选择应用、测试、维护工具和有效文档，拒绝链接，排除环境、用户状态、实验输出和私有历史。`tools/check_public_release.py`核对授权；不要把本地备份ZIP上传。当前版本说明和验收见[发布记录](releases/CURRENT.md)，来源追溯见[provenance](provenance/README.md)。

## 桌面翻译维护

`desktop/i18n.py`负责语言设置和呈现绑定，`desktop/widgets.py`提供明确导入的Qt显示组件，`data/desktop_en.json`保存静态词汇，`desktop/english.py`保存内置工具英文说明。未知文本保留原文；不要直接替换工具Schema、原始参数、JSON、图标签或模型回复。

新增界面文本应补充词表或显式上下文翻译，并使用绑定控件；数据单元格默认不翻译，只有明确标为UI状态的单元格才翻译。共享说明必须按实际语义翻译，不能用某个工具摘要覆盖通用提示。保持草稿、选项UserRole值、计算预算和线程状态，语言切换期间阻止控件选择信号产生业务动作。

回归位于 `tests/test_desktop_localization.py`，涵盖双语覆盖、所有枚举原值、实时切换、原子保存失败、已销毁Qt对象及计算中切换。原始记录和导出科研数据不因界面语言重写。
