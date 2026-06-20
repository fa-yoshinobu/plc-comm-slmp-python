# GX Simulator 3 L16H SLMP Connection Result

Date: 2026-06-21 JST

## Summary

The L16H simulation endpoint was checked only for basic SLMP communication
availability. Communication was confirmed.

TCP port `127.0.0.1:5511` was listening, owned by `LSimRun3.exe`.

The `0101` type-name read returned `L16HCPU` with model code `0x48C2`.
Read-only device checks also succeeded with `D130` word read and `M0` bit read.

## Target

- Simulator: GX Simulator 3
- GX Works3 version: 1.125F
- Target machine: L16H simulation, as specified by the operator
- Host: 127.0.0.1
- Port: 5511
- Transport: TCP

## Profile Attempts

These are low-level frame/subcommand combinations, intentionally written without
using saved canonical profile names.

| Frame | Device subcommand style | `0101` | `0401 D130` | `0401 M0` | Result |
|:--|:--|:--:|:--:|:--:|:--|
| 3E | Q/L compatible word/bit subcommands (`0000`/`0001`) | OK | OK | OK | Usable |
| 4E | Q/L compatible word/bit subcommands (`0000`/`0001`) | OK | OK | OK | Usable |
| 3E | iQ-R style word/bit subcommands (`0002`/`0003`) | OK | OK | OK | Usable |
| 4E | iQ-R style word/bit subcommands (`0002`/`0003`) | OK | OK | OK | Usable |

## Conclusion

For this L16H GX Simulator 3 session, basic SLMP communication over
`127.0.0.1:5511/TCP` is available with all four tested low-level combinations.

This was a quick connection/profile check only. A full command availability
matrix was not run.

## Setting Note

For any future write-capable SLMP retest, keep this setting enabled:

- `Enable/Disable Online Change: Enable All (SLMP)`

Without that setting, write commands may fail even after basic communication is
established.
