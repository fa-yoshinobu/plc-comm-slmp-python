# Connection Check and Other-Station Series Auto

- Date: 2026-03-19
- Scope: `slmp_connection_check.py`, `slmp_other_station_check.py`
- Purpose: add `--series auto` and keep the other-station path on route-probe selection

## Change Summary

- `--series auto` is now accepted by the connection check and other-station check entry points.
- Connection check probes `SM400` and uses the first series candidate that succeeds.
- When `4E` is used, `read_type_name()` still runs automatically and can refine the resolved family.
- Other-station check now probes `0401` only and selects the first successful `frame/series` combination.

## Validation

| Check | Result | Detail |
|---|---|---|
| `python -m unittest tests.test_slmp.TestCli.test_connection_check_main_selects_frame_type tests.test_slmp.TestCli.test_connection_check_main_auto_series_uses_smoke_probe tests.test_slmp.TestCli.test_other_station_check_main_auto_series_and_frame_uses_route_probe -v` | PASS | verified `series auto` for both paths |
| `python scripts/slmp_connection_check.py --help` | PASS | CLI help shows `--series {auto,ql,iqr}` |
| `python scripts/slmp_other_station_check.py --help` | PASS | CLI help shows `--series {auto,ql,iqr}` |
| `python -m ruff check slmp tests scripts` | PASS | no lint issues |

## Notes

- No live PLC was used for this verification.
