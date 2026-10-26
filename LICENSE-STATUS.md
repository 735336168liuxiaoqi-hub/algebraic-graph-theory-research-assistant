# License and publication status

The project owner confirmed permission to publicly redistribute the supplied research source and its adaptations on **2026-10-20**, and selected the **MIT License** for that release where the authorization permits choosing a license. On **2026-10-26** the owner selected the **Apache License 2.0** for the project as a whole.

The project is [Apache-2.0 licensed](LICENSE). The machine-readable owner-confirmed publication record is [docs/provenance/rights-status.json](docs/provenance/rights-status.json). This records the owner's declaration; private authorization correspondence is not included in the repository.

The supplied **Haiying Shan** files keep the MIT redistribution terms recorded for them in [docs/provenance/rights-status.json](docs/provenance/rights-status.json). MIT permits inclusion in an Apache-2.0 work, so the project-wide grant neither revokes nor narrows them. The original copyright attribution remains in [NOTICE.md](NOTICE.md) and the migration records. Removing an old runtime module does not remove those acknowledgments or adaptation history.

Third-party dependencies retain their own licenses. The project's Apache-2.0 grant does not relicense Python, Qt/PySide6, NumPy, NetworkX, SymPy, Matplotlib, LangGraph, HTTPX, jsonschema, the MCP SDK or their dependencies. Source and wheel releases install these separately rather than bundling an entire Python runtime.

`python tools/check_public_release.py` verifies that the confirmed publication record, project metadata and actual LICENSE agree before publication. Changes to the permission basis or license must update these records together and retain required attribution.
