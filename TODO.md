# TODO

Approved implementation status and current active TODOs.

## Current Status

### SLMP-PYTHON-TODO-1: Remove unused Memory / Extend Unit functions from the public API

Status: `implemented` (2026-09-03). There are no users of these methods, so no compatibility alias or migration path is required.

- [x] Remove the following methods from both `SlmpClient` and `AsyncSlmpClient` (20 public callables total):
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
- [x] Do not retain public compatibility aliases or deprecated wrappers for commands `0x0601`, `0x0613`, `0x1601`, or `0x1613`.
- [x] Keep command encoding/decoding private only if another internal path requires it; otherwise remove it.
- [x] Update exported symbols, tests, API reference, and changelog, then run the repository release gate and self-review.

Verification note (2026-09-03): version `5.2.0`, canonical profile fixtures, CI, registry duplicate guard, artifact metadata, and isolated wheel/package checks passed. The final diff and public API were self-reviewed against the approved contract.

The approved cross-library contract is recorded in [DECISION-SLMP-PUBLIC-API-001](https://github.com/fa-yoshinobu/plc-comm-publish/blob/main/slmp_library_next_improvement_goal_20260830.md#decision-slmp-public-api-001-未使用のmemory--extend-unit関数を非公開化する).

### SLMP-PYTHON-TODO-2: Remove the obsolete open-items recheck console

Status: `implemented` (2026-09-03). The `slmp-open-items-recheck` console depended on the removed Extend Unit APIs and duplicated live-verification work owned by `plc-comm-soak-test`.

- [x] Remove the `slmp-open-items-recheck` package entry, `open_items_recheck_main`, and its dedicated launcher.
- [x] Remove maintainer instructions that invoke the deleted launcher.
- [x] Verify that package metadata and source contain no executable entry for this command.
- [x] Keep unrelated CLI commands and normal SLMP library behavior unchanged.

### SLMP-PYTHON-TODO-3: Use extended in canonical public API names

Status: `implemented` (2026-09-03).

- [x] Rename the six sync/async name families `read_devices_ext`, `write_devices_ext`, `read_random_ext`, `write_random_words_ext`, `write_random_bits_ext`, and `register_monitor_devices_ext` to corresponding `_extended` canonical names.
- [x] Keep the old `_ext` names temporarily as direct delegates under the approved migration policy.
- [x] Preserve signatures, results, validation, exceptions, command/subcommand, and wire behavior.
- [x] Update tests, exports, API reference, migration notes, examples, and changelog.

### SLMP-PYTHON-TODO-4: Clarify the top-level PLC profile display-name function

Status: `implemented` (2026-09-03).

- [x] Add canonical top-level `plc_profile_display_name`.
- [x] Keep `display_name` temporarily as a direct delegate under the approved migration policy.
- [x] Keep `SlmpPlcProfileDescriptor.display_name` unchanged.
- [x] Preserve profile normalization, returned display text, and error semantics.
- [x] Update tests, exports, API reference, migration notes, examples, and changelog.

### SLMP-PYTHON-TODO-5: Deprecate top-level read_dwords helpers for one compatibility release

Status: `implemented` (2026-09-03). The required immediately-following-release removal remains tracked below as `SLMP-PYTHON-TODO-7`.

- [x] Make top-level `read_dwords` and `read_dwords_sync` emit `DeprecationWarning` with the canonical replacement and removal timing.
- [x] Keep the old top-level functions for exactly one compatibility release, then remove them in the immediately following release.
- [x] Delegate directly to `read_dwords_single_request` and `read_dwords_single_request_sync` so validation, errors, request count, payload, and result agree.
- [x] Do not change `AsyncSlmpClient.read_dwords` or `SlmpClient.read_dwords`.
- [x] Update tests, exports, API reference, migration notes, examples, and changelog.
- [x] Retain an explicit next-release TODO to remove both old top-level functions.

### SLMP-PYTHON-TODO-6: Add latest self-diagnosis error-code reads

Status: `implemented` (2026-09-03).

- [x] Add `read_latest_self_diagnosis_error_code()` to both `AsyncSlmpClient` and `SlmpClient`.
- [x] Read exactly one word from `SD0` in one Direct Read request and return the raw unsigned integer value.
- [x] Reuse existing profile, timeout, cancellation, and error behavior without retries, fallback, classification, or writes.
- [x] Do not add duplicate top-level helpers.
- [x] Update tests, API reference, examples, and changelog.

### SLMP-PYTHON-TODO-7: Remove deprecated top-level read_dwords compatibility helpers

Status: `required for the immediately following release`.

- [ ] Remove only the top-level `read_dwords` and `read_dwords_sync` compatibility functions after their one compatibility release.
- [ ] Keep `AsyncSlmpClient.read_dwords` and `SlmpClient.read_dwords` unchanged.
- [ ] Remove the old top-level exports and compatibility tests, then update the API reference, migration notes, and changelog.
