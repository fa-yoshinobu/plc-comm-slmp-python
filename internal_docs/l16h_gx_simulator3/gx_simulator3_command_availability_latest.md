# GX Simulator 3 L16H Command Availability

Date: 2026-06-21 JST

## Summary

The L16H GX Simulator 3 endpoint was tested over `127.0.0.1:5511/TCP`.

Primary low-level combination used for this full command matrix:

- Frame: 3E
- Device subcommand style: Q/L compatible word/bit subcommands (`0000`/`0001`)
- Target header: network `0x00`, station `0xFF`, module I/O `0x03FF`, multidrop `0x00`

The same full command matrix was also rerun with:

- Frame: 4E
- Device subcommand style: iQ-R style word/bit subcommands (`0002`/`0003`)
- Target header: network `0x00`, station `0xFF`, module I/O `0x03FF`, multidrop `0x00`

Result:

- Normal device, random, monitor, block, memory, extend unit, remote operation,
  self-test, and clear-error commands succeeded.
- Label commands reached the PLC but returned `0x40C0` with a dummy label name.
- Remote password commands were not executed to avoid changing/locking the
  simulator password state.

## Target

- Simulator: GX Simulator 3
- GX Works3 version: 1.125F
- Target machine: L16H simulation, as specified by the operator
- Reported model: `L16HCPU`
- Reported model code: `0x48C2`
- Host: `127.0.0.1`
- Port: `5511`
- Transport: TCP
- Owner process during test: `LSimRun3.exe`

## Write Safety

The writable device checks used low addresses in the simulator and restored the
original values where values were changed.

- `D130/D131` were restored after direct word write.
- `M0` was restored after direct bit write.
- Block write used the same values already present for `D130` and `M0`.
- Memory and extend-unit write checks wrote back the same word that was read.

## Command Matrix

### 3E + Q/L-Compatible Subcommands

| Code | Category | Command | Result | Detail |
|:--:|:--|:--|:--:|:--|
| `0101` | System | Read type name | OK | model=`L16HCPU`, model_code=`0x48C2` |
| `0401` | System | Read CPU operation state (`SD203`) | OK | status=Run, raw=`0x0000` |
| `0401` | Device | Read words `D130 x2` | OK | values=`[0, 0]` |
| `0401` | Device | Read bits `M0 x16` | OK | all false |
| `1401` | Device | Write words `D130 x2` and restore | OK | after=`[4660, 0]`, restored=`[0, 0]` |
| `1401` | Device | Write bit `M0` and restore | OK | after=`[True]`, restored=`[False]` |
| `0403` | Device | Read random `D130`/`D132` | OK | word=`{'D130': 0}`, dword=`{'D132': 0}` |
| `1402` | Device | Write random words `D130`/`D132` | OK | accepted |
| `1402` | Device | Write random bit `M0` | OK | accepted |
| `0801`/`0802` | Device | Register and execute monitor `D130`/`D132` | OK | word=`[0]`, dword=`[0]` |
| `0406` | Device | Read block `D130 x2` + `M0` word | OK | word block=`[0, 0]`, bit block=`[0]` |
| `1406` | Device | Write block same values `D130`/`M0` | OK | `D130=[0, 0]`, `M0..M15` all false |
| `041A` | Label | Array label read dummy | NG | `end_code=0x40C0` |
| `141A` | Label | Array label write dummy | NG | `end_code=0x40C0` |
| `041C` | Label | Random label read dummy | NG | `end_code=0x40C0` |
| `141B` | Label | Random label write dummy | NG | `end_code=0x40C0` |
| `0613` | Memory | Memory read words head `0 x1` | OK | values=`[0]` |
| `1613` | Memory | Memory write same word head `0` | OK | accepted |
| `0601` | Extend unit | Extend unit read words module `0x03E0`, head `0 x1` | OK | values=`[27330]` |
| `1601` | Extend unit | Extend unit write same word module `0x03E0`, head `0` | OK | accepted |
| `0619` | Other | Self test loopback `ABCD` | OK | loopback=`b'ABCD'` |
| `1617` | Other | Clear error | OK | accepted |
| `1002` | Remote | Remote STOP | OK | accepted |
| `0401` | Remote | State after STOP | OK | status=Stop, raw=`0x0002` |
| `1005` | Remote | Remote latch clear while STOP | OK | accepted |
| `1001` | Remote | Remote RUN | OK | accepted |
| `0401` | Remote | State after RUN | OK | status=Run, raw=`0x0000` |
| `1003` | Remote | Remote PAUSE | OK | accepted |
| `0401` | Remote | State after PAUSE | OK | status=Pause, raw=`0x0003` |
| `1001` | Remote | Remote RUN after PAUSE | OK | accepted |
| `1630` | Remote password | Remote password unlock dummy | SKIP | not executed; may alter/require password state |
| `1631` | Remote password | Remote password lock dummy | SKIP | not executed; may lock simulator access |
| `1006` | Remote | Remote RESET and reconnect | OK | reconnect returned model=`L16HCPU` |

