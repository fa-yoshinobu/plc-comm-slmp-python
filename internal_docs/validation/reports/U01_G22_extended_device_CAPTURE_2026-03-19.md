# U01\G22 Extended Specification Capture

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Topic: capture-based evidence for `U01\G22`

## 2. Observed Requests

Request counts:

- `0401/0080`: 818
- `1401/0080`: 3

Representative read request:

```text
54 00 46 11 00 00 00 FF FF 03 00 13 00 10 00 01 04 80 00 00 00 16 00 00 AB 00 00 01 00 F8 01 00
```

Representative write request:

```text
54 00 8D 12 00 00 00 FF FF 03 00 15 00 10 00 01 14 80 00 00 00 16 00 00 AB 00 00 01 00 F8 01 00 04 00
```

## 3. Confirmed Read / Write / Readback Cycles

### 3.1 First write cycle

- read before write:

```text
request:  54 00 8C 12 00 00 00 FF FF 03 00 13 00 10 00 01 04 80 00 00 00 16 00 00 AB 00 00 01 00 F8 01 00
response: D4 00 8C 12 00 00 00 FF FF 03 00 04 00 00 00 03 00
```

- write:

```text
request:  54 00 8D 12 00 00 00 FF FF 03 00 15 00 10 00 01 14 80 00 00 00 16 00 00 AB 00 00 01 00 F8 01 00 04 00
response: D4 00 8D 12 00 00 00 FF FF 03 00 02 00 00 00
```

- readback:

```text
request:  54 00 8E 12 00 00 00 FF FF 03 00 13 00 10 00 01 04 80 00 00 00 16 00 00 AB 00 00 01 00 F8 01 00
response: D4 00 8E 12 00 00 00 FF FF 03 00 04 00 00 00 04 00
```

Observed value transition:

- `U01\G22`: `3 -> 4`

### 3.2 Additional write cycles

- second cycle: `4 -> 5`
- third cycle: `5 -> 9`

## 4. Layout Interpretation

Extracted Extended Specification payload from the read request:

```text
00 00 16 00 00 AB 00 00 01 00 F8
```

Interpreted field order:

```text
[extension_specification_modification:1]
[device_modification_index:1]
[device_spec:4]
[device_modification_flags:1]
[reserved_zero:1]
[extension_specification:2]
[direct_memory_specification:1]
```

Observed values:

- device spec (`G22`, Q/L format): `16 00 00 AB`
- extension specification: `0x0001`
- direct memory specification: `0xF8`

## 5. Practical Conclusion

- `U01\G22` is operational in this capture.
- The operational command/subcommand pair is `0401/0080` for read and `1401/0080` for write.
- The payload layout is not the old generic Extended Specification field order.
- It uses the same capture-aligned `G/HG` ordering pattern already observed for `U3E0\G10` and `U3E0\HG20`, but with the Q/L device-spec width and `0x0080` subcommand family.

## 6. Repository Impact

- The repository should not treat the capture-aligned `G/HG` payload as an iQ-R-only exception.
- The layout rule now has capture evidence for:
  - iQ-R `0401/1401 + 0082 + FA`
  - Q/L-style `0401/1401 + 0080 + F8`
- Broader hardware validation is still required for additional unit numbers and `HG`.

