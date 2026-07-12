# SLMP Python Quality-Overhaul Migration

This document records source migrations required by the cross-library quality overhaul. The approved rationale and acceptance history remain in the workspace decision records.

## Legacy validation scripts

The repository no longer ships one-off scripts that select frame/series
combinations independently, call removed raw or split APIs, or probe
standalone G/HG routes. Those scripts could bypass the canonical profile and
reintroduce behavior intentionally removed from the public contract.

Use `plc-comm-slmp-profiles/tools/live_profile_probe.py` with
`capability/slmp_ethernet_profiles.json` for live profile evidence. This is a
breaking removal; there are no compatibility wrappers.

## Connection construction

Always provide `port`, `transport`, `plc_profile`, and a complete `SlmpTarget`. The library no longer chooses a destination port, TCP, a PLC family, or an own-station route when those values are missing.

This requirement also applies to the internal CLI probe client. Its constructor has no transport default, every communicating CLI parser requires `--transport`, and bundled samples either accept an explicit transport input or intentionally pass a concrete transport in code. The D-002 regression suite includes direct construction with an omitted transport and confirms signature rejection before transport creation.

The internal CLI probe client also requires `default_target` in its signature. Every communicating CLI and the shared sample parser require all four route options: `--network`, `--station`, `--module-io`, and `--multidrop`. They do not fill missing values with the own-station route. A source-level regression test walks all route parser declarations and rejects any default or non-required route component. Samples that deliberately construct a concrete `SlmpTarget` in code remain explicit callers and are not omission fallbacks.

The regression-suite command remains usable without any PLC settings for local-only checks. If `--include-live-connection-check` is selected, it additionally requires `--live-network`, `--live-station`, `--live-module-io`, and `--live-multidrop` and forwards all four to the connection-check command. No live route is synthesized by the suite.

Communication timeout remains the one approved omission: exactly 3 seconds. Sync/async/options/internal CLI client defaults and every communicating CLI `--timeout` default use the same value. Explicit non-positive, non-finite, Boolean, and nonnumeric programmatic inputs are rejected before socket use. The CLI source regression walks every `--timeout` parser declaration and requires a numeric default of `3.0`.

Request-level monitoring timer omission inherits the validated connection timer. An explicit exact integer in `0..65535` overrides it for that request, including zero for PLC-side indefinite processing wait. Boolean, fractional, string, negative, overflow, and container overrides fail before framing in both sync and async clients; they never become zero or inheritance.

TCP keepalive is also omitted by callers and fixed by the library: TCP enables keepalive with a 30-second idle period, while UDP never applies it. Keepalive is a required part of successful TCP setup. If socket access or keepalive configuration fails, sync closes the new socket and async closes and awaits the new writer before rethrowing; neither client publishes a partially configured connection. Platform-specific probe intervals and counts are not normalized.

## Profile guard

Normal public options and clients do not expose `strict_profile`. Profile feature guards are always enabled when that setting is omitted because omission is the only public state. Controlled maintainer tests may pass the underscore-prefixed `_maintainer_strict_profile` Boolean; aliases, strings, numbers, null, and other coercions are rejected. Setting this internal Boolean to `False` bypasses only `blocked` or `unverified` profile-feature decisions. Point limits, write policy, address validation, route validation, and command validation remain active.

User-facing errors do not advertise the maintainer bypass. They report the canonical profile, feature, state, and available evidence only. User documentation must continue to describe the supported guarded behavior rather than the investigation switch.

## PLC end-code policy

`raise_on_error` remains optional and defaults to `True`. A non-zero PLC end code therefore raises `SlmpError` in normal sync and async use. Controlled evidence tools may pass the actual Boolean `False` to collect the structured response, but strings, numbers, null, empty values, and containers are rejected at options/client construction or before request framing. Each request snapshots the inherited or explicit Boolean before queue/transport work, so later mutation of the client setting cannot change an in-flight response decision. This switch affects only non-zero PLC end codes; connection failure and communication timeout remain errors.

## Trace callback

Normal sync and async clients omit the underscore-prefixed `_maintainer_trace_hook`, so no callback is registered and no trace is automatically written. The callback is an internal diagnostic integration point used by maintained evidence commands, not a user-facing option. When supplied internally it must be callable; invalid values fail during construction before any transport is created.

