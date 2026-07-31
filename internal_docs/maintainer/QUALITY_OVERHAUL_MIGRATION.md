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

Named reads and polling cycles may split only at independent entry boundaries
under `PY-AGGREGATE-002`; they preserve declared order and execute under one
exclusive ordinary-client turn. Named writes remain single-request-or-reject:
one word/DWord random family or one random-bit family. Other routes must be
called explicitly by the application.

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

## PY-LABEL-001 — Deterministic label-command wire contract

Scope: sync and async array/random label read and write APIs.

Target contract: implement `GOAL-SLMP-LABEL-001` from the workspace decision record. Unit `0` is a
logical bit count padded per 16 bits, unit `1` is a logical byte count padded per two bytes, caller
write buffers are exact and even, and response count/metadata/length/trailing data are validated.
The sync and async APIs snapshot request metadata before communication so correlation is stable.

Compatibility impact: zero lengths, odd random-label data, unpadded array data, and malformed or
uncorrelated responses that were previously tolerated now fail before transport or as `SlmpError`.

Acceptance criteria:

1. The shared bit and byte boundary vectors produce the approved padded wire lengths.
2. Invalid caller data produces no request in the typed sync API and uses the same builder in async.
3. Response count, array metadata, positive/even length, truncation, and full consumption are checked.
4. Unknown data type IDs and random spare values remain observable.

- [x] Implementation completed in this repository.
- [x] Tests added for every local acceptance criterion.
- [x] Ruff, mypy, complete tests, build, and package checks passed.
- [x] Codex self-review completed and accepted findings corrected.
- [x] Live PLC verification is not required for deterministic arithmetic and injected response vectors.
- [x] Documentation, migration note, changelog, and package contents agree.
- [x] Final acceptance verified.

Verification evidence:

- Ruff lint/format, mypy over 13 source files, and the public-documentation coverage check passed.
- Pytest passed 418 tests and 257 subtests.
- The final source state produced both sdist and wheel; Twine accepted both artifacts.
- The no-auto-publish guard and `git diff --check` passed.

Self-review disposition:

- Accepted: request and response code duplicated the same wire-length arithmetic. One pure
  calculator now owns the formula and both paths use it.
- Accepted: invalid request-unit and truncated item-header cases were missing from the first test
  draft. Those cases were added and reverified.
- Rejected: a shallow-snapshot mutation concern does not apply because label request points are
  frozen dataclasses; tuple conversion snapshots the sequence and the element state is immutable.
- No duplicate or deferred finding changes this contract.

## PY-REQUEST-001 — Representable and transport-safe request payloads

Scope: sync and async request submission plus Array/Random Label Read/Write payload construction.

Target contract: implement `GOAL-SLMP-REQUEST-001` from the workspace decision record. TCP command
payloads are limited to 65,529 bytes. UDP 3E/4E payloads are limited to 65,492/65,488 bytes so the
complete frame is at most 65,507 bytes. Rejection precedes connection, send, counters, trace state,
and 4E serial allocation. Label aggregate length is checked before joining the complete payload.

Compatibility impact: oversized inputs now raise `ValueError` deterministically and are never
truncated or split automatically.

Acceptance criteria:

1. TCP 3E/4E and UDP 3E/4E boundary frames encode the exact request-data length and UDP datagram size.
2. Sync and async boundary-plus-one rejection preserves serial, counters, trace, and connection state.
3. All four label builders accept 65,528 bytes and reject 65,530-byte aggregates, including
   abbreviation, multiple-point, and write-data cases.
4. Random Label Write rejects individual data lengths 65,536 and 65,537 before wire conversion.

- [x] Implementation completed in this repository.
- [x] Tests added for every local acceptance criterion.
- [x] Ruff, mypy, complete tests, build, and package checks passed.
- [x] Codex self-review completed and accepted findings corrected.
- [x] Live PLC verification is not required for deterministic field/datagram arithmetic.
- [x] Documentation, migration note, changelog, and generated API agree.
- [x] Final acceptance verified.

Verification evidence:

- `run_ci.bat` passed Ruff lint/format, mypy over 13 source files, public-API documentation coverage,
  421 tests, and 269 subtests.
