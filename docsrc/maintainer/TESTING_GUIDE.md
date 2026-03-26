# Testing Guide

This guide explains what to run locally, what to run on a live PLC, and what should be committed afterward.

## 1. What Most Changes Need

For most code changes, the minimum useful sequence is:

1. run unit tests
2. run `ruff`
3. run `mypy`
4. run one safe live smoke check on the target PLC

Only run the heavier live scripts when the change actually touches that area.

## 2. Setup

```powershell
python -m pip install -e ".[dev]"
```

Optional:

```powershell
pre-commit install
```

## 3. Local Checks

Run these from the repository root:

```powershell
python scripts/slmp_regression_suite.py
python -m unittest discover -s tests -v
python -m ruff check slmp tests scripts
python -m mypy slmp scripts
```

Recommended pass criteria:

1. unit tests pass
2. `ruff` reports no errors
3. `mypy` reports no errors

Recommended default:

- start with `python scripts/slmp_regression_suite.py`
- only run the individual commands when you are isolating a failure

## 4. CLI Smoke Checks

Use these when changing `slmp.cli`, script wrappers, or packaging:

```powershell
python scripts/slmp_regression_suite.py --help
python scripts/slmp_connection_check.py --help
python scripts/slmp_compatibility_probe.py --help
python scripts/slmp_compatibility_matrix_render.py --help
python scripts/slmp_device_range_probe.py --help
python scripts/slmp_register_boundary_probe.py --help
python scripts/slmp_device_access_matrix_sync.py --help
python scripts/slmp_init_model_docs.py --help
python scripts/slmp_other_station_check.py --help
python scripts/slmp_open_items_recheck.py --help
python scripts/slmp_pending_live_verification.py --help
python scripts/slmp_manual_write_verification.py --help
python scripts/slmp_manual_label_verification.py --help
python scripts/slmp_supported_device_rw_probe.py --help
python scripts/slmp_special_device_probe.py --help
python scripts/slmp_read_soak.py --help
python scripts/slmp_mixed_read_load.py --help
python scripts/slmp_tcp_concurrency.py --help
```

Installed entry points are listed in [Script Reference](SCRIPT_REFERENCE.md).

If you want a single local gate plus an optional safe live smoke check:

```powershell
python scripts/slmp_regression_suite.py --include-live-connection-check --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

## 5. Live Test Environment

Current project example target:

- PLC: Mitsubishi MELSEC iQ-R `R08CPU`
- host: `192.168.250.100`
- TCP: `1025`
- UDP: `1027`
- series: `iqr`

Replace these values when testing another PLC.

If you add a new target folder first:

```powershell
python scripts/slmp_init_model_docs.py --series iqr --model R16CPU
```

## 6. Safe Live Order

Use this order unless you have a reason not to:

1. `slmp_connection_check.py` over TCP
2. optional `slmp_connection_check.py` over UDP
3. `slmp_open_items_recheck.py` if you touched unresolved behavior
4. `slmp_pending_live_verification.py` if you touched command-family support
5. a focused script only for the area you changed

This keeps destructive or noisy checks until the end.

## 7. Safe Smoke Tests

TCP:

```powershell
python scripts/slmp_connection_check.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

For Q-series internal ports such as `Q26UDEHCPU`, use explicit stable settings such as `--series ql --frame-type 3e`. For iQ-R paths, use `--series iqr --frame-type 4e`. Use `model_code` first, and fall back to the returned `model` text when the local code table does not have a match.

TCP with a harmless device read:

```powershell
python scripts/slmp_connection_check.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --read-device D1000 --points 1
```

UDP:

```powershell
python scripts/slmp_connection_check.py --host 192.168.250.100 --port 1027 --transport udp --series iqr
```

Expected result:

1. `0101` succeeds
2. model and model code are printed
3. optional device read succeeds if the device is valid

## 8. Focused Live Scripts

### Device Range Boundary Probe

