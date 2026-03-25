# `S` Typed Write Policy

- Date: 2026-03-19
- Scope: `S` device family in typed device APIs
- Project: `plc-comm-slmp-python`

## Decision

The project keeps typed `S` device write unsupported.

This is not treated as an open protocol-investigation item anymore on the current validated target.

## Evidence

1. The validated iQ-R target accepts `S0` read but rejects direct typed `S0` bit write with `0x4030`.
2. The project already blocks `S` in typed device APIs with `SLMPUnsupportedDeviceError`.
3. The user reported that GOT also could not write the same `S` path in the current environment.

## Practical Rule

- Keep typed `S` access unsupported in this repository.
- Do not spend more investigation time on `S` write unless a new target demonstrates a valid operational path.
- Continue using other validated device families for writable state where needed.

## Related Files

- `docsrc/maintainer/plc_device_range_expectations.md`
- `docsrc/maintainer/manual_implementation_differences.md`
- `internal_docsrc/iqr_r08cpu/open_items_recheck_latest.md`

