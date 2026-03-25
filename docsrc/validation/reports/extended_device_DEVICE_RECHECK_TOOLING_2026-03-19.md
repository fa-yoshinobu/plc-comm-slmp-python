# Extended Specification Device Recheck Tooling

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Goal: provide one reusable command for Extended Specification qualified word devices beyond the fixed iQ-R `G/HG` pair

## 2. Added Tooling

- New CLI entry point: `slmp.cli:extended_device_device_recheck_main`
- New script wrapper: `scripts/slmp_extended_device_device_recheck.py`
- New console script entry: `slmp-extended_device-device-recheck`

## 3. Command Shape

The new command accepts repeatable probe definitions:

```text
--probe LABEL,DEVICE,WRITE_VALUE[,DIRECT_MEMORY]
```

Examples:

```text
--probe u01_g22,U01\G22,0x0004,0xF8
--probe u4_g0,U4\G0,0x0001,0xF8
```

Behavior:

- reads the current word value
- writes a temporary value
- reads back the written value
- restores the original value unless `--keep-written-value` is used
- writes a markdown report under `internal_docsrc/<series>_<model>/extended_device_device_recheck_latest.md`
- dumps request/response hex frames under `internal_docsrc/<series>_<model>/frame_dumps_extended_device_device_recheck/`

## 4. Reason

- The earlier `slmp_g_hg_extended_device_recheck.py` tool was intentionally focused on `U3E0\G10` / `U3E0\HG20`.
- The new `U01\G22` capture proved that Extended Specification `G/HG` validation now needs a reusable command that can cover additional unit-qualified targets without adding one-off scripts for every new device.

## 5. Verification

Static checks completed:

- `python -m pytest tests/test_slmp.py -q`
- `python -m ruff check slmp tests`
- `python -m mypy slmp`

Unit-test coverage added for:

- probe parsing
- `U01\G22` payload generation through the generic recheck flow

## 6. Remaining Work

- Run the new generic command against a live PLC for `U01\G22`.
- Reuse the same command for the upcoming `U4\G0` capture-driven check.


