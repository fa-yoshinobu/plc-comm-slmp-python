# SLMP Connect Python v0.1.2

## Summary

Patch release to align the published release tag with the CI-passing commit.

This release keeps the mixed block write compatibility work from `v0.1.1` and republishes it on a tag that passed the full local verification flow.

## Highlights

- mixed `write_block(...)` fallback support remains available through `retry_mixed_on_error=True`
- focused live comparison script for mixed block read/write scenarios is included
- release tag now points to a commit that passes unit tests, `ruff`, `mypy`, and package build

## Packaging

- Repository: `https://github.com/fa-yoshinobu/plc-comm-slmp-python`
- Install from GitHub:

```powershell
python -m pip install "git+https://github.com/fa-yoshinobu/plc-comm-slmp-python.git@v0.1.2"
```

- Source archive: `slmp_connect_python-0.1.2.tar.gz`
- Wheel: `slmp_connect_python-0.1.2-py3-none-any.whl`
- License: `MIT`

## Verification

The following checks were completed for this release:

- `python -m unittest discover -s tests -v`
- `python -m ruff check .`
- `python -m mypy slmp scripts`
- `python -m build`
- `python -m twine check dist/*`

## Live Validation

- target series/model: Mitsubishi MELSEC iQ-R `R08CPU`
- transport: `TCP 1025`
- host/port: `192.168.250.100:1025`
- focused script: `python scripts/slmp_mixed_block_compare.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --retry-mixed-on-error`
- report updates:
  - `internal_docsrc/iqr_r08cpu/mixed_block_compare_latest.md`
  - `internal_docsrc/iqr_r08cpu/slmp_connect_python_comparison_checklist.md`

## Breaking Changes

- none

## Upgrade Notes

- Python import path is `slmp`
- CLI names use the `slmp-*` prefix
- if a target rejects one mixed word+bit block write, use `split_mixed_blocks=True` or `retry_mixed_on_error=True`

## Known Limits

- `3E` and `4E` frames are supported
- only binary data code is supported
- ASCII mode is not implemented
- some paths remain target-specific on the currently validated iQ-R target
- unresolved target-specific items are tracked in `internal_docsrc/open_items.md`

## Full Changelog

See `CHANGELOG.md` for the full project history.


