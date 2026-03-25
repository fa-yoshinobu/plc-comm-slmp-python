# Compatibility Policy Auto-Detection Validation

- Date: 2026-03-19
- Scope: generate `compatibility_policy.json` from probe JSON files and use that policy in auto-detection paths
- Live PLC execution: not performed in this validation step

## Changes

- Added structured policy generation to `slmp.cli.compatibility_matrix_render_main()`
- Added `--policy-output` to `scripts/slmp_compatibility_matrix_render.py`
- Added automatic policy loading to `slmp.cli.connection_check_main()`
- Added automatic policy loading to `slmp.cli.other_station_check_main()`
- Added `--compatibility-policy` overrides to `scripts/slmp_connection_check.py` and `scripts/slmp_other_station_check.py`
- Added `detected_family` reporting for successful type-name reads in other-station checks
- Updated docs to describe policy generation and policy-driven auto ordering

## Local Verification

```powershell
python -m unittest tests.test_slmp.TestCodec.test_build_compatibility_policy_prefers_family_profiles tests.test_slmp.TestCli.test_connection_check_main_selects_frame_type tests.test_slmp.TestCli.test_connection_check_main_auto_series_uses_smoke_probe tests.test_slmp.TestCli.test_connection_check_main_uses_compatibility_policy_order tests.test_slmp.TestCli.test_other_station_check_main_auto_series_and_frame_uses_route_probe tests.test_slmp.TestCli.test_other_station_check_main_type_name_failure_is_nonfatal tests.test_slmp.TestCli.test_other_station_check_main_adds_practical_note_for_ql_other_station_failures tests.test_slmp.TestCli.test_other_station_check_main_uses_compatibility_policy_order tests.test_slmp.TestCli.test_compatibility_matrix_render_main_renders_output -v
python -m ruff check slmp tests scripts
python -m mypy slmp scripts
```

## Result

- Targeted unit coverage passed for policy generation, connection auto ordering, other-station auto ordering, and matrix sidecar output.
- `ruff` passed for `slmp`, `tests`, and `scripts`.
- `mypy` passed for `slmp` and `scripts`.

## Practical Notes

- Policy-driven auto ordering only changes the attempt order; it does not persist live decisions across runs.
- `access_profile` remains the route-probe encoding that succeeded first.
- `detected_family` comes from `read_type_name()` and is only available when that command succeeds on the resolved path.
