# G Extended Specification Capture Analysis

- Date: 2026-03-19
- Scope: capture-based evidence for `U3E0\G10`
- Companion report: `HG_extended_device_CAPTURE_2026-03-19.md`

## 1. Observed Traffic

- Transport: TCP
- Client: `192.168.250.100:5031`
- PLC: `192.168.250.100:1025`
- Total packets: `1049`
- SLMP request types observed:
  - `0401/0082` read: `524` requests
  - `1401/0082` write: `1` request

## 2. Key Successful Sequence

Read before write:

```text
Request : 54003411000000FFFF0300150010000104820000000A000000AB000000E003FA0100
Response: D4003411000000FFFF0300040000000A00
```

- Observed readback value before the write: `0x000A` (`10`)

Write:

```text
Request : 54003511000000FFFF0300170010000114820000000A000000AB000000E003FA01001E00
Response: D4003511000000FFFF030002000000
```

- Command: `1401`
- Subcommand: `0082`
- End code: `0x0000`
- Written value: `0x001E` (`30`)

Read after write:

```text
Request : 54003611000000FFFF0300150010000104820000000A000000AB000000E003FA0100
Response: D4003611000000FFFF0300040000001E00
```

- Observed readback value after the write: `0x001E` (`30`)

## 3. Practical Conclusion

- This capture is direct evidence that one Extended Specification path for `G` is operational in at least one real environment.
- Specifically, `U3E0\G10` was read successfully, written successfully, and read back successfully.
- Therefore, repository-wide wording such as "Extended Specification `G/HG` is rejected" is too strong when applied without qualification.

## 4. Current Repository Gap

- The original generic Extended Specification builder did not reproduce this successful frame shape.
- The repository now contains an iQ-R `G/HG` special case that reproduces this captured payload layout in unit tests.
- A live R120PCPU smoke check also passed for single-word `G10` read-write-readback with restore.
- As a result, the remaining open item is coverage expansion beyond this exact target/address combination.
- `HG` is covered separately by `HG_extended_device_CAPTURE_2026-03-19.md`.

## 5. Next Work Item

- Extend verification beyond the current single-word R120PCPU `G10` smoke case: more addresses, multi-point reads/writes, and alternate transports.


