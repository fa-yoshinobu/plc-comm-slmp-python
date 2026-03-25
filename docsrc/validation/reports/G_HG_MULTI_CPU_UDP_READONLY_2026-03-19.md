# G/HG Multi-CPU UDP Read-Only Follow-Up

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Target PLC family set observed in this sweep: `R08CPU`, `R08PCPU`
- Scope: verify whether aligned multi-CPU `G/HG` Extended Specification read-only access works over `UDP` when using the environment's dedicated UDP port `1027`

## 1. Executed Commands

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --port 1027 --series iqr --transport udp --target SELF-CPU2 --device U3E1\G10 --device U3E1\HG20 --points 1 --points 4
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --port 1027 --series iqr --transport udp --target SELF-CPU3 --device U3E2\G10 --device U3E2\HG20 --points 1 --points 4
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --port 1027 --series iqr --transport udp --target SELF-CPU4 --device U3E3\G10 --device U3E3\HG20 --points 1 --points 4
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
- Mode: read-only

Total combinations executed: `12`

- `OK=12`
- `NG=0`

## 3. Positive Results

All tested combinations succeeded:

| Target | Device | Points | Result |
|---|---|---:|---|
| `SELF-CPU2` | `U3E1\G10` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\G10` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\HG20` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\HG20` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\G10` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\G10` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\HG20` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\HG20` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\G10` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\G10` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\HG20` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\HG20` | `4` | `OK` |

`read_type_name()` also succeeded on all three UDP target paths:

- `SELF-CPU2` -> `R08CPU / 0x4801`
- `SELF-CPU3` -> `R08PCPU / 0x4841`
- `SELF-CPU4` -> `R08PCPU / 0x4841`

Observed read values were all zero on this follow-up:

- point-1 reads: `[0x0000]`
- point-4 reads: `[0x0000, 0x0000, 0x0000, 0x0000]`

## 4. Practical Interpretation

- The earlier `UDP` timeout result was not a universal protocol conclusion. It came from a different environment assumption: `udp` was tested on port `1025`.
- On this hardware setup, `UDP` uses port `1027`.
- With the corrected UDP port, aligned multi-CPU Extended Specification read-only access works on:
  - `SELF-CPU2 + U3E1`
  - `SELF-CPU3 + U3E2`
  - `SELF-CPU4 + U3E3`
- This follow-up confirms that the Extended Specification aligned-pair rule is not `TCP`-only for read access.
- Later same-day follow-up extended the proof to `UDP` write/readback/restore for aligned `G10/HG20` at `points=1` and `points=4`. See `G_HG_MULTI_CPU_UDP_WRITE_2026-03-19.md`.

## 5. Generated Local Evidence

- Coverage report path used for the `SELF-CPU2` run: `internal_docsrc/iqr_r08cpu/g_hg_extended_device_coverage_latest.md`
- Coverage report path used for the later `SELF-CPU3` / `SELF-CPU4` runs: `internal_docsrc/iqr_r08pcpu/g_hg_extended_device_coverage_latest.md`

Because `*_latest.md` is reused, rely on the archived copies under the same directories when you need per-run preservation.

## 6. Remaining Work

- UDP write/readback/restore on the corrected UDP port
- whether `SELF` / `SELF-CPU1` also require `1027` for successful UDP Extended Specification coverage
- whether the same UDP behavior holds on other PLC families


