# Algebraic Graph Theory Research Assistant — User Guide

Version **0.36.0rc4**, [MIT licensed](../LICENSE). [中文使用指南](../使用指南.md) · [Project home](../README.md)

This Python application provides graph and hypergraph computation, symbolic algebra, interactive drawing and research result management. Use the desktop manually, connect a model for research chat, or expose the same computation tools to a host agent through MCP. SageMath and WSL are not required.

The desktop currently uses Chinese labels. This guide gives their English meanings beside the labels you will see; it does not imply that an English interface is available.

## 1. Capabilities and usage modes

| Area | Supported capabilities |
| --- | --- |
| Graphs | Construction and transformations, invariants, isomorphism and symmetry, quotient matrices, numerical spectra, exact characteristic/matching polynomials, energy, weighted and directed matrices |
| Hypergraphs | Construction and transformations, structural analysis, uniform-hypergraph α-spectral radius and Perron vectors, weighted incidence matrices, tensor equations and bounded exact characteristic-polynomial elimination |
| Algebra and combinatorics | Matrix and block operations, recurrences, integer linear systems, symbolic sums/series, finite permutation groups, Cayley graphs and rook polynomials |
| Visualization | Mouse construction, draggable layouts, saved coordinates, PNG/SVG/PDF and TikZ export, paper schematics with hyperpaths of unspecified length |
| Research workflows | Batch computations, session result bundles, result cleanup/recovery, user preferences, reviewed research experience and separate extension packages |

There are **43 built-in computation tools**. The desktop groups some drawing/layout/export operations beside the relevant graph. All three modes share tool definitions and the protected computation core.

| Mode | Start here | Assistant model API required? |
| --- | --- | --- |
| Local tools | **本地工具** — select a function and fill its form | No |
| API research chat | **科研对话** → **模型设置** — configure a compatible service | Yes; a compatible local model service is also possible |
| MCP delegation | Let a compatible host start the local STDIO server | No for fixed tool tasks; the host uses its own model configuration |

![Three modes and research outputs](diagrams/workflow-overview-en.svg)

Non-uniform hypergraphs can be drawn. Hypergraph tensor-spectrum tools enforce uniformity and their other mathematical conditions. Exact elimination, enumeration and numerical calculations have tool-specific limits; an unresolved or unconverged result is not a proof or a counterexample.

## 2. Download and install

### Choose a package

Use the [v0.36.0rc4 release page](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.36.0rc4). While the repository is private, sign in with an authorized GitHub account.

| Asset | Intended use |
| --- | --- |
| [Source ZIP](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/algebraic-graph-theory-research-assistant-0.36.0rc4-source-candidate.zip) | Recommended for first-time desktop use; includes the source and launchers |
| [Python wheel](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/graph_research_assistant-0.36.0rc4-py3-none-any.whl) | Install with pip into an existing Python/Conda environment |
| `SHA256SUMS.txt` / `RELEASE_VALIDATION.json` | Checksums and validation evidence; these are not installers |

Expand **Assets** at the bottom of the release page. Download one application package; you do not need both ZIP and wheel. The first installation downloads dependencies. A fully offline new computer needs separately prepared dependency wheels matching its Windows/Python version.

### Recommended source installation

The complete desktop and protected workflow are validated on Windows. Use **64-bit Python 3.11+**; Python 3.13 is recommended for this release.

