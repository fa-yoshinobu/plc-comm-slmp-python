# HG Extended Specification Capture Analysis

- Date: 2026-03-19
- Scope: capture-based evidence for `U3E0\HG20`

## 1. Observed Traffic

- Transport: TCP
- Client: `192.168.250.100:5031`
- PLC: `192.168.250.100:1025`
- Total packets: `1098`
- SLMP request types observed:
  - `0401/0082` read: `548` requests
  - `1401/0082` write: `1` request

## 2. Key Successful Sequence

Read before write:

```text
Request : 5400A204000000FFFF030015001000010482000000140000002E000000E003FA0100
Response: D400A204000000FFFF0300040000000A00
```

- Observed readback value before the write: `0x000A` (`10`)

Write:

```text
Request : 5400A304000000FFFF030017001000011482000000140000002E000000E003FA01003200
Response: D400A304000000FFFF030002000000
```

- Command: `1401`
- Subcommand: `0082`
- End code: `0x0000`
- Written value: `0x0032` (`50`)

Read after write:

```text
Request : 5400A404000000FFFF030015001000010482000000140000002E000000E003FA0100
Response: D400A404000000FFFF0300040000003200
```

- Observed readback value after the write: `0x0032` (`50`)

## 3. Practical Conclusion

- This capture is direct evidence that one Extended Specification path for `HG` is operational in at least one real environment.
- Specifically, `U3E0\HG20` was read successfully, written successfully, and read back successfully.
- Together with the `U3E0\G10` capture, this proves that blanket wording such as "Extended Specification `G/HG` is rejected" is too strong.

## 4. Current Repository Gap

- The original generic Extended Specification builder did not reproduce this successful frame shape.
- The repository now contains an iQ-R `G/HG` special case that reproduces this captured payload layout in unit tests.
- A live R120PCPU smoke check also passed for single-word `HG20` read-write-readback with restore.
- As a result, the remaining open item is coverage expansion beyond this exact target/address combination.

## 5. Next Work Item

- Extend verification beyond the current single-word R120PCPU `HG20` smoke case: more addresses, multi-point reads/writes, and alternate transports.

