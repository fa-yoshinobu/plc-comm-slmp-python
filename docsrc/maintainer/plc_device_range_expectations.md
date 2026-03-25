# PLC Device Range Expectation Table

## Scope

- Date: 2026-03-13
- PLC: Mitsubishi MELSEC iQ-R (`R08CPU`)
- Host: `192.168.250.100`
- Source of configured ranges: current PLC device-setting screen provided by the user
- Library policy: do not hard-code these PLC-setting-dependent limits in the client
- Current probe inputs:
  - `internal_docsrc/iqr_r08cpu/current_plc_boundary_specs_20260313.txt`
  - `internal_docsrc/iqr_r08cpu/device_range_probe_latest.md`

This document records the current PLC-side configured device ranges and the expected response pattern when a request stays inside the configured range, crosses the upper bound, or starts outside the configured range.

These values are evidence for the current validated target only. They are not client-side hard limits and must not be generalized to other PLC models or other parameter sets.

These expectations are for the normal direct-device command family:

- read: `0401`
- write: `1401`

The table is only applicable when the device family itself is supported by the chosen command path. If a device family is rejected for command/path reasons, a different end code may appear even when the requested number is inside the configured range.

## Current Configured Ranges

| Device | Size | Configured range | Numbering base | In-range single-point expectation | Cross-upper-bound expectation | Out-of-range start expectation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `X` | `12K` | `0 .. 2FFF` | hex | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `Y` | `12K` | `0 .. 2FFF` | hex | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `M` | `12K` | `0 .. 12287` | decimal | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `B` | `8K` | `0 .. 1FFF` | hex | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `SB` | `2K` | `0 .. 7FF` | hex | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `F` | `2K` | `0 .. 2047` | decimal | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `V` | `2K` | `0 .. 2047` | decimal | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `S` | `1K` | `0 .. 1023` | decimal | read: `0x0000` | range overflow usually `0x4031` | range overflow usually `0x4031` | write has a separate practical issue on this PLC |
| `T` | `1K` | `0 .. 1023` | decimal | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `LT` | `1K` | `0 .. 1023` | decimal | alternative helper path recommended | not characterized via direct path | not characterized via direct path | direct `LT*` path has a separate practical issue |
| `ST` | `1K` | `0 .. 1023` | decimal | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `LST` | `1K` | `0 .. 1023` | decimal | alternative helper path recommended | not characterized via direct path | not characterized via direct path | direct `LST*` path has a separate practical issue |
| `C` | `512` | `0 .. 511` | decimal | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `LC` | `512` | `0 .. 511` | decimal | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `D` | `10K` | `0 .. 10239` | decimal | `0x0000` | `0x4031` | `0x4031` | live verified |
| `W` | `8K` | `0 .. 1FFF` | hex | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `SW` | `2K` | `0 .. 7FF` | hex | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `L` | `8K` | `0 .. 8191` | decimal | `0x0000` | typically `0x4031` | typically `0x4031` | expected from current setting |
| `ZR` | `160K` | `0 .. 163839` | decimal | `0x0000` | expected `!= 0x0000`, but see live note below | `0x4031` observed at `ZR163840` | live note required |

Practical probe mapping:

- `T` family was probed through `TS`, `TC`, and `TN`
- `LT` family was probed through `LTS`, `LTC`, and `LTN`
- `ST` family was probed through `STS`, `STC`, and `STN`
- `LST` family was probed through `LSTS`, `LSTC`, and `LSTN`
- `C` family was probed through `CS`, `CC`, and `CN`
- `LC` family was probed through `LCS`, `LCC`, and `LCN`

## Live-Verified Boundary Cases

The following cases were measured directly against the current PLC using normal word access (`0401` / `1401`).

| Operation | Result |
| --- | --- |
| read `D10238`, `1 point` | `end_code=0x0000` |
| read `D10239`, `1 point` | `end_code=0x0000` |
| read `D10239`, `2 points` | `end_code=0x4031` |
| read `D10240`, `1 point` | `end_code=0x4031` |
| read `D12000`, `1 point` | `end_code=0x4031` |
| read `D12000`, `10 points` | `end_code=0x4031` |
| write `D12000`, `1 point` | `end_code=0x4031` |

Current full generated report:

