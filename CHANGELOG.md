# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Entry labels**

- `Release`: Package/version metadata and publishing preparation.
- `Library`: Runtime behavior, public API, protocol handling, or validation in the distributed library.
- `Docs`: README, user guides, generated API docs, or other documentation-only changes.
- `Samples`: Examples, sample flows, sample scripts, or sample applications.
- `Tests`: Test suites, test fixtures, golden vectors, or verification data.
- `Tooling`: Developer/operator command-line tools and helper utilities.
- `CI`: Release checks, workflow scripts, or automation-only changes.

## [Unreleased]

### BREAKING

- Tooling: Removed legacy library-local discovery, monitor, mixed-block split,
  and raw live-validation scripts that depended on APIs removed by the quality
  overhaul. Canonical live evidence collection now belongs to the profile
  repository and its profile-JSON-driven probe.
- Library: Made connection `port`, `transport`, canonical `plc_profile`, and all four `SlmpTarget` route fields explicit requirements. Missing or invalid values now fail before transport.
- Library: Removed request-level `series` overrides from normal device, remote-password, and long-device APIs. Wire format is derived only from the connection PLC profile.
- Library: Removed the public low-level `request()` method and caller-selected 4E serial numbers. `raw_command(command, subcommand, payload)` remains the single maintainer raw entry point and allocates serials internally.
- Library: Removed command-specific raw-payload wrappers and public label payload builder/parser methods. Use the semantic typed APIs, or the single maintainer `raw_command` entry point for investigation.
- Library: Removed public chunked read/write helpers and mixed-block request splitting. One standard API call now produces one protocol request and rejects profile-limit overflow before transport.
- Library: Made generic device access unit (`bit_unit`), typed CPU-buffer target (`module=CpuModule.CPU1` through `CPU4`), remote run/pause modes, and long-timer head/count values explicit where their omission could select a different operation or address. CPU-buffer helpers reject raw integers and unrelated module enums; Direct and Extended Device generic APIs reject every non-Boolean unit value before framing instead of treating false-like values as word access.
- Library: Long-timer and long-retentive-timer helpers now reject non-integer heads/counts, negative or 32-bit-overflow heads, zero counts, and counts above the one-request direct-word limit before transport in both sync and async clients.
- Library: Replaced public raw Extended Device field controls with qualified addresses and typed `SlmpExtendedDevice` modifiers.
- Library: Removed public error-code message/language lookup and public trace/strict-profile controls; structured end codes remain available without embedding manual wording.
- Library: Profile feature errors no longer append an internal bypass hint placeholder or the literal text `None`; normal error text reports only the profile, feature state, and available evidence.
- Library: `raise_on_error` now accepts only actual Booleans in connection options, sync/async clients, and internal request overrides. Omission remains `True`; strings, numbers, null, and containers cannot silently change PLC end-code handling. Each request snapshots the effective policy before waiting or transport, so later mutation cannot change an in-flight response decision.
- Library: The maintainer-only trace callback remains disabled by omission and now rejects non-callable values during sync/async client construction.

### Changed

- Library: Random read keeps the unused word or DWord category optional, rejects all-empty or invalid supplied collections before transport, and returns an explicit empty mapping for the unused result category.
- Library: Random word write keeps the unused word or DWord value category optional while rejecting all-empty, malformed, duplicate, overlapping, or invalid value collections before transport; random bit write remains a separate required-input API.
- Library: Block read/write keeps the unused word or bit block category optional, rejects all-empty or malformed inputs before transport, returns an explicit empty list for the unused read category, and rejects overlapping write ranges.
- Library: Request-level monitoring timer omission inherits the validated connection value, explicit zero is preserved, and sync/async overrides now reject Booleans, non-integers, and values outside `0..65535` before framing.
- Library: Standardized communication timeout omission to 3 seconds, monitoring timer omission to 4 seconds (`0x0010`), and TCP keepalive idle to 30 seconds.
- Library: TCP connection setup now fails closed when required keepalive configuration cannot be applied. Sync sockets and async writers are closed before the failure is returned, and no partially configured connection is retained.
- Tooling: Standardized every communicating CLI `--timeout` omission to 3 seconds; read-soak, mixed-load, and TCP-concurrency tools no longer select 5 seconds when the option is absent.
- Library: Reset UDP transport state after timeout/cancellation so a delayed 3E response cannot be accepted by a later request.
- Tooling: Required explicit port and transport for every bundled CLI command that communicates with a PLC.
- Tooling: The internal CLI probe client signature now also requires `transport`; direct internal construction can no longer infer TCP even when a command wrapper is bypassed.
- Tooling: The internal CLI probe client now requires a complete `default_target`, and every communicating CLI plus the shared sample parser requires explicit `--network`, `--station`, `--module-io`, and `--multidrop` values instead of constructing an own-station route from omission.
- Tooling: The optional live step in the regression-suite command now requires and forwards a complete route through `--live-network`, `--live-station`, `--live-module-io`, and `--live-multidrop`.
- Samples: Required explicit port and transport and bound address parsing/formatting to the selected PLC profile.
- Samples: Removed the last asynchronous sample fallback that supplied `192.168.250.100:1025`; every target must now be written as an explicit `HOST:PORT` pair.

