# G/HG Extended Specification Coverage Expansion Tooling

- Date: 2026-03-19
- Scope: broaden the dedicated `G/HG` Extended Specification coverage sweep so it can exercise more transports and named target paths in one run
- Live PLC execution: not performed in this validation step

## Changes

- Extended `slmp.cli.g_hg_extended_device_coverage_main()` to accept repeated `--transport`
- Added named target support via `--target` and `--target-file`
- Made `read_type_name()` non-fatal for the coverage sweep so Q-like paths can still be recorded
- Kept the existing address/point/direct-memory sweep behavior unchanged for single-target runs
- Updated user and maintainer docs for the expanded coverage workflow

## Local Verification

```powershell
python -m unittest tests.test_slmp.TestDeviceApi.test_g_hg_extended_device_coverage_main_read_only tests.test_slmp.TestDeviceApi.test_g_hg_extended_device_coverage_main_write_check_restores_values tests.test_slmp.TestDeviceApi.test_g_hg_extended_device_coverage_main_handles_multiple_transports_and_targets tests.test_slmp.TestDeviceApi.test_g_hg_extended_device_coverage_main_type_name_failure_is_nonfatal -v
python -m ruff check slmp tests scripts
python -m mypy slmp scripts
python scripts/slmp_g_hg_extended_device_coverage.py --help
```

## Result

- Targeted unit coverage passed for the original single-target sweep, the write/restore path, the new transport/target matrix flow, and type-name failure tolerance.
- `ruff` passed for `slmp`, `tests`, and `scripts`.
- `mypy` passed for `slmp` and `scripts`.
- Wrapper help passed.

## Practical Notes

- This change expands the tooling only. It does not claim new hardware compatibility results by itself.
- Use explicit named targets such as `SELF`, `SELF-CPU1`, or `NW1-ST2` when you want one report to compare multiple Extended Specification routes.
- Keep using explicit output paths if you want transport- or target-specific reports instead of one aggregated sweep.

