# TODO: SLMP Python (slmp)

This file tracks the remaining tasks and unresolved issues for the SLMP Python library.

## 1. Protocol Implementation Gaps

- **`G/HG` Extended Specification live coverage expansion**
  The capture-aligned implementation is working on validated paths, but broader
  address-range, transport, and PLC-family coverage is still open.

- **Mixed block write root cause**
  The practical fallback is implemented, but the reason some validated PLC
  paths reject the first one-request mixed `1406` write with `0xC05B` is still
  not fully explained.

- **`1617` Clear Error operator-visible effect**
  Transport-level acceptance is confirmed, but the operator-visible behavior on
  real hardware still needs better evidence.

## 2. Testing & Validation

- The local regression suite already covers unit tests, `ruff`, `mypy`, and
  CLI smoke checks. Expand automation only when a concrete live or manual flow
  needs a single-command runner.

## 3. Known Issues
- Single-request mixed block write (`1406`) has not yet been accepted on any current live-verified PLC path in this project. Prefer `split_mixed_blocks=True` for the safest operational behavior, or use `retry_mixed_on_error=True` if you still want to probe the one-request form first.
- ASCII mode is intentionally out of scope for this project. Binary 3E/4E is the only planned data-code path unless a concrete compatibility requirement appears.
- `*_raw` wrappers are for library developers and maintainers. Keep them documented only in internal maintainer materials; they are not a user-facing roadmap item.
- Extended Specification access for `G/HG` is not stable across all series. The iQ-R `_ext` builder now matches the captured `U3E0\G10` and `U3E0\HG20` payload shape, the dedicated coverage command can sweep multiple transports and named targets, and live checks now confirm: `TCP + SELF/SELF-CPU1 + U3E0\\G10/U3E0\\HG20 + points=1/4` for read-only coverage; target-aligned write/readback/restore for `SELF-CPU2/U3E1`, `SELF-CPU3/U3E2`, and `SELF-CPU4/U3E3` at both `points=1` and `points=4`, first on `G10/HG20`, then on `G30/HG30`, then on `G50/HG50` with restoration back to the original non-zero `G50` values, and now on `G70/HG70` and `G90/HG90`; aligned `UDP/1027` read-only and write/readback/restore for `SELF/U3E0`, `SELF-CPU1/U3E0`, and `SELF-CPU2..4/U3E1..3` on `G10/HG20` at `points=1` and `points=4`; non-aligned `points=1` write failures with the stable pattern `G -> 0x414A`, `HG -> readback_mismatch`; and `UDP/1025` timeouts for the earlier `SELF/SELF-CPU1` read-only sweep. Broader validation beyond those address ranges and broader UDP address coverage is still pending. Use CPU buffer access commands unless you have validated the exact Extended Specification path on the actual PLC.