- Isolated sdist and wheel builds succeeded and Twine accepted both artifacts.
- Canonical profile drift, the no-auto-publish guard, and `git diff --check` passed.

Self-review disposition:

- Accepted: sync and async send-only paths initially needed the same pre-serial guard as ordinary
  request/response paths. The shared validator now covers all four paths and was reverified.
- Accepted: aggregate growth must be bounded while appending chunks, not only after `b"".join`, to
  avoid constructing an oversized complete payload. All four label builders use the bounded helper.
- No rejected, duplicate, or deferred finding changes this contract.

## PY-PACKAGE-001 — Consumer-real package and worktree source gates

Scope: wheel/sdist construction and inspection, isolated consumer validation,
and self-contained source-archive validation.

Target contract: package evidence must come from a real wheel installed into a
fresh virtual environment while checkout and `PYTHONPATH` imports are disabled.
The source-archive script must construct its own synthetic Git tree from the
current worktree, including modified, untracked, and deleted paths, and the
extracted result must pass both the full repository gate and installed-wheel
consumer gate.

Compatibility impact: no runtime or public API behavior changes. Maintainer and
CI failures are stricter because build-only evidence, checkout imports, or an
incomplete current-worktree archive can no longer satisfy the release gate.

Acceptance criteria:

1. One real wheel and one sdist are built; consumer-only wheel and sdist
   inventories reject root maintainer/runner files, credential-like files,
   caches, and build/release output without excluding intended runtime source.
2. A fresh virtual environment installs the wheel with no dependencies, and an
   isolated interpreter proves `slmp` resolves inside that environment while
   checking public API types and both public RMW FIFO/no-retry docstrings from a
   generated UTF-8 Python smoke file.
3. `check_source_archive.ps1 -IncludeWorktree` internally creates a synthetic
   tree covering modified, untracked, and deleted Git worktree paths without
   changing the real index.
4. The extracted source runs the full repository gate and installed-wheel
   consumer gate under Python 3.10/current.

- [x] Implementation completed in this repository.
- [x] Tests and gates cover every acceptance criterion.
- [x] Python 3.10/current repository, package, and source-archive gates passed.
- [x] Codex self-review completed against artifact boundaries and the actual diff.
- [x] Live PLC verification is not required for deterministic packaging and archive mechanics.
- [x] Maintainer notes, changelog, CI, and gate behavior agree.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence:

- Python 3.10.20 and 3.14.3 each passed the 100-file current-worktree
  source-archive gate after extraction: Ruff lint/format, mypy over 15 source
  files, public API doc coverage, 446 tests, and 305 subtests.
- Each extracted archive built one 22-file wheel and one 28-file sdist. A fresh
  virtual environment installed the wheel, and isolated mode resolved `slmp`
  from that environment while reproducing the public API/RMW docstring checks.
- The no-auto-publish guard, `git diff --check`, temporary-index cleanup, and
  overhaul-branch check passed.

Self-review disposition:

- Accepted: build and inventory inspection did not prove the built wheel was an
  importable consumer artifact. The gate now installs it into a fresh virtual
  environment and uses isolated mode with `PYTHONPATH` removed.
- Accepted: the public RMW documentation contract was not reproduced by the
  package gate. Both installed helper docstrings are now checked for FIFO-turn
  ownership and the no-automatic-retry rule.
- Accepted: caller-built synthetic tree state was not an enforceable archive
  mode. The archive script now creates and removes its own temporary index.
- Accepted: extracted-source validation did not execute the installed-package
  contract. It now runs the package gate after the full source gate.
- Accepted: passing a here-string directly to native `python -I -c` on Windows
  did not preserve the Python quoting, so process success did not prove the
  intended assertions ran. The gate now writes UTF-8 Python under its disposable
  work root and executes that file in isolated mode.
- Accepted: the wheel/sdist inventory guard did not cover all AC9/DIST AC7
  negative categories. It now also rejects root maintainer/runner files,
  credential-like files, caches, and build/release output while retaining the
  intended runtime source and package metadata.
- No rejected, duplicate, or deferred finding remains for this item.

## PY-SERIAL-002 — Ordinary-client FIFO and close generations

