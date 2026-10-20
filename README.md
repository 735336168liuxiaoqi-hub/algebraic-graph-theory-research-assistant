# Algebraic Graph Theory Research Assistant

**代数图论科研助手** — native Python tools for graph and hypergraph spectra, symbolic computation and research visualization.

> **MIT licensed · v0.36.0rc4 pre-release.** Original-code publication permission and the MIT license selection were confirmed by the project owner on 2026-10-20. See [LICENSE](LICENSE), [attribution](NOTICE.md) and the [permission record](LICENSE-STATUS.md).

The repository may be private during preparation; package downloads require an authorized GitHub account.

## Download and start

**Recommended: [download the source runtime ZIP](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/algebraic-graph-theory-research-assistant-0.36.0rc4-source-candidate.zip).** It contains the desktop launcher and application source. Windows and 64-bit Python 3.11+ are required for the validated complete application; Python 3.13 is recommended.

| Download | Use |
| --- | --- |
| [Source runtime ZIP](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/algebraic-graph-theory-research-assistant-0.36.0rc4-source-candidate.zip) | Extract, install dependencies and launch with the commands below |
| [Python wheel](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/download/v0.36.0rc4/graph_research_assistant-0.36.0rc4-py3-none-any.whl) | Install into an existing Python/Conda environment using pip |
| [Release page and all assets](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant/releases/tag/v0.36.0rc4) | Expand Assets for packages, checksums and validation details |

Extract the ZIP, open PowerShell **inside the folder containing pyproject.toml and start-desktop.cmd**, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[all]"
.\.venv\Scripts\python.exe -m graph_research desktop
```

Choose **本地工具** in the desktop for offline tools without a model API. The first installation downloads dependencies. Later, double-click start-desktop.cmd or the source-tree .exe in the same folder. Keep the entire folder: the launcher uses the project's .venv.

See the [English quick start](docs/QUICKSTART.md) or [中文安装指南](使用指南.md) for wheel/Conda installation and the three modes. These packages use an existing Python installation; the .exe is a launcher.

## Research capabilities

| Area | Capabilities |
| --- | --- |
| Graphs | Construction, structure transformations, symmetry, quotient matrices, numerical spectra, exact characteristic and matching polynomials, energy and weighted/directed matrices |
| Uniform hypergraphs | α-spectral radius, Perron vectors, weighted incidence matrices, tensor eigen-equations and bounded exact characteristic-polynomial elimination |
| Symbolic research | Recurrences, integer linear systems, block matrices, finite permutation groups, Cayley graphs, symbolic sums/series and rook polynomials |
| Visualization | Graph/hypergraph drawings, draggable layouts, saved coordinates, PNG/SVG/PDF, TikZ and symbolic paper diagrams |
| Workflows | Batch computations, verified result bundles, optional API chat, governed extension development, user memory and MCP delegation |

The desktop and model interfaces share **43 built-in tools and 238 parameter descriptions**. The old-code lookup tool and Sage bridge are removed. Source migration records remain in [docs/provenance](docs/provenance/README.md), outside the runtime package.

Use [functional coverage](FUNCTIONAL_COVERAGE.md) and individual tool contracts for mathematical assumptions and size limits. Tensor computations concern uniform hypergraphs; general hypergraph structure drawings can be non-uniform.

## Workflow

Choose local tools for manual computation, API chat for natural-language research, or MCP for delegation from a host agent. All three use the same protected local computation core and preserve execution records and result artifacts.

![Workflow overview](docs/diagrams/workflow-overview-en.svg)

[Detailed workflow diagrams and usage paths (中文)](docs/WORKFLOW.md) cover API planning, asynchronous MCP tasks, user interaction and separate extension development. These diagrams describe the current implementation; performance improvements discussed after the A/B trial remain future work.

## Run locally

Python 3.11 or newer is required. The native desktop and protected computation workflows are currently validated on Windows. SageMath, WSL and a model API are not required for local tools.

From an extracted source candidate, use a dedicated environment or your own activated Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[all]"
.\.venv\Scripts\python.exe -m graph_research desktop
```

For a Python library installation, use `python -m pip install .`. Optional extras are `visual`, `tools`, `desktop`, `assistant` and `mcp`; `all` installs all application dependencies. The repository's small `.exe` launcher uses an existing Python environment; this is not a bundled Windows installer.

The desktop has local classified tools and optional API conversation modes. Every tool has Chinese parameter help and examples. Model settings are configured locally; do not commit API keys.

- [English installation and three-mode quick start](docs/QUICKSTART.md)
- [中文说明](README.zh-CN.md)
- [Installation and three-mode user guide (Chinese)](使用指南.md)
- [Environment selection](ENVIRONMENT.md)
- [Desktop](DESKTOP_APP.md) and [tool inputs](docs/OFFLINE_INPUTS.md)
- [Python capability entries](LIBRARY_ENTRIES.md)
- [API setup](API_SETUP.md) and [model settings](MODEL_SELECTION.md)
- [MCP integration](MCP_INTEGRATION.md): Codex, DeepSeek Harness and other compatible hosts can delegate calculations without a separate assistant API key.

## Reproduce a computation

```powershell
.\.venv\Scripts\python.exe -m graph_research call graph_spectrum '{"kind":"path","n":5}'
```

Model-facing calls use documented tools, explicit data and bounded execution. Results contain reusable graph descriptions, coordinates and evidence. Batch steps pass values through bindings rather than executable expressions. Mathematical and runtime limits are described in the [tool reference](docs/model/TOOL_REFERENCE.md).

## Development and verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -X utf8 tools/checks.py --full --strict-lock
```

Core changes require maintainer review and a new integrity inventory. Do not regenerate the inventory to conceal corruption. [Protection and recovery](PROTECTION.md) cover the execution model.

## Research and performance limits

This is a pre-release for evaluation and research use. Uniform-hypergraph tensor tools enforce their documented assumptions and size limits; numerical output and tested extension examples are not general mathematical proofs. MCP delegation includes discovery, protected execution, result transport and artifact handling; lower latency or model-token use than direct Python is not guaranteed.

The native desktop and protected execution are validated on Windows. A complete Windows installer, full implicit 3D plotting and automatic TeX compilation are outside this release. Generating TeX source does not require TeX; compiling it does.

## Release and contribution

The project repository is [algebraic-graph-theory-research-assistant](https://github.com/735336168liuxiaoqi-hub/algebraic-graph-theory-research-assistant). The reviewed source is released under the [MIT License](LICENSE), with original attribution and migration records retained. Third-party dependencies keep their upstream licenses and are installed separately.

Read the [v0.36.0rc4 release notes](RELEASE_0.36.0rc4.md), [workflow guide](docs/WORKFLOW.md) and [contribution guide](CONTRIBUTING.md). Issues should include the observed version, relevant core fingerprint, a small reproducible input and redacted diagnostics. Keep credentials, private research, local environments and personal state out of submissions.
