# SLMP Python API Reference

This page is a user-facing index of the public Python SLMP API surface.
Use the usage guide for examples, and this page when you need to find the
operation name for a specific SLMP command family.

The sync `SlmpClient` and async `AsyncSlmpClient` expose the same semantic
operation names unless noted otherwise.

All TCP and UDP clients are IPv4-only. A host may be an IPv4 literal or a
hostname with an IPv4 result. IPv6 literals and hostnames without an IPv4
result are rejected without IPv6 fallback.

## Direct And Random Device Operations

Individual bit-write values must be actual Python `bool` objects. Numeric `0`
and `1`, strings, bytes, `None`, and other truthy/falsy objects are rejected
before request construction. Packed bit-block words are a distinct wire-level
API and remain unsigned 16-bit integers.

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
Raw extension fields are not part of the public semantic API. Use
`SlmpExtendedDevice` with `SlmpIndexZ`, `SlmpIndexLz`, or `SlmpIndirect` only
when a typed modification is required; otherwise pass the qualified string.
`read_random_ext` result keys preserve the canonical complete route and typed
modifier, for example `U3E1\HG0`, `J2\W10`, or `U3E0\D100+Z4`. Only the
Extended Device result-key contract changed; ordinary `read_random` keys remain
plain canonical device addresses.

## Specialized Operations

| Operation | Public API |
| --- | --- |
| Monitor registration/cycle | `register_monitor_devices`, `register_monitor_devices_ext`, `run_monitor_cycle` |
| Self-test loopback | `self_test_loopback` |
| Clear PLC error | `clear_error` |
| Memory command words | `memory_read_words`, `memory_write_words` |
| Extend-unit command words | `extend_unit_read_words`, `extend_unit_write_words` |
| HG CPU-buffer words | `read_devices_ext`, `write_devices_ext` with a qualified `U3E0\HG` through `U3E3\HG` address |
| Label array access | `read_array_labels`, `write_array_labels` |
| Label random access | `read_random_labels`, `write_random_labels` |
| Remote CPU control | `remote_run`, `remote_stop`, `remote_pause`, `remote_latch_clear`, `remote_reset` |
| Remote password | `remote_password_unlock`, `remote_password_lock` |

Array label `unit_specification` is `0` for a logical bit count and `1` for a
logical byte count. Both forms occupy whole two-byte wire units: bit counts use
`ceil(array_data_length / 16) * 2` bytes and byte counts use
`ceil(array_data_length / 2) * 2` bytes. The logical length must be positive,
and `write_array_labels` requires the exact padded buffer length. Random label
read and write data lengths must also be positive and even. Read responses must
match the requested count and, for array labels, each requested unit and
logical length; malformed or trailing data raises `SlmpError`.

## High-Level Helpers

| Operation | Public API |
| --- | --- |
| Connection helper | `open_and_connect`, `open_and_connect_sync` |
| Profile descriptors | `plc_profile_descriptors`, `SlmpPlcProfileDescriptor` |
| Typed values | `read_typed`, `write_typed` |
| Named read/write collections | `read_named`, `write_named`, `poll` (the polling iterator prepares its immutable Random Read payload and compact decode indexes once) |
| Single-request word/dword reads | `read_words_single_request`, `read_dwords_single_request` |
| Profile-bound device address | `DeviceRef(code, number, plc_profile)`, `parse_device(value, plc_profile=...)` |
| Named address handling | `normalize_address`, `parse_address`, `try_parse_address`, `format_address` |
| Bit-in-word write | `write_bit_in_word` |

`write_named` emits exactly one random-write request. It rejects mixed
bit/word command families and bit-in-word read-modify-write entries. The
dedicated `write_bit_in_word` helper visibly performs the required read and
write requests. It snapshots and validates the complete operation before FIFO
admission, then holds one ordinary-client FIFO turn across both requests. This
prevents same-client interleaving only. The operation is not atomic at the PLC:
another connection or PLC program logic can change the word in the race window,
and the requests can run in different PLC scans. A possibly-sent write uses the
outcome-unknown error contract. The helper never retries automatically.

The contiguous, named, polling, and write helpers never split one call into
multiple protocol requests. `read_named` and each `poll` cycle validate the
complete plan, issue exactly one canonical Random Read, or reject before
transport. Oversized plans and entries requiring another command family must be
split into explicit application calls. Writes that would require multiple
requests are also rejected before send.

Typed command decoding uses private response-frame views internally. Public
raw command results, trace frames, error data, and APIs whose result is bytes
remain owned `bytes`; callers never receive a borrowed view.

Device requests must fit completely in the device-number field selected by the
entry's wire layout: 24 bits for Q/L and link-direct `J` entries, and 32 bits
for other iQ-R entries. A `J`-qualified link-direct device therefore keeps the
24-bit Q/L device specification even when the client profile is iQ-R. The
check covers contiguous Direct and Extended Device
reads/writes, Random/Monitor DWord entries, and Block ranges. A word-unit
operation on a bit device consumes 16 bit-device addresses per word, so a
DWord/float32 consumes 32; a Block bit point likewise consumes 16. Ordinary
word devices consume one address per word, while each four-word LTN/LSTN
current block consumes one logical long-timer device. If the final consumed
address would exceed the wire field, sync and async APIs raise `ValueError`
before framing, connection, or traffic-counter changes. This is a wire-format
bound, not a guard based on the profile device-range catalog.
Native LTN/LSTN/LCN/LZ Random and Monitor DWord entries consume one logical
device, and Random-write overlap checks use these same route-specific widths.