Scope: synchronous and asynchronous ordinary clients; removal of the queued wrapper.

Target contract: every valid operation joins one re-entrant FIFO queue owned by
the ordinary client. Queue wait does not consume the request exchange deadline.
Async cancellation before activation removes the waiter without sending.
`close()` rejects the active and queued transport generation. No second public
queue wrapper remains.

Compatibility impact: `QueuedAsyncSlmpClient` is removed and
`open_and_connect()` returns `AsyncSlmpClient`. Operations overtaken by close now
fail as `SlmpClosedError` instead of running on an implicitly reopened transport.

Acceptance criteria:

1. Five sync and four async arrivals execute in FIFO order; a cancelled async waiter sends nothing.
2. Local close rejects both active and queued work from the prior generation.
3. A multi-request helper owns one re-entrant turn without deadlock or interleaving.
4. Request timeout begins after queue activation and remains one absolute send/response deadline.

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live PLC checks are not required for this deterministic queue/lifecycle contract.
- [x] Documentation, migration notes, changelog, and generated API reference agree.
- [x] Final acceptance criteria verified and the item marked complete.

## PY-ERROR-002 — Stable transport and outcome-unknown taxonomy

Scope: sync/async transport exchange and all known state-changing commands.

Target contract: timeout, caller cancellation, local close, not-connected state,
transport I/O, malformed protocol data, and PLC NG remain distinguishable. If a
state-changing frame may have been sent and completion is not known, raise
`SlmpOutcomeUnknownError` with `SlmpOutcomeUnknownReason` and the original cause.
Do not retry automatically.

Compatibility impact: post-send write/reset failures no longer surface as a
plain `OSError` or timeout. Callers must verify PLC state before retry.

Acceptance criteria:

1. Public exception types are exported and pairwise machine distinguishable.
2. Pre-send failures never become outcome-unknown.
3. Timeout, cancellation, close, transport, and malformed response after possible state-changing send preserve reason and cause.
4. PLC NG remains a structured `SlmpError`; no automatic retry is introduced.

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live PLC checks are not required for this deterministic error-classification contract.
- [x] Documentation, migration notes, changelog, and generated API reference agree.
- [x] Final acceptance criteria verified and the item marked complete.

## PY-AGGREGATE-002 — Read-only entry-boundary aggregation

Scope: `read_named`, `read_named_sync`, and `poll`.

Target contract: snapshot and preflight the full plan before send. An oversized
read may split only between independent entries, never within a scalar/DWord or
future string/structure/array/coherence unit. Preserve declared input and wire
order, hold one ordinary-client turn, stop on first failure, and expose no
partial normal result. The chunks are explicitly non-atomic. A write requiring
multiple protocol requests is rejected before send.

Compatibility impact: large named reads previously rejected can now execute as
ordered chunks. Mixed word/DWord input may use more requests to preserve wire
timing order. Duplicate result keys are rejected as ambiguous.

Acceptance criteria:

1. Selected-profile maximum and maximum-plus-one vectors produce one and two requests respectively.
2. Internal request order and result insertion order exactly match declared input order without sorting.
3. Full validation and request construction completes before the first send.
4. No operation interleaves between chunks and a later failure returns no partial dictionary.
5. All write aggregates that need more than one request fail before transport.

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live PLC checks are not required for this deterministic planner/aggregation contract.
- [x] Documentation, migration notes, changelog, and generated API reference agree.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence for `PY-SERIAL-002`, `PY-ERROR-002`, and
`PY-AGGREGATE-002`:

- The source-archive CI gate passed Ruff lint and formatting, mypy over 15
  source files, public API documentation coverage, 442 tests, and 305 subtests.
- Python 3.10.20 passed the same 442 tests and 305 subtests.
- Wheel and sdist construction, package-content validation, Twine checks, and
  an isolated Python 3.10 wheel import/export/type-marker check passed.
- The no-auto-publish guard and `git diff --check` passed.

Self-review disposition:

- Accepted: an active request overtaken by local close could initially surface
  as a transport failure. Generation rechecks now classify it as local close.
- Accepted: connection failures initially bypassed the exchange classifier.
  Connection establishment is now inside the classified operation scope.
