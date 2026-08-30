# TODO

Current active TODOs only.

## Current Status

### SLMP-PYTHON-TODO-1: Remove unused Memory / Extend Unit functions from the public API

Status: `approved`. Complete this public API cleanup in the next release. There are no users of these methods, so no compatibility alias or migration path is required.

- [ ] Remove the following methods from both `SlmpClient` and `AsyncSlmpClient` (20 public callables total):
  - `memory_read_words`
  - `memory_write_words`
  - `extend_unit_read_bytes`
  - `extend_unit_read_words`
  - `extend_unit_read_word`
  - `extend_unit_read_dword`
  - `extend_unit_write_bytes`
  - `extend_unit_write_words`
  - `extend_unit_write_word`
  - `extend_unit_write_dword`
- [ ] Do not retain public compatibility aliases or deprecated wrappers for commands `0x0601`, `0x0613`, `0x1601`, or `0x1613`.
- [ ] Keep command encoding/decoding private only if another internal path requires it; otherwise remove it.
- [ ] Update exported symbols, tests, API reference, and changelog, then run the repository release gate and self-review.

The approved cross-library contract is recorded in [DECISION-SLMP-PUBLIC-API-001](https://github.com/fa-yoshinobu/plc-comm-publish/blob/main/slmp_library_next_improvement_goal_20260830.md#decision-slmp-public-api-001-未使用のmemory--extend-unit関数を非公開化する).
