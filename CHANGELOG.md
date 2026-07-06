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

### Changed
- Library: Synced the embedded SLMP capability fixture to `plc-comm-slmp-profiles` `v1.2.2`, including inferred Q/L 008x extended random/monitor limit keys and iQ-F `not-adopted` monitor limit placeholders.
- Docs: Added the 2026-07-06 five-implementation SLMP API parity snapshot to the maintainer API unification policy.
- Tooling: Changed the canonical profile update script default ref to `v1.2.2`.

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