- Accepted: send-only tracing initially happened outside the FIFO turn and
  before transport invalidation. Transport is invalidated first and tracing
  remains inside the operation turn.
- Accepted: the first named-read split used only the wire count field instead
  of the selected profile limit. Planning now uses the profile limit.
- Accepted: grouping mixed word/DWord entries by protocol category reordered
  the declared wire sequence. Category transitions now form chunk boundaries.
- Accepted: sync transport subclass ordering could classify a transport error
  as malformed protocol data. The classifier order was corrected.
- Accepted: user documentation and public helper docstrings still called a
  potentially multi-request named result a snapshot. They now use
  collection/result terminology while retaining explicit non-atomic timing.
- Not applicable: the synchronous API has no caller cancellation token; async
  queued and active cancellation are covered explicitly.
- No rejected, duplicate, or deferred finding changes these contracts.

## PY-RMW-001 — Explicit bit-in-word read-modify-write turn

Scope: sync/async `write_bit_in_word`, the ordinary-client operation queues,
public helper docstrings, samples, user docs, and package-consumer behavior.

Target contract: bind and validate the complete device, exact integer bit index,
exact Boolean value, selected profile, and both direct request paths before the
first send. Hold one re-entrant ordinary-client FIFO turn across the word read
and word write in both sync and async clients. This is same-client exclusion,
not PLC atomicity: another connection or PLC program logic can race, the two
requests can occur in different PLC scans, a possibly-sent write remains
outcome-unknown, and no automatic retry is allowed.

Compatibility impact: both public helper names and signatures remain. They now
reject coercible values and invalid targets before reading, and another
operation on the same client waits until the complete RMW operation finishes.
The removed queued wrapper is not reintroduced; samples use ordinary
`AsyncSlmpClient` FIFO ownership.

Acceptance criteria:

1. Non-integer/Boolean bit indexes, non-Boolean values, non-word devices,
   profile mismatch, unsupported direct routes, and write policy fail before the
   first read request.
2. Sync and async normal-client order is read, write, then any later queued
   operation, with no nested-queue deadlock.
3. A possibly-sent write uses `SlmpOutcomeUnknownError`; no automatic retry is
   introduced.
4. Public API/usage docs, public helper docstrings, sample language, and
   changelog state the two-request/non-atomic race and ordinary-client FIFO turn.
5. Python 3.10/current source gates and an installed wheel consumer reproduce
   the contract.

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live PLC checks are not required for this deterministic queue/validation contract; existing direct read/write protocol behavior is unchanged.
- [x] Documentation, migration notes, changelog, and generated API reference agree.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence:

- The current Python 3.10.20 environment and an isolated Python 3.10 gate passed
  Ruff lint/format, mypy over 15 source files, public API docstring coverage for
  206 definitions and 127 methods, 446 tests, and 305 subtests.
- Wheel/sdist content validation, Twine checks, MkDocs strict, and the
  no-auto-publish guard passed. An installed Python 3.10 wheel consumer reproduced
  RMW ordering and rendered the public FIFO/no-retry docstring.
- A synthetic Git tree containing the complete uncommitted worktree passed the
  100-file source-archive gate and its extracted full validation.
- `git diff --check` passed.

Self-review disposition:

- Accepted: sync and async RMW previously acquired a separate ordinary-client
  turn for each public read/write call. Both now hold one re-entrant aggregate
  turn around those calls.
- Accepted: bit indexes accepted `bool` through Python integer subtyping and the
  value used general truthiness. Exact integer and exact Boolean validation now
  completes before the first read.
- Accepted: the async sample still described the removed queued wrapper. It now
  demonstrates the FIFO owned by ordinary `AsyncSlmpClient`, with a source-level
  regression test.
- Accepted: user error/deadline text omitted dedicated transport/lifecycle types,
  decode coverage, and transport-generation retirement. API, usage, changelog,
  and public helper docstrings now agree.
- Accepted: the full format gate exposed pre-existing Markdown code-fence drift;
  Ruff formatting corrected it without changing the documented contracts.
- No rejected, duplicate, or deferred finding changes this contract.
