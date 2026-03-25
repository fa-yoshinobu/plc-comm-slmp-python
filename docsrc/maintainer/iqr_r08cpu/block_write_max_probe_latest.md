# Block Write Maximum Probe Report

- Date: 2026-03-13 16:23:00
- PLC: Mitsubishi MELSEC iQ-R `R08CPU`
- Host: `192.168.250.101`
- Transport: `TCP`
- Port: `1025`
- Series: `iqr`

## Scope

This probe checked the practical maximum for a single word block write on the current validated target.

Test target:

- command: `1406` block write
- block type: single word block
- start device: `D100`
- validation method:
  1. read the original range in safe chunks
  2. send one `1406` word-block write for the full candidate size
  3. read back in safe chunks
  4. restore the original values in safe chunks

The probe intentionally avoided head addresses such as `D0`.

## Result

Focused boundary result:

| Points | Result | Detail |
|---|---|---|
| 951 | OK | write accepted, readback matched, restore confirmed |
| 952 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |
| 953 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |
| 954 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |
| 955 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |
| 956 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |
| 957 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |
| 958 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |
| 959 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |
| 960 | NG | `SLMPError end_code=0xC051 command=0x1406 subcommand=0x0002` |

Additional note:

- `1024` points was rejected by the client before send:
  - `ValueError: write_block total device points out of range (<=960): 1024`

## Practical Conclusion

- current client-side block-write limit for one request is `<=960` total device points
- on the validated `R08CPU`, the practical single word block-write limit was `951` points
- `952` through `960` were accepted by the client but rejected by the PLC with `0xC051`

## Cleanup

- the original `D100` range values were restored after every candidate probe
- restore verification succeeded for the checked prefix after each run