- `internal_docsrc/iqr_r08cpu/device_range_probe_latest.md`
- `internal_docsrc/iqr_r08cpu/register_boundary_comparison_latest.md`
- `internal_docsrc/iqr_r08cpu/additional_register_boundary_probe_latest.md`
- `internal_docsrc/iqr_r08cpu/lz_boundary_probe_latest.md`
- `internal_docsrc/iqr_r08cpu/zr_boundary_probe_latest.md`
- `internal_docsrc/iqr_r08cpu/register_boundary_probe_latest.md`

Selected 2026-03-13 observations from the generated report:

- `S1023` same-value writeback returned `0x4030`
- `LTN1023` with `4-point` in-range read passed, `5-point` crossing read returned `0x4031`
- `LSTN1023` with `4-point` in-range read passed, `5-point` crossing read returned `0x4031`
- `LCN511` with `2-point` in-range read passed, `3-point` crossing read returned `0x4031`
- `LTN1024`, `LSTN1024`, and `LCN512` out-of-range writes returned `0xC051`
- `Z19` `1-point` read/write passed, while `Z19` `2-point` read and `Z20` start were rejected with `0x4031`
- `LZ1` `1-point` and `2-point` reads passed, `LZ2` start read returned `0x4031`
- `LZ1` `1-point` write returned `0xC051`, while `LZ1` `2-point` write returned `0x0000`
- repeatable focused recheck corrected `RD` behavior:
  - `RD524286 x2` read/write: `0x0000`
  - `RD524287 x2` read/write: `0x4031`
  - `RD524286 x16` and `x64`: `0x4031`
- `ZR163839` `2-point` read unexpectedly returned `0x0000`
- `ZR163840` `1-point` read returned `0x4031`
- live-detected `R` comparison also confirmed:
  - last accepted start address: `R32767`
  - `R32767` reads/writes starting there still succeeded for `x2`, `x16`, and `x64`
  - `R32768` reads were rejected with `0x4031`
- focused `ZR` probe also confirmed:
  - `ZR163838` `3-point` read: `0x0000`
  - `ZR163839` `3-point` read: `0x0000`
  - `ZR163839` `16-point` read: `0x0000`
  - `ZR163839` `64-point` read: `0x0000`
  - same-value writes for `ZR163838 x3`, `ZR163839 x2`, `ZR163839 x3`, `ZR163839 x16`, `ZR163839 x64`: all `0x0000`
  - `ZR163840` `1-point` / `2-point` writes: `0x4031`

Observed response payloads:

- `0401` range failure: `00 ff ff 03 00 01 04 02 00`
- `1401` range failure: `00 ff ff 03 00 01 14 02 00`

Current practical interpretation on this PLC:

- `0x4031`: device number range or allocation mismatch for the requested device

## Important Exceptions

These are not pure range issues. They are command-path or target-specific behavior already observed on the current PLC.

1. `S`
- `S0` read is OK.
- `S0` write returned `0x4030`.
- Therefore, `S` write cannot be interpreted only by configured range.
- Current project policy keeps typed `S` device write unsupported instead of treating this as an open investigation.

2. `LT` / `LST`
- Direct `LTC`, `LTS`, `LSTC`, `LSTS` access returned `0x4030`.
- Use `LTN` / `LSTN`-based helper APIs instead:
  - `read_ltc_states`
  - `read_lts_states`
  - `read_lstc_states`
  - `read_lsts_states`
  - `read_long_timer`
  - `read_long_retentive_timer`
- In the current range probe:
  - `LTN1024` out-of-range write returned `0xC051`
  - `LSTN1024` out-of-range write returned `0xC051`

3. `G` / `HG`
- These are not governed by the device-range setting screen above.
- Direct `0401` access returned `0xC05B`.
- Extended Specification `0401/0082` access returned `0xC061`.
- The currently verified practical path is `0601/1601` via:
  - `cpu_buffer_read_*`
  - `cpu_buffer_write_*`
  - `extend_unit_*`

4. `ZR`
- The current manual device table and the validated target do not agree on the `ZR` numbering base.
- The validated target behavior is decimal, and the current implementation follows that live result.
- The configured upper bound corresponds to `ZR163839` in this client.
- `ZR163840` start is rejected with `0x4031`.
- However, requests starting at `ZR163838` / `ZR163839` still succeeded even when the requested span clearly crossed into `ZR163840` or later.
- Focused live results:
  - reads: `ZR163838 x3`, `ZR163839 x2`, `ZR163839 x3`, `ZR163839 x16`, `ZR163839 x64` all returned `0x0000`
  - same-value writes: `ZR163838 x3`, `ZR163839 x2`, `ZR163839 x3`, `ZR163839 x16`, `ZR163839 x64` all returned `0x0000`
