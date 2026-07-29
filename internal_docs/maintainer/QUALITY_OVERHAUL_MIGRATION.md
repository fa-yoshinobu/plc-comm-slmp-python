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

Specify choices that change the command meaning or destination: `bit_unit`, remote run/pause mode arguments, and long-timer `head_no`/`points`. The four sync/async generic Direct and Extended Device read/write methods require an actual Boolean `bit_unit`; omission is a signature error and null, numbers, strings, and containers fail in the shared operation builder before framing. Long-timer and long-retentive-timer multi-point helpers require exact integer `head_no` and `points`; heads must fit `0..0xFFFFFFFF`, points must fit the active profile's one-request direct-word limit after multiplication by four, and no missing, null, Boolean, string, zero, negative, overflow, or wrapped value reaches transport. Unit-specific helpers select their unit internally. Remote RUN requires an actual Boolean `force` plus `RemoteClearMode`; Remote PAUSE requires the Boolean `force`. Missing, false-like aliases, raw numeric clear modes, and undefined choices fail before request creation. The clear-mode enum maps NoClear, ClearExceptLatch, and ClearAll to wire values 0, 1, and 2.

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

## 2026-07-12 D-128 through D-132 delta

### D-128 — Monitor contract

- Scope: sync/async monitor registration and cycle APIs.
- Target: registration and every cycle are separate single requests; cycle counts are explicit, nonzero, and within the active profile limit, and no registration, split, retry, or fallback is hidden.
- Compatibility: calling a cycle before PLC registration still sends one cycle request and returns the PLC result.
- Acceptance: Word/DWord typing, empty/count/profile/device checks, PLC NG, exact response length, and three-cycle behavior are covered.

### D-129 — Exact self-test echo

- Scope: sync/async `self_test_loopback`.
- Target: accept only 1–960 ASCII `0-9/A-F` bytes and require declared length, actual length, and byte-for-byte echo equality.
- Compatibility: trailing, short, wrong-length, and mismatched echoes now fail instead of returning bytes.
- Acceptance: valid and every malformed response class are covered for sync and async clients.

### D-130 — Qualified Extended Device result keys

- Scope: sync/async `read_random_ext` result mappings.
- Target: canonical keys retain CPU/unit/network route and typed modifier.
- Compatibility: keys such as `HG0` become `U3E0\HG0`; applications must migrate lookups. Ordinary `read_random` keys do not change.
- Acceptance: distinct `U3E0/U3E1`, `U1/U2`, and `J1/J2` routes coexist; only an identical canonical wire target is rejected before transport.

### D-131 — Clear Error semantic API

- Scope: sync/async `clear_error`.
- Target: one fixed `0x1617/0x0000` request with empty payload and no retry or fallback.
- Compatibility: callers no longer need maintainer raw command access.
- Acceptance: exact request and PLC-error propagation are covered.

### D-132 — HG target ownership

- Scope: qualified `U3En\HG` operations, Extend Unit operations, public aliases, and target documentation.
- Target: `0x0601/0x1601` remain available only as `extend_unit_*`; HG remains available only through qualified Extended Device APIs. The qualified device never changes the user-selected request target. Cross-CPU reads remain allowed; applications explicitly select the destination CPU for writes.
- Compatibility: `CpuModule` and all sync/async `cpu_buffer_*` aliases are removed. Migrate those calls to `extend_unit_*`; do not rename them mechanically to an HG address because live evidence proves the physical areas differ. No automatic target match, other-CPU fallback, resend, readback, or retry will be added.
- Acceptance: public-surface tests reject the removed names, Extend Unit exact-frame tests remain, qualified HG exact-frame tests remain, and frames retain `0x03FF` for an Own Station client while using `0x03E1` only for an explicitly CPU No.2-targeted client.

- [x] Local implementation and regression tests completed.
- [x] Ruff, formatting, Mypy, full unit suite, CLI checks, docs coverage, and release check passed.
- [x] User API, migration, changelog, and shared target guidance updated.
- [x] Claude review of this delta completed through `CLAUDE-SLMP-20260712-02`; all findings were dispositioned and affected checks rerun.
- [x] New public-API verification completed through deterministic regression coverage and the approved D-128/D-129/D-131 live checks.
- [x] D-132 Extend Unit versus HG physical-area classification completed: independent values remained stable through immediate, 50 ms, 250 ms, and 1 s cross-reads.
- [x] Removed the misleading CPU-buffer aliases and typed alias-only enum; retained distinct Extend Unit and qualified HG surfaces.

## NR-006: Lifetime traffic statistics

Scope: synchronous, asynchronous, and queued client `traffic_stats()`, next release.

Target contract: the method returns a client-lifetime immutable snapshot. A request and its full
frame bytes count only after a complete transport send succeeds. A complete received frame/datagram
TCP response counts after assembly in the selected frame format; a UDP datagram counts on receipt.
Both count before serial, end-code, or payload validation. Unrecognized TCP subheaders, partial
sends/receives, and pre-send failures do not count. Close/reconnect does not reset counters.

Acceptance criteria:

- [x] Implementation and deterministic boundary tests completed.
- [x] Public exports, API reference, usage guide, and Unreleased changelog agree.
- [x] Live PLC verification is unnecessary because deterministic transports observe every boundary.
- [x] Final next-release package and cross-language API comparison completed. Evidence: the `v4.0.0`
  tag equals repository HEAD, the GitHub Release and PyPI `plc-comm-slmp` `4.0.0` package are public,
  tag-commit checks passed, and the final five-implementation source/API comparison was completed
  on 2026-07-18.

## BH-LIVE-SLMP-20260729 — Supplemental bug-hunt live verification

Scope: commit `ab729d3b53cbe49690c25e46669f0ad11714cd51`, profile `melsec:iq-r`, TCP
`192.168.250.100:1025`.

Target contract: the library sends profile-catalog range exceedances that fit the wire format, uses
the Q/L layout for J link-direct extended random and monitor operations, and leaves every test
device in its documented final state.

Acceptance evidence:

- [x] `D100` one-word read succeeded with value `0`.
- [x] `R32768` reached the PLC and surfaced `slmp.errors.SlmpError` end code `0x4031` for command
  `0x0401`, subcommand `0x0002`; no pre-send profile-range rejection occurred.
- [x] Extended random read of `J1\W10` succeeded with value `0`.
- [x] Extended random word write changed `J1\W10` from `0` to `0x4A71`, read back `0x4A71`,
  restored `0`, and confirmed the restoration.
- [x] Extended random bit write changed `J1\B10` to ON, read ON, reset it to OFF, and confirmed OFF.
- [x] Extended monitor registration for `J1\W10` and one monitor cycle succeeded with value `0`;
  the TCP session was then closed.
- [x] The repository working tree was clean after the live probes.

Disposition: all supplemental live checks passed. The `R32768` result is PLC-side address evidence,
not authority to add a communication-library profile-range guard.