### 4E + iQ-R-Style Subcommands

This matrix used 4E frames and device word/bit subcommands `0002`/`0003`.

| Code | Category | Command | Result | Detail |
|:--:|:--|:--|:--:|:--|
| `0101` | System | Read type name | OK | model=`L16HCPU`, model_code=`0x48C2` |
| `0401` | System | Read CPU operation state (`SD203`) | OK | status=Run, raw=`0x0000` |
| `0401` | Device | Read words `D130 x2` | OK | values=`[0, 0]` |
| `0401` | Device | Read bits `M0 x16` | OK | all false |
| `1401` | Device | Write words `D130 x2` and restore | OK | after=`[4660, 0]`, restored=`[0, 0]` |
| `1401` | Device | Write bit `M0` and restore | OK | after=`[True]`, restored=`[False]` |
| `0403` | Device | Read random `D130`/`D132` | OK | word=`{'D130': 0}`, dword=`{'D132': 0}` |
| `1402` | Device | Write random words `D130`/`D132` | OK | accepted |
| `1402` | Device | Write random bit `M0` | OK | accepted |
| `0801`/`0802` | Device | Register and execute monitor `D130`/`D132` | OK | word=`[0]`, dword=`[0]` |
| `0406` | Device | Read block `D130 x2` + `M0` word | OK | word block=`[0, 0]`, bit block=`[0]` |
| `1406` | Device | Write block same values `D130`/`M0` | OK | `D130=[0, 0]`, `M0..M15` all false |
| `041A` | Label | Array label read dummy | NG | `end_code=0x40C0` |
| `141A` | Label | Array label write dummy | NG | `end_code=0x40C0` |
| `041C` | Label | Random label read dummy | NG | `end_code=0x40C0` |
| `141B` | Label | Random label write dummy | NG | `end_code=0x40C0` |
| `0613` | Memory | Memory read words head `0 x1` | OK | values=`[0]` |
| `1613` | Memory | Memory write same word head `0` | OK | accepted |
| `0601` | Extend unit | Extend unit read words module `0x03E0`, head `0 x1` | OK | values=`[27330]` |
| `1601` | Extend unit | Extend unit write same word module `0x03E0`, head `0` | OK | accepted |
| `0619` | Other | Self test loopback `ABCD` | OK | loopback=`b'ABCD'` |
| `1617` | Other | Clear error | OK | accepted |
| `1002` | Remote | Remote STOP | OK | accepted |
| `0401` | Remote | State after STOP | OK | status=Stop, raw=`0x0002` |
| `1005` | Remote | Remote latch clear while STOP | OK | accepted |
| `1001` | Remote | Remote RUN | OK | accepted |
| `0401` | Remote | State after RUN | OK | status=Run, raw=`0x0000` |
| `1003` | Remote | Remote PAUSE | OK | accepted |
| `0401` | Remote | State after PAUSE | OK | status=Pause, raw=`0x0003` |
| `1001` | Remote | Remote RUN after PAUSE | OK | accepted |
| `1630` | Remote password | Remote password unlock dummy | SKIP | not executed; may alter/require password state |
| `1631` | Remote password | Remote password lock dummy | SKIP | not executed; may lock simulator access |
| `1006` | Remote | Remote RESET and reconnect | OK | reconnect returned model=`L16HCPU` |

## Conclusion

For the tested L16H GX Simulator 3 session, all non-password SLMP command
families implemented by this client were usable with both tested full-matrix
combinations:

- 3E frame + Q/L compatible device subcommands (`0000`/`0001`)
- 4E frame + iQ-R style device subcommands (`0002`/`0003`)

Label commands returned a valid SLMP error for a nonexistent label. This means
the command path responds, but real label availability was not validated because
no valid label name was provided.

## Setting Note

For write-capable SLMP tests, keep this setting enabled:

- `Enable/Disable Online Change: Enable All (SLMP)`
