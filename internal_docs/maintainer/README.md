
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/maintainer/)

This folder is for repository maintainers.

It holds:

- stable project decisions
- implementation decisions
- operator-facing verification summaries that back implementation choices

This folder is not part of the user-facing manual.

## Start Here

Read these in order when you need current project truth:

- [TODO.md](../../TODO.md)
  - current active TODOs
- [communication_test_record.md](communication_test_record.md)
  - chronological record of important live checks
- [manual_implementation_differences.md](manual_implementation_differences.md)
  - manual-vs-live decisions that affect implementation
- [error_code_reference.md](error_code_reference.md)
  - maintainer-facing end-code interpretation table

Supporting stable documents:

- [plc_setting_change_log_template.md](plc_setting_change_log_template.md)
- [plc_device_range_expectations.md](plc_device_range_expectations.md)
- [API_UNIFICATION_POLICY.md](API_UNIFICATION_POLICY.md)
  - includes the maintainer-only boundary for `*_raw` wrappers

## Commit Policy

Tracked:

- stable Markdown documents

Do not commit:

- one-off probe logs
- packet captures
- raw communication logs
- frame-dump scratch data
- `archive/` outputs

Those artifacts are for local debugging only and are intentionally ignored by Git.

## Update Rule

- update the matching stable summary when the conclusion changed, not only the timestamp



