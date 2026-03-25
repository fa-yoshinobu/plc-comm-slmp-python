# G/HG Multi-CPU UDP Write Follow-Up

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Target PLC family set observed in this sweep: `R08CPU`, `R08PCPU`
- Scope: verify whether aligned multi-CPU `G/HG` Extended Specification write/readback/restore works over `UDP` when using the environment's dedicated UDP port `1027`

## 1. Executed Commands

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --port 1027 --series iqr --transport udp --target SELF-CPU2 --device U3E1\G10 --device U3E1\HG20 --points 1 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --port 1027 --series iqr --transport udp --target SELF-CPU3 --device U3E2\G10 --device U3E2\HG20 --points 1 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --port 1027 --series iqr --transport udp --target SELF-CPU4 --device U3E3\G10 --device U3E3\HG20 --points 1 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --port 1027 --series iqr --transport udp --target SELF-CPU2 --device U3E1\G10 --device U3E1\HG20 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --port 1027 --series iqr --transport udp --target SELF-CPU3 --device U3E2\G10 --device U3E2\HG20 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --port 1027 --series iqr --transport udp --target SELF-CPU4 --device U3E3\G10 --device U3E3\HG20 --points 4 --write-check
```

## 2. Result Summary

- Transport: `udp`
- Port: `1027`
- Targets:
  - `SELF-CPU2` -> `module_io=0x03E1`
  - `SELF-CPU3` -> `module_io=0x03E2`
  - `SELF-CPU4` -> `module_io=0x03E3`
- Devices:
  - `U3E1\G10`, `U3E1\HG20`
  - `U3E2\G10`, `U3E2\HG20`
  - `U3E3\G10`, `U3E3\HG20`
- Point counts: `1`, `4`
- Direct memory: `0xFA`
- Mode: write-check

Total combinations executed: `12`

- `OK=12`
- `NG=0`

## 3. Positive Results

All tested combinations completed `write -> readback -> restore` successfully:

| Target | Device | Points | Result |
|---|---|---:|---|
| `SELF-CPU2` | `U3E1\G10` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\HG20` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\G10` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\HG20` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\G10` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\HG20` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\G10` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\HG20` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\G10` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\HG20` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\G10` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\HG20` | `4` | `OK` |

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

`read_type_name()` also succeeded on all three UDP target paths:

- `SELF-CPU2` -> `R08CPU / 0x4801`
- `SELF-CPU3` -> `R08PCPU / 0x4841`
- `SELF-CPU4` -> `R08PCPU / 0x4841`

## 4. Practical Interpretation

- On this hardware setup, `UDP` is not generally broken for Extended Specification. The earlier failures were tied to using the wrong UDP port.
- With the corrected UDP port `1027`, aligned multi-CPU Extended Specification access now has both:
  - read-only confirmation
  - write/readback/restore confirmation
- The current evidence is specific to the aligned pattern:
  - `SELF-CPU2 + U3E1`
  - `SELF-CPU3 + U3E2`
  - `SELF-CPU4 + U3E3`
- The current UDP write proof covers `G10/HG20` at `points=1` and `points=4`.

## 5. Generated Local Evidence

- Coverage report path used for the `SELF-CPU2` run: `internal_docsrc/iqr_r08cpu/g_hg_extended_device_coverage_latest.md`
- Coverage report path used for the later `SELF-CPU3` / `SELF-CPU4` runs: `internal_docsrc/iqr_r08pcpu/g_hg_extended_device_coverage_latest.md`

Because `*_latest.md` is reused, rely on the archived copies under the same directories when you need per-run preservation.

## 6. Remaining Work

- UDP write/readback/restore at later addresses beyond `G10/HG20`
- whether `SELF` / `SELF-CPU1` also require `1027` for successful UDP Extended Specification coverage
- whether the same UDP behavior holds on other PLC families


