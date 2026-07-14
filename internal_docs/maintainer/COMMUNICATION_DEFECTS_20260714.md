# Communication Defect Corrections — 2026-07-14

Status: Python implementation, deterministic verification, Claude disposition, and cross-library QREV comparison are
complete. Next-release publication remains a separate explicitly authorized action.

## GOAL-QREV-20260714-002 — Complete SLMP response route correlation

- Implementation scope: `plc-comm-slmp-python`, synchronous and asynchronous clients, 3E/4E, TCP/UDP.
- Target contract: A syntactically complete response completes a request only when network, station, module I/O, and
  multidrop equal the request target. A 4E response must also match its allocated serial. Valid foreign responses are
  counted and discarded within the original deadline; malformed frames are protocol errors and invalidate transport.
- Compatibility impact: Frames with a route different from the request are no longer returned as successful results or
  PLC end-code responses. No public signature changes.

### Machine-verifiable acceptance criteria

1. For 3E/4E over TCP/UDP in sync and async clients, changing each route field independently and then supplying a
   matching response returns only the matching payload.
2. A delayed matching response after a valid foreign response succeeds when it arrives within the original deadline.
3. A continuing foreign-route response stream cannot extend the deadline, and deadline expiry invalidates the active
   transport generation.
4. A malformed TCP header or UDP datagram raises `SlmpError` and invalidates the active transport generation.
5. Every complete foreign frame/datagram is included in `rx_bytes` before correlation rejection.

### Completion checklist

- [x] Approved target contract recorded in the workspace QREV decision record.
- [x] Python sync/async implementation completed for 3E/4E and TCP/UDP.
- [x] Implementation completed in every other affected SLMP repository.
- [x] Tests added for every Python acceptance criterion.
- [x] Python static checks, unit tests, documentation checks, and package/build checks passed.
- [x] Codex self-review completed against the Python diff, public API, error/state behavior, statistics, timeout, tests,
  documentation, and packaging.
- [x] Claude source review completed and findings recorded in `D:\APP\claude_review_findings_20260714.md`.
- [x] Codex dispositioned every Claude finding and reran affected checks.
- [x] Live PLC verification is not required; deterministic response headers fully expose the identity comparison.
- [x] Python documentation, migration note, changelog, and generated API checks agree with the implementation.
- [x] Python acceptance criteria and cross-library QREV comparison verified; item marked complete.

## GOAL-QREV-20260714-003 — One request deadline and one Python timeout taxonomy

- Implementation scope: `plc-comm-slmp-python`, synchronous and asynchronous clients, 3E/4E, TCP/UDP.
- Target contract: One monotonic deadline covers the complete send and response operation after the client owns its
  serialized transport. Header/body reads and every discarded foreign-route or wrong-serial response consume the same
  budget. Deadline expiry raises the public `SlmpTimeoutError` subtype of `SlmpError`. Cancellation after acquiring the
  serialized transport invalidates that transport; cancellation while waiting for ownership does not close another
  request's active transport.
- Compatibility impact: `timeout` is no longer restarted by each receive. The synchronous client now reports
  request-exchange deadline expiry as `SlmpTimeoutError` instead of a raw socket `TimeoutError`; asynchronous callers
  comparing exact exception types must accept the new subtype.

### Machine-verifiable acceptance criteria

1. Wrong-serial and foreign-route floods over TCP/UDP fail at the original deadline in both sync and async clients.
2. A delayed matching response immediately following a wrong-serial or foreign-route response succeeds inside the
   original deadline.
3. TCP header and body delays each shorter than `timeout`, but cumulatively longer than it, fail at the one request
   deadline; a cumulative duration inside the deadline succeeds.
4. Sync and async deadline expiry both raise `SlmpTimeoutError` with the same documented message family.
5. Timeout and cancellation after send invalidate the active TCP stream or UDP socket generation without resetting
   lifetime traffic counters.
6. Cancellation while waiting for the request lock leaves the current transport owner and its generation untouched.

### Completion checklist

