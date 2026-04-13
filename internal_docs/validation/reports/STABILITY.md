# Stability and Verification Report (2026-03-18)

## 1. Executive Summary
This document records the verification and bug-fixing process performed to improve stability. It summarizes protocol and compatibility findings that informed the current implementation.

## 2. Critical Bug Fixes
### 2.1. Bit Packing Order (The SM400/401 Issue)
- **Problem**: Previous implementation mapped the 1st bit to the lower nibble and the 2nd to the upper nibble.
- **Root Cause**: Misinterpretation of SLMP binary mapping vs. ASCII mapping.
- **Fix**: Swapped nibble order in `pack_bit_values` and `unpack_bit_values`.
  - **1st Point**: Upper 4 bits (Bit 4-7)
  - **2nd Point**: Lower 4 bits (Bit 0-3)
- **Verification**: Verified with `SM400` (Always ON) and `SM401` (Always OFF). Simultaneous read returns `[True, False]` correctly in both Sync and Async clients.

### 2.2. ZR Device Numbering
- **Problem**: `ZR` was treated as hexadecimal (radix 16).
- **Fix**: Changed to decimal (radix 10) to match live iQ-R PLC behavior where `ZR163839` is followed by `ZR163840`.
- **Verification**: Boundary tests confirmed that `ZR163840` start is rejected with `0x4031` while `ZR163839` is accepted.

### 2.3. Robustness and Validation
- **Node Search**: Added bounds-checking to `decode_node_search_response` to prevent `IndexError` on truncated UDP packets.
- **File Commands**: Added 6-32 character password validation for iQ-R file subcommands (`0x0040`).

## 3. Verification Matrix
| Test Case | Frames | Sync/Async | Result | Note |
|---|---|---|---|---|
| Basic R/W | 4E | Sync | **PASS** | D, M, X, Y, W, ZR, R |
| Bit Order | 4E | Sync | **PASS** | SM400/401 match |
| Basic R/W | 3E | Sync | **PASS** | Subheader `50 00` |
| Mixed Frames | 3E Write -> 4E Read | Sync | **PASS** | Cross-frame integrity |
| Mixed Frames | 4E Write -> 3E Read | Sync | **PASS** | Cross-frame integrity |
| Cross-Client | Sync Write -> Async Read| Mixed | **PASS** | Implementation parity |
| Concurrency | 4E | Async | **PASS** | 20 parallel tasks |

## 4. Current Permanent Tests
The current permanent repository tests focus on local and repeatable checks:
- `tests/test_async_client.py`: async client protocol behavior and timeout coverage.
- `tests/test_bugs_and_edges.py`: focused regressions and edge cases.
- `tests/test_device_vectors.py`: device encoding and vector coverage.
- `tests/test_slmp.py`: synchronous protocol behavior and command coverage.
- `tests/test_utils.py`: helper-layer batching, typing, and address normalization.

Historical simulator-oriented validation notes were removed from the permanent test suite.
