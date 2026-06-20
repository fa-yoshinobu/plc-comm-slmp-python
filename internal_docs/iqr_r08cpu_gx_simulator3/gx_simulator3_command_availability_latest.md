# GX Simulator 3 Command Availability Report

## Target

- Date: 2026-06-21 JST
- Endpoint: `127.0.0.1:5511`
- Transport: TCP
- Simulator: GX Simulator 3
- GX Works3 version: 1.125F
- Reported model: `R08CPU`
- Reported model code: `0x4801`
- Main validation profile: `4e/iqr`
- Standard target header: network `0x00`, station `0xFF`, module I/O `0x03FF`, multidrop `0x00`
- Required GX Works3/GX Simulator 3 setting: `Enable/Disable Online Change: Enable All (SLMP)`

The standard high-level canonical PLC profile route was intentionally not used
for this local probe. The probe used the low-level manual profile path:

- frame type: `3e` or `4e`
- access profile: `ql` or `iqr`
- data code: binary

## Parameter Change

Before the PC parameter change, device write commands returned:

- `1401/0000`: `end_code=0x0055`
- `1401/0001`: `end_code=0x0055`
- `1401/0002`: `end_code=0x0055`
- `1401/0003`: `end_code=0x0055`

After setting `Enable/Disable Online Change` to `Enable All (SLMP)` in GX
Works3/GX Simulator 3, representative word and bit writes succeeded and were
confirmed by readback. This setting is required for SLMP write commands on this
simulation endpoint; without it, the simulator returns `0x0055` for writes.

## Profile Combination Sweep

Representative write/restore checks were run against `D1100` and `M1100`.

| Combination | Word write | Bit write | Result |
| --- | --- | --- | --- |
| `3e/ql` | OK | OK | Usable |
| `4e/ql` | OK | OK | Usable |
| `3e/iqr` | OK | OK | Usable |
| `4e/iqr` | OK | OK | Usable |

The simulator is permissive: all four frame/access-profile combinations accept
basic reads and writes. For this R08CPU simulation target, `4e/iqr` remains the
preferred manual combination because `0101` reports an R-series CPU.

## Command Results

The following table records the command availability observed with `4e/iqr`.
Write tests used read-modify-write or same-value writeback and restored the
original value where applicable.

| Command | Operation | Result | Detail |
| --- | --- | --- | --- |
| `0101/0000` | Read type name | OK | `R08CPU`, model code `0x4801` |
| `0401/0002` | Batch read word | OK | `D1000 x2` returned `[0, 0]` |
| `0401/0003` | Batch read bit | OK | `M1000 x4` returned all OFF |
| `1401/0002` | Batch write word | OK | `D1000` changed `0 -> 1`, readback OK, restored |
| `1401/0003` | Batch write bit | OK | `M1000` changed `False -> True`, readback OK, restored |
| `0403/0002` | Random read | OK | `D1000` word and `D1002` dword read OK |
| `1402/0002` | Random write word | OK | `D1001` changed `0 -> 2`, readback OK, restored |
| `1402/0002` | Random write dword | OK | `D1002` changed `0 -> 65536`, readback OK, restored |
| `1402/0003` | Random write bit | OK | `M1001` changed `False -> True`, readback OK, restored |
| `0801/0002` | Monitor entry | OK | Registered `D1000` word and `D1002` dword |
| `0802/0000` | Monitor execute | OK | Returned one word and one dword |
| `0406/0002` | Block read | OK | Word and bit block read returned success |
| `1406/0002` | Block write word | OK | `D1010 x2` changed and restored |
| `1406/0002` | Block write bit block | OK | Command accepted and restored; simple bit readback confirmed first changed bit |
| `1406/0002` | Mixed block write | OK | `D1020` + `M1020` mixed write accepted, readback changed, restored |
| `0619/0000` | Self test | OK | Loopback `A1B2` returned successfully |
| `0613/0000` | Memory read | OK | Head `0`, length `1` returned `[0]` |
| `1613/0000` | Memory write | OK | Same-value writeback at head `0` succeeded |
| `0601/0000` | Extend unit read | OK | Module `0x03E0`, head `0`, length `1` returned data |
| `1601/0000` | Extend unit write | OK | Same-value writeback to module `0x03E0` succeeded |
| `1001/0000` | Remote RUN | OK | Accepted; used to restore final state |
| `1002/0000` | Remote STOP | OK | Accepted |
| `1003/0000` | Remote PAUSE | OK | Accepted; RUN restore accepted |
| `1005/0000` | Remote latch clear | Conditional OK | `0x4013` while RUN; OK after remote STOP |
| `1006/0000` | Remote RESET | Conditional OK | In STOP state, the simulator closed the connection after request; reconnect succeeded |
| `1617/0000` | Clear error | OK | Accepted |
| `041A/0000` | Label array read | NG | Dummy label returned `0x40C0` |
| `141A/0000` | Label array write | NG | Dummy label returned `0x40C0` |
| `041C/0000` | Label random read | NG | Dummy label returned `0x40C0` |
| `141B/0000` | Label random write | NG | Dummy label returned `0x40C0` |

## Conditional and Excluded Items

- `1005` remote latch clear is PLC-state dependent. On this target it failed in
  RUN with `0x4013`, then succeeded after `1002` remote STOP.
- `1006` remote reset is disruptive. With response waiting enabled, the
  connection closed while receiving data after the reset request. A subsequent
  reconnect and `0101` read succeeded. The final state was restored with
  `1001` remote RUN.
- Label commands were probed only with a dummy label. `0x40C0` should be treated
  as a label-side condition, such as a missing label or external label access not
  being enabled. To confirm label command usability, create or identify a real
  externally accessible label in the GX Works3 project and rerun the label tests.
- Remote password lock/unlock (`1631`/`1630`) was not executed in this pass to
  avoid changing or depending on remote-password state.

## Conclusion

After the PC parameter change, the GX Simulator 3 R08CPU endpoint allows the
device, monitor, memory, extend-unit, self-test, error-clear, and most remote
control command groups tested here. The previous `0x0055` write rejection is no
longer present.

The only remaining non-general result is the label command group, which requires
project-specific label definitions and external access settings before it can be
validated as usable.