### Tests

- Tests: Added sync/async contract tests for removed overrides, internal serial allocation, required parameters, profile-derived wire shapes, timeout validation, UDP reset behavior, and public-surface removal.
- Tests: Added a source-level invariant requiring every communicating CLI and shared sample monitoring-timer default to remain `0x0010` (four seconds).
- Tests: Added sync and async regressions proving keepalive setup failure closes the new transport and leaves the client disconnected.
- Tests: Added sync and async regressions proving the maintainer raw command cannot omit its keyword-only subcommand or payload and reaches no transport when either field is missing.

## [3.1.0] - 2026-07-10

### Added
- Library: Added `SlmpPlcProfileDescriptor` and `plc_profile_descriptors()` for canonical SLMP profile metadata.

### Changed
- Release: Bumped package metadata and `slmp.__version__` to `3.1.0`.
- Tooling: Pinned canonical SLMP profile imports to immutable profile commit `e7e8f071ff1819a6b088b6a793e6f08029c54e38`.
- Docs: Corrected the current wheel and source-distribution names in release guidance and removed hand-maintained page navigation from `GETTING_STARTED.md`.

### Fixed
- CI: Required an existing exact release tag checkout and matching tag, `pyproject.toml`, runtime, filename, and package metadata before GitHub Release upload.
- CI: Removed the broken generic PyInstaller executable gate; supported CLI tools remain wheel console entry points and built distributions are now inspected before upload.

## [3.0.0] - 2026-07-10

### Changed
- Release: Bumped package metadata and `slmp.__version__` to `3.0.0`.
- Docs: Replaced relative README links with absolute URLs so they resolve on package registry pages.

### BREAKING
- Library: Breaking: Removed `plc_profile_label()`. Calls written for v2.0.0 now fail immediately instead of silently changing the stored value; use `plc_profile_canonical_name()` for canonical IDs or `device_range_model_label()` to obtain the v2.0.0 return value `IQ-R`.

### Added
- Library: Added `available_plc_profiles()` for connection-selectable profile enumeration.
- Library: Added `plc_profile_canonical_name()` for canonical profile IDs.

### Docs
- Docs: Documented the distinct canonical, display-name, and device-range model-label APIs.

## [2.0.0] - 2026-07-06

### BREAKING
- Release: Renamed the PyPI install package while keeping the Python import name unchanged.

| Old install name | New install name | Import name |
| --- | --- | --- |
| `slmp-connect-python` | `plc-comm-slmp` | `slmp` |

- Library: Removed short `ModuleIONo` aliases in favor of the canonical module I/O vocabulary.

| Removed name | Use instead |
| --- | --- |
| `CONTROL_CPU`, `CONNECTED_CPU`, `DEFAULT` | `OWN_STATION` |
| `ACTIVE_CPU` | `CONTROL_SYSTEM_CPU` |
| `STANDBY_CPU` | `STANDBY_SYSTEM_CPU` |
| `TYPE_A_CPU` | `SYSTEM_A_CPU` |
| `TYPE_B_CPU` | `SYSTEM_B_CPU` |
| `CPU_1` to `CPU_4` | `MULTIPLE_CPU_1` to `MULTIPLE_CPU_4` |
| `SELF-CPU1` to `SELF-CPU4` | `SELF-MULTIPLE-CPU-1` to `SELF-MULTIPLE-CPU-4` |

### Changed
- Release: Bumped package metadata to `2.0.0`.
- Library: Added named SLMP target module I/O constants for multi-CPU routing while keeping the default own-station target unchanged.
- Library: Synced the embedded SLMP capability fixture to `plc-comm-slmp-profiles` `v1.2.2`, including inferred Q/L 008x extended random/monitor limit keys and iQ-F `not-adopted` monitor limit placeholders.
- Docs: Added the plc-comm family package matrix link to the README and documented `ModuleIONo` values in user-facing API/routing docs.
- Tests: Added package-rename import-name coverage for `import slmp`.
- Tooling: Updated release duplicate checks to query `plc-comm-slmp`.

