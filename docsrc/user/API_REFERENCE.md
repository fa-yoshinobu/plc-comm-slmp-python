# SLMP Python API Reference

This page is a user-facing index of the public Python SLMP API surface.
Use the usage guide for examples, and this page when you need to find the
operation name for a specific SLMP command family.

The sync `SlmpClient` and async `AsyncSlmpClient` expose the same low-level
operation names unless noted otherwise.

## Direct And Random Device Operations

| Operation | Public API |
| --- | --- |
| Direct device read/write | `read_devices`, `write_devices` |
| 32-bit values | `read_dword`, `write_dword`, `read_dwords`, `write_dwords` |
| Float32 values | `read_float32`, `write_float32`, `read_float32s`, `write_float32s` |
| Extended direct device read/write | `read_devices_ext`, `write_devices_ext` |
| Random read | `read_random` |
| Extended random read | `read_random_ext` |
| Random word/dword write | `write_random_words` |
| Extended random word/dword write | `write_random_words_ext` |
| Random bit write | `write_random_bits` |
| Extended random bit write | `write_random_bits_ext` |
| Block read/write | `read_block`, `write_block` |
| Type name | `read_type_name` |

Extended random APIs use the 008x subcommands. Use qualified device notation
such as `U1\G0`, `U3E0\HG0`, or `J2\SW10` where the route requires it.

## Specialized Operations

| Operation | Public API |
| --- | --- |
| Monitor registration/cycle | `register_monitor_devices`, `register_monitor_devices_ext`, `run_monitor_cycle` |
| Memory command words | `memory_read_words`, `memory_write_words` |
| Extend-unit command words | `extend_unit_read_words`, `extend_unit_write_words` |
| CPU-buffer convenience words | `cpu_buffer_read_words`, `cpu_buffer_write_words` |
| Label array access | `read_array_labels`, `write_array_labels` |
| Label random access | `read_random_labels`, `write_random_labels` |
| Remote CPU control | `remote_run`, `remote_stop`, `remote_pause`, `remote_latch_clear`, `remote_reset` |
| Remote password | `remote_password_unlock`, `remote_password_lock` |

## High-Level Helpers

| Operation | Public API |
| --- | --- |
| Connection helper | `open_and_connect`, `open_and_connect_sync`, `QueuedAsyncSlmpClient` |
| Typed values | `read_typed`, `write_typed` |
| Named mixed snapshots | `read_named`, `write_named`, `poll` |
| Chunked word/dword reads | `read_words_single_request`, `read_words_chunked`, `read_dwords_single_request`, `read_dwords_chunked` |
| Address handling | `normalize_address`, `parse_address`, `try_parse_address`, `format_address` |
| Bit-in-word write | `write_bit_in_word` |

## Target Module I/O Constants

`ModuleIONo` provides named request-header module I/O numbers for multi-CPU
and routed CPU targets. Pass these values to `SlmpTarget(module_io=...)`;
the default `SlmpTarget()` remains the own-station route `0x03FF`.

| Constant | Value |
| --- | --- |
| `ModuleIONo.CONTROL_SYSTEM_CPU` | `0x03D0` |
| `ModuleIONo.STANDBY_SYSTEM_CPU` | `0x03D1` |
| `ModuleIONo.SYSTEM_A_CPU` | `0x03D2` |
| `ModuleIONo.SYSTEM_B_CPU` | `0x03D3` |
| `ModuleIONo.MULTIPLE_CPU_1` .. `ModuleIONo.MULTIPLE_CPU_4` | `0x03E0` .. `0x03E3` |
| `ModuleIONo.REMOTE_HEAD_1` / `ModuleIONo.REMOTE_HEAD_2` | `0x03E0` / `0x03E1` |
| `ModuleIONo.CONTROL_SYSTEM_REMOTE_HEAD` / `ModuleIONo.STANDBY_SYSTEM_REMOTE_HEAD` | `0x03D0` / `0x03D1` |
| `ModuleIONo.OWN_STATION` | `0x03FF` |

## Generated API Details

The docs site also renders the installed package with mkdocstrings so class,
function, and dataclass signatures are searchable from the site API reference.
