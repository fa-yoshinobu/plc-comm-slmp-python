# R00CPU Small Write Readback Restore

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Target:
  - host `192.168.250.101`
  - port `1025`
  - transport `tcp`
  - `network=0x01`
  - `station=0x02`
  - `module_io=0x03FF`
  - `multidrop=0x00`
- Detected model: `R00CPU` (`0x48A0`)

## Scope

Single-point temporary write/readback/restore on low-address devices:

- `D10`
- `M10`
- `R10`
- `W10`

The probe intentionally used the smallest practical temporary value change:

- word devices: `0 -> 1`, otherwise `nonzero -> 0`
- bit devices: toggle once and restore immediately

## Result

All four probes completed successfully.

| Device | Before | Test | After | Restored |
|---|---:|---:|---:|---:|
| `D10` | `0` | `1` | `1` | `0` |
| `M10` | `False` | `True` | `True` | `False` |
| `R10` | `0` | `1` | `1` | `0` |
| `W10` | `0` | `1` | `1` | `0` |

## Evidence

Detailed live output is stored in:

- `internal_docsrc/iqr_r00cpu/small_write_probe_latest.md`

