# Open Items

This page is the documentation-facing summary of the current unresolved work.

In a source checkout, the authoritative maintainer checklist remains the
repository-root `TODO.md`.

## Current Active Items

### 1. `G/HG` Extended Specification live coverage expansion

Current evidence already confirms:

- aligned `TCP` write/readback/restore for `SELF` through `SELF-CPU4`
- aligned `UDP/1027` write/readback/restore for `SELF` through `SELF-CPU4`
- stable non-aligned write failures with `G -> 0x414A` and `HG -> readback_mismatch`

Remaining work is broader coverage across:

- additional address ranges beyond the currently validated bands
- broader UDP address coverage
- additional PLC families

### 2. `1617` Clear Error operator-visible effect

Transport-level acceptance is confirmed, but the practical, operator-visible
effect is still not pinned down on real hardware.

### 3. Regression suite expansion

The local regression suite already covers unit tests, `ruff`, `mypy`, and CLI
`--help` smoke checks. Expand it only if selected live or manual flows need a
single-command orchestrator.

## Current Practical Limits

- ASCII mode remains intentionally out of scope

## Resolved Historical Items

### Mixed block write root cause

The old `0xC05B` mixed block write note is no longer tracked as an unresolved
item. The 2026-06-12 root-cause check found that the failing clients were using
an invalid Write Block payload layout: they grouped all block specs first and
all data last. The corrected layout writes each block's data immediately after
that block's device spec and point count.

Current guidance:

- automatic mixed-write split retry has been removed
- if a PLC rejects one mixed `1406` write, the library returns the original PLC
  end code
- callers that intentionally want separate word-only and bit-only requests must
  opt into `split_mixed_blocks=True`
- QnUDV was revalidated as genuine command non-support
- L16HCPU was revalidated as the old layout bug and fixed clients were verified
  live

See
`../validation/reports/MIXED_BLOCK_WRITE_1406_LAYOUT_ROOT_CAUSE_2026-06-12.md`.

Related maintainer pages:

- [Communication Test Record](communication_test_record.md)
- [Testing Guide](TESTING_GUIDE.md)
- [Protocol Spec](PROTOCOL_SPEC.md)
