# License and publication status

The project owner confirmed permission to publicly redistribute the supplied research source and its adaptations on **2026-10-20**, and explicitly selected the **MIT License** where the authorization permits choosing a license.

The project is [MIT licensed](LICENSE). The machine-readable owner-confirmed publication record is [docs/provenance/rights-status.json](docs/provenance/rights-status.json). This records the owner's declaration; private authorization correspondence is not included in the repository.

The original **Haiying Shan** copyright attribution remains in [NOTICE.md](NOTICE.md) and the migration records. Removing an old runtime module does not remove those acknowledgments or adaptation history.

Third-party dependencies retain their own licenses. The project's MIT grant does not relicense Python, Qt/PySide6, NumPy, NetworkX, SymPy, Matplotlib, LangGraph, HTTPX, jsonschema, the MCP SDK or their dependencies. Source and wheel releases install these separately rather than bundling an entire Python runtime.

`python tools/check_public_release.py` verifies that the confirmed publication record, project metadata and actual LICENSE agree before publication. Changes to the permission basis or license must update these records together and retain required attribution.
