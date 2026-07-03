# Release Guide

This is the minimum release checklist for this repository.

## 1. Update the Human-Facing Files

Check these before tagging:

- `README.md`
- `docsrc/user/GETTING_STARTED.md`
- `docsrc/user/USAGE_GUIDE.md`
- `internal_docs/maintainer/TESTING_GUIDE.md`
- `CHANGELOG.md`
- `internal_docs/maintainer/PROTOCOL_SPEC.md`
- `TODO.md`
- `internal_docs/maintainer/communication_test_record.md`

## 2. Run Local Verification

Clean old packaging artifacts first so you do not accidentally publish stale files:

```powershell
Remove-Item -Recurse -Force build, dist, *.egg-info
```

```powershell
python -m unittest discover -s tests -v
python -m ruff check .
python -m mypy slmp scripts
python -m build
```

Expected result:

- tests pass
- `ruff` passes
- `mypy` passes
- `dist/` contains a source distribution and wheel

Optional packaging smoke check:

```powershell
$smokeVenv = Join-Path $env:TEMP "slmp_release_smoke"
$wheel = Get-ChildItem .\dist\slmp_connect_python-*.whl | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python -m venv $smokeVenv
& (Join-Path $smokeVenv "Scripts\python.exe") -m pip install $wheel.FullName
& (Join-Path $smokeVenv "Scripts\python.exe") -c "import slmp; print(slmp.__version__)"
& (Join-Path $smokeVenv "Scripts\slmp-connection-check.exe") --help
```

## 3. Run the Minimum Live Check

```powershell
$plcHost = "192.168.3.10"
$plcPort = 1025
$series = "iqr"
python scripts/slmp_connection_check.py --host $plcHost --port $plcPort --transport tcp --series $series
```

If the release changes live behavior, also run the focused script for that area.

Typical examples:

- `scripts/slmp_open_items_recheck.py`
- `scripts/slmp_pending_live_verification.py`
- `scripts/slmp_device_range_probe.py`
- `scripts/slmp_register_boundary_probe.py`
- `scripts/slmp_special_device_probe.py`

## 4. Review Report Updates

If you ran live verification:

- reflect conclusion changes in:
  - repository-root `TODO.md`
  - `communication_test_record.md`
  - `manual_implementation_differences.md`
- keep generated probe reports local unless they are needed as durable evidence
  for a current implementation decision

## 5. Artifact Policy

- do not commit build artifacts from `dist/`
- do not commit packet captures or raw communication logs

## 6. Tagging Flow

1. update `version` in `pyproject.toml`
2. update `CHANGELOG.md`
3. finish local and live verification
4. create a normal release commit
5. create the tag

## 7. Publish

If you are publishing artifacts:

```powershell
python -m twine check dist/*
```

Then:

- push the release commit and tag to `https://github.com/fa-yoshinobu/plc-comm-slmp-python`
- create the GitHub release entry using `.github/RELEASE_TEMPLATE.md`
- for `v0.1.0`, you can start from `.github/RELEASE_v0.1.0.md`
- upload `dist/` artifacts if you are distributing release packages outside the repository

## 8. Current Baseline

- package version: `0.1.6`
- validated target: MELSEC iQ-R `R08CPU`
