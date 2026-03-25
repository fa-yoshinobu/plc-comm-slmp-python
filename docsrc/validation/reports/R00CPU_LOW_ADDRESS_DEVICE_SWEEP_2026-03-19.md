# R00CPU Low-Address Device Sweep

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Target:
  - host `192.168.250.100`
  - TCP `1025`
  - `network=0x01`
  - `station=0x02`
  - `module_io=0x03FF`
  - `multidrop=0x00`
- Detected model: `R00CPU` (`0x48A0`)

## Scope

This probe intentionally avoided large addresses.

- one representative low address per device family
- read-only only
- direct `0401` for standard device families
- helper-backed normal access for `LTS/LTC/LSTS/LSTC`
- raw `0401` for `S0` because typed APIs intentionally disable `S` on this project
- Extended Specification `0401/0082` CPU-buffer path for `G/HG`

## Summary

- `OK`: 40 families/paths
- `NG`: 1 family/path

`OK` families/paths:

- `SM0`
- `SD0`
- `X0`
- `Y0`
- `M0`
- `L0`
- `F0`
- `V0`
- `B0`
- `D0`
- `W0`
- `TS0`
- `TC0`
- `TN0`
- `LTS0` through `read_lts_states(...)`
- `LTC0` through `read_ltc_states(...)`
- `LTN0`
- `STS0`
- `STC0`
- `STN0`
- `LSTS0` through `read_lsts_states(...)`
- `LSTC0` through `read_lstc_states(...)`
- `LSTN0`
- `CS0`
- `CC0`
- `CN0`
- `LCS0`
- `LCC0`
- `LCN0`
- `SB0`
- `SW0`
- `DX0`
- `DY0`
- `S0`
- `Z0`
- `LZ0`
- `R0`
- `ZR0`
- `RD0`
`U3E0\G0` through Extended Specification CPU-buffer read

`NG` families/paths:

`U3E0\HG0` through Extended Specification CPU-buffer read -> `target-specific (skip)`

## Notes

- `LTS/LTC/LSTS/LSTC` should not be interpreted through exploratory direct bit access on this project. The intended read path is the helper-backed `LTN/LSTN` decode route, and that route returned `False` successfully on this target.
- `S0` itself is readable on this target; only typed API write support stays intentionally disabled by project policy.
- `G` and `HG` are not ordinary direct-device results here. They were checked through the current Extended Specification CPU-buffer route.
- Detailed per-row output is stored in:
  - `internal_docsrc/iqr_r00cpu/low_address_device_sweep_latest.md`