1. Extract the whole ZIP. Do not run files inside the archive.
2. Choose a short, writable path, such as `D:\Research\agt-assistant`.
3. Open PowerShell in the directory containing `pyproject.toml` and `start-desktop.cmd`.
4. Run these commands in order:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[all]"
.\.venv\Scripts\python.exe -m graph_research doctor
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m graph_research protect check
.\.venv\Scripts\python.exe -m graph_research desktop
```

If only the Windows `py` launcher is available, use `py -3.13 -m venv .venv` for the first command. No activation or PowerShell execution-policy change is needed. `[all]` installs desktop, plotting, API-chat and MCP dependencies. The checks should report the intended environment, no dependency conflicts and integrity `ok: true`; they do not request a model.

On later runs, double-click **`start-desktop.cmd`** or **`algebraic graph theory research assistant.exe`** in the same directory. The `.exe` is a launcher using the project's `.venv` and source, not an installer containing Python. Keep the whole directory. Recreate the environment after moving it or transferring it to another computer.

### Existing Conda or virtual environment

Activate the intended environment, enter the extracted source directory, then run:

```powershell
python -m pip install ".[all]"
python -m graph_research doctor
python -m pip check
python -m graph_research protect check
python -m graph_research desktop
```

You can also launch `graph-research-desktop` from that environment. The source-tree `.exe` and `start-desktop.cmd` specifically look for the project's `.venv`; they do not select an activated Conda environment automatically.

For editable development, use `python -m pip install -e ".[all]"`. Ordinary use does not require development dependencies or the complete test suite.

### Wheel installation

Download the wheel through your browser. From its directory, use the Python environment you selected:

```powershell
python -m pip install ".\graph_research_assistant-0.36.0rc4-py3-none-any.whl[all]"
python -m graph_research desktop
```

A wheel is not a double-click application. pip does not inherit browser authentication, so use the local downloaded file for a private repository. For base library use, omit `[all]`; optional extras are `visual`, `tools`, `desktop`, `assistant` and `mcp`.

## 3. Local tools — no model API

### First computation

1. Choose **本地工具** (Local tools).
2. Under **普通图** (Graphs), select **图的基本信息** (`graph_invariants`).
3. Set graph type to `path` and vertex count to `5`, or use **填入示例** (Fill example).
4. Click **开始计算** (Start computation).
5. Expect 5 vertices, 4 edges, diameter 4 and degrees `[1,2,2,2,1]`.
6. Inspect the overview, tables, graphics/files and raw data. **查看结构图** means View structure.

Required fields must be filled. Optional fields are enabled by checkboxes. Dropdowns have Chinese names and contextual hover help; **说明与示例** means Help and examples. Full JSON and parameter-file import are also available. Filling/importing parameters prepares a form without starting computation.

See the [input manual — Chinese](OFFLINE_INPUTS.md) and [importable examples](../examples/offline-inputs).

### Enter your own graph

Open **图输入** (Graph input) for edge lists, adjacency/incidence matrices, graph6, JSON, graph families, graph-library objects or mouse construction. Confirm type, direction, weights and isolated vertices, then select **使用此图** (Use this graph). Comparison tools let you choose the left or right graph.

For a four-vertex graph with edges `[[0,1],[1,2]]`, specify `n=4` to retain isolated vertex 3. Numbered calculation inputs retain an explicit mapping to original labels; tools reject inputs they cannot preserve. In mouse editing, the first delete click previews the impact; click the same object again to delete. Empty space or Esc cancels.

### Drawing, layout and TikZ

- Before computation, **绘图与导出** (Drawing and export) can use the graph prepared in the form or graph-input window.
- After computation, use **查看结构图** or **绘图 / 布局 / LaTeX** beside the relevant graph. Select the object first for multi-graph results.
- Drag vertices to update curves immediately. Use the wheel to zoom and **适应窗口** (Fit to window) to restore the view.
- **保存坐标** (Save coordinates) writes graph-and-position JSON for later import.
- Set options under **图片设置** (Image settings), then **生成图片** (Generate image). Save the actual attachment from **图形与文件** (Graphics and files); a preview alone is not a saved image.
- Use **LaTeX设置** → **导出LaTeX** for TikZ. Weighted/directed output retains original weights and arrows within its supported contracts.

Ordinary graphs have automatic layouts and coordinate transformations; hypergraphs support spring/circular layouts and manual dragging. Spectral coordinates can overlap or be non-unique; inspect warnings and adjust the layout rather than treating it as an isomorphism certificate.

Generating TeX needs no compiler. Compiling it to PDF requires a separate TeX environment; automatic complete TeX compilation is not included. See [graphics — Chinese](GRAPHICS.md) for detailed options and limits.

### Paper schematics

**论文示意图** (Paper schematic) supports central edges, omitted hyperpath sections, ellipsis points inside edges, parameter labels and braces. Use mouse editing, save scene JSON and export SVG/TeX. Ordinary structure drawing remains available.

A path of unspecified length is a symbolic diagram, not a fully defined computation graph. Fix its parameters and expand it into a concrete graph before numerical calculation.

## 4. API research chat

### Configure a model

1. Choose **科研对话** (Research chat) → **模型设置** (Model settings).
2. Select the protocol, enter the service's base URL and actual model ID, and choose a key source if required.
3. Enter the model ID manually or use **获取模型列表** (Fetch models) where supported.
4. Select supported reasoning effort or **服务默认** (Service default).
5. Click **保存并启用** (Save and enable). Named profiles let you switch service/model/effort above the input area.

The client supports Responses and Chat Completions compatible formats. The service must accept the selected protocol and return the assistant's JSON decisions; other authentication/message formats can require adaptation.

Saving/loading/switching does not send a model request. Fetching models contacts the service; **测试连接** (Test connection) sends one diagnostic request that may be billed. Options depend on the service. Service default omits the reasoning parameter.

Provide credentials locally through temporary settings or the chosen environment variable. Keys are not saved in public configuration files. Do not put them in task text, source or shared logs. Closing the application or **断开并清除密钥** (Disconnect and clear keys) clears process-held credentials.

### Ask, inspect and continue

Example request:

> Compute the adjacency spectrum and diameter of the path on five vertices. Draw it, export TikZ, and bundle the results.

Send with the button or Ctrl+Enter; Enter inserts a line break. **插入图** (Insert graph) binds an explicit graph version. **先查看计划** (Review the plan first) allows plan inspection. Answer clarification questions in the same conversation.

Inspect actual tool arguments, status, verification and attachments; model prose is not execution evidence. Manual graphic exports beside a result execute locally without a new model request and remain subject to the tool budget.

Compose existing tools when sufficient. A missing algorithm requires clarification, an assessment and estimated consumption, then real user approval before separately packaged development. It cannot overwrite the base package.

### Budget and stopping

**预算与用量** (Budget and usage) shows cumulative limits and consumption. Monetary estimates require prices you provide. **停止** (Stop) cancels further scheduling and stops computation subprocesses; an already-sent model request can still wait for response or timeout.

Successful steps/history are preserved. Restart does not resend requests automatically; continuation requires user action. Model switching does not reset budgets or approvals.

For terminal use, run `python -m graph_research connect`. Configuration commands are listed by `python -m graph_research model --help`. See [API details — Chinese](API.md) for endpoint rules, environment variables and diagnostics.

## 5. MCP delegation from a host agent

### Configure this computer

Use the application's interpreter and short, writable state/result directories outside the installed package:

```powershell
.\.venv\Scripts\python.exe -m graph_research mcp-config --root D:/Research/agt-state --results-root D:/Research/agt-results --user researcher --max-tool-calls 15
```

The output contains STDIO transport, an absolute interpreter `command` and startup `args`. It does not edit host settings, connect the service or read credentials. Put command/arguments in the host's local MCP settings, with the wrapper required by that host.

The command accepts `--format codex` for TOML or `--format dsh` for a DeepSeek Harness plugin entry. Refresh/reconnect after saving. Usually the host starts the process; do not also start a second manual copy. Regenerate paths on each computer.

The service exposes **13 scheduling/integration tools**. The 43 computation tools are discovered through the catalog rather than individually expanding the host's tool list.

### First task

Ask the host:

> Use graph_research. Read the graph_invariants contract, then compute the diameter of the path on three vertices using existing tools. Do not invoke the research assistant's own model API.

The expected diameter is 2. The calling sequence is:

1. `research_catalog` retrieves the needed contract.
2. `research_submit` submits explicit steps and returns a `task_id`.
3. `research_get` queries the same task until completion or user interaction.
4. `research_inspect_result` / `research_read_artifact` retrieve full fields and registered files.

`queued`/`running` are not completed results. Keep the same task/request while waiting; retrying a request ID requires identical input. Use bindings to pass results between steps. Scan/batch workflows can group suitable repeated work.

### Models, limits and approval

Fixed tool tasks need no separate assistant API: the host interprets the request and delegates computation. The host's own model setup remains its responsibility.

`--max-tool-calls 15` is this service's per-task tool-attempt ceiling. Task constraints can lower it, not increase it. It is not a host-model token/call allowance. Failures can consume budget; reconnect/resume does not reset usage. Change startup limits and reconnect for subsequent work rather than assuming an existing task receives a fresh budget.

Enable `--allow-development` explicitly for host-requested new tools. Real-user approval through the trusted interface remains necessary; a model cannot approve itself. `--allow-agent` separately enables internal model planning and requires the assistant's model configuration; it is unnecessary for fixed tool tasks.

See [MCP](MCP.md), [batch workflows](BATCH.md) and [host protocol](reference/SUBAGENT.md), currently in Chinese, for schemas, user events and recovery. MCP discovery, protection and result handling add overhead; lower time/token use than direct Python is not guaranteed.

## 6. Results, memory, extensions and migration

### Results

**导出结果包** (Export result bundle) saves the conversation's calculations and registered artifacts up to that point. Export again after further work. Bundles can contain parameters, scientific data, receipts and image/TeX files. Check actual export status/content rather than relying on a filename.

Open **成果 → 成果中心** (Results → Result center) for project organization, snapshots, keep flags, cleanup previews and recovery. The window shows the actual result location; MCP can set `--results-root` explicitly.

Preview cleanup before confirming. Running or user/approval-waiting tasks cannot be cleaned. Recovery does not recompute or reset budgets. Calculation and export status are distinct. Back up important research separately.

### Memory

Use a stable user ID and the same memory location to reuse explicit preferences and successful tool-use counts. Preferences do not infer or override α, weights, tolerances or other scientific parameters. Current instructions take priority.

Research experience is extracted from verifiable execution records and reviewed before reuse. A historical case does not replace a fresh computation or proof; memory does not train the model. MCP memory/experience access is read-only; trusted user actions manage and review records.

### Extensions

Check existing tools/compositions first. A missing algorithm follows assessment, estimated consumption, user approval, protected validation and independent packaging. Experimental tools retain their validation limits when reused. New dependencies, UI or unrestricted Python beyond the restricted extension mechanism require manual development.

See [results/memory](RESULTS_AND_MEMORY.md) and [extension library](EXTENSIONS.md), currently in Chinese, for management commands and limits.

### Another computer

Reinstall Python/dependencies and regenerate model/MCP paths. Do not copy the old `.venv` instead. Transfer required result bundles, graph documents, memory and extension libraries separately; source packages contain neither personal research data nor credentials.

## 7. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Missing/wrong Python | Verify the interpreter; use `py -3.13 -m venv .venv` where appropriate |
| Installation failure | Keep the error and resolve it in the intended environment before launching |
| Launcher does not open | Check the project `.venv`; use the terminal launch command and `outputs/desktop/startup.log` |
| Version/source conflict | Run `doctor`, confirm the interpreter/directory and reinstall the intended source |
| Integrity mismatch | Restore verified source while preserving research data; do not reseal unexplained damage |
| Timeout/nonconvergence | Check tool limits, structured errors, algorithm parameters and verification; an unfinished value is not a conclusion |
| API authentication/model/effort error | Check URL, protocol, model ID, key and service-supported parameters; use Service default if appropriate |
| Missing MCP tools/timeout | Check absolute command path, dependencies and STDIO settings, then reconnect; a manual STDIO process waiting for input is normal |
| Missing Chinese glyphs in figures | Install a suitable font on the target computer and restart; fonts are not downloaded automatically |

After upgrades, restart desktop/reconnect MCP and refresh contracts. Report version/core fingerprint, a small reproducible input and redacted diagnostics to [Issues](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/issues).

## 8. Reference navigation

This English guide covers installation and the user workflows. Detailed parameter/topic manuals below are currently in Chinese. Tool IDs, JSON keys and parameter values remain unchanged.

| Reference | Content |
| --- | --- |
| [Features](FEATURES.md) | Capabilities, mathematical prerequisites and limits |
| [Inputs](OFFLINE_INPUTS.md) / [Tool contracts](model/TOOL_REFERENCE.md) | Formats, examples, outputs and effects |
| [Graphics](GRAPHICS.md) | Graph input, layout, TikZ and paper schematics |
| [API](API.md) / [MCP](MCP.md) / [Batch](BATCH.md) | Service setup, host integration and multi-case tasks |
| [Results and memory](RESULTS_AND_MEMORY.md) / [Extensions](EXTENSIONS.md) | Saved research, cleanup, preferences and governed development |
| [Numerical methods](NUMERICS.md) | High-α algorithms, diagnostics and exact tensor elimination |
| [Python interfaces](reference/PYTHON_API.md) | Library use outside desktop forms |
| [Development](DEVELOPMENT.md) / [Contributing](../CONTRIBUTING.md) | Environment, protection, checks and source export |
| [Current release](releases/CURRENT.md) | Delivered scope and recorded validation |
| [Provenance](provenance/README.md) / [Attribution](../NOTICE.md) | Migration records and author credits |

A complete Windows installer, full implicit 3D plotting and automatic TeX compilation are not included. Numerical outputs and finite extension test cases do not establish general theorems. Source-migration records are maintenance references, not a list of missing research capabilities.