- [x] Approved target contract recorded in the workspace QREV decision record.
- [x] Python sync/async implementation completed for TCP/UDP response operations.
- [x] Cross-language SLMP deadline behavior completed and compared in every affected repository.
- [x] Tests added for every Python acceptance criterion.
- [x] Python static checks, unit tests, documentation checks, and package/build checks passed.
- [x] Codex self-review completed against deadline arithmetic, send/receive boundaries, cancellation, state invalidation,
  error taxonomy, tests, documentation, and packaging.
- [x] Claude source review completed and findings recorded in `D:\APP\claude_review_findings_20260714.md`.
- [x] Codex dispositioned every Claude finding and reran affected checks.
- [x] Live PLC verification is not required; deterministic timing transports fully expose deadline behavior.
- [x] Python documentation, migration note, changelog, and generated API checks agree with the implementation.
- [x] Python acceptance criteria and cross-language QREV comparison verified; item marked complete.

## CLAUDE-REVIEW-20260714-PYTHON — Finding dispositions

Scope: Python findings P-1 through P-13 and family findings F-X1, F-X2, and F-X5 from the authorized Claude review.

| Finding | Disposition | Resolution or technical rationale |
| --- | --- | --- |
| F-X1 | Accepted, resolved | The canonical import default is `v2.1.0`; `-FailIfChanged` reproduces the checked-in fixtures without edits. |
| F-X2 / P-1 | Accepted, resolved | `PROFILES.md` lists `melsec:mx-r:rj71en71` with its 4E/iQ-R/MX-R relationship. |
| F-X5 | Not applicable | Claude scoped F-X5 to .NET, Rust, and C++. Python nevertheless records the profile as a Library addition rather than only as fixture tooling. |
| P-2 | Accepted, resolved | Every maintained sample selector includes the profile; direct parser and operational-choice tests prevent regression. |
| P-3 | Accepted, resolved | The two MX-R model-label entries use the surrounding dictionary indentation. |
| P-4 | Accepted, resolved | Direct catalog and connection-option tests verify the unit label, MX-R address base, range profile, frame, and compatibility mode. |
| P-5 | Accepted, resolved | Sync/async TCP/UDP flood tests assert retained `rx_bytes`, closed failed transport, and a clean matching exchange on a new transport generation. |
| P-6 | Accepted, resolved | Public `SlmpTimeoutError(SlmpError)` provides stable type-based timeout handling in both clients. |
| P-7 | Accepted, resolved | Utility and sample text now distinguishes each connection timeout from each absolute request-exchange deadline. |
| P-8 | Accepted, resolved | The changelog records route rejection, one-deadline semantics, and exact timeout-type changes under `BREAKING`. |
| P-9 | Accepted, documented | Connection establishment intentionally remains a separate timed operation. QREV-003 starts after connection and serialized transport ownership; extending the request deadline across connect would change the approved contract. |
| P-10 | Accepted, resolved | Response identity is derived fail-closed from the encoded request frame. Missing identity can no longer accept an arbitrary response, and invalid internal frames fail before transport. |
| P-11 | Accepted, resolved | Async `_receive_frame` now requires an absolute deadline; the obsolete optional per-read timeout branch was removed. |
| P-12 | Accepted, no code change | Test timing values are deterministic harness parameters, not protocol constants. Both success-before-deadline and cumulative-timeout boundaries are asserted. |
| P-13 | Rejected as a repository-local change | Vendored cross-repository vectors were deliberately removed because duplicated fixtures drift. Local exhaustive matrices remain executable evidence and family comparison stays in the workspace review. This has no runtime or release-safety impact. |

### Verification evidence

- [x] Targeted Python correlation, profile, sample-surface, error, sync, and async tests passed.
- [x] Canonical `v2.1.0` profile import completed with no fixture changes.
- [x] `run_ci.bat` passed Ruff, formatting, Mypy, public-doc coverage, and 271 unittest cases.
- [x] Full pytest passed on Python 3.14 and 3.10: 407 tests and 227 subtests on each runtime.
- [x] The 70-case response-correlation file passed five consecutive runs on each Python runtime.
- [x] `mkdocs build --strict`, sdist/wheel build, Twine checks, version sync, isolated wheel import, and
  `git diff --check` passed.
- [x] Final Codex diff review completed after the full gate rerun.
