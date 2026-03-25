# G/HG Multi-CPU Non-Aligned Write Follow-Up

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Target PLC family set observed in this sweep: `R08CPU`, `R08PCPU`
- Scope: check whether non-aligned multi-CPU target-header / qualifier combinations are writable after the aligned pairs succeeded

## 1. Executed Commands

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --series iqr --transport tcp --target SELF-CPU2 --device U3E2\G10 --device U3E2\HG20 --device U3E3\G10 --device U3E3\HG20 --points 1 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --series iqr --transport tcp --target SELF-CPU3 --device U3E1\G10 --device U3E1\HG20 --device U3E3\G10 --device U3E3\HG20 --points 1 --write-check
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.101 --series iqr --transport tcp --target SELF-CPU4 --device U3E1\G10 --device U3E1\HG20 --device U3E2\G10 --device U3E2\HG20 --points 1 --write-check
```

## 2. Tested Non-Aligned Pairs

- `SELF-CPU2` with `U3E2`, `U3E3`
- `SELF-CPU3` with `U3E1`, `U3E3`
- `SELF-CPU4` with `U3E1`, `U3E2`

Each command used:

- `transport=tcp`
- `direct_memory=0xFA`
- `points=1`
- `write-check` enabled

## 3. Result Summary

All non-aligned write attempts failed.

| Target | Device | Result | Failure Pattern |
|---|---|---|---|
| `SELF-CPU2` | `U3E2\G10` | `NG` | `0x414A` on `1401/0082` |
| `SELF-CPU2` | `U3E2\HG20` | `NG` | write issued, readback stayed `0x0000` |
| `SELF-CPU2` | `U3E3\G10` | `NG` | `0x414A` on `1401/0082` |
| `SELF-CPU2` | `U3E3\HG20` | `NG` | write issued, readback stayed `0x0000` |
| `SELF-CPU3` | `U3E1\G10` | `NG` | `0x414A` on `1401/0082` |
| `SELF-CPU3` | `U3E1\HG20` | `NG` | write issued, readback stayed `0x0000` |
| `SELF-CPU3` | `U3E3\G10` | `NG` | `0x414A` on `1401/0082` |
| `SELF-CPU3` | `U3E3\HG20` | `NG` | write issued, readback stayed `0x0000` |
| `SELF-CPU4` | `U3E1\G10` | `NG` | `0x414A` on `1401/0082` |
| `SELF-CPU4` | `U3E1\HG20` | `NG` | write issued, readback stayed `0x0000` |
| `SELF-CPU4` | `U3E2\G10` | `NG` | `0x414A` on `1401/0082` |
| `SELF-CPU4` | `U3E2\HG20` | `NG` | write issued, readback stayed `0x0000` |

## 4. Practical Interpretation

- The earlier contradictory results are now coherent:
  - aligned pairs write successfully
  - non-aligned pairs do not
- On this environment, write acceptance is not just a property of the `U3E*` qualifier alone; it depends on matching the target-header CPU selection to the qualifier.
- The failure mode is consistent across all non-aligned tests:
  - `G10` fails hard with `0x414A`
  - `HG20` accepts the write request path enough to avoid an exception, but the value does not take effect

## 5. Generated Local Evidence

- `internal_docsrc/iqr_r08cpu/g_hg_extended_device_coverage_latest.md`
- `internal_docsrc/iqr_r08pcpu/g_hg_extended_device_coverage_latest.md`

Because `*_latest.md` is reused, rely on archived copies under those directories when you need the exact per-run snapshots.

## 6. Conclusion

For the currently validated environment:

- `aligned target-header + aligned U3E* qualifier` = writable for `points=1` and `points=4`
- `non-aligned target-header + U3E* qualifier` = not writable at the tested `points=1` paths

This is the current practical rule to carry forward unless later evidence disproves it.


