# Mixed Block Write 0x1406 Root Cause: Payload Layout Bug (RESOLVED)

- Date: 2026-06-12
- Host: 192.168.250.100:1025 (TCP)
- Model: R08CPU (live, `read_type_name`)
- Series: iqr, subcommand `0x0002`
- Probe script: `scripts/slmp_mixed_block_layout_probe.py`
- Status: canonical repository record for the resolved mixed `0x1406` layout
  issue

## Root Cause

`build_write_block_request` (`slmp/_operations.py`) assembles the `0x1406`
payload as:

```
[n_word][n_bit][word specs...][bit specs...][all word data][all bit data]
```

The SLMP reference manual section for Write Block (local English PDF pages
76-78) requires each block's write data to follow that block's own spec
inline:

```
[n_word][n_bit][word spec + data]...[bit spec + data]...
```

The two layouts coincide only when the request contains exactly one block,
which is why word-only and bit-only single-block writes always succeeded
while mixed word+bit (and multi-block) writes failed. The PLC parses the
first block spec, consumes the following bytes as that block's data, then
misparses the remainder — yielding target-dependent end codes:

- `0xC05B` on R08CPU mixed word+bit (misparsed device spec not accessible)
- `0xC051` on R08CPU two word blocks (misparsed point count out of range)
- `0xC061` on FX5UC-32MT/D mixed (length/count mismatch, report 2026-03-19)

These are all the same client bug, not target capability variation.

Local manual references used during the investigation:

- English: `D:\_github_plc\sh080956engn.pdf`
  - PDF page 33: command list and subcommand overview
  - PDF pages 76-78: `Write Block (command: 1406)` request, subcommand,
    response, and communication example
- Japanese: `D:\_github_plc\sh080931r.pdf`
  - PDF page 32: command list and subcommand overview
  - PDF pages 75-77: `Write Block(コマンド: 1406)` request, subcommand,
    response, and communication example

## Live Evidence (R08CPU, 2026-06-12)

| Scenario | Layout | End code | Readback |
|---|---|---|---|
| mixed 1 word + 1 bit block | current library | `0xC05B` | unchanged |
| mixed 1 word + 1 bit block | manual-conformant | `0x0000` | MATCH |
| 2 word blocks | current library | `0xC051` | unchanged |
| 2 word blocks | manual-conformant | `0x0000` | MATCH |

Successful manual-layout mixed frame payload (subcommand `0x0002`):

```
01 01 2C 01 00 00 A8 00 02 00 33 33 44 44 C8 00 00 00 90 00 01 00 0F 0F
   |  D300 spec        x2    word data   M200 spec          x1    bit data
```

All test devices (D300, D310, M200) were restored to their original values
after the probe (restore OK).

## Fix Applied (2026-06-12)

All three clients now emit each block's data inline after its own spec:

- Python `slmp/_operations.py` `build_write_block_request` — 224 unit tests
  pass, plus new layout regression tests in `tests/test_slmp.py`.
- Rust `src/client.rs` `write_block_once` — all `cargo test` pass, plus a
  full-payload assertion added to
  `tests/route_guards.rs::mixed_block_write_does_not_retry_c05b_as_split_requests`.
- .NET `src/PlcComm.Slmp/SlmpClient.cs` `WriteBlockAsync` — 169 unit tests
  pass, plus a full-payload assertion in `SlmpClientGuardTests`.

Live re-verification on R08CPU (192.168.250.100:1025, TCP, iqr/0x0002):

- Python `scripts/slmp_mixed_block_compare.py` (no fallback options): mixed
  write now `0x0000` in one request, readback MATCH, restore OK
  (`internal_docs/iqr_r08cpu/mixed_block_compare_latest.md`).
- Rust `slmp_verify_client block-write` mixed D300+M200: success, readback
  `[0x1234, 0x5678]` / `[0x00FF]`, restored to original values.
- .NET `PlcComm.Slmp.Cli block-check --write-check` mixed D300+M200: success,
  readback `[0x1000, 0x1001]` / `[0x0001]`, restored to original values.

## QnUDV Re-Validation (2026-06-12, same day, target swapped)

Bench PLC swapped to a QnUDV target (built-in Ethernet, 3E frame, `ql`
series, subcommand `0x0000`). Results:

- `0x0101` Read Type Name: `0xC059` (not supported on this path)
- `0x0401`/`0x1401` word read/write D300: OK, readback MATCH, restored
- `0x0406` Read Block (single word block): `0xC059`
- `0x1406` Write Block word-only: `0xC059`
- `0x1406` mixed, manual-conformant layout: `0xC059`
- `0x1406` mixed, old (buggy) layout: `0xC059`

