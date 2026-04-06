
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/scripts/)

This folder contains thin wrappers around `slmp.cli`.

You can use either:

- `python scripts/<name>.py ...`
- the installed console entry point

Use [TESTING_GUIDE.md](../internal_docs/maintainer/TESTING_GUIDE.md) for when to run each script and [USER_GUIDE.md](../docsrc/user/USER_GUIDE.md) for API-side context.

## Start Here

If you only need a safe first check, use:

- `slmp_connection_check.py`
- `slmp_regression_suite.py`

If you need to validate unresolved behavior, use:

- `slmp_open_items_recheck.py`
- `slmp_pending_live_verification.py`
- `slmp_special_device_probe.py`
- `slmp_extended_device_device_recheck.py`
- `slmp_g_hg_extended_device_recheck.py`
- `slmp_g_hg_extended_device_coverage.py`
- `slmp_mixed_block_compare.py`

If you need human confirmation, use:

- `slmp_manual_write_verification.py`
- `slmp_manual_label_verification.py`

## Script List by Purpose

### Setup and housekeeping

- `slmp_regression_suite.py`
  - Run unit tests, `ruff`, `mypy`, and wrapper `--help` smoke checks in one command.
  - Optional safe live connection smoke check is available by flag.
- `slmp_compatibility_probe.py`
  - Run a structured compatibility probe and emit both Markdown and JSON results.
- `slmp_compatibility_matrix_render.py`
  - Render `internal_docs/validation/reports/PLC_COMPATIBILITY.md` from probe JSON files.
  - `--omit-pending-columns` is available when you want to hide command families that were not probed yet.
  - The same run also emits `internal_docs/validation/reports/compatibility_policy.json` for explicit compatibility-policy defaults.
- `slmp_init_model_docs.py`
  - Create `internal_docsrc/<series>_<model>/`.
- `slmp_device_access_matrix_sync.py`
  - Render `device_access_matrix.md` from `device_access_matrix.csv`.

### Safe connection and scope checks

- `slmp_connection_check.py`
  - Basic communication check and harmless command smoke test.
  - Loads `compatibility_policy.json` automatically when present; `--compatibility-policy` overrides it.
- `slmp_other_station_check.py`
  - Verify explicit target-header access to other network/station combinations.
  - Loads `compatibility_policy.json` automatically when present; `--compatibility-policy` overrides it.

### Rechecks for maintained open areas

- `slmp_open_items_recheck.py`
  - Re-run the current unresolved item set.
- `slmp_pending_live_verification.py`
  - Re-check maintained command families.
  - Current workflow excludes `1006 remote reset`.
- `slmp_special_device_probe.py`
  - Focused recheck for `G/HG` and `LT/LST` related paths.
- `slmp_extended_device_device_recheck.py`
  - Generic Extended Specification word-device read-write-readback with restore for qualified devices such as `U01\G22`.
- `slmp_g_hg_extended_device_recheck.py`
  - Focused Extended Specification `G10` / `HG20` read-write-readback with restore and frame dumps.
- `slmp_g_hg_extended_device_coverage.py`
  - Sweep qualified `G/HG` Extended Specification devices across addresses and point counts, with optional temporary write/readback/restore.
  - Supports repeated `--transport` and named `--target` entries for broader live coverage in one report.
- `slmp_mixed_block_compare.py`
  - Checklist-oriented live compare for word-only, bit-only, and mixed `0406/1406` block access.

### Human-in-the-loop verification

- `slmp_manual_write_verification.py`
  - Temporary write/restore check for representative devices from the matrix.
- `slmp_manual_label_verification.py`
  - Temporary write/restore check for explicitly named labels.

### Automated write/read/restore probes

- `slmp_supported_device_rw_probe.py`
  - Automated probe across currently supported writable device families.

### Boundary and range probes

- `slmp_device_range_probe.py`
  - Probe configured device-family upper boundaries.
- `slmp_register_boundary_probe.py`
  - Probe focused register-boundary edge cases.

### Load and performance

- `slmp_read_soak.py`
  - Repeated single-command read soak.
- `slmp_mixed_read_load.py`
  - Mixed `0401` / `0403` / `0406` load.
- `slmp_tcp_concurrency.py`
  - Practical multi-client TCP concurrency test.

## Notes

- Most scripts write a `*_latest.md` report under `internal_docsrc/<series>_<model>/`.
- Interactive scripts temporarily change PLC values; read [TESTING.md](../TESTING.md) first.
- Packet captures and raw communication logs are local-only and must not be committed.




