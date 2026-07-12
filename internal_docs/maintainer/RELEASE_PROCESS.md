# Release Guide

This is the minimum release checklist for this repository.

## 1. Update the Human-Facing Files

Check these before tagging:

- `README.md`
- `docsrc/user/GETTING_STARTED.md`
- `docsrc/user/USAGE_GUIDE.md`
- `internal_docs/maintainer/TESTING_GUIDE.md`
- `CHANGELOG.md`
- `TODO.md`

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
$wheel = Get-ChildItem .\dist\plc_comm_slmp-*.whl | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python -m venv $smokeVenv
& (Join-Path $smokeVenv "Scripts\python.exe") -m pip install $wheel.FullName
& (Join-Path $smokeVenv "Scripts\python.exe") -c "import slmp; print(slmp.__version__)"
& (Join-Path $smokeVenv "Scripts\slmp-connection-check.exe") --help
```

## 3. Run the Minimum Live Check

```powershell
$plcHost = "<plc-host>"
$plcPort = 1025
$series = "<profile-series>"
python scripts/slmp_connection_check.py --host $plcHost --port $plcPort --transport tcp --series $series
```

If the release changes live behavior, also run the focused script for that area.

Typical examples:

- `scripts/slmp_open_items_recheck.py`
- `scripts/slmp_pending_live_verification.py`
- `scripts/slmp_device_range_probe.py`
- `scripts/slmp_register_boundary_probe.py`

## 4. Result Updates

If you ran live verification:

- close or add concrete active items in repository-root `TODO.md`
- update tests or the current specification only when behavior changes
- keep generated probe reports local

## 5. Artifact Policy

- do not commit build artifacts from `dist/`
- do not commit packet captures or raw communication logs
- do not commit one-off verification reports or templates

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
- run the GitHub release workflow for that existing tag; it checks out the tag, verifies source/package versions, and uploads the `dist/` artifacts
- publish to a package registry separately after the GitHub release artifacts have been checked; this workflow does not publish to PyPI
