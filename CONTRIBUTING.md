# Contributing

## Report a reproducible issue

Include the package version/core fingerprint, OS/Python version, selected tool, small synthetic input, actual error/result and expected mathematical definition. Remove credentials, private data and personal paths from logs. Distinguish numerical failure, unsupported input, incomplete export and host/API integration issues; requested tolerance alone is not an error certificate.

## Prepare a change

Use a dedicated environment and read [environment guidance](docs/DEVELOPMENT.md), [workflow](docs/WORKFLOW.md), [tool contracts](docs/model/TOOL_REFERENCE.md) and [protection](docs/DEVELOPMENT.md). Preserve graph identities, mathematical semantics, task budgets, approvals and separate extension packages.

Add a meaningful regression for changed behavior. Update contracts, parameter help and generated manuals together. Keep tests/gates.json synchronized with test modules.

```powershell
python -m pip install -r requirements-lock.txt -r requirements-dev.txt
python -m pip install --no-deps --no-build-isolation -e .
python -X utf8 tools/checks.py --full --strict-lock
```

Intentional core changes require maintainer review and an updated integrity inventory through tools/seal_release.py, followed by checks. Do not regenerate a manifest to hide corruption. Tests use simulated model clients; do not call paid services without an explicit test scope.

Explain the concrete problem, resulting behavior and validation in pull requests. Keep unrelated refactors, personal outputs, environments and secrets out of commits. Contributions use the project's [MIT License](LICENSE), retaining applicable attribution.
