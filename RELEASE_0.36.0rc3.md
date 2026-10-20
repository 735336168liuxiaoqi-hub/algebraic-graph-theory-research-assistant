# v0.36.0rc3 · First public pre-release

Algebraic Graph Theory Research Assistant is released under the **MIT License** following the project owner's publication-permission confirmation on 2026-10-20. Original attribution and the source migration record are retained.

## Included

- **43 built-in tools**, shared by desktop/model interfaces, Chinese explanations and 238 top-level parameter descriptions.
- Local classified tools, optional API research chat and STDIO MCP delegation without a separate assistant API in default tools mode.
- Graph and uniform-hypergraph spectra, bounded exact/symbolic computation, drawing, draggable layouts, TikZ and paper-style schematic figures.
- Direction/weight/label/style-preserving export, graph/hypergraph TeX naming, multi-graph results and saved coordinates.
- MCP interaction fixes: explicit operation errors, stable repeated cancellation, cumulative/request/job accounting, service/core identification and field-level validation.
- Execution evidence, result bundles, user-scoped memory/reviewed experience, and independently assessed/approved extension packages.
- English/Chinese entry documentation, three-mode quick starts, four Chinese workflow diagrams and an English overview in SVG/PNG/Mermaid.

This release carries the current implementation. Performance changes proposed after the external A/B trial are **not implemented** here.

## Install and verify

Download the source ZIP or clone the repository, create a Python 3.11+ environment, install `.[all]` and launch `python -m graph_research desktop`. See [English quick start](docs/QUICKSTART.md) and [中文使用指南](使用指南.md).

The wheel installs into an existing Python environment. The source-tree .exe is a launcher, not a bundled Windows installer. Python and third-party environments are not included.

The preceding implementation passed 691 tests with one Windows symlink-permission skip. This release additionally updates version/license/publication metadata and documentation; its final validation is recorded in [release validation](docs/RELEASE_VALIDATION_0.36.0rc3.md).

## Limits

Complete native desktop/protected workflows are currently validated on Windows. Tensor spectra/characteristic polynomials concern uniform hypergraphs and enforce documented assumptions/size limits; non-uniform hypergraph structure drawing is supported. Numerical results and extension fixtures do not prove general mathematical claims.

MCP includes discovery, protected workers, transport and artifact handling, and does not guarantee lower latency, tokens or cost than direct Python. Full implicit 3D rendering, automatic TeX compilation and a bundled Windows installer remain outside this release. Generating TeX source needs no TeX installation; compiling it requires a separately installed environment.

[MIT License](LICENSE) · [Attribution](NOTICE.md) · [Permission record](LICENSE-STATUS.md). Dependencies retain their own licenses. Private environments, results, credentials, user memory and original Git history are excluded from the independent public source repository.
