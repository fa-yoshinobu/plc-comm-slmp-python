# G/HG Extended Specification R120PCPU UDP/1027 Follow-Up

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Target PLC: `R120PCPU`
- Scope: verify whether `SELF` and `SELF-CPU1` Extended Specification `G/HG` access works over the environment's actual UDP port `1027`

## 1. Executed Commands

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --port 1027 --series iqr --transport udp --target SELF --target SELF-CPU1 --device U3E0\G10 --device U3E0\HG20 --points 1 --points 4
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --port 1027 --series iqr --transport udp --target SELF --target SELF-CPU1 --device U3E0\G10 --device U3E0\HG20 --points 1 --points 4 --write-check
```

## 2. Result Summary

- Transport: `udp`
- Port: `1027`
- Targets:
  - `SELF` -> `module_io=0x03FF`
  - `SELF-CPU1` -> `module_io=0x03E0`
- Devices:
  - `U3E0\G10`
  - `U3E0\HG20`
- Point counts:
  - `1`
  - `4`
- Direct memory: `0xFA`

All tested combinations succeeded for both:

- read-only coverage
- write/readback/restore

## 3. Positive Results

The following aligned `UDP/1027` combinations completed `write -> readback -> restore` successfully:

| Target | Device | Points | Result |
|---|---|---:|---|
| `SELF` | `U3E0\G10` | `1` | `OK` |
| `SELF` | `U3E0\G10` | `4` | `OK` |
| `SELF` | `U3E0\HG20` | `1` | `OK` |
| `SELF` | `U3E0\HG20` | `4` | `OK` |
| `SELF-CPU1` | `U3E0\G10` | `1` | `OK` |
| `SELF-CPU1` | `U3E0\G10` | `4` | `OK` |
| `SELF-CPU1` | `U3E0\HG20` | `1` | `OK` |
| `SELF-CPU1` | `U3E0\HG20` | `4` | `OK` |

Common detail pattern:

- `points=1`
  - `before=[0x0000]`
  - `write=[0x001E]`
  - `readback=[0x001E]`
  - `restored=[0x0000]`
- `points=4`
  - `before=[0x0000, 0x0000, 0x0000, 0x0000]`
  - `write=[0x001E, 0x001F, 0x0020, 0x0021]`
  - `readback=[0x001E, 0x001F, 0x0020, 0x0021]`
  - `restored=[0x0000, 0x0000, 0x0000, 0x0000]`
- `restore=ok`

`read_type_name()` also succeeded on both UDP target paths:

- `SELF` -> `R120PCPU / 0x4844`
- `SELF-CPU1` -> `R120PCPU / 0x4844`

## 4. Practical Interpretation

- The earlier `udp` timeout result for `SELF` / `SELF-CPU1` was caused by using the wrong port (`1025`).
- On this hardware setup, the working UDP port is `1027`.
- With that correction, the same `U3E0\G10` / `U3E0\HG20` Extended Specification path now has both:
  - read-only confirmation
  - write/readback/restore confirmation
- This means the current environment has aligned Extended Specification proof on `UDP/1027` for:
  - `SELF + U3E0`
  - `SELF-CPU1 + U3E0`
  - `SELF-CPU2 + U3E1`
  - `SELF-CPU3 + U3E2`
  - `SELF-CPU4 + U3E3` for `G10/HG20`

## 5. Generated Local Evidence

- Coverage report: `internal_docsrc/iqr_r120pcpu/g_hg_extended_device_coverage_latest.md`
- Frame dumps: `internal_docsrc/iqr_r120pcpu/frame_dumps_g_hg_extended_device_coverage/`

## 6. Remaining Work

- whether `UDP/1027` also supports later addresses beyond `U3E0\G10` / `U3E0\HG20`
- whether `UDP/1027` and aligned write behavior hold on other PLC families


