# Other-Station R00CPU Read-Only Probe

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Scope:
  - verify safe other-station access to `NW=1`, `station=2`
  - record read-only command coverage against the detected low-end CPU target
  - validate that `slmp_special_device_probe.py` no longer aborts on unsupported `LT/LST` paths

## Target

- Host: `192.168.250.101`
- TCP port: `1025`
- UDP port: `1027`
- Transport tested: TCP and UDP
- Series: `iqr`
- Target header:
  - `network=0x01`
  - `station=0x02`
  - `module_io=0x03FF`
  - `multidrop=0x00`

Detected model:

- `R00CPU`
- model code `0x48A0`

## Safe Read Results

Confirmed over TCP:

1. `0101 read_type_name`
2. `0401` direct reads:
   - `D0`
   - `M0`
   - `X0`
   - `Y0`
   - `R0`
   - `ZR0`
   - `W0`
3. `0403 read_random`
   - `D0`
   - `R0`
   - `D10` as dword read
4. `0406 read_block`
   - word blocks: `D0`, `R0`, `W0`
   - bit blocks: `M0`, `X0`, `Y0`
5. `0801/0802 monitor`
   - `D0`
   - `D1`
   - `D10` as dword monitor

Confirmed over UDP:

1. `0101 read_type_name`
2. `0401 D0`
3. `0403 read_random`
4. `0406 read_block`
5. `0801/0802 monitor`

Observed values were all zero in this probe session.

## Extended Specification / Special Device Notes

- `Extended Specification CPU buffer G0` with `ext=0x03E0`, `direct=0xFA` returned `OK` and value `[0]`.
- `Extended Specification CPU buffer HG0` returned `0x4031` on the same target.
- Direct `G0` / `HG0` `0401` returned `0xC05B`.
- `0601` module reads succeeded only for `module_no=0x03E0`; `0x0000` returned `0x4043`, `0x03FF` returned `0x4080`.
- `LT/LST` state devices should be checked through helper-backed normal access rather than exploratory direct bit access on this project.
- After aligning the probe with that policy, `read_ltc_states(...)`, `read_lts_states(...)`, `read_lstc_states(...)`, and `read_lsts_states(...)` all returned `OK` on this target.

## Script Robustness Fix

`scripts/slmp_special_device_probe.py` previously aborted when the initial read in the manual-write helper failed on an unsupported target. The helper paths now record `NG` and continue so the script always produces a report.

Validated by:

```text
python scripts/slmp_special_device_probe.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr --network 0x01 --station 0x02 --module-io 0x03FF --multidrop 0x00
```

Result:

- script completed
- report written to `internal_docsrc/iqr_r00cpu/special_device_probe_latest.md`
- unsupported paths were recorded as `NG` instead of terminating the run

