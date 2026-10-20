# v0.36.0rc3 release validation

Completed: 2026-10-20. Windows, Python 3.13.9, MIT license.

## Results

- Full suite: **693 collected and started; 692 passed, 1 skipped, zero failures/errors/not-run**.
- Skipped: the host does not allow unprivileged symlink creation for the managed-result cleanup test. This is not counted as a pass.
- Tests: 911.523s. Complete gate: 921.074s.
- Doctor, pip dependency checks, strict dependency lock, Ruff, 199-file core integrity, generated documentation and git diff checks passed.
- Source did not change during execution. Test-ID list SHA256: 414983a92cc47eb39eb6894ad912ea889519de2e5169b2817780d08a6968158e.
- Core manifest SHA256: a44e4e2c95fbb62c542714b7082f203d2d992d3a6509a78eb5313517d5008b6a.
- The wheel was verified from a separate extracted installation: math, plots, desktop forms, simulated API adapters, real STDIO MCP, pause/resume, batches, memory and independent extensions passed. It contains the MIT license and original attribution notice.
- Export audit found no credential patterns or remaining personal user-home paths in selected source text; public documentation link targets exist.

## Reproduce and interpret

Run `python -X utf8 tools/checks.py --full --strict-lock` in the declared Windows development environment. Then run tools/build_release.py and tools/verify_release.py. Commands use local/mock model clients and do not bill model providers.

The full suite was run on the maintainer tree. The clean export preserves the tested application core byte-for-byte and carries its own SOURCE_MANIFEST.json; private research scripts/results/history/environments are excluded. The worktree-wide fingerprint is not the checksum of the downloadable source archive. Verify release asset SHA256SUMS and the source manifest for the exact delivered files.

An earlier partial run was stopped before correcting the setuptools minimum required for SPDX/PEP639 metadata; it is not counted in these results. Only the final run is summarized here. The source uses setuptools>=77 with the locked release check environment.

Real third-party model service compatibility, all graph families/scales and clean-machine dependency downloads are not implied by this run. Numerical results are not general proofs. The earlier A/B performance optimizations remain deferred.
