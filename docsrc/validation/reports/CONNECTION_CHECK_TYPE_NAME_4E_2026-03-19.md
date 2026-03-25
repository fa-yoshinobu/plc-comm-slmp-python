# Connection Check Type Name on 4E

- Date: 2026-03-19
- Scope: `slmp_connection_check.py`
- Purpose: auto-attempt `read_type_name()` only on `4E` while keeping `SM400` as the universal smoke check

## Change Summary

- `SM400` bit read remains the first smoke check for all frame types.
- `read_type_name()` is now attempted automatically only when the resolved frame type is `4E`.
- If `read_type_name()` fails, the connection check continues instead of failing the whole run.
- `model_code` is the primary identifier, and the code falls back to the returned `model` text when the local lookup table does not contain a match.

## Validation

| Check | Result | Detail |
|---|---|---|
| `python -m unittest tests.test_slmp.TestCli.test_connection_check_main_selects_frame_type -v` | PASS | verified `3E` skips type name and `4E` attempts it |
| `python scripts/slmp_connection_check.py --help` | PASS | CLI help still shows `--frame-type {auto,3e,4e}` |
| `python -m ruff check slmp tests scripts` | PASS | no lint issues |

## Notes

- No live PLC was used for this verification.
- This keeps `Q26UDEHCPU` usable with `SM400` even when `0101` is rejected on that endpoint.
