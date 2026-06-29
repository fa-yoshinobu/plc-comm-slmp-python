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

## [Unreleased] - 2026-06-28

### Changed
- Library: Made named-address parsing and typed read/write helpers require explicit dtype suffixes such as `:U`, `:S`, `:D`, `:L`, `:F`, or `:BIT`; bare devices no longer default to `U`, `BIT`, or long-timer `D`.
- Tests: Updated high-level address parser and shared-spec vectors for explicit dtype requirements.

### Fixed
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