Use this after PLC-side device-range settings changed:

```powershell
python scripts/slmp_device_range_probe.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --spec-file internal_docsrc/iqr_r08cpu/current_plc_boundary_specs_20260313.txt --include-writeback
```

Report:

- `internal_docsrc/<series>_<model>/device_range_probe_latest.md`

### Register Boundary Probe

Use this for `Z`, `LZ`, `R`, `ZR`, and `RD` edge behavior:

```powershell
python scripts/slmp_register_boundary_probe.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --spec-file internal_docsrc/iqr_r08cpu/current_register_boundary_focus_specs_20260313.txt
```

Report:

- `internal_docsrc/<series>_<model>/register_boundary_probe_latest.md`

### Compatibility Probe and Matrix Render

Use this when you want to rebuild `PLC_COMPATIBILITY.md` from structured probe output rather than hand-maintained notes:

```powershell
python scripts/slmp_compatibility_probe.py --host 192.168.250.100 --port 1025 --transport tcp --series ql --frame-type 3e --plc-label R08CPU_Main
```

Default behavior is read-only. The probe emits:

- `internal_docsrc/compatibility_<plc_label>/compatibility_probe_latest.md`
- `internal_docsrc/compatibility_<plc_label>/compatibility_probe_latest.json`

Higher-risk families remain opt-in:

- `--include-write-restore`
- `--include-remote-control`
- `--include-maintenance`

Render the matrix after collecting one JSON file per PLC path you want represented:

```powershell
python scripts/slmp_compatibility_matrix_render.py --input internal_docsrc/compatibility_r08cpu_main/compatibility_probe_latest.json --output docsrc/validation/reports/PLC_COMPATIBILITY.md
```

Useful renderer behavior:

- rows are ordered by product family, then by PLC label
- `--omit-pending-columns` hides command columns that are still `PENDING` for every PLC row
- the same render pass also emits `docsrc/validation/reports/compatibility_policy.json`

Interpretation rules:

- treat each `frame/access_profile` combination independently
- treat `YES` as "at least one executed combination succeeded and none failed"
- treat `PARTIAL` as mixed outcomes across combinations or subprobes
- treat `PENDING` as "not executed"

### Other-Station Check

`slmp_connection_check.py` and `slmp_other_station_check.py` both load `compatibility_policy.json` automatically when it exists. `--compatibility-policy <path>` overrides the default file for ad-hoc policy testing.

Use this to validate explicit target headers with a fixed series/frame pair. Choose `ql + 3e` for Q-compatible paths and `iqr + 4e` for iQ-R paths. The reported `access_profile` is the explicitly requested encoding. Once a route probe succeeds, the tool also attempts `read_type_name()` on that same path for reporting, but a `0101` failure stays non-fatal:

```powershell
python scripts/slmp_other_station_check.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --frame-type 4e --target NW1-ST1
```

Own-station multiple-CPU shorthand is also supported at the parser level:

```powershell
python scripts/slmp_other_station_check.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --frame-type 4e --target SELF-CPU1
```

Report:

- `internal_docsrc/<series>_<model>/other_station_check_latest.md`

Validated practical note:

- `Q26UDEHCPU` built-in Ethernet accepted `SELF` route probing, returned `0xC059` for `read_type_name()`, and timed out on `NW1`/`NW2` other-station probes during the 2026-03-19 validation session.

### Open-Item Recheck

Use this when you changed an unresolved area:

```powershell
python scripts/slmp_open_items_recheck.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

Report:

- `internal_docsrc/<series>_<model>/open_items_recheck_latest.md`

### Pending Command-Family Verification

Use this when you changed implemented command-family behavior:

```powershell
python scripts/slmp_pending_live_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

If you have real external-device-accessible labels, override the placeholders:

```powershell
python scripts/slmp_pending_live_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --label-random DDD[0] --label-array DDD[0]:1:20
```

