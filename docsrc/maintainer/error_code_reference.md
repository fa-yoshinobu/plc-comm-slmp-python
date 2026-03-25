# Internal Error Code Reference

This is the maintainer-facing end-code table for the validated target.

## Scope

- date: 2026-03-14
- PLC: Mitsubishi MELSEC iQ-R `R08CPU`
- host: `192.168.250.101`

This table records what the project actually observed on the validated target. It is intentionally practical rather than universal.

## Observed Codes

| End code | Observed on | Current interpretation in this project | Typical trigger | Current action |
| --- | --- | --- | --- | --- |
| `0x0000` | validated success paths | normal success | accepted request | continue |
| `0x4013` | `1005` | PLC-state-dependent rejection | remote latch clear outside the accepted state | perform under the accepted `STOP` condition |
| `0x4030` | direct `LTC/LTS/LSTC/LSTS`, `S0` bit write | selected device/path rejected | unsupported direct path on the current target | use the practical helper path or keep unsupported |
| `0x4031` | boundary probes | configured range/allocation mismatch | request starts outside the accepted range | treat as PLC-side range rejection |
| `0x4043` | `0601` | extend-unit argument invalid | `module_no=0x0000` | use the verified `0x03E0` path |
| `0x4080` | `0601` | target/module mismatch | `module_no=0x03FF` | do not use this module number on the validated target |
| `0x40C0` | label family | label-side condition failure | missing label or external access disabled | check label definition before retrying |
| `0x413E` | file family | file state/environment rejected the operation | some `18xx` file commands | keep as environment-dependent |
| `0xC051` | long-counter and `LZ` writes | point-count or write-unit rule violation | `LZ1 x1`, some long-counter writes | treat as manual-confirmed |
| `0xC059` | unsupported request family on the current endpoint | request family not accepted | unsupported command family on the current target | treat as out of supported scope |
| `0xC05B` | direct `G0` / `HG0` read, first one-request mixed `1406` block write | direct path or combined request path rejected | trying to use `G/HG` as normal devices, or sending one mixed word+bit block write on the validated target | use CPU-buffer helpers for `G/HG`; use split mixed-block fallback for the mixed `1406` case |
| `0xC061` | Extended Specification CPU-buffer path, some file commands | request content/path not accepted in the current environment | unresolved Extended Specification or file conditions | keep the practical alternative path |
| `0xC075` | historical label payload attempt | payload formatting error | earlier incorrect label payload | resolved |
| `0xC207` | file family | file environment rejected the operation | some `18xx` file commands | keep as environment-dependent |

## Notes

### `0x4030` vs `0x4031`

Current project interpretation:

- `0x4030`: wrong device/path for the selected command
- `0x4031`: configured range/allocation mismatch

### `0xC051`

This meaning is treated as manual-confirmed in the project for:

- long-counter write-unit issues
- `LZ` write word-count issues

### `0x40C0`

Current practical rule:

- first suspect label definition
- then check `Access from External Device`

### `0xC061`

Do not overfit this code to one universal meaning. On this project it means the target rejected the request content/path for that context.

### `0xC05B`

Do not overfit this code to only one feature family either.

On this project it was observed on:

- direct `G/HG` normal-device access
- the first one-request mixed `1406` block write for `D300 x2 + M200 x1 packed`

For the mixed block case, the practical workaround is to retry as separate word-only and bit-only block writes.

## Related Documents

- [open_items.md](open_items.md)
- [communication_test_record.md](communication_test_record.md)
- [manual_implementation_differences.md](manual_implementation_differences.md)
