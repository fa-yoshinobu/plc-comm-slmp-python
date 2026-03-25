# G/HG Extended Specification Live Recheck Tooling

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Area: live validation tooling for the iQ-R `G/HG` Extended Specification path
- Goal: provide one command that performs `read -> temporary write -> readback -> restore` for the captured `U3E0\G10` / `U3E0\HG20` pattern

## 2. Added Entry Points

- CLI entry point: `slmp-g-hg-extended_device-recheck`
- Wrapper script: `scripts/slmp_g_hg_extended_device_recheck.py`
- Main implementation: `slmp.cli:g_hg_extended_device_recheck_main`

## 3. Behavior

- Default targets:
  - `G10` with preferred temporary write value `0x001E`
  - `HG20` with preferred temporary write value `0x0032`
- Qualified shorthand is accepted:
  - `U3E0\G10`
  - `U3E0\HG20`
- Default extension path:
  - Extended Specification CPU buffer style with `extension_specification=0x03E0`
  - `direct_memory_specification=0xFA`
- Safety rule:
  - restore the original value by default after the temporary write/readback check
- Output:
  - Markdown report under `internal_docsrc/<series>_<model>/g_hg_extended_device_recheck_latest.md`
  - Request/response frame dumps under `internal_docsrc/<series>_<model>/frame_dumps_extended_device_g_hg_recheck/`

## 4. Verification

Commands:

```powershell
python scripts/slmp_g_hg_extended_device_recheck.py --help
python -m pytest tests/test_slmp.py -q
python -m ruff check slmp tests
python -m mypy slmp
```

Result:

- CLI help rendered successfully
- unit tests passed
- lint passed
- type check passed

## 5. Remaining Work

- Run the new command against the actual PLC and archive the generated report and frame dumps as hardware evidence.


