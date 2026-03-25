# G/HG Multi-CPU Hardware Recheck

Date: 2026-03-19

> Follow-up note: this report captures an earlier target-agnostic probe sequence. A later target-aligned check
> (`SELF-CPU2/U3E1`, `SELF-CPU3/U3E2`, `SELF-CPU4/U3E3`) succeeded for both read-only coverage and single-point
> write/readback/restore. See `G_HG_MULTI_CPU_TARGET_ALIGNED_WRITE_2026-03-19.md` for the corrected operational guidance.

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Target PLC: `R120PCPU`
- Goal: extend the earlier `U3E0` Extended Specification `G/HG` recheck to the user-defined multi-CPU qualifier set `U3E0..U3E3`

## 2. Assumed Qualifier Mapping

On the user's current multi-CPU environment:

- `U3E0` = CPU No.1 memory
- `U3E1` = CPU No.2 memory
- `U3E2` = CPU No.3 memory
- `U3E3` = CPU No.4 memory

## 3. Executed Command

```powershell
python scripts/slmp_extended_device_device_recheck.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --probe cpu1_g,U3E0\G10,0x001E,0xFA --probe cpu1_hg,U3E0\HG20,0x0032,0xFA --probe cpu2_g,U3E1\G10,0x001E,0xFA --probe cpu2_hg,U3E1\HG20,0x0032,0xFA --probe cpu3_g,U3E2\G10,0x001E,0xFA --probe cpu3_hg,U3E2\HG20,0x0032,0xFA --probe cpu4_g,U3E3\G10,0x001E,0xFA --probe cpu4_hg,U3E3\HG20,0x0032,0xFA
```

## 4. Baseline Read Result

Separate follow-up direct reads through the current repository returned `0` for all tested points:

- `U3E0\G10 = 0`
- `U3E0\HG20 = 0`
- `U3E1\G10 = 0`
- `U3E1\HG20 = 0`
- `U3E2\G10 = 0`
- `U3E2\HG20 = 0`
- `U3E3\G10 = 0`
- `U3E3\HG20 = 0`

This means all tested CPU-memory qualifiers were at least readable on the current target.

## 5. Write / Readback Result

| Probe | Result | Detail |
|---|---|---|
| `U3E0\G10` | `OK` | write/readback/restore all passed |
| `U3E0\HG20` | `OK` | write/readback/restore all passed |
| `U3E1\G10` | `NG` | write failed with `end_code=0x414A` |
| `U3E1\HG20` | `NG` | write returned success but readback stayed `0x0000` |
| `U3E2\G10` | `NG` | write failed with `end_code=0x414A` |
| `U3E2\HG20` | `NG` | write returned success but readback stayed `0x0000` |
| `U3E3\G10` | `NG` | write failed with `end_code=0x414A` |
| `U3E3\HG20` | `NG` | write returned success but readback stayed `0x0000` |

Observed summary:

- `OK=2`
- `NG=6`
- `SKIP=0`

## 6. Practical Interpretation

- On the current target, `U3E0` is confirmed for both `G` and `HG` at the tested addresses.
- `U3E1..U3E3` are readable at the tested addresses, but write equivalence with `U3E0` is not confirmed.
- The failure pattern is not uniform:
  - `G` writes on `U3E1..U3E3` were rejected with `0x414A`
  - `HG` writes on `U3E1..U3E3` returned normal completion but did not change the readback value
- Therefore, the current repository must not assume that `U3E0..U3E3` are operationally symmetric even when the user-side qualifier meaning is known.

This interpretation is limited to the exact probe shape used here. Later target-aligned checks showed that the matched
target-header/qualifier pairs can succeed even though this earlier target-agnostic sequence did not.

## 7. Generated Local Evidence

- Report: `internal_docsrc/iqr_r120pcpu/extended_device_device_recheck_latest.md`
- Frame dumps: `internal_docsrc/iqr_r120pcpu/frame_dumps_extended_device_device_recheck/`

## 8. Next Work

- Confirm whether CPU No.2..No.4 require different writable addresses.
- Confirm whether write permission or CPU state differs across CPU No.2..No.4.
- Capture one known-good `U3E1` or `U3E2` write session if the engineering tool can perform it.


