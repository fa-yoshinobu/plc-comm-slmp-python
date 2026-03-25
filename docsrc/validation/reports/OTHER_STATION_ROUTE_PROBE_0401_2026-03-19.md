# Other-Station Route Probe 0401

- Date: 2026-03-19
- Scope: `slmp_other_station_check.py`
- Purpose: remove `0101` from the other-station path, use `0401` only for route verification, and probe `3E/4E` when frame auto is enabled

## Change Summary

- `other_station_check` no longer calls `read_type_name()`.
- The target check now relies on `0401` device read only.
- With `--series auto`, the check retries `ql` then `iqr` until one route read succeeds.
- With `--frame-type auto`, the check tries `3E` and `4E` as needed.
- The report output falls back to the first successful series when `--output` is not specified.

## Validation

| Check | Result | Detail |
|---|---|---|
| `python -m unittest tests.test_slmp.TestCli.test_other_station_check_main_auto_series_and_frame_uses_route_probe -v` | PASS | verified no `0101` call and `ql/iqr` plus `3E/4E` fallback |
| `python scripts/slmp_other_station_check.py --help` | PASS | CLI help reflects route-probe behavior |
| `python -m ruff check slmp tests scripts` | PASS | no lint issues |

## Notes

- No live PLC was used for this verification.