Conclusion: on the QnUDV built-in Ethernet path the block commands are not
supported at all (`0xC059` = command/subcommand error) regardless of payload
layout. The earlier QnUDV `0xC059` classification as target command support
was correct and is unrelated to the layout bug. Applications targeting this
path must use `0x0401`/`0x1401`/`0x0403`/`0x1402` instead of block commands.
Check command: `qnudv_1406_check` probe (basic ops + raw both-layout block
frames; D300/M200 restored after the run).

## LJ71E71-100 / L02SCPU Re-Validation (2026-06-12, target swapped again)

Bench swapped to L02SCPU accessed through an LJ71E71-100 Ethernet module
(4E frame, `ql` series, subcommand `0x0000`). This is an "Ethernet-equipped
module" path — the wording used by the `0xC05B` end-code text.

Raw layout probe:

| Scenario | Layout | End code | Readback |
|---|---|---|---|
| mixed 1 word + 1 bit block | old (buggy) | `0xC056` | unchanged |
| mixed 1 word + 1 bit block | manual-conformant | `0x0000` | MATCH |
| 2 word blocks | old (buggy) | `0xC056` | unchanged |
| 2 word blocks | manual-conformant | `0x0000` | MATCH |

Fixed clients, all against the same target:

- Python `scripts/slmp_mixed_block_compare.py`: all scenarios OK, mixed write
  one request `0x0000`, restore OK
  (`internal_docs/ql_l02scpu/mixed_block_compare_latest.md`)
- Rust `slmp_verify_client block-write` mixed: success, readback
  `[0x1234, 0x5678]` / `[0x00FF]`
- .NET `PlcComm.Slmp.Cli block-check --write-check` mixed: success, readback
  `[0x1000, 0x1001]` / `[0x0001]`
- All devices restored to original values afterwards.

Note: the historical `0xC056` record for L16HCPU mixed writes (maintainer
communication test record) is a DIFFERENT target — L16HCPU is iQ-L series
(built-in Ethernet, iqr-style `0x0002` encoding), not the classic MELSEC-L
+ LJ71E71-100 path tested here. Since the old layout was used there too,
that `0xC056` is plausibly the same layout bug, but it remains unverified
until the iQ-L hardware is reconnected; do not treat it as covered by this
section.

End-code-specific behavior so far for the same wrong frame: `0xC05B`
(R08CPU built-in), `0xC061` (FX5UC), `0xC056` (LJ71E71-100/L02SCPU,
verified; L16HCPU/iQ-L historical, unverified), while `0xC059` is unrelated
(QnUDV: block commands unsupported).

## QJ71E71-100 / Q06UDVCPU Re-Validation (2026-06-12, target swapped again)

Bench swapped to a QJ71E71-100 Ethernet module in front of a Q06UDVCPU
(4E frame, `ql` series, subcommand `0x0000`). This is the same QnUDV-class
CPU family that rejected all block commands with `0xC059` on the built-in
Ethernet path earlier the same day — via the E71 module the block commands
are supported, so the two paths must not be conflated.

- `0x0101` Read Type Name: OK (`Q06UDVCPU`) — also works via module, unlike
  the built-in path.

Raw layout probe:

| Scenario | Layout | End code | Readback |
|---|---|---|---|
| mixed 1 word + 1 bit block | old (buggy) | `0xC056` | unchanged |
| mixed 1 word + 1 bit block | manual-conformant | `0x0000` | MATCH |
| 2 word blocks | old (buggy) | `0xC056` | unchanged |
| 2 word blocks | manual-conformant | `0x0000` | MATCH |

Fixed clients, all against the same target:

- Python `scripts/slmp_mixed_block_compare.py`: all scenarios OK, mixed write
  one request `0x0000`, restore OK
  (`internal_docs/ql_q06udvcpu/mixed_block_compare_latest.md`)
- Rust `slmp_verify_client block-write` mixed: success, readback
  `[0x1234, 0x5678]` / `[0x00FF]`
- .NET `PlcComm.Slmp.Cli block-check --write-check` mixed: success, readback
  `[0x1000, 0x1001]` / `[0x0001]`
- All devices restored to original values afterwards.

The `0xC056` rejection of the old layout matches the QJ71E71-100/L02SCPU
result: E71-family modules consistently answer the misparsed frame with
`0xC056`, while CPU built-in ports answered `0xC05B` (R08CPU) or `0xC061`
(FX5UC). QnUDV path summary:

