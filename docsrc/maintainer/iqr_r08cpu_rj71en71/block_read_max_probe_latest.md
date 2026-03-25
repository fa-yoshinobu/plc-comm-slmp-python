# Block Read Maximum Probe Report

- Date: 2026-03-13 16:58:50
- Path under test: R08CPU + RJ71EN71 (assumed current route by operator setup)
- Host: `192.168.250.101`
- Port: `1025`
- Transport: `tcp`
- Series: `iqr`
- Method: binary search for highest command-accepted total points up to the client limit, then direct word-read cross-check at the accepted maximum
- Word device under test: `D100`
- Bit device under test: `M1000`

## Result Summary

- word block read practical maximum: `960` points
- bit block read practical maximum: `705` packed 16-bit points
- client-side request limit: `<=960` total points

## Important Interpretation Note

- `bit_blocks` in `0406` uses packed 16-bit units for bit devices
- example:
  - `read_block(bit_blocks=[("M1000", 1)])` returns one packed 16-bit value for `M1000..M1015`
  - if `M1000..M1003 = 1,0,1,0`, the first packed value is `0x0005`

## Client-Limit Confirmation

- word read 961: ValueError: read_block total device points out of range (<=960): 961
- bit read 961: ValueError: read_block total device points out of range (<=960): 961

### Word Block Read Attempts

| Points | Status | Detail |
|---|---|---|
| 960 | OK | read_ok count=960 |

### Bit Block Read Attempts

| Points | Status | Detail |
|---|---|---|
| 960 | NG | SLMPError: SLMP error end_code=0x4031 command=0x0406 subcommand=0x0002 |
| 480 | OK | read_ok count=480 |
| 720 | NG | SLMPError: SLMP error end_code=0x4031 command=0x0406 subcommand=0x0002 |
| 600 | OK | read_ok count=600 |
| 660 | OK | read_ok count=660 |
| 690 | OK | read_ok count=690 |
| 705 | OK | read_ok count=705 |
| 712 | NG | SLMPError: SLMP error end_code=0x4031 command=0x0406 subcommand=0x0002 |
| 708 | NG | SLMPError: SLMP error end_code=0x4031 command=0x0406 subcommand=0x0002 |
| 706 | NG | SLMPError: SLMP error end_code=0x4031 command=0x0406 subcommand=0x0002 |

## Functional Cross-Check at Accepted Maximum

- direct word read of `M1000` for `705` points matched `read_block(bit_blocks=[("M1000", 705)])`
- result: functional readback verified at the accepted maximum
