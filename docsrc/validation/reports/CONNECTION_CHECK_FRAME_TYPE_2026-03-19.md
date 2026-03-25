# Connection Check Frame Type Update

- Date: 2026-03-19
- Scope: `slmp_connection_check.py` / `connection_check_main`
- Purpose: add explicit frame selection for the connection check and make `ql` default to `3e`

## Change Summary

- Added `--frame-type {auto,3e,4e}` to the connection check CLI.
- `auto` now resolves to `3e` for `series=ql` and `4e` for `series=iqr`.
- The connection check prints the resolved frame and passes it to `SlmpClient`.
- Updated user and maintainer docs to mention the Q-series `3e` path.

## Validation

| Check | Result | Detail |
|---|---|---|
| `python -m unittest tests.test_slmp.TestCli.test_connection_check_main_selects_frame_type -v` | PASS | verified `ql -> 3e` and explicit `4e` override |
| `python scripts/slmp_connection_check.py --help` | PASS | help shows `--frame-type {auto,3e,4e}` |
| `python -m ruff check slmp tests scripts` | PASS | no lint issues |

## Notes

- No live PLC was used for this verification.
- The change is intentionally scoped to the connection check CLI; other CLI entry points were left unchanged.
