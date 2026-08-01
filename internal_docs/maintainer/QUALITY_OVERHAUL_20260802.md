# Quality Overhaul Decisions — 2026-08-02

This maintainer record preserves approved target-state decisions before implementation. A checked
acceptance box requires recorded evidence; approval or intent alone is not completion evidence.

## SLMP-ERROR-INFO-CORRELATION-001 — Correlate present PLC error information with the active request

Decision status: implemented and verified on 2026-08-02.

### Implementation scope

All synchronous and asynchronous Python SLMP 3E/4E TCP and UDP response paths that receive a
non-zero end code and at least the 9-byte PLC error-information prefix, including state-changing and
read-only command paths, error objects, transport invalidation, tests, user documentation, migration
notes, and changelog entries. The cross-language contract applies to the Node.js, Python, Rust, C++,
and .NET SLMP implementations.

### Target contract

When a non-zero-end-code response contains the 9-byte PLC error-information prefix, the embedded
network, station, module I/O, multidrop, command, and subcommand must match the active request's
wire identity. A mismatch is a malformed, uncorrelated response rather than a definitive PLC error.
The transport is invalidated so that the response cannot affect a later request. A read-only
operation reports the implementation's malformed/protocol response error. A state-changing
operation reports `SlmpOutcomeUnknownError` with `PROTOCOL` reason.

Bytes following the 9-byte prefix remain permitted and are preserved as PLC-supplied additional
error data. This decision does not define the handling of a non-zero-end-code response whose error
information is absent or shorter than 9 bytes; that remains a separate specification item.

### Compatibility and operational impact

Responses whose outer route or 4E serial previously matched, but whose embedded error information
identified another request, no longer surface as definitive PLC errors and no longer leave the
transport reusable. Valid PLC errors with matching embedded request identity are unchanged. This is
an intentional behavioral break with no compatibility fallback.

### Machine-verifiable acceptance criteria

1. For synchronous and asynchronous 3E and 4E over TCP and UDP, each embedded route-field mismatch
   is rejected as malformed and invalidates the transport.
2. For the same matrix, embedded command and subcommand mismatches are rejected as malformed and
   invalidate the transport.
3. A mismatched error-information response for a state-changing request produces
   `SlmpOutcomeUnknownError` with `PROTOCOL` reason.
4. The same mismatch for a read-only request produces the documented malformed/protocol error and
   never a definitive PLC error.
5. A matching 9-byte prefix still produces the existing structured PLC error, and additional bytes
   after that prefix are retained without imposing an exact 9-byte response length.
6. Existing outer route, frame type, complete-length, reserved-field where implemented, and 4E
   serial correlation checks continue to pass.
7. Cross-language contract tests use equivalent vectors in Node.js, Python, Rust, C++, and .NET.

### Acceptance tracking

- [x] Implementation completed in this repository. Evidence: sync/async request identity includes route, command, and subcommand, and correlation rejects a mismatched present error-information prefix before publication.
- [x] Tests added or updated for every acceptance criterion in this repository. Evidence: deterministic 3E/4E, TCP/UDP, sync/async, read/write matrices cover every embedded route field, command, subcommand, matching prefixes, and trailing data.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed. Evidence: `run_ci.bat` passed Ruff, format, Mypy, API coverage, and 733 tests plus 317 subtests; the 103-file current-worktree source archive, wheel/sdist contents, and isolated package consumer also passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements. Evidence: the actual diff, public and private request paths, validation order, transport retirement, error classification, tests, package contents, and equivalent Node.js, C++, Rust, and .NET vectors were reviewed; no accepted finding remains.
- [x] Required live-PLC checks passed, or each unavailable check has an explicit release disposition. Disposition: no live PLC check is required because deliberately mismatched response identities are completely determined by local frame vectors and must not be induced on hardware.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation. Evidence: user usage, gotchas, API reference, migration record, and Unreleased changelog describe the same validation and error behavior.
- [x] Final acceptance criteria verified and the item marked complete. Evidence: an independent cross-language audit confirmed all six embedded identity fields, additional-data retention, read/write classification, invalidation, and supported frame/transport matrices; the final Rust and .NET full gates passed after their accepted findings were corrected.

## 2026-08-02 local Codex self-review classification

### SLMP-ERROR-INFO-CORRELATION-001

- Accepted and corrected: an existing structured-error test encoded subcommand
  `0x0001` while the active iQ-R bit request used `0x0003`. The fixture and
  assertion now use the actual request identity.
- Accepted and corrected: the initial regression covered command mismatch but
  not each embedded route field and subcommand independently. The final matrix
  covers all six identity fields for sync/async, 3E/4E, TCP/UDP, and read/write.
