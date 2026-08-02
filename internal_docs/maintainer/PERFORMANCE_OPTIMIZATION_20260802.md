# Python SLMP performance optimization acceptance record

This record applies the approved workspace contracts PERF2-002, PERF2-004,
and PERF2-008 to the Python implementation. These are internal optimizations;
wire bytes, public results, validation/error order, FIFO behavior, lifecycle,
timeouts, cancellation, serial handling, tracing, and error ownership remain
unchanged.

## PERF2-002 — Prepared named polling

- Scope: sync/async named-read planning, `poll`, and Random Read execution.
- Target contract: validate and encode one client/profile/frame/compatibility-bound immutable Random Read payload and compact decode-index plan once per polling iterator, then reuse both for every cycle.
- Compatibility impact: none; public overrides and mock/subclass behavior retain their documented fallback path.
- Acceptance criteria: two cycles perform one preparation, reuse identical payload bytes, decode from compact indexed lists without per-cycle address maps, and retain the normal exclusive client turn.
- [x] Implementation completed in this repository.
- [x] Tests added for every acceptance criterion available without a live PLC.
- [x] Ruff, mypy, and targeted tests passed.
- [x] Codex self-review completed against the approved contract.
- [x] Live PLC checks are not required because wire bytes and transport behavior are unchanged and covered by deterministic tests.
- [x] User/API documentation and changelog agree with the implementation.
- [x] Final acceptance criteria verified.

## PERF2-004 — Response-frame view decoding

- Scope: private sync/async response parsing and typed command decoders.
- Target contract: typed decoders consume a private `memoryview` into the owned response frame; the view cannot escape. Public raw, trace, error, and byte-result surfaces retain owned `bytes`.
- Compatibility impact: none.
- Acceptance criteria: typed operations avoid a response-payload `bytes` copy, raw access materializes owned bytes, and final byte-returning results and failures cannot expose a borrowed view.
- [x] Implementation completed in this repository.
- [x] Tests added for typed/raw and final byte-result ownership.
- [x] Ruff, mypy, and targeted tests passed.
- [x] Codex self-review completed against the approved contract.
- [x] Live PLC checks are not required for private ownership behavior.
- [x] User/API documentation and changelog agree with the implementation.
- [x] Final acceptance criteria verified.

## PERF2-008 — Exact-size Extended payload encoding

- Scope: Extended Random read/write and Extended Monitor registration.
- Target contract: first resolve and validate every entry while calculating the checked exact size, then allocate one final payload and encode directly into it; the second pass performs no validation and creates no per-device encoded byte buffer. Because Python `bytes` cannot be filled in place, the uniquely owned final `bytearray` is frozen as a zero-copy read-only `memoryview` used only by the private operation/transport path. No mutable reference or borrowed payload is exposed through public or trace surfaces.
- Compatibility impact: none; accepted bytes and validation/error order remain unchanged.
- Acceptance criteria: golden bytes remain identical, each valid builder records one exact final `bytearray`, returns a read-only private view, records zero owned device-spec encodes, and invalid input fails before final allocation.
- [x] Implementation completed in this repository.
- [x] Tests added for all four builders, validation boundary, and byte equality.
- [x] Ruff, mypy, and targeted tests passed.
- [x] Codex self-review completed against the approved contract.
- [x] Live PLC checks are not required because protocol bytes are unchanged.
- [x] User/API documentation and changelog agree with the implementation.
- [x] Final acceptance criteria verified.
