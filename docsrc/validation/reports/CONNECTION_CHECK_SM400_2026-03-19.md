# Connection Check SM400 Smoke Test

- Date: 2026-03-19
- Scope: `slmp_connection_check.py`
- Purpose: replace the initial `0101 type name` probe with a `SM400` bit read for Q-series internal ports that reject `read_type_name()`

## Change Summary

- The connection check now starts with `SM400` bit read at `0401`.
- `read_type_name()` is no longer required for the connection check path.
- `--frame-type auto` still resolves to `3e` for `series=ql` and `4e` for `series=iqr`.

## Validation

| Check | Result | Detail |
|---|---|---|
| `python -m unittest tests.test_slmp.TestCli.test_connection_check_main_selects_frame_type -v` | PASS | verified `SM400` is read first for both `3e` and `4e` paths |
| `python scripts/slmp_connection_check.py --help` | PASS | CLI help reflects `--frame-type {auto,3e,4e}` |
| `python -m ruff check slmp tests scripts` | PASS | no lint issues |

## Notes

- No live PLC was used during this verification.
- The connection check still accepts an optional `--read-device` follow-up probe after the `SM400` smoke read.