## [1.2.0] - 2026-07-05

### Changed
- Release: Bumped package metadata to `1.2.0`.
- Tooling: Normalized line-ending handling in the canonical profile JSON update script so `-SourceRoot` runs no longer report false changes.
- Library: Synced the embedded SLMP capability fixture to `plc-comm-slmp-profiles` `v1.2.1`, including `display_name` labels and Ethernet unit profiles for RJ71EN71, LJ71E71-100, and QJ71E71-100 variants.
- Library: Added `display_name(plc_profile)` as the public UI-label helper while keeping stored PLC profile values canonical.
- Docs: Documented the profile display-name helper and canonical-ID storage guidance.
- Tests: Added canonical fixture parity coverage for profile `display_name` values.
- Library: Added non-breaking SLMP specification-audit updates for manual-conformant request framing, point-limit guards, response correlation, UDP source filtering, and PLC error diagnostics.
- Library: Exposed structured PLC error information on `SlmpResponse.error_info` and `SlmpError.error_info` when a non-zero end-code response carries the 9-byte error information block.
- Library: Enforced documented point limits before transport: iQ-F direct bit access is limited to 3584 points, and 008x extended random/monitor routes use the 96-point / weighted-960 / 94-bit limits.
- Library: Connected UDP sockets before sending and receiving so datagrams from unrelated sources are not accepted as PLC responses.
- Tooling: Changed the canonical profile update script default ref from `v1.0.0` to `v1.1.0`.
- Library: Added SLMP `S` step relay device-code support for reads and profile-specific write policy enforcement.
- Library: Rejected `G/HG` random bit writes; callers should use U-qualified word access for buffer-memory devices.
- Library: Aligned long counter state helper metadata so `LCS/LCC` remain long-helper entries while using their direct bit-read route internally.
- Library: Added built-in SLMP capability profiles from `plc-comm-slmp-profiles` v1.0.0 and `strict_profile=True` defaults for sync and async clients so high-level APIs reject profile `blocked` / `unverified` features before transport.
- Library: Added `SlmpProfileFeatureError` for profile guard failures with profile ID, feature key, state, evidence, and the `strict_profile=False` bypass hint.
- Library: Moved direct/random point limits to the capability table for all canonical built-in Ethernet profiles, including `melsec:qcpu` and `melsec:qnu`.
- Library: Kept the 008x extended random/monitor limits at 96 points, weighted 960, and 94 bits even when the selected profile allows larger plain random/monitor counts.
- Library: Added canonical weighted random-word write limits for `melsec:iq-l` and `melsec:iq-f`, so mixed word/dword random writes are guarded before transport.
- Library: Enforced capability write policies independently of `strict_profile`; `S` is read-only on iQ-R/iQ-L/MX/Q/L profiles and read-write on iQ-F.
- Library: Used direct write capability-limit keys for direct write requests instead of reusing direct read keys.
- Library: Rejected profile-unsupported device families before transport while leaving device address upper-bound checks to application/live-probe code.
- Library: Moved Q/L profile Read Block (`0x0406`) and Write Block (`0x1406`) rejection to the capability profile guard so `strict_profile=False` can intentionally send the request and let the PLC answer.
- Library: Batched named plain-bit reads through random word-read only for `SM/X/Y/M/L/F/V/B/SB`; `TS/TC/STS/STC/CS/CC/DX/DY` stay on direct bit reads.
- Docs: Documented profile-specific `S` write policy in supported-register, bit-device table, gotcha, audit-reflection, and maintainer difference notes.
- Docs: Documented the Q-series Read Block (`0x0406`) and Write Block (`0x1406`) profile guard in user profiles and gotchas.
- Docs: Removed the duplicated SLMP supported-register user page and linked users to the shared SLMP Profile Reference.
- Docs: Removed the per-library troubleshooting/code page; shared SLMP troubleshooting and code guidance now lives in the PLC Setup Guide.
- Docs: Added a Usage Guide example showing how to read `SlmpError.end_code` and structured `error_info`.
- Docs: Slimmed Gotchas to library-specific items and moved shared setup/end-code symptoms to the PLC Setup Guide.
- Docs: Standardized the Gotchas page structure with KV Host Link so library-specific caveats have the same destination across protocols.
- Docs: Merged bit-device packed access and extended-device access into the Usage Guide and removed the standalone user pages.
- Docs: Removed the manual page-navigation block from Getting Started and rely on site navigation instead.
- Docs: Moved shared SLMP gotcha items to the common troubleshooting page and kept Gotchas focused on Python-specific behavior.
- Docs: Added public API docstrings for the shared operation builders and a CI coverage check for public API documentation.
- Docs: Documented read-only operational recipes for multiple PLC monitoring and config-file polling.
- Docs: Fixed recent maintainer release/process and R120PCPU audit-note text issues.
- Docs: Fixed remaining PowerShell release/test command placeholders in maintainer docs.
- Docs: Cleaned up maintainer notes, obsolete probe records, and root TODO handling.
- Samples: Print `SlmpError.end_code` and structured command/subcommand details when high-level samples catch a PLC response error.
- Samples: Added read-only `multi_plc_monitor.py` and `config_polling.py` operational recipes, plus an example JSON config.
- Release: Aligned `slmp.__version__` with package metadata version `1.1.1`.
- Release: Excluded maintainer-only files, scripts, and tests from generated source archives via `.gitattributes`.
- Tooling: Changed the canonical profile update script default ref from `main` to fixed tag `v1.0.0`; `SLMP_PROFILES_REF` can still override it.
- Tests: Added guard coverage for `S` read-only writes and `G/HG` random bit write rejection.
- Tests: Added canonical capability fixture comparison plus sync and async strict-profile coverage for qnudv block/type-name guards, qnudv `strict_profile=False`, iQ-F link-direct, iQ-F `U\G`, iQ-L HG, profile limits, and profile write policies.
- Tests: Added regression coverage that profile-specific plain random/monitor limits do not relax 008x extended command limits.
- Tests: Added regression coverage that direct writes use direct write capability-limit keys.
- Tests: Updated coverage so `melsec:qcpu` and `melsec:qnu` reject block read/write through the capability profile guard.
- Tests: Added named-read planning coverage for random-word-safe plain bit families versus the direct-bit-only families seen on R-series hardware.
- Tooling: Added a release check that requires `pyproject.toml` and `slmp.__version__` to match.

