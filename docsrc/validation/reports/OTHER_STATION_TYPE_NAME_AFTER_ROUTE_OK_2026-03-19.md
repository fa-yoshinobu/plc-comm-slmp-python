# Other-Station Type Name After Route Success

- Date: 2026-03-19
- Scope: `slmp_other_station_check.py`
- Purpose: keep `0401` as the route verification gate, then attempt `read_type_name()` only after the route succeeds

## Change Summary

- `other_station_check` still uses `0401` device read as the success criterion for route verification.
- After a successful route probe, the tool now attempts `read_type_name()` on the resolved frame/series/target path.
- `read_type_name()` results are reported as `model` and `model_code` when available.
- A `read_type_name()` failure is reported as supplemental information and does not turn a successful route probe into `NG`.
- Default report output now uses the resolved type-name identity when available instead of forcing `unknown_target`.

## Validation

| Check | Result | Detail |
|---|---|---|
| `python -m unittest tests.test_slmp.TestCli.test_other_station_check_main_auto_series_and_frame_uses_route_probe tests.test_slmp.TestCli.test_other_station_check_main_type_name_failure_is_nonfatal -v` | PASS | verified post-success `read_type_name()` attempt and non-fatal failure handling |
| `python -m ruff check slmp tests scripts` | PASS | no lint issues |

## Notes

- No live PLC was used for this verification.
