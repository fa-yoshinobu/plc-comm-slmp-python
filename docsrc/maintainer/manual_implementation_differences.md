# Manual vs Implementation Differences

This file records places where the implementation follows a practical rule that is narrower, clearer, or different from what the manuals alone would suggest.

## Review Baseline

- last updated: 2026-03-14
- validated target: Mitsubishi MELSEC iQ-R `R08CPU`
- host: `192.168.250.101`

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
- Extended Specification access should work when the correct context is supplied

Current implementation:

- direct typed device APIs intentionally reject `G` and `HG`
- Extended Specification `_ext` APIs now build a capture-aligned `G/HG` payload that matches the recorded `U3E0\G10`, `U3E0\HG20`, and `U01\G22` sessions
- the current R120PCPU target passed a live single-word `G10` / `HG20` read-write-readback with restore
- the practical supported path is:
  - `cpu_buffer_read_*`
  - `cpu_buffer_write_*`
  - implemented via `0601/1601` with `module_no=0x03E0`

Reason:

- direct `G/HG` normal-device access remains rejected on the validated target
- earlier repository Extended Specification `G/HG` requests still failed on the validated target
- separate capture-based `U3E0\G10`, `U3E0\HG20`, and `U01\G22` sessions proved that Extended Specification `G/HG` can work in real environments, and the current builder now reproduces that reordered payload shape
- the CPU-buffer helper path was live-verified

Status:

- practical deviation in favor of the verified helper path, with Extended Specification `G/HG` coverage expansion still open

## 3. Step Relay `S`

Manual expectation:

- `S` exists as a normal device family

Current implementation:

- typed device APIs intentionally reject `S`

Reason:

- live verification showed read OK but write `0x4030`

Status:

- intentionally unsupported in typed device APIs on this project

## 4. Mixed Block Fallback

Manual expectation:

- mixed word and bit blocks are sent in one `0406/1406` request

Current implementation:

- default behavior still sends one mixed request
- optional compatibility fallbacks exist:
  - `split_mixed_blocks=True`
  - `retry_mixed_on_error=True` for `write_block(...)` on known mixed-write rejection end codes (`0xC056`, `0xC05B`, `0xC061` currently)

Reason:

- some PLC environments reject one mixed request

Observed on the validated target:

- one-request mixed `write_block(D300 x2 + M200 x1 packed)` returned `0xC05B`
- the PLC memory remained unchanged after that first failed request
- `retry_mixed_on_error=True` then succeeded by retrying as separate word-only and bit-only writes
- later live checks on additional targets also rejected the first mixed write:
  - `L16HCPU` -> `0xC056`
  - `FX5UC-32MT/D` -> `0xC061`
  - `R08CPU + RJ71EN71` -> `0xC05B`

Status:

- keep the manual-aligned one-request mixed form implemented
- but document `split_mixed_blocks=True` as the safest operational choice on current hardware evidence

- optional non-default deviation

## 5. Remote Reset `1006`

Manual expectation:

- the manual is internally inconsistent between `0000` and `0001`
- successful `0000` may return no response

Current implementation:

- `remote_reset()` defaults to `1006/0000`
- no-response handling is the default behavior

Reason:

- this best matches the manual note about successful completion without a response

Status:

- manual ambiguity resolved by implementation choice

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