- Current practical interpretation for this PLC:
  - `ZR` acceptance appears to be checked primarily by start address, not by full end-of-span overrun
  - this is an observed target behavior, not yet a general protocol rule
  - a separate capture from another PLC environment showed successful direct `0401/1401` access to `ZR1535996`, so this validated-target boundary must not be treated as a protocol-wide or client-wide ceiling
  - that large-`ZR` target was later revalidated through the current Python client by writing `1234` to `ZR1535996` and reading back the same value

5. `R`
- The current device-setting screenshot did not include `R`, so the exact configured setting was not taken from the screenshot.
- However, live probing detected the last accepted start address as `R32767`.
- Focused comparison showed:
  - `R32767` reads/writes starting there still succeeded for `x2`, `x16`, and `x64`
  - `R32768` reads `x1`, `x2`, and `x16` all returned `0x4031`
- Current practical interpretation for this PLC:
  - `R` behaves like `ZR` in that acceptance appears to depend mainly on the start address rather than the full end-of-span overrun
  - this is an observed target behavior, not yet a general protocol rule

6. `LC`
- `LCN511` `2-point` in-range read/writeback was OK.
- `LCN512` out-of-range write returned `0xC051`.
- So `LCN` write-side out-of-range behavior differs from the simpler `0x4031` seen on many 1-word families.

7. `Z`
- Live probe detected the last accepted start address as `Z19`.
- `Z19 x1` read/write was `0x0000`.
- `Z19 x2` read and `Z20 x1` read/write were `0x4031`.
- So `Z` behaved like the simpler `D/W/SW` family, not like `R/ZR`.

8. `LZ`
- Live probe detected the last accepted start address as `LZ1`.
- `LZ1 x1` and `LZ1 x2` reads were both `0x0000`, while `LZ2 x1` read was `0x4031`.
- `LZ1 x1` write returned `0xC051`, while `LZ1 x2` write returned `0x0000`.
- `LZ2 x1` write returned `0xC051`, while `LZ2 x2` write returned `0x4031`.
- Current practical interpretation:
  - `LZ` write behavior is governed not only by start address but also by the required word-unit count
  - this matches the manual meaning of `C051H`

9. `RD`
- Repeatable focused recheck on 2026-03-13 corrected the earlier ad hoc note for `RD`.
- `RD524286 x2` read/write was `0x0000`.
- `RD524287 x2` read/write was `0x4031`.
- `RD524286 x16` and `x64` were also `0x4031`.
- Current practical interpretation:
  - `RD` does not currently show the same start-address-based overrun acceptance as `R` and `ZR` on this validated PLC
  - treat `RD` as a simpler boundary family unless a later recheck shows otherwise

## Client Behavior Policy

- The Python client must not embed PLC-setting-dependent limits such as "`D` ends at `10239`".
- The client may validate only protocol-format limits that are independent of PLC settings.
- Device-range acceptance must be determined by the PLC response for the actual target.
- Current deliberate project exception: `R` is treated as capped at `32767`.

## References

- `internal_docsrc/communication_test_record.md`
- `internal_docsrc/iqr_r08cpu/device_range_probe_latest.md`
- `internal_docsrc/iqr_r08cpu/register_boundary_comparison_latest.md`
- `internal_docsrc/iqr_r08cpu/additional_register_boundary_probe_latest.md`
- `internal_docsrc/iqr_r08cpu/lz_boundary_probe_latest.md`
- `internal_docsrc/iqr_r08cpu/zr_boundary_probe_latest.md`
- `internal_docsrc/iqr_r08cpu/register_boundary_probe_latest.md`
- `internal_docsrc/open_items.md`
- `internal_docsrc/manual_implementation_differences.md`
- `docsrc/validation/reports/ZR1535996_CAPTURE_2026-03-19.md`
- `docsrc/validation/reports/ZR1535996_HARDWARE_REVALIDATION_2026-03-19.md`
- `docsrc/validation/reports/R_FIXED_LIMIT_POLICY_2026-03-19.md`

