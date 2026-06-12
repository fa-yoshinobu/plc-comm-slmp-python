# TODO: SLMP Python (slmp)

This file tracks the remaining tasks and unresolved issues for the SLMP Python library.

## 1. Protocol Implementation Gaps

- [x] **Mixed block write root cause**: The old `0xC05B` note is no longer
  tracked as a live unresolved PLC behavior; it was likely from an in-progress
  library/payload implementation. Current QCPU/QnU/QnUDV live checks across
  Python, Node-RED, .NET, Rust, and C++ Minimal consistently show: word-only
  block read/write for `D9000` succeeds, bit-only block read/write for `Y1FFF`
  returns `0x4031`, mixed word+bit block read returns `0x4031`, and mixed
  word+bit block write returns `0xC056`. Mixed block access is rejected because
  the bit-block part is rejected.

## 2. Testing & Validation

- [x] **Local regression baseline**: The local regression suite already covers unit tests, `ruff`, `mypy`, and
  CLI smoke checks. Expand automation only when a concrete live or manual flow
  needs a single-command runner.

## 3. Known Issues
- [x] **Single-request mixed block write (`1406`)**: Current live checks show
  single-request mixed block write is rejected on the checked QCPU/QnU/QnUDV
  targets because the bit-block part is rejected. This is documented behavior
  and not a remaining Python defect.
- [x] **ASCII mode out of scope**: ASCII mode is intentionally out of scope for this project. Binary 3E/4E is the only planned data-code path unless a concrete compatibility requirement appears.
- [x] **Raw wrappers internal-only**: `*_raw` wrappers are for library developers and maintainers. Keep them documented only in internal maintainer materials; they are not a user-facing roadmap item.

## 4. Cross-Stack API Alignment

- [x] **Keep helper naming aligned with the managed stacks**: Preserve the shared high-level contract around `open_and_connect`, `read_typed`, `write_typed`, `write_bit_in_word`, `read_named`, and `poll`.
- [x] **Review public address helper exposure**: Decide whether the address parse/normalize/format helpers should be elevated into an explicit public utility API so applications do not need private string-parsing copies.
- [x] **Keep `plc_family` as the only high-level PLC selector**: Raw `frame_type`, access-profile, and range-family knobs should stay low-level only unless new live evidence forces a public exception.
- [x] **Preserve semantic atomicity by default**: Do not silently split reads or writes that callers would reasonably treat as one logical value or one logical block. Protocol-defined boundaries are acceptable, but fallback retries that change semantics should be opt-in and explicitly named.
