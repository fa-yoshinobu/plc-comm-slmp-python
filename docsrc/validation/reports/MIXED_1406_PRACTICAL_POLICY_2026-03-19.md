# Mixed `1406` Practical Policy

- Date: 2026-03-19
- Scope: mixed word+bit `1406` block write
- Project: `plc-comm-slmp-python`

## Current Project Position

Keep the manual-aligned one-request mixed `1406` implementation in the library, but treat `split_mixed_blocks=True` as the safest operational choice on current hardware evidence.

## Why

The project now has live checks on multiple real PLC paths, and none of them accepted the first one-request mixed `1406` write:

| Hardware path | Series mode | First mixed `1406` result |
| --- | --- | --- |
| `R120PCPU` | `iqr` | `0xC05B` |
| `R08CPU + RJ71EN71` | `iqr` | `0xC05B` |
| `L16HCPU` | `ql` | `0xC056` |
| `FX5UC-32MT/D` | `ql` | `0xC061` |

In the same checks:

- mixed `0406` read succeeded
- word-only `1406` write succeeded
- bit-only `1406` write succeeded
- the first rejected mixed write left the PLC values unchanged

## Practical Guidance

1. If you want the safest real-hardware behavior, use `split_mixed_blocks=True`.
2. If you still want to test the one-request manual form first, use `retry_mixed_on_error=True`.
3. Do not assume that "Block Write = YES" in a compatibility summary means the first mixed word+bit `1406` request is accepted.

## Related Reports

- `docsrc/validation/reports/MIXED_1406_RETRY_END_CODES_2026-03-19.md`
- `internal_docsrc/iqr_r120pcpu/mixed_block_compare_latest.md`
- `internal_docsrc/iqr_r08cpu/mixed_block_compare_latest.md`
- `internal_docsrc/ql_l16hcpu/mixed_block_compare_latest.md`
- `internal_docsrc/ql_unknown_target/mixed_block_compare_latest.md`

