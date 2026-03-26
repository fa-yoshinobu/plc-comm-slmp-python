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

### 2. Mixed block write root cause

The project still needs a root-cause explanation for why the validated iQ-R
path rejects the first single-request mixed `1406` block write with `0xC05B`
even when the request format matches the manual.

### 3. `1617` Clear Error operator-visible effect

Transport-level acceptance is confirmed, but the practical, operator-visible
effect is still not pinned down on real hardware.

### 4. Regression suite expansion

The local regression suite already covers unit tests, `ruff`, `mypy`, and CLI
`--help` smoke checks. Expand it only if selected live or manual flows need a
single-command orchestrator.

## Current Practical Limits

- one-request mixed `1406` writes are not currently accepted on any live-verified path in this project
- ASCII mode remains intentionally out of scope

Related maintainer pages:

- [Communication Test Record](communication_test_record.md)
- [Testing Guide](TESTING_GUIDE.md)
- [Protocol Spec](PROTOCOL_SPEC.md)
