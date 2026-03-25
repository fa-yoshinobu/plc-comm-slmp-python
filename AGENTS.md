# Agent Guide: SLMP Python (slmp)

This repository is part of the PLC Communication Workspace and follows the global standards defined in `D:\PLC_COMM_PROJ\AGENTS.md`.

## 1. Project-Specific Context
- **Protocol**: SLMP (Seamless Message Protocol)
- **Authoritative Source**: Mitsubishi Electric specifications.
- **Language**: Python (3.11+)
- **Role**: Core Communication Library (Binary 3E/4E frames).

## 2. Mandatory Rules (Global Standards)
- **Language**: All code, comments, and documentation MUST be in **English**.
- **Encoding**: Use **UTF-8 (without BOM)** for all files to prevent Mojibake.
- **Mandatory Static Analysis**:
  - All changes must pass `ruff` (linting/formatting) and `mypy` (type checking).
  - Use `ruff check .` and `ruff format .` before committing.
- **Documentation Structure**: Follow the Modern Documentation Policy:
  - `docsrc/user/`: User manuals and API guides. [DIST]
  - `docsrc/maintainer/`: Protocol specs and internal logic. [REPO]
  - `docsrc/validation/`: Hardware QA reports and bug analysis. [REPO]
- **Distribution Control**: Ensure `pyproject.toml` excludes `docsrc/maintainer/`, `docsrc/validation/`, `tests/`, `scripts/`, and `TODO.md` from PyPI/Wheel packages.

## 3. Reference Materials
- **Official Specs**: Refer to `internal_reference_library/CLPA_DOWNLOAD_.../` for authoritative English manuals (Local only).
- **Evidence**: Check `docsrc/validation/reports/` for verified communication results.

## 4. Documentation Standards
- **Docstrings**: Use **Google Style** docstrings for all functions and classes.
- **Auto-Generation**: Documentation is generated using `MkDocs` and `mkdocstrings`.
- **Build**: Use `build_docs.bat` to generate the HTML site in `publish/docsrc/`.

## 5. Development Workflow
- **Issue Tracking**: Log remaining tasks in `TODO.md`.
- **Change Tracking**: Update `CHANGELOG.md` for every fix or feature.
- **QA Requirement**: Every hardware-related fix must include an evidence report in `docsrc/validation/reports/`.

## 6. API Naming Policy

Detailed naming policy lives in `docsrc/maintainer/API_UNIFICATION_POLICY.md`.

Public API rules:

- Canonical low-level class names are `SlmpClient` and `AsyncSlmpClient`.
- If a separate string-address facade is ever added, reserve `SlmpDeviceClient` and `AsyncSlmpDeviceClient` for that layer instead of renaming the protocol-oriented client.
- Keep direct device access explicit with names such as `read_devices`, `write_devices`, `read_random`, and `read_block`.
- Keep 32-bit helpers explicit with names such as `read_dword`, `write_dword`, `read_dwords`, `write_dwords`, `read_float32`, and `write_float32`.
- Prefer clear English names for monitor, label, and remote-control helpers even when the raw SLMP spec wording is more awkward.
- Sync and async clients must keep the same base method names.

Canonical specialized names:

- `register_monitor_devices`
- `register_monitor_devices_ext`
- `run_monitor_cycle`
- `read_array_labels`
- `write_array_labels`
- `read_random_labels`
- `write_random_labels`
- `remote_run`
- `remote_stop`
- `remote_pause`
- `remote_latch_clear`
- `remote_reset`
- `remote_password_unlock`
- `remote_password_lock`
- 32-bit codec helpers should include both type and word order, for example `pack_uint32_low_word_first` or `unpack_float32_low_word_first`


