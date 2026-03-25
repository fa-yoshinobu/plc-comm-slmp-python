# Compatibility Probe Tooling Validation

- Date: 2026-03-19
- Scope: add a structured compatibility probe and a matrix renderer so `PLC_COMPATIBILITY.md` can be rebuilt from probe JSON files
- Live PLC execution: not performed in this validation step

## Changes

- Added `scripts/slmp_compatibility_probe.py`
- Added `scripts/slmp_compatibility_matrix_render.py`
- Added `slmp.cli.compatibility_probe_main()`
- Added `slmp.cli.compatibility_matrix_render_main()`
- Added renderer helpers for `PLC_COMPATIBILITY.md`
- Added stable product-family row ordering in the rendered matrix
- Added `--omit-pending-columns` to hide command families that were not probed yet
- Added console entry points in `pyproject.toml`
- Added unit coverage for probe JSON/Markdown output and matrix rendering

## Local Verification

```powershell
python -m unittest tests.test_slmp.TestCodec.test_render_compatibility_matrix_markdown tests.test_slmp.TestCli.test_compatibility_probe_main_writes_json_and_markdown tests.test_slmp.TestCli.test_compatibility_matrix_render_main_renders_output -v
python -m ruff check slmp tests scripts
python scripts/slmp_compatibility_probe.py --help
python scripts/slmp_compatibility_matrix_render.py --help
```

## Result

- Local unit coverage passed for the new probe and renderer.
- `ruff` passed for `slmp`, `tests`, and `scripts`.
- Wrapper help smoke checks passed.

## Practical Notes

- The compatibility probe is read-only by default.
- Write/restore, remote-control, and maintenance probes are opt-in.
- The renderer is intentionally data-driven: probe JSON files are the source of truth for the generated compatibility matrix.
- This validation does not claim any PLC command compatibility result. It only validates the tooling that records and renders those results.
