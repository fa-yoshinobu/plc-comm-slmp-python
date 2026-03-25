# G/HG Multi-CPU Validation Checklist

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Goal: expand Extended Specification `G/HG` validation from `U3E0` to the full user-defined CPU-memory qualifier set `U3E0..U3E3`

## 2. Environment Assumption

On the user's current multi-CPU environment:

- `U3E0` = CPU No.1 memory
- `U3E1` = CPU No.2 memory
- `U3E2` = CPU No.3 memory
- `U3E3` = CPU No.4 memory

Lower `U**` values are ordinary I/O unit addresses and must not be mixed into this CPU-memory checklist.

## 3. Minimum Word-Level Smoke Checks

Run the generic Extended Specification recheck command for one representative `G` and one representative `HG` address on each CPU-memory qualifier:

```powershell
python scripts/slmp_extended_device_device_recheck.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr --probe cpu1_g,U3E0\G10,0x001E,0xFA --probe cpu1_hg,U3E0\HG20,0x0032,0xFA --probe cpu2_g,U3E1\G10,0x001E,0xFA --probe cpu2_hg,U3E1\HG20,0x0032,0xFA --probe cpu3_g,U3E2\G10,0x001E,0xFA --probe cpu3_hg,U3E2\HG20,0x0032,0xFA --probe cpu4_g,U3E3\G10,0x001E,0xFA --probe cpu4_hg,U3E3\HG20,0x0032,0xFA
```

Expected minimum evidence per probe:

- read succeeds
- temporary write succeeds
- readback matches
- restore succeeds

## 4. Coverage Expansion After Word-Level Smoke

After all `U3E0..U3E3` word-level probes pass, expand in this order:

1. different word addresses for `G`
2. different word addresses for `HG`
3. multi-point direct Extended Specification read/write
4. random read/write
5. monitor registration
6. block-style coverage if a confirmed practical path exists

## 5. Current Status

- confirmed:
  - `U3E0\G10`
  - `U3E0\HG20`
- rechecked with mixed result on the current target:
  - `U3E1\G10`: read OK, write `0x414A`
  - `U3E1\HG20`: read OK, write returned success but readback mismatch
  - `U3E2\G10`: read OK, write `0x414A`
  - `U3E2\HG20`: read OK, write returned success but readback mismatch
  - `U3E3\G10`: read OK, write `0x414A`
  - `U3E3\HG20`: read OK, write returned success but readback mismatch
- still pending:
  - alternate writable addresses for `U3E1..U3E3`
  - multi-point/random/monitor expansion for all CPU-memory qualifiers

## 6. Output Targets

Record results into:

- `internal_docsrc/<series>_<model>/extended_device_device_recheck_latest.md`
- `internal_docsrc/<series>_<model>/frame_dumps_extended_device_device_recheck/`

If a full CPU1..CPU4 pass completes, add a dedicated summary report under:

- `docsrc/validation/reports/`

Current dedicated summary report:

- `docsrc/validation/reports/G_HG_MULTI_CPU_HARDWARE_RECHECK_2026-03-19.md`