## [1.1.1] - 2026-06-29

### Changed
- Release: Bumped package metadata to `1.1.1`.
- Docs: Documented explicit named-address dtype requirements in existing user docs.
- Samples: Updated high-level samples to use explicit dtype suffixes.

## [1.1.0] - 2026-06-29

### Changed
- Release: Bumped package metadata to `1.1.0`.
- Library: Made named-address parsing and typed read/write helpers require explicit dtype suffixes such as `:U`, `:S`, `:D`, `:L`, `:F`, or `:BIT`; bare devices no longer default to `U`, `BIT`, or long-timer `D`.
- Library: Removed embedded localized SLMP end-code message text; end-code helpers now return stable code-derived keys while message lookup hooks return `None`.
- Docs: Reworked the end-code page around raw `end_code` inspection and code-derived keys instead of bundled message text.
- Tests: Updated high-level address parser and shared-spec vectors for explicit dtype requirements.
- Tests: Updated SLMP end-code helper coverage for code-derived keys and non-embedded messages.

### Fixed
- Library: Aligned standard 008x extended device specifications with the manual 11-byte Q/L and 13-byte iQ-R layouts.
- Library: Matched 4E responses by request serial and discarded mismatched D4 responses before parsing the response payload.
- Library: Made `BIT_IN_WORD` helper addresses require an explicit bit index such as `D100.0` through `D100.F`; `D100:BIT_IN_WORD` now fails instead of silently reading or writing bit 0.
- Tests: Added coverage for rejecting `BIT_IN_WORD` addresses without an explicit bit index.

## [1.0.1] - 2026-06-25

### Changed
- Release: Bumped Python package metadata to `1.0.1`.
- Library: Removed the legacy `family` alias from helper-layer address parsing and formatting APIs; callers should pass `plc_profile`.
- Docs: Updated documentation so write examples restore the original PLC values after demonstration writes.
- Samples: Made sample scripts require an explicit `--plc-profile` instead of defaulting to `melsec:iq-r`.
- Samples: Updated write examples to restore the original PLC values after demonstration writes.

### Fixed
- Library: Corrected typed helper handling so boolean `BIT` writes stay on the intended bool path.
- Docs: Corrected typed helper annotations and user documentation to include boolean `BIT` reads and writes.

## [1.0.0] - 2026-06-24

### Added
- Tests: Added 4 missing RD device encoding vectors (`rd0_iqr`, `rd0_legacy`, `rd524287_iqr`, `rd524287_legacy`) to `tests/shared-spec/device_spec_vectors.json`.
- Tests: Added `read_words_rd524286_2_iqr` frame golden vector to `tests/shared-spec/frame_golden_vectors.json`.

### Changed
- Release: Bumped package metadata to `1.0.0` for the first stable release line.
