# G/HG Extended Specification Coverage Sweep on R120PCPU

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Target PLC: `R120PCPU`
- Scope: expanded read-only coverage sweep for `G/HG` Extended Specification on multiple transports, named targets, and point counts

## 1. Executed Command

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --series iqr --transport tcp --transport udp --target SELF --target SELF-CPU1 --device U3E0\G10 --device U3E0\HG20 --points 1 --points 4
```

## 2. Sweep Dimensions

- Transports: `tcp`, `udp`
- Targets:
  - `SELF` -> `network=0x00`, `station=0xFF`, `module_io=0x03FF`, `multidrop=0x00`
  - `SELF-CPU1` -> `network=0x00`, `station=0xFF`, `module_io=0x03E0`, `multidrop=0x00`
- Devices:
  - `U3E0\G10`
  - `U3E0\HG20`
- Point counts:
  - `1`
  - `4`
- Direct memory: `0xFA`
- Mode: read-only

Total combinations executed: `16`

## 3. Result Summary

- `TCP`: `OK=8`, `NG=0`
- `UDP`: `OK=0`, `NG=8`
- Overall: `OK=8`, `NG=8`, `SKIP=0`

## 4. Positive Results

The following combinations completed successfully:

- `tcp + SELF + U3E0\G10 + points=1`
- `tcp + SELF + U3E0\G10 + points=4`
- `tcp + SELF + U3E0\HG20 + points=1`
- `tcp + SELF + U3E0\HG20 + points=4`
- `tcp + SELF-CPU1 + U3E0\G10 + points=1`
- `tcp + SELF-CPU1 + U3E0\G10 + points=4`
- `tcp + SELF-CPU1 + U3E0\HG20 + points=1`
- `tcp + SELF-CPU1 + U3E0\HG20 + points=4`

Observed values were all zero on this sweep:

- point-1 reads: `[0x0000]`
- point-4 reads: `[0x0000, 0x0000, 0x0000, 0x0000]`

## 5. Negative Results

Every tested UDP combination timed out on port `1025`:

- `udp + SELF + U3E0\G10 + points=1/4`
- `udp + SELF + U3E0\HG20 + points=1/4`
- `udp + SELF-CPU1 + U3E0\G10 + points=1/4`
- `udp + SELF-CPU1 + U3E0\HG20 + points=1/4`

`read_type_name()` also timed out on both UDP target paths during the same sweep.

Later follow-up clarified that this was not a universal `UDP` failure. On the same hardware family, aligned multi-CPU Extended Specification access succeeded over `UDP` when the port was corrected to `1027`, first for read-only coverage and then for write/readback/restore on `G10/HG20`. A separate `R120PCPU` follow-up also confirmed the same correction for `SELF` / `SELF-CPU1`. See `G_HG_MULTI_CPU_UDP_READONLY_2026-03-19.md`, `G_HG_MULTI_CPU_UDP_WRITE_2026-03-19.md`, and `G_HG_extended_device_R120PCPU_UDP_1027_2026-03-19.md`.

## 6. Practical Interpretation

- The current iQ-R capture-aligned Extended Specification `G/HG` builder is confirmed on this `R120PCPU` target for:
  - `TCP`
  - `SELF`
  - `SELF-CPU1`
  - `U3E0\G10`
  - `U3E0\HG20`
  - point counts `1` and `4`
- This materially extends the earlier single-word smoke evidence.
- The same path is not confirmed over `UDP/1025` on this target; current evidence for that exact sweep is a full timeout across all tested combinations.
- Later follow-up indicates that `UDP/1027` can succeed for aligned multi-CPU read-only coverage, aligned `G10/HG20` write/readback/restore, and `SELF` / `SELF-CPU1` `U3E0\G10` / `U3E0\HG20` write/readback/restore, so the current `UDP` conclusion is port-specific rather than protocol-wide.

## 7. Generated Local Evidence

- Coverage report: `internal_docsrc/iqr_r120pcpu/g_hg_extended_device_coverage_latest.md`
- Frame dumps: `internal_docsrc/iqr_r120pcpu/frame_dumps_g_hg_extended_device_coverage/`

## 8. Remaining Work

Still open after this sweep:

- `SELF-CPU2` through `SELF-CPU4`
- temporary write/readback/restore at the wider point counts
- alternate qualified addresses beyond `U3E0\G10` and `U3E0\HG20`
- non-`R120PCPU` target families


