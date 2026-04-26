# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## 0.1.11 - 2026-04-27

### Changed
- Tightened long-device route guards so `LTN/LSTN/LCN/LZ` avoid unsupported direct/raw word and dword paths, while supported random/named dword paths remain available.
- Aligned `LCS/LCC` write validation with the random/named bit route policy.

## 0.1.10 - 2026-04-14

### Changed
- The standard client route now requires explicit `plc_family`. `SlmpClient`, `AsyncSlmpClient`, and the bundled samples derive frame, access-profile, and device-range defaults from that family instead of exposing raw profile selection.
- The CLI keeps the low-level compatibility path internally, but normal application code now uses `plc_family` as the single explicit PLC selection.

## 0.1.9 - 2026-04-14

### Changed
- High-level connection setup now centers on explicit `plc_family`, which derives fixed frame, access-profile, and device-range defaults from one canonical family selection.
- String `X/Y` addresses now require explicit `plc_family`; `iq-f` uses octal `X/Y`, other supported families use hexadecimal, and non-canonical family aliases are rejected across client and device-range helpers.

## 0.1.8 - 2026-04-14

### Added
- Public device-range catalog helpers and regression coverage for device-range lookup and CPU operation-state decoding.

### Changed
- Expanded the package exports and README guidance for the new device-range helpers and cleaned up lint and typing issues in the new paths.

## 0.1.7 - 2026-04-13

### Added
- Client-side guard coverage for unsupported long-timer and long-counter-state command paths, including synchronous and asynchronous regression tests.

### Changed
- The public client surfaces now reject unsupported direct reads for `LTS/LTC/LSTS/LSTC` and unsupported `LCS/LCC` random, block, and monitor-registration commands before transport.

## 0.1.6 - 2026-04-13

### Changed
- CI now checks out `plc-comm-slmp-cross-verify/specs/shared` before running the shared-vector parity tests, so the package tests use the same canonical verification inputs as the cross-library harness.

### Fixed
- `slmp.__version__` now matches the packaged project version and upcoming release tag.

## 0.1.5 - 2026-04-01

## 0.1.4 - 2026-03-29

### Removed
- **Step Relay `S`**: Removed `S` from the public device table and parser. `TS/LTS/STS/LSTS/CS/LCS` remain supported.
- **Stale scope references**: Removed current-doc references to file commands and PLC-initiated ondemand (`2101`), which are not part of the implemented public API.
- **Unstable CLI auto profile flags**: Removed `--series auto` and `--frame-type auto` from the current CLI entry points, including `connection-check`, `other-station-check`, `compatibility-probe`, and `ExtendedDevice-device-recheck`.
- **Auto profile helpers**: Removed `SlmpClient.resolve_profile()`, `AsyncSlmpClient.resolve_profile()`, `recommend_profile()`, `open_and_connect()`, and `open_and_connect_queued()`. Connection setup is now explicit.

### Added
- **`QueuedAsyncSlmpClient`**: Added a queued high-level wrapper for multi-coroutine shared use.
- **Asynchronous API**: New `AsyncSlmpClient` for high-concurrency non-blocking I/O via `asyncio`.
- **UDP Support**: Full support for UDP transport in both synchronous and asynchronous clients.
- **3E Frame Support**: Formally enabled and documented support for SLMP 3E frames (binary).
- **Module I/O Keywords**: Added `ModuleIONo` enum and keyword support (e.g. `OWN_STATION`, `MULTIPLE_CPU_1`) in `SLMPTarget`.
- **Comprehensive Device Coverage**: Ported all device-related APIs (random, block, monitor, memory, label, remote) to the async client.
- **`node_search` (sync)**: Added `SlmpClient.node_search()` for UDP broadcast node discovery, matching the existing async implementation.
- **`ip_address_set` (sync + async)**: Added `SlmpClient.ip_address_set()` and `AsyncSlmpClient.ip_address_set()` for UDP fire-and-forget IP address configuration (command 0x0E31).
- **`release_check.bat`**: Added a release-preflight batch entry point that runs CI and docs generation together.
- **S Device Support**: Added `S` (Step Relay) device code to `DEVICE_CODES`.
- **Compatibility Verification Notes**: Recorded compatibility verification findings for bit order consistency across device families and dynamic system-value behavior.

