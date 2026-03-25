# Regression Suite and Script Lint Validation

- Date: 2026-03-19
- Repository: `plc-comm-slmp-python`
- Scope:
  - add a single-command local regression entry point
  - bring legacy `scripts/` files back under the current `ruff` baseline

## Implemented Changes

1. Added `slmp.cli:regression_suite_main`.
2. Added wrapper script `scripts/slmp_regression_suite.py`.
3. Added console entry point `slmp-regression-suite`.
4. Updated maintainer/user-facing script documentation.
5. Applied `ruff --fix` cleanup to the legacy ad-hoc script set:
   - `scripts/fx5_discovery.py`
   - `scripts/fx5uc_master_validation.py`
   - `scripts/iql_series_master_validation.py`
   - `scripts/q_series_full_command_test.py`
   - `scripts/q_series_master_validation.py`
   - `scripts/q_series_matrix_sweep.py`
   - `scripts/q_series_test.py`

## Regression Suite Coverage

The new local regression suite currently orchestrates:

1. `python -m unittest discover -s tests -v`
2. `python -m ruff check slmp tests scripts`
3. `python -m mypy slmp scripts`
4. maintained wrapper `--help` smoke checks

Optional:

1. `slmp_connection_check.py` live smoke check through `--include-live-connection-check`

This is intentionally limited to safe local automation plus the safest live smoke step. Human-in-the-loop verification and broader live scripts remain separate.

## Validation Results

Executed on 2026-03-19:

```text
python -m ruff check scripts
python -m mypy slmp scripts
python -m pytest tests/test_slmp.py -q
```

Result summary:

- `ruff check scripts`: passed after cleanup
- `mypy slmp scripts`: passed
- `pytest tests/test_slmp.py -q`: passed after adding regression-suite coverage tests

## Remaining Follow-Up

- Keep the regression suite focused on safe local gates unless a concrete need appears for single-command orchestration of destructive or human-judged live checks.
