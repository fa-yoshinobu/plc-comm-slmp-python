
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/maintainer/)

This folder is for repository maintainers.

It holds:

- stable project decisions
- target-specific live reports
- operator-facing verification results that back implementation choices

If you are a library user, start from [Overview](../index.md) and [User Guide](../user/USER_GUIDE.md) first.

## Start Here

Read these in order when you need current project truth:

- [open_items.md](open_items.md)
  - current unresolved items and practical limits
- [communication_test_record.md](communication_test_record.md)
  - chronological record of important live checks
- [manual_implementation_differences.md](manual_implementation_differences.md)
  - manual-vs-live decisions that affect implementation
- [error_code_reference.md](error_code_reference.md)
  - maintainer-facing end-code interpretation table

Supporting stable documents:

- [device_access_matrix_policy.md](device_access_matrix_policy.md)
- [plc_setting_change_log_template.md](plc_setting_change_log_template.md)
- [plc_device_range_expectations.md](plc_device_range_expectations.md)
- [API_UNIFICATION_POLICY.md](API_UNIFICATION_POLICY.md)
  - includes the maintainer-only boundary for `*_raw` wrappers

## Model Folders

Generated live reports live under `internal_docsrc/<series>_<model>/`.

Current folders:

- [iqr_r08cpu/README.md](iqr_r08cpu/README.md): main validated target
- [iqr_r08cpu_rj71en71/README.md](iqr_r08cpu_rj71en71/README.md): performance-focused target

Use `python scripts/slmp_init_model_docs.py --series <series> --model <model>` to create a new folder scaffold.

## Commit Policy

Tracked:

- `*_latest.md` reports
- stable Markdown documents
- CSV/Markdown matrix files

Do not commit:

- packet captures
- raw communication logs
- frame-dump scratch data
- `archive/` outputs

Those artifacts are for local debugging only and are intentionally ignored by Git.

## Update Rule

- regenerate the relevant `*_latest.md` file when a live result changes
- update the matching stable summary when the conclusion changed, not only the timestamp
- keep model-folder `README.md` files aligned with the current report set



