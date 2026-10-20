# Source release notes · 2026-10-20

- Project: Algebraic Graph Theory Research Assistant / 代数图论科研助手.
- Version: **0.36.0rc4**, research pre-release; license: **MIT**. Original attribution and migration records are retained. See [LICENSE](LICENSE), [NOTICE](NOTICE.md) and [permission status](LICENSE-STATUS.md).
- Start with the [English quick start](docs/QUICKSTART.md), [中文使用指南](使用指南.md) and [workflow diagrams](docs/WORKFLOW.md).
- The source includes 43 native tools, desktop offline/API modes, MCP delegation, protected execution, graph drawing/layout/TikZ, result bundles and governed extensions. See [release notes](RELEASE_0.36.0rc4.md) for scope and limits.
- No SageMath or WSL is required. Python 3.11+ is required; complete desktop/protected workflows are validated on Windows. The source .exe uses an existing project Python environment; it is not a bundled installer.
- Clean exports exclude private Git history, local environments, credentials, personal results, user memory and installed experimental packages. Migration documentation remains under docs/provenance; the old executable Sage bridge and lookup tool are absent.
- SOURCE_MANIFEST.json records per-file SHA256; release assets have checksums. After installation run doctor, pip check and protect check in the chosen environment.
- API tests use simulated clients unless explicitly stated otherwise. Local tests do not verify every remote service, graph family or platform. MCP adds execution/orchestration overhead; lower time/token use than direct Python is not guaranteed.
- After upgrading, reopen the desktop or reconnect MCP and refresh changed contracts. Retain user approvals and task budgets; do not automatically replay old unfinished tasks.

Previous rc1/rc2 archives remain historical artifacts. This release's source, license metadata and core fingerprint identify v0.36.0rc4.