- Rejected: requiring the complete error data to be exactly nine bytes would
  discard permitted PLC additional error detail and contradict the approved
  prefix contract.
- Duplicate findings: none. Deferred findings: none.

### SLMP-PYTHON-4E-RESERVED-001

- Accepted and corrected: the initial transport regression covered only a
  synchronous read. Direct independent-byte/multi-byte decoder cases and the
  complete sync/async TCP/UDP read/write classification matrix were added.
- Rejected findings: none. Duplicate findings: none. Deferred findings: none.

### SLMP-EMPTY-ACK-001

- Accepted and corrected: representative write tests alone did not prove every
  listed semantic command family. A table now covers empty and non-empty success
  data for every classified ACK command in both clients, with transport-matrix
  integration and raw-command escape-hatch tests retained separately.
- Rejected: applying the empty-ACK rule to `raw_command()` would break its
  approved arbitrary vendor-response contract. Remote RESET also remains
  send-only.
- Duplicate findings: none. Deferred findings: none.

## SLMP-PYTHON-4E-RESERVED-001 — Require zero reserved bytes in every 4E response

Decision status: implemented and verified on 2026-08-02.

### Implementation scope

All synchronous and asynchronous Python SLMP 4E response paths over TCP and UDP, including frame
decoding, request correlation, malformed-response classification, state-changing outcome
classification, transport invalidation, deterministic tests, user documentation, migration notes,
changelog, and generated API reference. This brings Python into the same reserved-field contract as
the Node.js, Rust, C++, and .NET SLMP implementations. The 3E frame format is outside this field-level
requirement.

### Target contract

Every received 4E response must contain `0x0000` in zero-based frame bytes 4 and 5, the 4E reserved
field. The check applies before a response can be correlated with or published as the active
request's result. Any non-zero value is a malformed response and invalidates the active transport.

For a state-changing request that may have been transmitted, a non-zero reserved field produces
`SlmpOutcomeUnknownError` with `PROTOCOL` reason. For a read-only request, it
produces the documented protocol/malformed-response error. Synchronous and asynchronous clients,
and TCP and UDP transports, expose the same classification and transport state transition.

A correctly formed 4E response whose reserved field is `0x0000` retains its current behavior. All
3E responses retain their current behavior because 3E has no corresponding reserved field at those
offsets. No compatibility fallback accepts or clears a non-zero received value.

### Compatibility and cross-language impact

Python callers that previously accepted a 4E response with a non-zero reserved field now receive a
malformed or outcome-unknown result and cannot reuse that transport. Valid 4E and all 3E traffic are
unchanged. The resulting contract is consistent across the Node.js, Python, Rust, C++, and .NET
implementations rather than leaving Python as the sole permissive decoder.

### Machine-verifiable acceptance criteria

1. Direct 4E decoder tests reject each independently non-zero reserved byte and representative
   multi-byte non-zero values before returning a decoded response.
2. Sync TCP and UDP tests prove that non-zero 4E reserved bytes are malformed, invalidate the
   transport, and cannot be consumed as the active request's response even when route and serial
   otherwise match.
3. Equivalent async TCP and UDP tests prove the same malformed classification and transport
   invalidation.
4. Representative transmitted state-changing requests in the sync/async and TCP/UDP matrix produce
   `SlmpOutcomeUnknownError` with `PROTOCOL` reason.
5. Representative read-only requests in the same matrix produce the documented protocol/malformed
   response error and never return decoded data or a definitive PLC error.
6. Valid `0x0000` 4E responses retain success and PLC-end-code behavior, including existing route
   and serial correlation.
7. Existing 3E success, PLC-error, malformed-frame, and request-correlation tests remain unchanged
   and pass without applying the 4E-only reserved-field rule.
8. Cross-language conformance vectors contain matching valid-zero and invalid-nonzero 4E cases for
   Node.js, Python, Rust, C++, and .NET.
9. All acceptance tests use local deterministic frames or transports and require no live PLC.

### Acceptance tracking

- [x] Implementation completed in this repository. Evidence: `decode_4e_response()` rejects every non-zero reserved field before response publication.
- [x] Tests added or updated for every acceptance criterion in this repository. Evidence: direct decoder values and sync/async TCP/UDP read/write matrices cover independent reserved bytes, multi-byte non-zero values, transport retirement, and outcome classification while the full 3E suite remains passing.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed. Evidence: `run_ci.bat` passed Ruff, format, Mypy, API coverage, and 733 tests plus 317 subtests; the 103-file current-worktree source archive, wheel/sdist contents, and isolated package consumer also passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements. Evidence: direct decode and transport paths, validation order, sync/async error mapping, 3E non-applicability, and equivalent Node.js, C++, Rust, and .NET zero/non-zero reserved-field behavior were reviewed; no accepted finding remains.
- [x] Required live-PLC checks passed, or each unavailable check has an explicit release disposition. Disposition: no live PLC check is required because the reserved field is a deterministic received-frame invariant and malformed non-zero frames are locally injected.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation. Evidence: user usage, gotchas, API reference, migration record, and Unreleased changelog describe the zero-reserved-field requirement.
- [x] Final acceptance criteria verified and the item marked complete. Evidence: an independent cross-language audit confirmed that all five implementations reject non-zero 4E reserved bytes before response publication while preserving valid-zero and 3E behavior.

