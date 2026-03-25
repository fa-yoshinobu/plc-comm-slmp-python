
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/iqr_r08cpu/)

This is the main validated-target folder for the repository.

Target:

- series: `iqr`
- model: `R08CPU`
- host used in the current baseline: `192.168.250.101`
- primary ports: `TCP 1025`, `UDP 1027`

## Start Here

If you only need the current practical picture, read these first:

- [../open_items.md](../open_items.md)
  - unresolved items and current restrictions
- [pending_live_verification_latest.md](pending_live_verification_latest.md)
  - command-family live status
- [manual_label_verification_latest.md](manual_label_verification_latest.md)
  - human-confirmed label read/write/restore results
- [manual_write_verification_latest.md](manual_write_verification_latest.md)
  - human-confirmed device write/read/restore results
- [device_access_matrix.md](device_access_matrix.md)
  - current per-device snapshot from the matrix CSV

## Current Practical Snapshot

- label family is currently confirmed on real external-device-accessible labels
- remote `run`, `stop`, and `pause` are confirmed
- `1005` remote latch clear was confirmed under PLC `STOP`
- password lock/unlock is confirmed
- `0601/1601` is confirmed on the narrow CPU-buffer helper path
- `18xx` file commands remain environment-dependent and are still unresolved on this PLC
- direct `G`, `HG`, and `S` remain blocked in typed device APIs on this project

## Report Index

### Core status and rechecks

- [pending_live_verification_latest.md](pending_live_verification_latest.md)
- [open_items_recheck_latest.md](open_items_recheck_latest.md)
- [special_device_probe_latest.md](special_device_probe_latest.md)
- [other_station_check_latest.md](other_station_check_latest.md)
- [mixed_block_compare_latest.md](mixed_block_compare_latest.md)

### Human-confirmed verification

- [manual_write_verification_latest.md](manual_write_verification_latest.md)
- [manual_label_verification_latest.md](manual_label_verification_latest.md)
- [manual_write_verification_notes.md](manual_write_verification_notes.md)

### Matrix and device-family summaries

- [device_access_matrix.csv](device_access_matrix.csv)
- [device_access_matrix.md](device_access_matrix.md)
- [supported_device_rw_probe_latest.md](supported_device_rw_probe_latest.md)
- [bit_device_word_block_equivalence_latest.md](bit_device_word_block_equivalence_latest.md)

### Boundary and address-behavior reports

- [device_range_probe_latest.md](device_range_probe_latest.md)
- [register_boundary_probe_latest.md](register_boundary_probe_latest.md)
- [r_zr_overlap_verification_latest.md](r_zr_overlap_verification_latest.md)
- [register_boundary_comparison_latest.md](register_boundary_comparison_latest.md)
- [additional_register_boundary_probe_latest.md](additional_register_boundary_probe_latest.md)
- [lz_boundary_probe_latest.md](lz_boundary_probe_latest.md)
- [zr_boundary_probe_latest.md](zr_boundary_probe_latest.md)

### Load and performance reports

- [read_soak_latest.md](read_soak_latest.md)
- [mixed_read_load_latest.md](mixed_read_load_latest.md)
- [tcp_concurrency_latest.md](tcp_concurrency_latest.md)
- [read_cycle_probe_latest.md](read_cycle_probe_latest.md)
- [block_read_max_probe_latest.md](block_read_max_probe_latest.md)
- [block_write_max_probe_latest.md](block_write_max_probe_latest.md)

### Focused exploratory reports

- [u4_g0_probe_latest.md](u4_g0_probe_latest.md)
- [u4_module_no_0004_range_probe_latest.md](u4_module_no_0004_range_probe_latest.md)
- [slmp_connect_python_comparison_checklist.md](slmp_connect_python_comparison_checklist.md)

## Supporting Inputs

- [current_plc_boundary_specs_20260313.txt](current_plc_boundary_specs_20260313.txt)
- [current_register_boundary_focus_specs_20260313.txt](current_register_boundary_focus_specs_20260313.txt)
- [other_station_targets_example.txt](other_station_targets_example.txt)

## Local-Only Artifacts

Packet captures, communication logs, and frame dumps are intentionally not tracked in Git.

If you collect them locally for debugging:

- keep them out of commits
- summarize the conclusion in a stable Markdown file instead of storing the raw artifact here

## Archive Policy

- tracked `*_latest.md` files are the current canonical outputs
- `archive/` is for timestamped history and is intentionally ignored by Git


