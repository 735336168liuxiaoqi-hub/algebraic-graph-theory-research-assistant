# Installation and three-mode quick start

Version: **0.36.0rc4 pre-release**, [MIT licensed](../LICENSE). See [中文指南](../使用指南.md) and [workflow diagrams](WORKFLOW.md).

If the repository is private, sign in with an authorized GitHub account to download packages. Download the wheel in the browser and install its local path; pip does not inherit browser authentication.

## Choose a download

- **First-time desktop use:** [source runtime ZIP](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/algebraic-graph-theory-research-assistant-0.36.0rc4-source-candidate.zip), including the desktop launcher. Extract it and open PowerShell in the folder containing pyproject.toml, then follow the installation commands below. Git is optional.
- **Existing Python/Conda environment:** [wheel package](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/graph_research_assistant-0.36.0rc4-py3-none-any.whl); install with pip and launch the module. A .whl is not a double-click application.
- [Release page](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.36.0rc4): expand Assets at the bottom. Checksums and validation JSON are supporting files, not application packages.

Python and dependencies are required; the first install downloads dependencies. After the source install creates the project .venv, start-desktop.cmd and the included .exe can launch it on later runs.

## Install

Use 64-bit Python 3.11+. The complete native desktop and protected computation are currently validated on Windows; SageMath and WSL are not required. Extract the source archive or clone the repository:

```powershell
git clone https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant.git
cd algebraic-graph-theory-research-assistant
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[all]"
.\.venv\Scripts\python.exe -m graph_research doctor
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m graph_research protect check
.\.venv\Scripts\python.exe -m graph_research desktop
```

Dependencies download during installation; offline use on a new computer requires separately prepared wheels matching its Python/OS. Existing Conda/venv users can activate their environment and run its python for installation and launch.

The source-tree .exe and start-desktop.cmd use the project's .venv and are not bundled installers. They do not automatically select another activated environment. Keep the whole project directory; recreate a venv after moving it.

Alternatively install the wheel with `python -m pip install "path/to/graph_research_assistant-0.36.0rc4-py3-none-any.whl[all]"`, then launch the module. Base library use requires only base dependencies; extras are visual, tools, desktop, assistant and mcp.

## 1. Local tools

Choose **本地工具**, select a tool, read its help/example, fill parameters and start computation. First example: graph_invariants, kind=path, n=5 gives 5 vertices, 4 edges and diameter 4. No model API is needed.

Use **图输入** for edge lists, matrices, JSON, graph families or mouse construction. Confirm graph type, direction and weights. Result-side drawing/layout/LaTeX actions use the selected input/result graph. Drag vertices, save graph JSON with coordinates and export images or TikZ. A preview alone is not a saved image.

Non-uniform hypergraphs can be drawn; tensor computations enforce uniformity and their other documented conditions. See [tool inputs](OFFLINE_INPUTS.md) and [graph input](GRAPHICS.md).

## 2. API research chat

Choose **科研对话** → **模型设置**. Select a compatible protocol/service, enter its base URL/model ID, and provide credentials locally when required. Model-list and reasoning-effort options depend on the service. Never commit keys or paste them into task text.

Saving settings is local. Fetching models contacts the service; connection testing sends a diagnostic request and may be billed. Local simulated tests do not guarantee every provider's behavior.

Ask a question, insert a graph when needed and answer clarification questions in the same conversation. **先查看计划** lets you review a multi-step plan before execution. Existing tools can be composed; new tools require scoped assessment and real user approval, and are packaged separately.

Check actual tool records, verification data and files. Model prose is not execution evidence. See [API setup](API.md), [model settings](API.md) and [API workflow](API.md).

## 3. MCP host delegation

Install mcp or all. Use this installation's interpreter as the host's STDIO command. Print a snippet without changing host settings:

```powershell
.\.venv\Scripts\python.exe -m graph_research mcp-config --format json --root D:/agt-state --results-root D:/agt-results --user researcher --max-tool-calls 15
```

Add the returned command/args to the host and reconnect. Default tools mode uses the host agent's model, without a separate assistant API. Keep state/results outside the installed package.

The host discovers contracts with research_catalog, submits research_submit, saves task_id, polls research_get and reads full fields/artifacts as needed. Same request_id requires the same input. User events must come from trusted host actions; the model cannot approve itself. Resume/reconnect preserve budgets.

MCP adds discovery, protection and result-processing overhead; time/token savings over direct Python are not guaranteed. Start with a small synthetic graph. See [MCP integration](MCP.md).

## Results and troubleshooting

Use the [result center](RESULTS_AND_MEMORY.md) to locate artifacts. Inspect calculation and export status separately; verify hashes when moving archives. Generating TeX requires no compiler, while TeX-to-PDF compilation is a separate environment/task.

Restart the desktop or reconnect MCP after upgrading. Run doctor, pip check and protect check in the actual chosen environment. Investigate/restore an integrity mismatch rather than automatically resealing it. Report small reproducible inputs, actual version/core fingerprint and redacted diagnostics to repository Issues.
