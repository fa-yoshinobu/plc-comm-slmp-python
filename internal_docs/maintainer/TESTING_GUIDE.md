# Testing Guide

This guide keeps only the current check commands. Hardware names, result
records, and profile facts belong in the profile data, not here.

## Local Gate

Run from the repository root:

```powershell
python -m pip install -e ".[dev]"
python scripts/slmp_regression_suite.py
python -m unittest discover -s tests -v
python -m ruff check slmp tests scripts
python -m mypy slmp scripts
```

Expected result: all commands pass.

## Live Smoke Check

Use explicit variables for the currently connected test PLC:

```powershell
$plcHost = "<plc-host>"
$plcPort = 1025
$series = "<profile-series>"
python scripts/slmp_connection_check.py --host $plcHost --port $plcPort --transport tcp --series $series
```

Run focused live scripts only when the change touches that area:

- `scripts/slmp_pending_live_verification.py`
- `scripts/slmp_device_range_probe.py`
- `scripts/slmp_register_boundary_probe.py`
- `scripts/slmp_other_station_check.py`
- `scripts/slmp_g_hg_extended_device_recheck.py`
- `scripts/slmp_extended_device_device_recheck.py`
- `scripts/slmp_g_hg_extended_device_coverage.py`
- `scripts/slmp_read_soak.py`
- `scripts/slmp_mixed_read_load.py`
- `scripts/slmp_tcp_concurrency.py`
- `scripts/slmp_manual_label_verification.py`

Generated reports are temporary local outputs. Do not commit them.

## CLI Smoke Checks

Use these when changing `slmp.cli`, script wrappers, or packaging:

```powershell
python scripts/slmp_regression_suite.py --help
python scripts/slmp_connection_check.py --help
python scripts/slmp_device_range_probe.py --help
python scripts/slmp_register_boundary_probe.py --help
python scripts/slmp_init_model_docs.py --help
python scripts/slmp_other_station_check.py --help
python scripts/slmp_pending_live_verification.py --help
python scripts/slmp_manual_label_verification.py --help
python scripts/slmp_read_soak.py --help
python scripts/slmp_mixed_read_load.py --help
python scripts/slmp_tcp_concurrency.py --help
```

Installed entry points are listed in `scripts/README.md`.

## Release Gate

Before a release or a merge that changes behavior, run at least:

1. `python -m unittest discover -s tests -v`
2. `python -m ruff check slmp tests scripts`
3. `python -m mypy slmp scripts`
4. any live check explicitly required by the change, using the canonical
   profile probe after the user approves that specific PLC test

Do not use library-local discovery scripts to guess frame, compatibility, or
route combinations. Profile evidence collection belongs in
`plc-comm-slmp-profiles/tools/live_profile_probe.py`, driven by the canonical
profile JSON.
