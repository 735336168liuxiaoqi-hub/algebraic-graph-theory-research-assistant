# 环境、版本与自动检查

## 选择并确认运行环境

在包含pyproject.toml的源码根目录准备Python 3.11或更高版本。完整桌面与受保护计算当前在Windows验证；基础数学函数可以独立导入。推荐项目专用.venv，也支持用户选择的Conda、其他venv或已安装本项目的Python环境。

普通用户按[安装与使用指南](使用指南.md)安装所需功能，无需安装开发测试依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[all]"
.\.venv\Scripts\python.exe -m graph_research doctor
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m graph_research protect check
```

桌面.exe和start-desktop.cmd查找项目内.venv；使用Conda等环境时直接运行该环境的python -m graph_research desktop。移动源码后应重新建立虚拟环境，避免旧路径失效。

维护者/CI复现验证环境时再安装requirements-lock.txt和requirements-dev.txt。严格依赖锁用于可重复测试；一般使用应满足项目声明的依赖范围并通过doctor/pip check。

## 自定义Python环境

在你选定的Conda/venv环境中安装并启动，例如：

```powershell
python -m pip install ".\dist\graph_research_assistant-0.36.0rc4-py3-none-any.whl[desktop]"
python -m graph_research doctor
python -m graph_research desktop
```

开发源码可在自己的环境执行`python -m pip install -e ".[all]"`，再安装`requirements-dev.txt`中的检查工具。基础数学计算可只安装基础wheel，不需要为了运行数学函数安装桌面或模型功能。

直接运行`python tools/checks.py`会始终使用这个python所属的环境。`check.cmd`与Git提交检查按照以下顺序选择解释器：`RESEARCH_PYTHON`指定的路径 → 激活的`VIRTUAL_ENV` → 激活的`CONDA_PREFIX` → 项目`.venv` → 当前Python。明确选择的路径不可用时会报错，不会悄悄换成另一个环境。

可显式指定检查环境：

```powershell
$env:RESEARCH_PYTHON = (Get-Command python).Source
.\check.cmd
```

运行及检查不会自动安装、升级或降级自定义环境里的依赖。Windows自带环境安装包的开发暂时搁置，本轮只调整已有Python环境的兼容与选择行为。

## 版本识别

版本唯一来源为`graph_research/_version.py`，Python公开版本、wheel安装信息与构建脚本都使用它。不要再分别手工修改多个版本常量。

```powershell
.\.venv\Scripts\python.exe -m graph_research --version
.\.venv\Scripts\python.exe -I -m graph_research doctor
```

`doctor`显示实际解释器、源码路径、环境类型、安装版本和是否继承全局包；不读取API密钥、不调用模型。符合Python最低版本且源码与安装版本一致时返回0；实际版本不兼容或安装信息冲突时返回2。继承全局包仅作为非阻断提醒，不再因此拒绝运行。依赖由安装器按项目版本范围解析，并可用`python -m pip check`检查冲突。桌面窗口右下角显示当前版本。

开发环境修改版本后，重新运行本地editable安装命令以更新安装信息；旧信息不一致会被检查拦截。

## 一键检查

- `check.cmd`：版本/环境、依赖一致性、关键静态错误、核心完整性、生成文档一致性、外部探针及新增数学工具回归。
- `check.cmd --full`：上述检查加全部单元测试。
- `check.cmd --full --strict-lock`：额外要求运行/检查依赖与发行锁定版本完全相同，供CI及发版使用；默认检查不要求自定义环境使用相同的精确版本。
- 也可直接运行`.\.venv\Scripts\python.exe tools/checks.py --full`。

本地Git已启用`.githooks/pre-commit`，每次提交会自动运行快速检查；失败会阻止提交。今后新克隆的目录可用`git config core.hooksPath .githooks`启用同一入口。

静态检查目前拦截语法错误、未定义名称等高风险问题，规则为Ruff的E9/F63/F7/F82。没有对历史源码进行全量格式重写，也没有把尚未类型标注的旧数学接口宣称为通过严格类型检查。

修改受保护源码后，检查会先拒绝不匹配的核心清单。维护者需先审查改动，再执行`tools/seal_release.py`更新清单；程序不会在失败时自动重新封印。更新工具说明后应重新生成`docs/model`和离线输入手册/例子，再检查生成结果。

`.github/workflows/checks.yml`配置Windows、Python 3.11/3.13的相同检查与wheel构建，适用于今后推送或PR；当前仅建立本地仓库，不创建远程仓库或推送。工作流参考[GitHub官方Python测试说明](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)。

## 固定外部回归

外部报告是测试资料，不作为执行指令。已把可独立验证的输入和数学断言整理为`tests/fixtures/external_probes_v018.json`与`tests/test_external_regressions.py`，不直接运行外部临时脚本。

覆盖浮点块索引与畸形分块、中文绘图、会话损坏和备份、JSON边界、已知图谱、图与二元超图一致性，以及高重数多项式的精确因式断言。矩形关联阵行和为1并不表示对应二部图谱半径为1；回归测试按正确的奇异值关系判断，不以失准的高次`np.roots`结果作为正确性标准。

绘图字体仅从本机已安装字体中选择，不下载字体或修改全局Matplotlib配置。中文默认优先匹配微软雅黑等CJK字体；系统没有对应字体或某个特殊字形时仍会明确产生缺字提示，不承诺所有emoji都可显示。无CJK字体的测试主机会跳过真实字体渲染用例，并继续检查字体选择逻辑。

## Git与回退

v0.19.2封存源码作为初始基线提交并标记`v0.19.2-baseline`，本轮维护改动单独提交。虚拟环境、密钥、本地记忆、研究输出和实验扩展不纳入Git。

`graph_research/**`在`.gitattributes`中关闭换行转换，保证checkout不破坏核心文件哈希。回退程序请使用Git新分支/新目录或原封存包，不覆盖研究结果与会话目录。