### Changed
- **User-facing docs**: Reoriented the README, user guide, and sample guide around the high-level helper APIs only.
- **High-level samples**: Expanded the recommended sample documentation and updated `high_level_async.py` to use explicit `AsyncSlmpClient` / `QueuedAsyncSlmpClient` setup in the main flow.
- **High-level named reads**: `read_named` / `read_named_sync` now compile the address list once and batch word/DWord reads via `read_random` when possible.
- **Polling**: `poll` / `poll_sync` now reuse the compiled named-read plan across iterations instead of reparsing and reissuing per-address reads.
- **TCP receive path**: Reduced intermediate allocations in synchronous TCP frame reads by switching the hot path to `recv_into` and single-frame assembly.
- **Docstrings**: Expanded high-level helper docstrings so generated API docs describe the recommended connection, typed reads/writes, named snapshots, polling, and queued usage paths more clearly.
- **Sans-I/O Refactoring**: Moved protocol logic, validation, and data structures from `client.py` to `core.py` to achieve implementation consistency.
- **Documentation**: Updated the User Guide and compatibility notes for the newer feature set.

### Fixed
- **Qualified device DM override**: Explicit `direct_memory_specification` in `ExtensionSpec` is now respected when passing qualified device strings such as `U3E0\G10`; previously the auto-detected DM for `G` (0xF8) or `HG` (0xFA) devices would unconditionally override the caller's value. Auto-detection now only applies when the caller leaves DM at the default (`DIRECT_MEMORY_NORMAL = 0x00`).
- **Bit Data Packing**: Swapped nibble order in `pack_bit_values` and `unpack_bit_values` to correctly map the first device to the high nibble and the second device to the low nibble, matching the SLMP binary specification and live PLC behavior.
- **ZR Device Base**: Changed `ZR` device radix from hexadecimal to decimal in `constants.py` to align with live-verified iQ-R behavior.
- **Node Search**: Improved robustness of `decode_node_search_response` against truncated or malformed network data.
- **File Validation**: Added password length validation (6-32 characters) for iQ-R file subcommands (e.g. `0x0040`).
- Fixed several type hinting issues in `core.py` and redundant constant definitions.

## 0.1.3 - 2026-03-15

Documentation-only patch release.

### Changed

- added a README link to the related minimal C++ implementation package `slmp-connect-cpp-minimal`

## 0.1.2 - 2026-03-14

Patch release to align the repository release tag with the CI-passing commit.

### Fixed

- formatted `scripts/slmp_mixed_block_compare.py` so `ruff check .` passes in GitHub Actions
- release line now points to the same commit that passed unit tests, `ruff`, `mypy`, and package build

## 0.1.1 - 2026-03-14

Mixed block write compatibility update for the validated iQ-R target.

### Added

- `retry_mixed_on_error=True` fallback for `write_block(...)` so one mixed `1406/0002` write can recover by retrying as separate word-only and bit-only block writes on known rejection end codes
- `scripts/slmp_mixed_block_compare.py` for focused live comparison of mixed block read/write behavior
- focused unit tests for the mixed-write retry path
- validated-target comparison notes under `internal_docsrc/iqr_r08cpu/`

### Changed

- documentation now records that one-request mixed `writeBlock` on the validated `R08CPU` target reproduces `0xC05B`
- practical guidance now recommends `split_mixed_blocks=True` or `retry_mixed_on_error=True` when a PLC rejects one mixed word+bit block write
- project status and open-items tracking were updated with the latest live verification result

### Live Validation

- one-request mixed `writeBlock(D300 x2 + M200 x1 packed)` reproduced `0xC05B`
- equivalent word-only and bit-only block writes remained `OK`
- `retry_mixed_on_error=True` was live-verified as a working fallback on the validated target

## 0.1.0 - 2026-03-13

Initial packaged release for the current repository scope.

### Added

- 4E binary SLMP frame encoder/decoder
- TCP and UDP client support
- typed APIs for:
  - normal device read/write
  - random read/write
  - block read/write
  - monitor entry/execute
  - memory read/write
  - extend-unit read/write
  - label command family
  - remote control
  - password lock/unlock
  - self test
  - major file commands
- Extended Specification typed extension builders and access APIs
- practical helper APIs for:
  - long timer / long retentive timer decoding
  - `LTC/LTS/LSTC/LSTS` state helpers
  - CPU buffer read/write via the verified `0601/1601` path
- CLI entry points for:
  - base connection check
  - device-range boundary probe
  - focused register-boundary probe
  - other-station verification
  - open-item recheck
  - pending live verification

### Changed

- documentation split into user-facing guides and internal implementation-facing records
- generated live reports moved under `internal_docsrc/<series>_<model>/`
- current live reports now keep a tracked `*_latest.md` plus a timestamped `archive/` copy

### Validated Environment

- Mitsubishi MELSEC iQ-R `R08CPU`
- Host `192.168.250.100`
- `TCP 1025`
- `UDP 1027`
- library mode `series=iqr`

### Known Limitations

- 3E frame is not implemented
- ASCII protocol is not implemented
- some paths remain target-specific and unresolved on the validated iQ-R target
- current unresolved items are tracked in `internal_docsrc/open_items.md`
