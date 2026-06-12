# Open Items

This page is the documentation-facing summary of the current unresolved work.

In a source checkout, the authoritative maintainer checklist remains the
repository-root `TODO.md`.

## Current Active Items

No current active items are tracked here.

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
