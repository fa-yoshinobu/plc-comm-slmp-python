# GX Simulator 3 MXR300 SLMP Connection Result

Date: 2026-06-21 JST

## Summary

The MXR300 simulation endpoint was checked only for whether SLMP communication
can be established. It could not be confirmed.

TCP port `127.0.0.1:5511` was listening, owned by `MXSimRun3.exe`, but the
tested binary SLMP request profiles did not return a valid SLMP response.
Because the first read/type-name requests did not succeed, the full command
availability matrix was not run.

## Target

- Simulator: GX Simulator 3
- GX Works3 version: 1.125F
- Target machine: MXR300 simulation, as specified by the operator
- Host: `127.0.0.1`
- Port: `5511`
- Transport: TCP
- Owner process during test: `MXSimRun3.exe`

## Profile Attempts

These are low-level frame/subcommand combinations, intentionally written without
using saved canonical profile names.

| Frame | Device subcommand style | `0101` | `0401 D130` | `0401 M0` | Result |
|:--|:--|:--:|:--:|:--:|:--|
| 3E | Q/L compatible word/bit subcommands (`0000`/`0001`) | NG | NG | NG | timeout |
| 4E | Q/L compatible word/bit subcommands (`0000`/`0001`) | NG | NG | NG | timeout |
| 3E | iQ-R style word/bit subcommands (`0002`/`0003`) | NG | NG | NG | timeout |
| 4E | iQ-R style word/bit subcommands (`0002`/`0003`) | NG | NG | NG | timeout |

## Conclusion

For this MXR300 GX Simulator 3 session, SLMP communication over
`127.0.0.1:5511/TCP` is treated as not available from the tested client path.

The failure occurs before command-level validation, so no claim is made that
individual SLMP commands are supported or unsupported by the simulator target.
The current result is simply: no working connection combination was found.

## Setting Note

For any future write-capable SLMP retest, keep this setting enabled:

- `Enable/Disable Online Change: Enable All (SLMP)`

Without that setting, write commands may fail even after basic communication is
established.
