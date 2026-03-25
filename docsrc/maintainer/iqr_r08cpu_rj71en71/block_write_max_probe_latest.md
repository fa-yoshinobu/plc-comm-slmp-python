# Block Write Maximum Probe Report

- Date: 2026-03-13 16:58:50
- Path under test: R08CPU + RJ71EN71 (assumed current route by operator setup)
- Host: `192.168.250.101`
- Port: `1025`
- Transport: `tcp`
- Series: `iqr`
- Method: binary search for highest accepted total points up to the client limit, with functional readback/restore verification using packed bit-device words
- Word device under test: `D100`
- Bit device under test: `M1000`
- Backup/readback/restore chunk size: `240`

## Result Summary

- word block write practical maximum: `951` points
- bit block write practical maximum: `705` packed 16-bit points
- client-side request limit: `<=960` total points

## Important Interpretation Note

- `bit_blocks` in `1406` uses packed 16-bit units for bit devices
- example:
  - `write_block(bit_blocks=[("M1000", [0x0005])])` writes the packed pattern for `M1000..M1015`
  - direct bit readback then shows `M1000..M1003 = 1,0,1,0`

## Client-Limit Confirmation

- word write 961: ValueError: write_block total device points out of range (<=960): 961
- bit write 961: ValueError: write_block total device points out of range (<=960): 961

### Word Block Write Attempts

| Points | Status | Detail |
|---|---|---|
| 960 | NG | SLMPError: SLMP error end_code=0xC051 command=0x1406 subcommand=0x0002; restore_attempted |
| 480 | OK | write_ok verified_and_restored count=480 |
| 720 | OK | write_ok verified_and_restored count=720 |
| 840 | OK | write_ok verified_and_restored count=840 |
| 900 | OK | write_ok verified_and_restored count=900 |
| 930 | OK | write_ok verified_and_restored count=930 |
| 945 | OK | write_ok verified_and_restored count=945 |
| 952 | NG | SLMPError: SLMP error end_code=0xC051 command=0x1406 subcommand=0x0002; restore_attempted |
| 948 | OK | write_ok verified_and_restored count=948 |
| 950 | OK | write_ok verified_and_restored count=950 |
| 951 | OK | write_ok verified_and_restored count=951 |

### Bit Block Write Command-Acceptance Attempts

| Points | Status | Detail |
|---|---|---|
| 960 | NG | SLMPError: SLMP error end_code=0xC051 command=0x1406 subcommand=0x0002 |
| 480 | OK | command accepted |
| 720 | NG | SLMPError: SLMP error end_code=0x4031 command=0x1406 subcommand=0x0002 |
| 600 | OK | command accepted |
| 660 | OK | command accepted |
| 690 | OK | command accepted |
| 705 | OK | command accepted |
| 712 | NG | SLMPError: SLMP error end_code=0x4031 command=0x1406 subcommand=0x0002 |
| 708 | NG | SLMPError: SLMP error end_code=0x4031 command=0x1406 subcommand=0x0002 |
| 706 | NG | SLMPError: SLMP error end_code=0x4031 command=0x1406 subcommand=0x0002 |

## Functional Cross-Check at Accepted Maximum

- direct word read of `M1000` for `705` points was used as the backup image
- `write_block(bit_blocks=[("M1000", packed_values)])` succeeded for `705` points
- direct word readback matched the written packed values
- `read_block(bit_blocks=[("M1000", 705)])` also matched the written packed values
- restore by packed block write succeeded and direct word readback returned the original image
