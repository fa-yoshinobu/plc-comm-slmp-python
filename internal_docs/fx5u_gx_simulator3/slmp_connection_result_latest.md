# GX Simulator 3 FX5U SLMP Connection Result

Date: 2026-06-21 JST

## Summary

The FX5U simulation endpoint was checked only for whether SLMP communication
can be established. It could not be confirmed.

TCP port `127.0.0.1:5511` was listening, but the tested binary SLMP request
profiles did not return a valid SLMP response. Because the first read/type-name
requests did not succeed, the full command availability matrix was not run.

## Target

- Simulator: GX Simulator 3
- GX Works3 version: 1.125F
- Target machine: FX5U simulation, as specified by the operator
- Host: 127.0.0.1
- Port: 5511
- Transport: TCP

## Profile Attempts

These are low-level frame/subcommand combinations, intentionally written without
using saved canonical profile names.

| Frame | Device subcommand style | Result |
|:--|:--|:--|
| 3E | Q/L compatible word/bit subcommands (`0000`/`0001`) | NG: timeout or connection reset |
| 4E | Q/L compatible word/bit subcommands (`0000`/`0001`) | NG: timeout or connection reset |
| 3E | iQ-R style word/bit subcommands (`0002`/`0003`) | NG: timeout or connection reset |
| 4E | iQ-R style word/bit subcommands (`0002`/`0003`) | NG: timeout or connection reset |

Additional target-header variants were also sampled with read-only requests
(`0101` and `0401`), but none returned a valid SLMP response.

## Conclusion

For this FX5U GX Simulator 3 session, SLMP communication over
`127.0.0.1:5511/TCP` is treated as not available from the tested client path.

The failure occurs before command-level validation, so no claim is made that
individual SLMP commands are supported or unsupported by the CPU. The current
result is simply: no working connection combination was found.

## Recheck

2026-06-21 JST recheck:

- `127.0.0.1:5511/TCP` was listening.
- Owner process: `FSimRun3.exe`.
- `0101` type-name read and `0401` `D130` word read were retried.
- Result remained NG for all four frame/subcommand combinations.

| Frame | Device subcommand style | Recheck result |
|:--|:--|:--|
| 3E | Q/L compatible word/bit subcommands (`0000`/`0001`) | NG: timeout |
| 4E | Q/L compatible word/bit subcommands (`0000`/`0001`) | NG: connection reset or timeout |
| 3E | iQ-R style word/bit subcommands (`0002`/`0003`) | NG: connection reset or timeout |
| 4E | iQ-R style word/bit subcommands (`0002`/`0003`) | NG: connection reset or timeout |

## Setting Note

For any future write-capable SLMP retest, keep this setting enabled:

- `Enable/Disable Online Change: Enable All (SLMP)`

Without that setting, write commands may fail even after basic communication is
established.