## Profile-bound requests

Remove request-level `series=` arguments. Construct the client with the exact canonical PLC profile; device encoding, subcommand family, password shape, frame type, and address rules are derived from that profile.

`DeviceRef` is profile-bound. Construct it as `DeviceRef(code, number, plc_profile)`, or parse text with an explicit profile.

## Raw access

Replace direct `request()` calls and command-specific raw wrappers with one of the following:

- the semantic public method for the operation; or
- `raw_command(command, subcommand=..., payload=...)` for maintainer investigation.

All three raw command fields are required. The client owns 4E serial allocation and response correlation.

## Required operation choices

Specify choices that change the command meaning or destination: `bit_unit`, CPU-buffer `module=CpuModule.CPU1` through `CPU4`, remote run/pause mode arguments, and long-timer `head_no`/`points`. The four sync/async generic Direct and Extended Device read/write methods require an actual Boolean `bit_unit`; omission is a signature error and null, numbers, strings, and containers fail in the shared operation builder before framing. CPU-buffer helpers require the typed `CpuModule`; raw integers and `ModuleIONo` values are rejected so the selected CPU remains discoverable and explicit. Long-timer and long-retentive-timer multi-point helpers require exact integer `head_no` and `points`; heads must fit `0..0xFFFFFFFF`, points must fit the active profile's one-request direct-word limit after multiplication by four, and no missing, null, Boolean, string, zero, negative, overflow, or wrapped value reaches transport. Unit-specific helpers select their unit internally. Remote RUN requires an actual Boolean `force` plus `RemoteClearMode`; Remote PAUSE requires the Boolean `force`. Missing, false-like aliases, raw numeric clear modes, and undefined choices fail before request creation. The clear-mode enum maps NoClear, ClearExceptLatch, and ClearAll to wire values 0, 1, and 2.

## Multiple-request behavior

Replace chunked helpers and automatic mixed-block splitting with explicit application-controlled requests. If a logical read spans requests, the application must define snapshot/version checks. If a logical write spans requests, it must define partial-success and retry handling.

Named reads, polling cycles, and named writes are also single-request-or-reject. A named read/poll accepts only entries that fit one random-read request. A named write accepts one word/DWord random family or one random-bit family. Other routes must be called explicitly by the application.

Random read may omit either the word or DWord device collection. At least one valid device is required across both categories; all-empty and invalid supplied collections fail before transport. The result always contains both mappings, with the unused category represented by an empty mapping. The same rule applies to semantic Extended Device random reads.

Random word write follows the same category-omission rule for word and DWord value collections. At least one valid address/value pair is required; all-empty, malformed, invalid, duplicate, and overlapping destinations fail before transport. Random bit write remains a separate API with one required bit-value collection.

Block read and write may omit either the word or bit block collection. At least one valid block is required; all-empty, malformed, invalid-unit, out-of-limit, and overlapping write ranges fail before transport. A block-read result always contains both block lists, with the unused category represented by an empty list. One mixed call remains one protocol request.

`write_named` no longer performs one hidden request per entry. Compatible
word/DWord entries are compiled to one random-word write and compatible bit
entries to one random-bit write. Mixing those command families fails before
transport. Bit-in-word entries are not accepted because they require a
read-modify-write pair; maintainers and applications must call
`write_bit_in_word` explicitly and account for its two-request race window.

All numeric write builders require exact integers in their wire range and all
bit builders require `bool` or the exact integers 0/1. Typed helpers are
stricter: `BIT` requires `bool`; U/S/D/L enforce their semantic ranges; F
requires a finite value representable as float32. No write path masks,
truncates, parses, or applies truthiness to an invalid value.

Send-only remote reset always invalidates the current transport after the
frame is transmitted. UDP receive timeout/error also invalidates the socket
generation. These are response-ownership requirements: a possible residual
3E response must never be eligible for the next request.

## Extended Device access

Use qualified device text such as `U3E0\G10`. For supported index/indirect modification, wrap it in `SlmpExtendedDevice` with `SlmpIndexZ`, `SlmpIndexLz`, or `SlmpIndirect`. Raw extension bitfields are no longer a public contract.
