# G/HG Extended Specification Coverage Tooling

- Date: 2026-03-19
- Scope: dedicated command for `G/HG` Extended Specification horizontal coverage checks
- Project: `plc-comm-slmp-python`

## Goal

Add a dedicated command that can later recheck:

- multiple qualified `G/HG` addresses
- multiple point counts
- different transports and series modes
- optional temporary write/readback/restore

without mixing that workflow into unrelated live-verification commands.

## Delivered Entry Points

- script: `scripts/slmp_g_hg_extended_device_coverage.py`
- console entry: `slmp-g-hg-extended_device-coverage`

## Command Shape

Typical read-only sweep:

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series iqr --device U3E0\G10 --device U3E0\HG20 --points 1 --points 4
```

Optional temporary write/readback/restore sweep:

```powershell
python scripts/slmp_g_hg_extended_device_coverage.py --host 192.168.250.100 --series ql --device U01\G22 --points 1 --points 2 --write-check
```

## Behavior

- default mode is read-only
- `--write-check` enables temporary write/readback/restore
- `--direct-memory` can be repeated when the target needs explicit Extended Specification direct-memory variants
- default direct-memory value is:
  - `0xFA` for `series=iqr`
  - `0xF8` for `series=ql`

## Validation

Unit coverage was added for:

- read-only sweep on multiple `G/HG` devices and point counts
- write/readback/restore sweep on `U01\G22`
- console entry registration in `pyproject.toml`

