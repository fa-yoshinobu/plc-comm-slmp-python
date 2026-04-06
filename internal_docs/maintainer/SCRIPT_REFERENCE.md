# Script Reference

This page summarizes the repository CLI wrappers around `slmp.cli`.

The executable source files live under the repository `scripts/` directory in a
source checkout.

## Start Here

Safe first checks:

- `slmp_connection_check.py`
- `slmp_regression_suite.py`

Focused verification:

- `slmp_open_items_recheck.py`
- `slmp_pending_live_verification.py`
- `slmp_special_device_probe.py`
- `slmp_extended_device_device_recheck.py`
- `slmp_g_hg_extended_device_recheck.py`
- `slmp_g_hg_extended_device_coverage.py`
- `slmp_mixed_block_compare.py`

Human-in-the-loop verification:

- `slmp_manual_write_verification.py`
- `slmp_manual_label_verification.py`

## Key Script Groups

### Setup and housekeeping

- `slmp_regression_suite.py`
- `slmp_compatibility_probe.py`
- `slmp_compatibility_matrix_render.py`
- `slmp_init_model_docs.py`
- `slmp_device_access_matrix_sync.py`

### Safe connection and scope checks

- `slmp_connection_check.py`
- `slmp_other_station_check.py`

### Rechecks for maintained open areas

- `slmp_open_items_recheck.py`
- `slmp_pending_live_verification.py`
- `slmp_special_device_probe.py`
- `slmp_extended_device_device_recheck.py`
- `slmp_g_hg_extended_device_recheck.py`
- `slmp_g_hg_extended_device_coverage.py`
- `slmp_mixed_block_compare.py`

### Boundary and range probes

- `slmp_device_range_probe.py`
- `slmp_register_boundary_probe.py`

### Load and performance

- `slmp_read_soak.py`
- `slmp_mixed_read_load.py`
- `slmp_tcp_concurrency.py`

Use [Testing Guide](TESTING_GUIDE.md) for execution order and release gates. Use
[User Guide](../user/USER_GUIDE.md) for API-facing examples.

