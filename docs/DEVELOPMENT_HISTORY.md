# Development History

## 2026-06-11 Archived Refactor Plan

The previous `refactor-instructions.md` was archived into this history file.

### Scope

- Library: Python SLMP package, published as `slmp-connect-python`.
- Primary task: add sync/async wire-parity tests, then reduce duplicated logic in `client.py`, `async_client.py`, and selected `utils.py` helper pairs.
- CLI module splitting was proposal-only and required separate approval.

### Contracts To Preserve

- Public exports from `slmp/__init__.py` and public modules such as `slmp.client`, `slmp.async_client`, `slmp.utils`, and `slmp.spec`.
- Exact transmitted frame bytes for all commands.
- All 13 console-script entry points in `pyproject.toml`.
- Existing warnings, exception types, and exception messages.
- Dependency-free runtime metadata, package version, and changelog.
- Documented protocol semantics, including device path warnings, bit semantics, boundary behavior, and semantic atomicity.

### Debt Notes

- D1: sync/async wire parity lacked a direct safety net.
- D2: roughly 60 command methods were duplicated between sync and async clients.
- D3: several `utils.py` async/sync helper pairs duplicated branching logic.
- D4: `cli.py` was large and multi-purpose, but implementation was out of scope.
- D5: version mismatch was noted as report-only.

### Planned Verification

- Record baseline lint, type, and pytest results.
- Add mock-transport parity tests for command groups, comparing sync and async output without choosing which side is correct.
- Extract request building and response parsing into shared pure functions one command group at a time.
- Reduce `utils.py` helper duplication after client parity work.
- Run all tests, parity tests, mypy, and ruff after each group.

### Out Of Scope

- Public API, module-path, console-script, frame-byte, warning, or exception-message changes.
- Dependency, version, changelog, release, PyInstaller, or real PLC verification work.
