# Device Access Matrix Policy

This note defines how `device_access_matrix.csv` should be used for each target model folder under `internal_docsrc/<series>_<model>/`.

## Purpose

- keep a per-model device support sheet in a format that opens directly in Excel
- separate machine-recorded test facts from human operational judgement
- make device availability differences across PLC models easy to compare

## Canonical File

For each model folder, the canonical management sheet is:

- `device_access_matrix.csv`

The human-readable Markdown file:

- `device_access_matrix.md`

is a report snapshot, not the preferred editing format for routine model-by-model support management.

## Column Policy

Current columns:

- `device_code`
- `device`
- `kind`
- `unsupported`
- `read`
- `write`
- `note`
- `manual_write`
- `manual_write_note`

Meaning:

- `device`
  - stores the representative verification address for that device family on the target model
  - avoid head addresses such as `D0` when a safer representative address is available
- `read` and `write`
  - store observed test results or stable support status values
- `manual_write`
  - stores the result of the interactive temporary write verification flow
  - expected short values are `OK`, `NG`, `SKIP`, or blank
- `manual_write_note`
  - stores a short note about the latest human-confirmed temporary write verification
- `note`
  - stores short reasons, caveats, or error-code summaries
- `unsupported`
  - is intentionally reserved for human judgement
  - do not auto-fill it from scripts
  - use it when the team decides that a device/path should be treated as unavailable for that model in practice

## Why `unsupported` Is Manual

The repository already records raw facts such as:

- command success or failure
- end codes
- practical-path workarounds
- target-specific exceptions

However, the decision that a device should be treated as "unsupported" is not always identical to a single failed test result.

Examples:

- a direct path may fail, but an alternative supported helper path exists
- a device may be intentionally out of scope for a given model or project
- a result may still be under investigation and should not yet be marked unsupported

For that reason, `unsupported` is a human-maintained operational decision column.

## `manual_write` Status Convention

- blank
  - no current human temporary-write judgement has been recorded
- `OK`
  - a human confirmed that the temporary value was reflected and the original value was restored
- `NG`
  - a human confirmed that the reflected value did not match the expected temporary write
- `SKIP`
  - the row was intentionally skipped or no final human judgement was entered

If a human check used a special path instead of the normal direct path, record that explicitly in `manual_write_note`.
Examples:

- helper-backed `LTN/LSTN` decode used for `LTC/LTS/LSTC/LSTS`
- focused write path used only for a residual device family

## Editing Rule

- edit `device_access_matrix.csv` directly in Excel or another spreadsheet tool
- keep `device` on a representative verification address that is safe for temporary checks
- keep `unsupported` blank until a human reviewer decides to mark it
- update `manual_write` and `manual_write_note` when a human temporary write verification result becomes part of the current model state
- prefer short stable values such as `YES`, `NO`, or blank, depending on team convention
- if a value is changed because of a live verification result, also update the relevant note or linked report if needed
- regenerate `device_access_matrix.md` from the CSV after changing the sheet

## Relationship to Other Documents

- use `open_items.md` for unresolved protocol or environment issues
- use `communication_test_record.md` for chronological verification history
- use `manual_implementation_differences.md` for implementation-vs-documented-behavior differences
- use model-folder `*_latest.md` files for generated report outputs

## Current Repository Usage

The validated target folder:

- `internal_docsrc/iqr_r08cpu/`

now contains:

- `device_access_matrix.csv` for Excel-based management
- `device_access_matrix.md` for the generated human-readable snapshot

