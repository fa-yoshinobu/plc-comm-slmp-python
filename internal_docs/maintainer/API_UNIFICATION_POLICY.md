# API Unification Policy

This document defines the public API rules for the SLMP Python library.
The high-level helper surface follows these rules as of 0.1.14.

## Purpose

- Keep the SLMP Python API internally consistent between sync and async clients.
- Keep operation names aligned with the C++ SLMP library where the operation class is the same.
- Avoid hiding protocol-specific distinctions behind overly generic names.

## Public API Shape

The canonical low-level client classes are:

- `SlmpClient`
- `AsyncSlmpClient`

This library is protocol-oriented.
It must not replace clear SLMP operation names with a generic `read()` or `write()` facade.

If a separate string-address facade is ever introduced, reserve these names for that layer:

- `SlmpDeviceClient`
- `AsyncSlmpDeviceClient`

The top-level helper surface for normal application code is:

- `SlmpConnectionOptions`
- `open_and_connect` / `open_and_connect_sync`
- `QueuedAsyncSlmpClient`
- `normalize_address`
- `parse_address` / `try_parse_address` / `format_address`
- `read_typed` / `write_typed`
- `read_named` / `write_named`
- `write_bit_in_word`
- `read_words_single_request` / `read_dwords_single_request`
- `read_words_chunked` / `read_dwords_chunked`
- `poll`

Canonical direct device names:

- `read_devices`
- `write_devices`
- `read_dword`
- `write_dword`
- `read_dwords`
- `write_dwords`
- `read_float32`
- `write_float32`
- `read_float32s`
- `write_float32s`
- `read_devices_ext`
- `write_devices_ext`
- `read_random`
- `read_random_ext`
- `write_random_words`
- `write_random_words_ext`
- `write_random_bits`
- `write_random_bits_ext`
- `read_block`
- `write_block`
- `read_type_name`

Canonical specialized names:

- `register_monitor_devices`
- `register_monitor_devices_ext`
- `run_monitor_cycle`
- `memory_read_words`
- `memory_write_words`
- `extend_unit_read_words`
- `extend_unit_write_words`
- `cpu_buffer_read_words`
- `cpu_buffer_write_words`
- `read_array_labels`
- `write_array_labels`
- `read_random_labels`
- `write_random_labels`
- `remote_run`
- `remote_stop`
- `remote_pause`
- `remote_latch_clear`
- `remote_reset`
- `remote_password_unlock`
- `remote_password_lock`

## Raw Wrapper Boundary

`*_raw` helpers are maintainer-facing protocol tools.

Rules:

- keep `*_raw` helpers available for library development, protocol investigation, and regression reproduction
- do not treat `*_raw` helpers as part of the normal user-facing API surface
- do not promote `*_raw` helpers in README, samples, or user-guide-first workflows
- typed helpers remain the canonical public API for normal consumers
- breaking changes to `*_raw` helpers may be acceptable when required for internal protocol correctness, as long as maintainer docs are updated

## Sync and Async Parity Rules

The async client must mirror the sync client as closely as possible.

Rules:

- The async method name stays identical to the sync method name.
- The async method returns the same logical result shape as the sync method.
- Argument names and ordering stay aligned.
- Missing async parity is considered backlog, not a reason to rename the sync API.

Examples:

- `client.read_devices(...)`
- `await async_client.read_devices(...)`
- `client.read_block(...)`
- `await async_client.read_block(...)`

## Address Helper Rules

Public helper-layer address utilities must accept the same notation as
`read_named` and `write_named`.

Rules:

- `normalize_address(...)` returns canonical text only.
- `parse_address(...)` returns `SlmpAddress` with `base_device`, `dtype`, bit index, and explicit dtype state.
- `try_parse_address(...)` is the non-throwing UI/config validation path.
- `format_address(...)` renders stored address metadata back to canonical helper-layer text.
- `X` / `Y` string notation still requires `plc_family` or an explicit device-family hint.
- `plc_family` remains the only normal high-level PLC selector. Raw `frame_type`, access profile, and range-family knobs stay in low-level/client tooling unless live evidence creates a concrete public need.

## Cross-Language Parity Rules

When an equivalent operation exists in the C++ SLMP library, semantic names should stay aligned.

Examples:

- `read_type_name` <-> `readTypeName`
- `read_random` <-> `readRandom`
- `read_block` <-> `readBlock`
- `write_random_bits` <-> `writeRandomBits`

Python-specific helper names may remain more descriptive where the C++ layer uses overloads or buffer-oriented signatures.

## Internal Naming Rules

Public methods should be action-first and domain-clear.
If a method name mainly mirrors a spec phrase but reads awkwardly in Python, prefer clearer English for the public API and keep the spec-oriented form private.

Canonical specialized names:

- `register_monitor_devices`
- `register_monitor_devices_ext`
- `run_monitor_cycle`
- `read_array_labels`
- `write_array_labels`
- `read_random_labels`
- `write_random_labels`
- `remote_run`
- `remote_stop`
- `remote_pause`
- `remote_latch_clear`
- `remote_reset`
- `remote_password_unlock`
- `remote_password_lock`

Private or builder helpers may keep explicit construction names such as:

- `build_array_label_read_payload`
- `build_label_write_random_payload`
- `parse_array_label_read_response`

For 32-bit codecs, prefer helper names that include both type and word order.

- `pack_uint32_low_word_first`
- `unpack_uint32_low_word_first`
- `pack_float32_low_word_first`
- `unpack_float32_low_word_first`

## 32-Bit Value Rules

The library should distinguish raw 32-bit integers from IEEE 754 floating-point values.

- `dword` means a raw 32-bit unsigned value stored across two PLC words.
- Signed 32-bit helpers, if added later, should be named `read_int32` and `write_int32`.
- Floating-point helpers should use `float32` in the public name, not plain `float`.

Default 32-bit word-pair interpretation:

- The default contract is protocol-native low-word-first ordering.
- If alternate word order must be supported, use an explicit keyword such as `word_order`.
- Avoid public names such as `read_float_swapped`.

## Semantic Atomicity Rules

High-level helpers must keep one user-visible logical value intact unless the
caller chooses an explicit chunked helper.

Rules:

- `*_single_request` helpers keep one logical operation on one protocol request.
- `*_chunked` helpers are opt-in and must keep 32-bit values aligned.
- Fallbacks that change mixed-block write semantics must stay explicit.
  `split_mixed_blocks=True` is the supported split path; automatic retry is
  not part of the API.

## Non-Goals

The following are intentionally not goals for the SLMP Python API.

- Adding a generic top-level `read()`/`write()` abstraction for all device access.
- Renaming protocol-specific operations only to match non-SLMP libraries.
- Creating different sync and async vocabularies for the same operation.

## Documentation Rules

README, samples, and generated docs must describe the canonical names from this document.
If a sync method exists and async parity is not implemented yet, that gap should be documented as a backlog item rather than hidden behind a new alias.
Primary docs must use `SlmpClient` and `AsyncSlmpClient`.
