# G/HG Multi-CPU Target-Aligned Write Follow-Up

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Target PLC family set observed in this sweep: `R08CPU`, `R08PCPU`
- Scope: confirm whether target-aligned multi-CPU target headers restore write symmetry for `G/HG` Extended Specification across multiple point counts, follow-up addresses, and non-zero restore cases

## 1. Executed Commands

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU2 --device U3E1\G10 --device U3E1\HG20 --points 1 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU3 --device U3E2\G10 --device U3E2\HG20 --points 1 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU4 --device U3E3\G10 --device U3E3\HG20 --points 1 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU2 --device U3E1\G10 --device U3E1\HG20 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU3 --device U3E2\G10 --device U3E2\HG20 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU4 --device U3E3\G10 --device U3E3\HG20 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU2 --device U3E1\G30 --device U3E1\HG30 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU3 --device U3E2\G30 --device U3E2\HG30 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU4 --device U3E3\G30 --device U3E3\HG30 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU2 --device U3E1\G50 --device U3E1\HG50 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU3 --device U3E2\G50 --device U3E2\HG50 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU4 --device U3E3\G50 --device U3E3\HG50 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU2 --device U3E1\G70 --device U3E1\HG70 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU3 --device U3E2\G70 --device U3E2\HG70 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU4 --device U3E3\G70 --device U3E3\HG70 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU2 --device U3E1\G90 --device U3E1\HG90 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU3 --device U3E2\G90 --device U3E2\HG90 --points 1 --points 4 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --target SELF-CPU4 --device U3E3\G90 --device U3E3\HG90 --points 1 --points 4 --write-check
```

## 2. Target / Qualifier Alignment

- `SELF-CPU2` paired with `U3E1`
- `SELF-CPU3` paired with `U3E2`
- `SELF-CPU4` paired with `U3E3`

Each command used:

- `transport=tcp`
- `direct_memory=0xFA`
- `points=1` and `points=4`
- validated addresses `G10`, `HG20`, `G30`, `HG30`, `G50`, `HG50`, `G70`, `HG70`, `G90`, and `HG90`
- `write-check` enabled

## 3. Result Summary

All aligned pairs completed `write -> readback -> restore` successfully:

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
| `SELF-CPU2` | `U3E1\G30` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\HG30` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\G30` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\HG30` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\G30` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\HG30` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\G30` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\HG30` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\G30` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\HG30` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\G30` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\HG30` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\G50` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\HG50` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\G50` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\HG50` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\G50` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\HG50` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\G50` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\HG50` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\G50` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\HG50` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\G50` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\HG50` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\G70` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\HG70` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\G70` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\HG70` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\G70` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\HG70` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\G70` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\HG70` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\G70` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\HG70` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\G70` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\HG70` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\G90` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\HG90` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\G90` | `1` | `OK` |
| `SELF-CPU3` | `U3E2\HG90` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\G90` | `1` | `OK` |
| `SELF-CPU4` | `U3E3\HG90` | `1` | `OK` |
| `SELF-CPU2` | `U3E1\G90` | `4` | `OK` |
| `SELF-CPU2` | `U3E1\HG90` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\G90` | `4` | `OK` |
| `SELF-CPU3` | `U3E2\HG90` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\G90` | `4` | `OK` |
| `SELF-CPU4` | `U3E3\HG90` | `4` | `OK` |

Common detail pattern:

- `points=1`
  - `before=[0x0000]` for `HG20/HG30/HG50` and earlier `G10`
  - `before=[0xFA65]` for `G50`
  - `write=[0x001E]`
  - `readback=[0x001E]`
  - `restored=[0x0000]` or the original non-zero value
- `points=4`
  - `before=[0x0000, 0x0000, 0x0000, 0x0000]` for `HG20/HG30/HG50` and earlier `G10`
  - `before=[0xFA65, 0xC0A8, 0x0000, 0x0000]` for `G50`
  - `write=[0x001E, 0x001F, 0x0020, 0x0021]`
  - `readback=[0x001E, 0x001F, 0x0020, 0x0021]`
  - `restored=[0x0000, 0x0000, 0x0000, 0x0000]` or the original non-zero values
- `restore=ok`

## 4. Practical Interpretation

- The earlier `U3E1..U3E3` write failures were not the whole story; target-header alignment matters.
- On the current environment, matched pairs are now confirmed for both `points=1` and `points=4` `G/HG` Extended Specification writes:
  - `SELF-CPU2` + `U3E1`
  - `SELF-CPU3` + `U3E2`
  - `SELF-CPU4` + `U3E3`
- That aligned-pair rule is no longer limited to the first captured addresses; it also holds at the later `G30/HG30`, `G50/HG50`, `G70/HG70`, and `G90/HG90` follow-up addresses.
- The `G50` runs matter because the original values were not all zero. Restore succeeded back to `0xFA65` and `0xC0A8`, so the current workflow is not only overwriting blank words.
- Later follow-up also showed that `UDP/1027` works on the same aligned pattern, first for read-only coverage and then for `G10/HG20` write/readback/restore at `points=1` and `points=4`. This report still holds the broader `TCP` address-expansion evidence.
- This means the repository can no longer treat `CPU2..4` writes as generally failing on this environment.
- The open question shifts from "can CPU2..4 write at all?" to "how broad is that success across addresses beyond the currently validated `G10/HG20`, `G30/HG30`, `G50/HG50`, `G70/HG70`, and `G90/HG90` ranges?"

## 5. Generated Local Evidence

- Coverage report path used for the `SELF-CPU2` run: `internal_docsrc/iqr_r08cpu/g_hg_extended_device_coverage_latest.md`
- Coverage report path used for the later `SELF-CPU3` / `SELF-CPU4` runs: `internal_docsrc/iqr_r08pcpu/g_hg_extended_device_coverage_latest.md`

Because `*_latest.md` is reused, rely on the archived copies under the same directories when you need per-run preservation.

## 6. Remaining Work

- aligned pairs at even more alternate `G/HG` addresses
- UDP write/readback/restore on the corrected UDP port beyond `G10/HG20`
- whether cross-pair combinations are intentionally readable-only or also writable
- whether the same target-aligned rule holds on other PLC families