- built-in Ethernet: block commands unsupported (`0xC059`) — use
  `0x0401`/`0x1401`/`0x0403`/`0x1402`
- via QJ71E71-100: block commands fully working with the fixed layout

## L16HCPU (iQ-L) Re-Validation (2026-06-12, target swapped again)

Bench swapped to L16HCPU — iQ-L series, built-in Ethernet, 4E frame,
`iqr`-style encoding, subcommand `0x0002`. This closes the last historical
target: the Rust notes' iQ-L stress `0xC05B` two-word-block rejection and
the maintainer record's `0xC056` mixed rejection.

Raw layout probe:

| Scenario | Layout | End code | Readback |
|---|---|---|---|
| mixed 1 word + 1 bit block | old (buggy) | `0xC05B` | unchanged |
| mixed 1 word + 1 bit block | manual-conformant | `0x0000` | MATCH |
| 2 word blocks | old (buggy) | `0xC051` | unchanged |
| 2 word blocks | manual-conformant | `0x0000` | MATCH |

Fixed clients, all against the same target:

- Python `scripts/slmp_mixed_block_compare.py`: all scenarios OK, mixed write
  one request `0x0000`, restore OK
  (`internal_docs/iqr_l16hcpu/mixed_block_compare_latest.md`)
- Rust `slmp_verify_client block-write` mixed: success, readback
  `[0x1234, 0x5678]` / `[0x00FF]`
- .NET `PlcComm.Slmp.Cli block-check --write-check` mixed: success, readback
  `[0x1000, 0x1001]` / `[0x0001]`
- All devices restored to original values afterwards.

Notes:

- Today's old-layout mixed write returned `0xC05B`, not the `0xC056` in the
  historical maintainer record. The historical code was not reproduced under
  today's conditions; either way both are now explained as reactions to the
  same misparsed frame, and the fixed layout succeeds.
- iQ-L built-in behavior matches R08CPU built-in (`0xC05B` for misparsed
  mixed, `0xC051` for misparsed multi-block), reinforcing the pattern that
  the end code depends on the receiving port/module family.

## FX5UC-32MT/D Re-Validation (2026-06-12, target swapped again)

Bench swapped back to FX5UC-32MT/D. Per the manual the FX5 SLMP path
supports the 3E frame only, so all checks used 3E (`ql` series, subcommand
`0x0000`). Note: the 2026-03-19 report frames were 4E and did get responses,
but 3E is the documented path and is what this re-validation used.

Raw layout probe:

| Scenario | Layout | End code | Readback |
|---|---|---|---|
| mixed 1 word + 1 bit block | old (buggy) | `0xC061` | unchanged |
| mixed 1 word + 1 bit block | manual-conformant | `0x0000` | MATCH |
| 2 word blocks | old (buggy) | `0xC061` | unchanged |
| 2 word blocks | manual-conformant | `0x0000` | MATCH |

This reproduces the historical `0xC061` (2026-03-19) and confirms it was the
layout bug on this target too.

Fixed clients, all against the same target (3E frame):

- Python `scripts/slmp_mixed_block_compare.py --frame-type 3e`: all
  scenarios OK, mixed write one request `0x0000`, restore OK
  (`internal_docs/ql_fx5uc_32mt_d/mixed_block_compare_latest.md`)
- Rust `slmp_verify_client block-write` mixed: success, readback
  `[0x1234, 0x5678]` / `[0x00FF]`
- .NET `PlcComm.Slmp.Cli block-check --write-check` mixed: success, readback
  `[0x1000, 0x1001]` / `[0x0001]`
- All devices restored to original values (D300 was `[0x0000, 0x0001]`
  before the run and was restored exactly).

Tooling note: `--frame-type 3e|4e` was added to
`scripts/slmp_mixed_block_compare.py` (default `4e`, unchanged behavior) and
to `scripts/slmp_mixed_block_layout_probe.py`.

## Remaining Follow-Ups

- Automatic mixed-write split retry has been removed. If a PLC rejects one
  mixed `0x1406` write, the library returns the original PLC end code.
  Callers that intentionally want two requests must choose
  `split_mixed_blocks=True`.
- Prior live conclusions attributing mixed/multi-block rejection to target
  command support should be re-validated with the corrected layout.
  - QnUDV: done 2026-06-12 (see above) — genuine command non-support.
  - L16HCPU (iQ-L): done 2026-06-12 (see above) — layout bug confirmed and
    fixed clients verified live. No open targets remain.