Notes:

- `1006 remote reset` is intentionally outside routine live verification
- `0x40C0` on labels usually means the label is missing or external access is not enabled

Report:

- `internal_docsrc/<series>_<model>/pending_live_verification_latest.md`

### Special Device Probe

Use this for `G/HG` and `LT/LST` related open items:

```powershell
python scripts/slmp_special_device_probe.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

Report:

- `internal_docsrc/<series>_<model>/special_device_probe_latest.md`

### G/HG Extended Specification Recheck

Use this after changing the iQ-R `G/HG` Extended Specification builder or when you want a focused `read -> temporary write -> readback -> restore` check for the captured `U3E0\G10` / `U3E0\HG20` style path:

```powershell
python scripts/slmp_g_hg_extended_device_recheck.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

Optional exact target overrides:

```powershell
python scripts/slmp_g_hg_extended_device_recheck.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --g-device U3E0\G10 --hg-device U3E0\HG20 --g-write-value 0x001E --hg-write-value 0x0032
```

Report:

- `internal_docsrc/<series>_<model>/g_hg_extended_device_recheck_latest.md`

Frame dumps:

- `internal_docsrc/<series>_<model>/frame_dumps_extended_device_g_hg_recheck/`

### Generic Extended Specification Device Recheck

Use this when you want the same `read -> temporary write -> readback -> restore` flow for arbitrary qualified Extended Specification word devices such as `U01\G22` or future `U4\G0` checks:

```powershell
python scripts/slmp_extended_device_device_recheck.py --host 192.168.250.100 --port 1025 --transport tcp --series ql --probe u01_g22,U01\G22,0x0004,0xF8
```

Repeat `--probe` to run multiple devices in one report:

```powershell
python scripts/slmp_extended_device_device_recheck.py --host 192.168.250.100 --port 1025 --transport tcp --series ql --probe u01_g22,U01\G22,0x0004,0xF8 --probe u4_g0,U4\G0,0x0001,0xF8
```

Report:

- `internal_docsrc/<series>_<model>/extended_device_device_recheck_latest.md`

Frame dumps:

- `internal_docsrc/<series>_<model>/frame_dumps_extended_device_device_recheck/`

Multi-CPU `G/HG` expansion checklist:

- `docsrc/validation/reports/G_HG_MULTI_CPU_CHECKLIST_2026-03-19.md`

### G/HG Extended Specification Coverage Sweep

Use this when you want horizontal coverage across multiple qualified `G/HG` devices, point counts, transports, or named targets without changing the focused recheck commands:

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --device U3E0\G10 --device U3E0\HG20 --points 1 --points 4
```

You can also sweep multiple transports and named targets in one report:

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --transport tcp --transport udp --target SELF --target SELF-CPU1 --device U3E0\G10 --points 1 --points 4
```

If `read_type_name()` is unsupported on the resolved path, the sweep continues and records the coverage rows anyway.

Report:

- `internal_docsrc/<series>_<model>/g_hg_extended_device_coverage_latest.md`

Frame dumps:

- `internal_docsrc/<series>_<model>/frame_dumps_g_hg_extended_device_coverage/`

### Supported-Device Write/Read/Restore Probe

Use this for automated smoke checks of the currently supported writable families:

```powershell
python scripts/slmp_supported_device_rw_probe.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

### Mixed Block Comparison

Use this when you want request/response hex plus before/after/restore details for the checklist-style `D300` + `M200` block scenarios:

```powershell
python scripts/slmp_mixed_block_compare.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

First-pass comparison rule:

- leave `--split-mixed-blocks` off
- leave `--retry-mixed-on-error` off
- capture the first mixed `1406` response before enabling any compatibility fallback

Report:

- `internal_docsrc/<series>_<model>/mixed_block_compare_latest.md`

### Performance Scripts

Read soak:

```powershell
python scripts/slmp_read_soak.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --device D1000 --rounds 5000 --rotate-span 200
```

