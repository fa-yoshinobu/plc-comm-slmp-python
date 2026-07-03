# Manual vs Implementation Differences

This file records places where the implementation follows a practical rule that is narrower, clearer, or different from what the manuals alone would suggest.

## Review Baseline

- last updated: 2026-03-14
- validated target: MELSEC iQ-R `R08CPU`
- host: `192.168.250.100`

## 1. `LT/LST` Read Semantics

Manual expectation:

- `LTN` / `LSTN` responses include the effective contact and coil bits
- direct devices such as `LTC`, `LTS`, `LSTC`, and `LSTS` also exist

Current implementation:

- the supported read rule is the `LTN/LSTN` 4-word decode path
- public helpers:
  - `read_long_timer(...)`
  - `read_long_retentive_timer(...)`
  - `read_ltc_states(...)`
  - `read_lts_states(...)`
  - `read_lstc_states(...)`
  - `read_lsts_states(...)`

Reason:

- the helper path is live-verified and manual-aligned on the validated target
- direct `LTC/LTS/LSTC/LSTS` reads remain rejected there

Status:

- settled practical rule

## 2. `G/HG` Access

Manual expectation:

- `G` is unit-qualified module access
- `HG` is CPU-buffer related
- Extended Specification access requires an explicit `U...` context such as
  `U3E0\G10` or `U3E0\HG20`

Current implementation:

- standalone typed device APIs intentionally reject `G` and `HG`
- Extended Specification `_ext` APIs now build a capture-aligned `G/HG` payload that matches the recorded `U3E0\G10`, `U3E0\HG20`, and `U01\G22` sessions
- the current R120PCPU target passed live single-word `U3E0\G10` / `U3E0\HG20` read-write-readback with restore
- the practical supported path is:
  - `cpu_buffer_read_*`
  - `cpu_buffer_write_*`
  - implemented via `0601/1601` with `module_no=0x03E0`

Reason:

- standalone `G/HG` normal-device access is invalid because the `U...` qualifier is required
- earlier repository probes that treated bare `G0` / `HG0` as meaningful access targets were based on the wrong premise
- separate capture-based `U3E0\G10`, `U3E0\HG20`, and `U01\G22` sessions proved that Extended Specification `G/HG` can work in real environments, and the current builder now reproduces that reordered payload shape
- the CPU-buffer helper path was live-verified

Status:

- settled rule: `G/HG` requires a qualified `U...` context; standalone `G/HG` is intentionally rejected

## 3. Step Relay `S`

Manual expectation:

- `S` exists as a normal device family

Current implementation:

- `S` is present in the repository device table and parser
- reads are allowed
- writes are rejected before transport because `S` is treated as read-only

Reason:

- current project policy follows the SLMP read-only treatment for `S`
- a device that is readable on a target is not automatically considered writable

Status:

- read-only public device family

## 4. Mixed Block Split Behavior

Manual expectation:

- mixed word and bit blocks are sent in one `0406/1406` request

Current implementation:

- default behavior still sends one mixed request
- optional compatibility split exists:
  - `split_mixed_blocks=True`
- automatic retry is not part of the API; PLC end codes are returned unchanged

Reason:

- after the fixed manual layout, any non-zero PLC end code should remain
  visible to the caller instead of being hidden by automatic retry

Historical observations before the 2026-06-12 layout fix:

- one-request mixed `write_block(D300 x2 + M200 x1 packed)` returned `0xC05B`
- the PLC memory remained unchanged after that first failed request
- the historical automatic-retry option then succeeded by retrying as separate
  word-only and bit-only writes; that option has since been removed
- later live checks on additional targets with the old layout also rejected the
  first mixed write:
  - `L16HCPU` -> `0xC056`
  - `FX5UC-32MT/D` -> `0xC061`
  - `R08CPU + RJ71EN71` -> `0xC05B`

Resolution:

- the 2026-06-12 root-cause check found that the failing clients used an
  invalid Write Block payload layout
- current clients emit the corrected layout, with each block's data immediately
  after that block's device spec and point count
- revalidated targets that support block commands accepted the corrected
  one-request mixed write; QnUDV was reclassified as genuine command
  non-support

Status:

- keep the manual-aligned one-request mixed form implemented
- document `split_mixed_blocks=True` as the only intentional split path

- optional non-default deviation

## 5. Remote Reset `1006`

Manual expectation:

- the supported subcommand is `0000`
- the request data after the subcommand is fixed data `01 00`
- successful `0000` may return no response

Current implementation:

- `remote_reset()` defaults to `1006/0000 + 01 00`
- no-response handling is the default behavior
- non-zero high-level subcommands are rejected

Reason:

- R120PCPU live verification on 2026-06-13 reset successfully with `1006/0000 + 01 00`
- the same target returned `0xC061` for `1006/0000` with an empty payload, even after enabling remote reset

Status:

- implementation follows the live-verified `1006/0000 + 01 00` request format

## 6. `R/ZR` Boundary Acceptance

Manual expectation:

- many devices are rejected once the requested span crosses the configured upper bound

Current implementation:

- the library does not hard-code those limits for most families
- project policy now treats `R` as a fixed exception and rejects `R32768` and above before frame encoding
- other families still go to the PLC for the actual acceptance decision

Observed on the validated target:

- `R32767` and `ZR163839` were accepted as start addresses
- `R32768` and `ZR163840` were rejected as start addresses
- a separate capture from another PLC environment showed successful direct `0401/1401` access to `ZR1535996`
- a later repository-driven live recheck also completed `ZR1535996` write/readback successfully on that large-`ZR` target

Status:

- target-specific live behavior recorded

## 7. `LZ` Write Unit Rule

Manual expectation:

- `C051H` covers word-count or unit violations

Current implementation:

- the library does not add a PLC-specific client-side special case
- it sends the request and lets the PLC validate it

Observed on the validated target:

- `LZ1 x1` write -> `0xC051`
- `LZ1 x2` write -> `0x0000`

Status:

- target-specific live behavior recorded

## 8. `ZR` Numbering Base

Manual expectation:

- current device tables suggest hexadecimal-style `ZR`

Current implementation:

- the library uses decimal `ZR` numbering on the validated iQ-R target

Reason:

- live verification showed decimal numbering is the working behavior there
- a separate `ZR1535996` capture also used decimal direct-device numbering on another PLC environment

Status:

- manual/live discrepancy recorded; implementation follows live behavior

## Use Rule

If a future change introduces another manual-vs-live rule, add it here immediately with:

1. manual expectation
2. implemented behavior
3. reason
4. current status
