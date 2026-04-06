# Python Comparison Checklist

Use this note when you want to compare the original Python implementation with the current C++ library on the same PLC and the same block-access scenarios.

The Python project referenced by this repository is:

- `slmp-connect-python`: <https://github.com/fa-yoshinobu/plc-comm-slmp-python>

## Purpose

The current C++ library already has:

- mixed block support in the codec and request builder (`src/slmp_minimal.cpp`)
- mock-PLC integration coverage that accepts mixed `writeBlock()` (`tests/slmp_socket_integration.cpp`)
- a real-board Atom Matrix result against Mitsubishi iQ-R `R08CPU` showing that mixed `writeBlock` was rejected on the real PLC (`HARDWARE_VALIDATION.md`)

What was still unknown before the 2026-03-14 live Python check was whether the original Python implementation:

- sends the same `1406/0002` mixed block frame
- passes on the same PLC
- fails with the same end code
- or uses a different fallback or packing rule

The 2026-03-14 live result now shows:

- Python sends the same one-request mixed `1406/0002` frame shape for `D300 x2` + `M200 x1 packed`
- the first mixed write fails on the same PLC with the same `0xC05B`
- word-only and bit-only block writes both pass
- `retry_mixed_on_error=True` recovers by retrying as separate word-only and bit-only block writes

## Current C++ Baseline

Recorded board:

- `m5stack-atom`
- sketch: `examples/atom_matrix_serial_console`
- PLC: Mitsubishi iQ-R `R08CPU`
- date: `2026-03-14`

Current result summary:

| Scenario | C++ result | Notes |
|---|---|---|
| `readBlock/writeBlock words` | pass | `word-only` block write succeeded |
| `readBlock/writeBlock bits` | pass | `bit-only` block write succeeded |
| `readBlock/writeBlock mixed` | fail | PLC returned `0xC05B` during mixed `writeBlock` |

Mixed write case used:

- word block device: `D300`, `2 points`
- bit block device: `M200`, `1 packed word`
- effective bit range: `M200..M215`

Sample failing C++ mixed request captured from the real PLC run:

```text
last request: 54 00 99 00 00 00 00 FF FF 03 00 1E 00 10 00 06 14 02 00 01 01 2C 01 00 00 A8 00 02 00 C8 00 00 00 90 00 01 00 F7 87 BE 80 FE 6D
last response: D4 00 99 00 00 00 00 FF FF 03 00 0B 00 5B C0 00 FF FF 03 00 06 14 02 00
```

Interpreted meaning:

- command: `1406`
- subcommand: `0002`
- word blocks: `1`
- bit blocks: `1`
- word block: `D300`, `2 points`
- bit block: `M200`, `1 packed word`

## Comparison Conditions

Keep the Python-side check as close as possible to the C++ run:

- same PLC: Mitsubishi iQ-R `R08CPU`
- same network path and target settings
- same device addresses
- same point counts
- same packed-bit interpretation for block bit writes
- capture both request hex and response hex

Important first-pass rule:

- keep `split_mixed_blocks=False`
- keep `retry_mixed_on_error=False`
- the first comparison run should capture the original one-request mixed frame and the first PLC response before any fallback behavior is enabled

Recommended device set:

- word-only block write: `D300`, `2 points`
- bit-only block write: `M200`, `1 packed word`
- mixed block write: `D300`, `2 points` plus `M200`, `1 packed word`

Convenience script for the default comparison case:

```powershell
python scripts/slmp_mixed_block_compare.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr
```

## What To Record From Python

For each case below, record:

- function or API name used in Python
- exact device list and values
- whether the write succeeded
- request hex
- response hex
- end code if failed
- whether actual PLC memory changed

Current live reference report:

- `internal_docsrc/iqr_r08cpu/mixed_block_compare_latest.md`

## Worksheet

Fill this table after running the Python version.

| Scenario | Devices | Expected comparison target | Python result | End code | Notes |
|---|---|---|---|---|---|
| `readBlock words+bits` | `D300 x2`, `M200 x1 packed` | C++ pass | `same_as_cpp_pass` | `0x0000` | request succeeded; returned `D300=[0x0000, 0x0000]`, `M200=[0x0000]` |
| `writeBlock words only` | `D300 x2` | C++ pass | `same_as_cpp_pass` | `0x0000` | write/readback/restore all `OK` |
| `writeBlock bits only` | `M200 x1 packed` | C++ pass | `same_as_cpp_pass` | `0x0000` | write/readback/restore all `OK` |
| `writeBlock mixed` | `D300 x2` + `M200 x1 packed` | C++ fail with `0xC05B` | `same_as_cpp_fail_same_end_code` | `0xC05B` | first one-request mixed write failed; PLC memory remained unchanged |

## Fallback Verification

The practical workaround was also checked live after the first-pass capture.

| Scenario | API/options | Python result | End code(s) | Notes |
|---|---|---|---|---|
| `writeBlock mixed fallback` | `write_block(..., retry_mixed_on_error=True)` | `different_runtime_behavior` | `0xC05B -> 0x0000 -> 0x0000` | first mixed write failed, then automatic split retry succeeded and restore was `OK` |

## Hidden-Condition Triage

If the Python-side mixed write also fails, narrow the cause with the smallest safe deltas first:

1. compare `0406` mixed `readBlock` against `1406` mixed `writeBlock` on the same `D300` + `M200` pair
2. compare `TCP 1025` and `UDP 1027`
3. compare PLC `RUN` and `STOP` if the write target is safe to test in both states
4. compare alternate base devices such as `D100/M100`, `D1000/M1000`, and the original `D300/M200`
5. compare alternate mixed pairs such as `D+B`, `W+M`, or `R+M` if those devices are writable on the target
6. vary point counts (`word x1/x2`, `bit packed x1/x2`) to see whether rejection depends on the mixed shape rather than on the device family alone
7. if another SLMP endpoint is available on the same PLC family, compare built-in Ethernet versus the external module path
8. if a later run enables fallback, capture the first failed request/response before retry by using a `trace_hook`

## Suggested Python Test Notes

If the Python project already has a block-write helper, prefer running exactly these three write cases:

1. `word-only`
2. `bit-only`
3. `mixed`

If `mixed` fails, capture:

- whether Python used the same combined request shape
- whether the end code was also `0xC05B`
- whether Python retried by splitting the request
- whether the first failed mixed request left PLC memory unchanged before any retry

Current live answer:

- yes, Python used the same combined request shape
- yes, the first mixed write also returned `0xC05B`
- with `retry_mixed_on_error=False`, no retry happened
- with `retry_mixed_on_error=True`, Python retried by splitting and then succeeded
- on the first-pass run, the failed mixed request left PLC memory unchanged

If `mixed` passes, capture:

- the full request hex
- any difference in subcommand, payload order, or packed-bit layout compared with the C++ request above

## Expected Outcome Categories

Use one of these when summarizing the Python result:

- `same_as_cpp_pass`
- `same_as_cpp_fail_same_end_code`
- `same_as_cpp_fail_different_end_code`
- `different_request_shape`
- `different_runtime_behavior`

## After Comparison

When the Python result is known, update:

- this file
- `internal_docsrc/communication_test_record.md`
- `internal_docsrc/manual_implementation_differences.md`
- `internal_docsrc/error_code_reference.md`
- any issue opened from the hardware-validation template

