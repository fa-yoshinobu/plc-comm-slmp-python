# TODO: SLMP Python (slmp)

This file tracks the remaining tasks and unresolved issues for the SLMP Python library.

## 1. Protocol Implementation Gaps

- [ ] **Extended Specification live coverage expansion**: The capture-aligned implementation is working on validated paths, but broader
  address-range, transport, and PLC-family coverage is still open. QnUDV has no
  `HG`; QnUDV `U0\G10` read-only was live-checked on 2026-05-15 against
  `Q06UDVCPU` and returned `[0]` across Python, Node-RED, .NET, Rust, and C++
  Minimal. QCPU `U0\G10` read-only was
  live-checked on 2026-05-15 against `Q12HCPU` and returned `[0]` across
  Python, Node-RED, .NET, Rust, and C++ Minimal. QnU `U0\G10` read-only was
  live-checked on 2026-05-15 against `Q26UDEHCPU` and returned `[0]` across the
  same five stacks.

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
- [ ] **Re-check high-level `plc_family` fixed mappings**: Re-check the provisional high-level `plc_family` fixed mappings on live
  hardware:
  - `mx-f` -> `4e/iqr` with range family `mx-f`
  - `mx-r` -> `4e/iqr` with range family `mx-r`

## 3. Known Issues
- [x] **Single-request mixed block write (`1406`)**: Current live checks show
  single-request mixed block write is rejected on the checked QCPU/QnU/QnUDV
  targets because the bit-block part is rejected. This is documented behavior
  and not a remaining Python defect.
- [x] **ASCII mode out of scope**: ASCII mode is intentionally out of scope for this project. Binary 3E/4E is the only planned data-code path unless a concrete compatibility requirement appears.
- [x] **Raw wrappers internal-only**: `*_raw` wrappers are for library developers and maintainers. Keep them documented only in internal maintainer materials; they are not a user-facing roadmap item.
- [ ] **Extended Specification broader validation**: Extended Specification access for `G/HG` is not stable across all series. The iQ-R `_ext` builder now matches the captured `U3E0\G10` and `U3E0\HG20` payload shape, the dedicated coverage command can sweep multiple transports and named targets, and live checks now confirm: `TCP + SELF/SELF-CPU1 + U3E0\\G10/U3E0\\HG20 + points=1/4` for read-only coverage; target-aligned write/readback/restore for `SELF-CPU2/U3E1`, `SELF-CPU3/U3E2`, and `SELF-CPU4/U3E3` at both `points=1` and `points=4`, first on `G10/HG20`, then on `G30/HG30`, then on `G50/HG50` with restoration back to the original non-zero `G50` values, and now on `G70/HG70` and `G90/HG90`; aligned `UDP/1027` read-only and write/readback/restore for `SELF/U3E0`, `SELF-CPU1/U3E0`, and `SELF-CPU2..4/U3E1..3` on `G10/HG20` at `points=1` and `points=4`; non-aligned `points=1` write failures with the stable pattern `G -> 0x414A`, `HG -> readback_mismatch`; and `UDP/1025` timeouts for the earlier `SELF/SELF-CPU1` read-only sweep. Broader validation beyond those address ranges and broader UDP address coverage is still pending. Use CPU buffer access commands unless you have validated the exact Extended Specification path on the actual PLC.

## 4. Cross-Stack API Alignment

- [x] **Keep helper naming aligned with the managed stacks**: Preserve the shared high-level contract around `open_and_connect`, `read_typed`, `write_typed`, `write_bit_in_word`, `read_named`, and `poll`.
- [x] **Review public address helper exposure**: Decide whether the address parse/normalize/format helpers should be elevated into an explicit public utility API so applications do not need private string-parsing copies.
- [x] **Keep `plc_family` as the only high-level PLC selector**: Raw `frame_type`, access-profile, and range-family knobs should stay low-level only unless new live evidence forces a public exception.
- [x] **Preserve semantic atomicity by default**: Do not silently split reads or writes that callers would reasonably treat as one logical value or one logical block. Protocol-defined boundaries are acceptable, but fallback retries that change semantics should be opt-in and explicitly named.
