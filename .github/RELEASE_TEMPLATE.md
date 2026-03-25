# SLMP Connect Python vX.Y.Z

## Summary

Short summary of this release.

Example:

- documentation refreshed for the `slmp` import path
- release metadata and CI updated
- CLI entry points aligned to the `slmp-*` prefix

## Highlights

- highlight 1
- highlight 2
- highlight 3

## Packaging

- Repository: `https://github.com/fa-yoshinobu/plc-comm-slmp-python`
- Install from GitHub:

```powershell
python -m pip install "git+https://github.com/fa-yoshinobu/plc-comm-slmp-python.git@vX.Y.Z"
```

- Source archive: `slmp_connect_python-X.Y.Z.tar.gz`
- Wheel: `slmp_connect_python-X.Y.Z-py3-none-any.whl`
- License: `MIT`

## Verification

- `python -m unittest discover -s tests -v`
- `python -m ruff check .`
- `python -m mypy slmp scripts`
- `python -m build`
- `python -m twine check dist/*`

## Live Validation

- target series/model:
- transport:
- host/port:
- scripts run:
- report updates:

## Breaking Changes

- none

## Upgrade Notes

- Python import path is `slmp`
- CLI names use the `slmp-*` prefix

## Known Limits

- `3E` and `4E` frames are supported
- only binary data code is supported
- ASCII mode is out of scope

## Full Changelog

See `CHANGELOG.md` for the full project history.