## SLMP-EMPTY-ACK-001 — Require empty success data for semantic ACK-only operations

Decision status: implemented and verified on 2026-08-02.

### Implementation scope

All synchronous and asynchronous Python SLMP 3E/4E TCP and UDP response paths used by normal
semantic state-changing APIs whose successful response is ACK-only. The affected API families are
Direct and Extended Device writes, Random writes, Monitor registration, Block writes, memory and
Extend Unit writes, array/random label writes, Remote RUN/STOP/PAUSE/latch clear, remote-password
lock/unlock, and Clear Error. Remote RESET is send-only and therefore has no ACK payload to validate.
The maintainer-level `raw_command` API is explicitly outside this decision because arbitrary raw
commands may validly return response data.

### Target contract

For an affected semantic ACK-only operation, an `end_code=0` response is successful only when its
response data is exactly empty. Any non-empty response data is a malformed response, invalidates
the active transport, and produces `SlmpOutcomeUnknownError` with `PROTOCOL`
reason because the state-changing request may already have reached the PLC. Synchronous and
asynchronous clients expose the same classification and transport state transition.

The client must perform this ACK-shape validation before publishing success. It must not discard,
ignore, truncate, or reinterpret unexpected response data. The generic `raw_command` result retains
its current arbitrary-data contract and does not pass through this semantic empty-ACK requirement.

### Compatibility and operational impact

An affected semantic API that previously returned success after receiving an `end_code=0` response
with extra data now returns an outcome-unknown malformed-response error and cannot reuse that
transport. Correct empty ACK responses are unchanged. Raw-command callers remain able to inspect
non-empty success data. This is an intentional behavioral break with no silent fallback.

### Machine-verifiable acceptance criteria

1. A table-driven API-surface test covers every affected sync and async semantic API family and
   proves that an empty `end_code=0` ACK retains its existing successful result.
2. The same API-family coverage injects non-empty success data and proves that no affected method
   returns success or exposes the response as a definitive ACK.
3. Representative sync and async TCP and UDP tests, across both 3E and 4E frames, classify a
   non-empty ACK as `SlmpOutcomeUnknownError` with `PROTOCOL` reason.
4. After the malformed ACK in each transport path, the active transport is invalidated and a
   following request cannot consume or reuse that response generation.
5. Validation occurs after complete frame, route, reserved-field where applicable, serial, and end
   code processing, but before ACK success is published to the caller.
6. `raw_command` accepts and returns arbitrary non-empty `end_code=0` response data without being
   subjected to this semantic empty-ACK rule.
7. Remote RESET remains send-only and is not changed to wait for or validate a response.
8. Equivalent sync and async error type, reason, transport invalidation, and success behavior are
   asserted without live PLC hardware.

### Acceptance tracking

- [x] Implementation completed in this repository. Evidence: normal known state-changing commands require empty success data, while explicit `raw_command()` state classification bypasses the semantic ACK rule and Remote RESET remains send-only.
- [x] Tests added or updated for every acceptance criterion in this repository. Evidence: all listed ACK command families cover empty and non-empty data in sync and async clients; representative 3E/4E TCP/UDP paths, raw command, transport retirement, and outcome reason are also asserted.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed. Evidence: `run_ci.bat` passed Ruff, format, Mypy, API coverage, and 733 tests plus 317 subtests; the 103-file current-worktree source archive, wheel/sdist contents, and isolated package consumer also passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements. Evidence: every standard semantic ACK command family, raw-command bypass, Remote RESET send-only behavior, validation order, transport retirement, and the equivalent Node.js implementation were reviewed; no accepted finding remains.
- [x] Required live-PLC checks passed, or each unavailable check has an explicit release disposition. Disposition: no live PLC check is required because malformed extra ACK data is a deterministic negative response-shape test and correct empty ACK behavior remains covered by local transports.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation. Evidence: user usage, gotchas, API reference, migration record, and Unreleased changelog distinguish semantic empty ACKs from `raw_command()`.
- [x] Final acceptance criteria verified and the item marked complete. Evidence: an independent Node.js/Python audit confirmed empty success data, malformed non-empty classification, outcome-unknown behavior, transport invalidation, raw-command data retention, and send-only reset semantics.
