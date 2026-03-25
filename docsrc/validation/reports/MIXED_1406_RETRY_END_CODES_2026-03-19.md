# Mixed `1406` Retry End Codes

- Date: 2026-03-19
- Scope: `write_block(..., retry_mixed_on_error=True)`
- Project: `plc-comm-slmp-python`

## Decision

The mixed-block automatic fallback now retries on these first-pass rejection end codes:

- `0xC056`
- `0xC05B`
- `0xC061`

## Hardware Evidence

Observed one-request mixed `1406` rejections on real hardware:

| Model | Series Mode | Mixed `1406` Result |
| --- | --- | --- |
| `R120PCPU` | `iqr` | `0xC05B` |
| `L16HCPU` | `ql` | `0xC056` |
| `FX5UC-32MT/D` | `ql` | `0xC061` |

In all three cases:

- mixed `0406` read succeeded
- word-only `1406` write succeeded
- bit-only `1406` write succeeded
- the single mixed `1406` write was rejected before the PLC state changed

## Practical Interpretation

These end codes are treated as target-specific "combined mixed write rejected" responses rather than as proof that the individual word-only or bit-only paths are invalid.

The fallback remains intentionally narrow:

- retry only when the first combined request returns one of the verified mixed-write rejection codes above
- do not retry on unrelated errors such as encoding mismatches, unsupported series settings, or ordinary address/range failures

## Related Evidence

- `internal_docsrc/iqr_r120pcpu/mixed_block_compare_latest.md`
- `internal_docsrc/ql_l16hcpu/mixed_block_compare_latest.md`
- `internal_docsrc/ql_unknown_target/mixed_block_compare_latest.md`

