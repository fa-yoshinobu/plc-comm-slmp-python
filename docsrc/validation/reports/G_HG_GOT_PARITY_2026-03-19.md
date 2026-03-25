# G/HG GOT Parity Check

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Goal: determine whether the current repository emits the same Extended Specification `G/HG` request payloads as the GOT-side traffic

## 2. Captured Traffic Summary

Observed command family:

- `0401/0082`: 1402 requests
- `1401/0082`: 8 requests

Observed write targets in the capture:

- `U03E0\G0`
- `U03E1\G0`
- `U03E2\G0`
- `U03E3\G0`
- `U03E1\HG0`
- `U03E2\HG0`
- `U03E3\HG0`
- `U03E0\HG11`

Observed write result pattern:

- `U03E0\G0`: success
- `U03E1\G0`, `U03E2\G0`, `U03E3\G0`: `end_code=0x414A`
- `U03E1\HG0`, `U03E2\HG0`, `U03E3\HG0`: write response `0x0000`, but later reads stayed `0`
- `U03E0\HG11`: success

## 3. Payload Parity Check

The current repository generated the same request-data payloads for the captured targets when using:

- series: `iqr`
- direct memory specification: `0xFA`
- point count: `1`
- write value: `0x0003`

Representative equality cases:

- `U03E0\G0` read payload:

```text
00 00 00 00 00 00 AB 00 00 00 E0 03 FA 01 00
```

- `U03E1\G0` write payload:

```text
00 00 00 00 00 00 AB 00 00 00 E1 03 FA 01 00 03 00
```

- `U03E1\HG0` write payload:

```text
00 00 00 00 00 00 2E 00 00 00 E1 03 FA 01 00 03 00
```

- `U03E0\HG11` write payload:

```text
00 00 0B 00 00 00 2E 00 00 00 E0 03 FA 01 00 03 00
```

The repository-side comparison against the captured request payloads returned `True` for the matched request set.

## 4. Practical Conclusion

- The current repository request layout matches the GOT capture for the checked `U03E0..U03E3` `G/HG` traffic.
- The observed `U03E1..U03E3` write problems are therefore not explained by a builder byte-order mismatch between GOT and this repository.
- The remaining difference is more likely target-side behavior such as:
  - address validity
  - write permission
  - CPU-memory state difference
  - environment-specific semantics for those CPU-memory qualifiers

## 5. Relationship to Live Recheck

- `docsrc/validation/reports/G_HG_MULTI_CPU_HARDWARE_RECHECK_2026-03-19.md` recorded the repository-driven live result for `U3E0..U3E3`.
- This report adds the wire-level parity conclusion: the repository is issuing the same Extended Specification request-data layout as the GOT capture for the checked devices.