Semantic bit-unit and bit-entry APIs accept only bit devices. Block word entries
and typed/named numeric or string values accept only word devices; typed/named
`BIT` accepts only bit devices. Explicit low-level word-unit direct APIs retain
protocol-defined packed word access to bit-device ranges. Use `.n` notation or
`write_bit_in_word` for one bit inside a word device.

The decimal network number in a link-direct Extended Device string such as
`J2\SW10` uses ASCII `0` through `9` only. Unicode digit characters are
rejected before request construction.

## Target Module I/O Constants

`ModuleIONo` provides named request-header module I/O numbers for multi-CPU
and routed CPU targets. Construct `SlmpTarget` with all four route fields;
there is no implicit own-station route in the public connection API.

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

## Errors

`SlmpClosedError`, `SlmpNotConnectedError`, `SlmpTransportError`, and
`SlmpTimeoutError` distinguish local lifecycle, missing connection, I/O, and
request-deadline failures. They are dedicated `SlmpError` subclasses;
`SlmpTimeoutError` is also a `TimeoutError`. A state-changing request whose
result cannot be known after possible send raises
`SlmpOutcomeUnknownError(reason=..., cause=...)`; reasons are defined by
`SlmpOutcomeUnknownReason`, and automatic retry is not performed.

Response validation requires a zero 4E reserved field. When a PLC error includes
the structured error-information prefix, its route, command, and subcommand must
match the active request; trailing PLC error detail is preserved. Standard
semantic ACK-only APIs accept only empty success data. Any mismatch or non-empty
ACK retires the transport and is `SlmpError` for a read-only operation or
`SlmpOutcomeUnknownError` with reason `PROTOCOL` for a possibly applied state
change. `raw_command()` intentionally retains arbitrary success response data.

After complete response correlation and command-specific decoding, the result
is definitive: a later concurrent `close()` does not replace a decoded value,
acknowledged write, or framed PLC end-code. A read interrupted before that point
raises `SlmpClosedError`. A state-changing request that may have been sent but
has no definitive response remains outcome-unknown with reason `CLOSED`.

FIFO queue wait is outside the request deadline. After activation, one absolute
deadline covers IPv4 resolution, connection and socket configuration, first
send, complete transmit, receive, route/4E-serial correlation, and response
decode; no phase or foreign response restarts it. Timeout retires the current
transport generation, so another operation must establish a new generation and
cannot consume a late connection or response result. An explicit `connect()`
uses the same one-deadline rule from resolution through client adoption.

Device-range catalog reads use the canonical profile rules and the profile's
documented SD-register block only. They do not probe candidate device addresses
or translate PLC errors into inferred range boundaries.

## Generated API Details

The docs site also renders the installed package with mkdocstrings so class,
function, and dataclass signatures are searchable from the site API reference.

## Request payload limits

TCP command payloads are limited to 65,529 bytes. UDP command payloads are limited to 65,492 bytes
for 3E and 65,488 bytes for 4E so the complete frame fits one datagram. Oversized sync and async
requests fail with `ValueError` before transport, trace publication, or 4E serial allocation and
are never truncated or split automatically. Label builders enforce their
aggregate size; their largest protocol-representable even payload is 65,528
bytes.

| Operation category | Effective one-request capacity |
| --- | --- |
| Direct bit/word read and write | Selected profile's direct limit, count field, request payload, and read-response size |
| Random read | Selected profile's combined random-read limit and each 8-bit category count |
| Random word/DWord or bit write | Selected profile's total/weighted or bit limit, category count fields, and request payload |
| Monitor registration/cycle | Selected profile's registration total and weighted limits; cycle counts must match one registration |
| Block read/write | Selected profile block count and weighted point limits plus encoded request/response size |
| Memory and extend unit | Command-specific manual maximum, count field, and encoded request/response size |
| Array/random labels | Per-item field validity plus aggregate request/response payload size |

All categories accept their computed maximum as one request and reject maximum
plus one before send. Python allocates decoded response storage dynamically; it
does not expose a caller buffer that can truncate a valid response.

## Traffic Statistics

`SlmpClient.traffic_stats()` and `AsyncSlmpClient.traffic_stats()` return an immutable
`SlmpTrafficStats(request_count, tx_bytes, rx_bytes)` snapshot. Counters are cumulative for the
client lifetime and are not reset by close or reconnect.

## Operation ordering and errors

Ordinary `SlmpClient` and `AsyncSlmpClient` instances own a re-entrant FIFO
operation queue. `QueuedAsyncSlmpClient` has been removed. A queued async task
cancelled before activation sends nothing. `close()` rejects the active and
queued generation; a later operation may establish a new transport generation.

Public communication classifications are `SlmpTimeoutError`,
`SlmpClosedError`, `SlmpNotConnectedError`, and `SlmpTransportError`. A
state-changing request that may have been sent raises
`SlmpOutcomeUnknownError(reason=..., cause=...)` when its final result cannot be
known. Reasons are defined by `SlmpOutcomeUnknownReason`.
