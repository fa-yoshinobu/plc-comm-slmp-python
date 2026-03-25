
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/iqr_r08cpu_rj71en71/)

This folder is for the `R08CPU + RJ71EN71` performance-focused target.

Target:

- series: `iqr`
- CPU: `R08CPU`
- Ethernet module: `RJ71EN71`
- host used in the current baseline: `192.168.250.101`
- verified ports: `TCP 1025`, `UDP 1027`

## Intended Use

Use this folder for:

- transport behavior
- concurrency limits
- read/write performance

Unless live evidence proves otherwise, device-family accessibility should be treated as inherited from [../iqr_r08cpu/README.md](../iqr_r08cpu/README.md).

## Start Here

- [read_soak_latest.md](read_soak_latest.md)
- [mixed_read_load_latest.md](mixed_read_load_latest.md)
- [tcp_concurrency_latest.md](tcp_concurrency_latest.md)
- [read_cycle_probe_latest.md](read_cycle_probe_latest.md)
- [block_read_max_probe_latest.md](block_read_max_probe_latest.md)
- [block_write_max_probe_latest.md](block_write_max_probe_latest.md)

## Current Baseline

- `read_soak_latest.md`: average `5.487 ms`, `181.4 reads/s`, errors `0`
- `mixed_read_load_latest.md`: overall average `5.502 ms`, errors `0`
- `tcp_concurrency_latest.md`: `63` clients accepted, `64` rejected
- `read_cycle_probe_latest.md`: slower than the direct CPU-path baseline for both `TCP` and `UDP`
- `block_read_max_probe_latest.md`: word read `960`, bit read `705`
- `block_write_max_probe_latest.md`: word write `951`, bit write `705`

## Supporting Files

- [device_access_matrix.csv](device_access_matrix.csv)
- [device_access_matrix.md](device_access_matrix.md)
- [current_plc_boundary_specs_example.txt](current_plc_boundary_specs_example.txt)
- [current_register_boundary_focus_specs_example.txt](current_register_boundary_focus_specs_example.txt)
- [other_station_targets_example.txt](other_station_targets_example.txt)

## Local-Only Artifacts

Packet captures and raw communication logs are intentionally not tracked in Git for this target either.

Summarize conclusions in Markdown instead of committing raw capture files.


