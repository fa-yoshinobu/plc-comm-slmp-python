# Self Multiple-CPU Target Shorthand

- Date: 2026-03-19
- Scope: `slmp_other_station_check.py` target parsing
- Purpose: add shorthand parsing for own-station multiple-CPU targets

## Change Summary

- Added `SELF-CPU1` through `SELF-CPU4` target shorthand.
- The shorthand resolves to `network=0x00` and `station=0xFF`.
- The shorthand also resolves `module_io` to `MULTIPLE_CPU_1` through `MULTIPLE_CPU_4` (`0x03E0` through `0x03E3`).
- Legacy five-field target input remains supported, and shorthand labels are validated against the numeric `module_io` value.

## Validation

| Check | Result | Detail |
|---|---|---|
| `python -m unittest tests.test_slmp.TestCodec.test_parse_named_target_self_cpu tests.test_slmp.TestCodec.test_parse_named_target_rejects_self_cpu_module_io_mismatch tests.test_slmp.TestCodec.test_load_named_targets_from_file -v` | PASS | verified shorthand parsing and module-I/O mismatch detection |
| `python -m ruff check slmp tests scripts` | PASS | no lint issues |

## Notes

- No live PLC validation was performed for this shorthand change.
- The shorthand is parser/CLI support only until live target-specific validation is recorded.