Mixed read load:

```powershell
python scripts/slmp_mixed_read_load.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --base-device D1000 --rounds 2000
```

TCP concurrency:

```powershell
python scripts/slmp_tcp_concurrency.py --host 192.168.250.100 --port 1025 --series iqr --device D1000 --clients 1,2,4,8,16,32 --rounds-per-client 100
```

## 9. Human-in-the-Loop Checks

### Manual Write Verification

Use this to temporarily write representative devices from the matrix:

```powershell
python scripts/slmp_manual_write_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --matrix internal_docsrc/iqr_r08cpu/device_access_matrix.csv --device-code D --device-code M
```

Resume from the last report:

```powershell
python scripts/slmp_manual_write_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --matrix internal_docsrc/iqr_r08cpu/device_access_matrix.csv --resume-from-report internal_docsrc/iqr_r08cpu/manual_write_verification_latest.md
```

### Manual Label Verification

Use this for explicit labels rather than the matrix:

```powershell
python scripts/slmp_manual_label_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --label-random LabelB --label-random LabelW --label-array DDD[0]:1:20
```

Both scripts:

1. read the current value
2. write a temporary value
3. wait for human judgement
4. restore the original value unless told otherwise

## 10. Extended Specification Checks

Use Extended Specification checks only when your change touches that area:

```powershell
python scripts/slmp_connection_check.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --extended_device all --extended_device-j-network 0x0001 --extended_device-u-io 0x0000 --extended_device-cpu-io 0x03E0
```

If you need frame dumps or packet captures for local debugging:

- keep them local
- do not commit them
- do not add them back under `internal_docsrc/*/frame_dumps*` or `wireshark/`

## 11. What Each Layer Covers

`python -m unittest discover -s tests -v`

- frame encode/decode
- device encoding helpers
- typed API payload formation
- response parsing
- client-side validation logic

`python -m ruff check .`

- style and correctness rules
- import order
- common bug patterns

`python -m mypy slmp scripts`

- API typing consistency
- CLI/library interface drift

Focused scripts then verify real PLC behavior for their own area.

## 12. Interpreting Failures

Local failures usually mean:

- import or packaging problem
- request/response regression
- API drift

Live failures usually mean:

- wrong host/port/transport
- PLC communication settings mismatch
- target-specific unsupported path
- device-range or label-side condition failure

Common examples in this project:

- `0x4030`: selected device/path rejected
- `0x4031`: configured range/allocation mismatch
- `0x40C0`: label missing or external access disabled
- `0xC061`: request content/path not accepted in the current environment

Use:

- [Error Codes Guide](../user/ERROR_CODES.md) for the quick table
- [Open Items](open_items.md) for current unresolved items
- [Communication Test Record](communication_test_record.md) for chronology

## 13. Report Files

Common tracked report outputs:

- `internal_docsrc/<series>_<model>/open_items_recheck_latest.md`
- `internal_docsrc/<series>_<model>/pending_live_verification_latest.md`
- `internal_docsrc/<series>_<model>/register_boundary_probe_latest.md`
- `internal_docsrc/<series>_<model>/manual_write_verification_latest.md`
- `internal_docsrc/<series>_<model>/manual_label_verification_latest.md`

Stable summaries live in:

- `open_items.md`
- `communication_test_record.md`
- `manual_implementation_differences.md`

## 14. Minimum Release Gate

Before a release or a merge that changes behavior, run at least:

1. `python -m unittest discover -s tests -v`
2. `python -m ruff check slmp tests scripts`
3. `python -m mypy slmp scripts`
4. `python scripts/slmp_connection_check.py --host <host> --port <port> --transport tcp --series <series>`

Also run focused live scripts when the change touches that area.

Equivalent convenience command:

1. `python scripts/slmp_regression_suite.py --include-live-connection-check --host <host> --port <port> --transport tcp --series <series>`


