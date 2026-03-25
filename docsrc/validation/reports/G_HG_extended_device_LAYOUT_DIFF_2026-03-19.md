# G/HG Extended Specification Layout Difference

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Topic: byte-level difference between the original generic Extended Specification builder and the captured working `G/HG` layout
- Captures:
  - `U3E0\G10`
  - `U3E0\HG20`
  - `U01\G22`

## 2. Why the Manual Was Not Enough

- The manual explained the semantic fields of Extended Specification, but it did not uniquely determine the exact byte order that this PLC accepted for `G/HG`.
- `G/HG` are not plain standalone devices. They are unit-qualified or CPU-buffer-related paths, so the accepted request shape depends on more than the device code itself.
- The PLC only reported rejection codes such as `0xC061`, which showed that the request was not accepted but did not identify which field ordering or reserved byte was wrong.
- The captured working frames showed that `G/HG` are a special case relative to the generic builder.

## 3. Generic Builder vs Captured Working Layout

Reference conditions:

- extension specification: `0x03E0`
- extension specification modification: `0x00`
- device modification index: `0x00`
- device modification flags: `0x00`
- direct memory specification: `0xFA`
- on the user's current multi-CPU environment, `U3E0`, `U3E1`, `U3E2`, and `U3E3` correspond to CPU No.1..No.4 memory for `G/HG`
- lower `U**` values in the same workspace context are ordinary I/O unit addresses unless the PLC environment explicitly defines the CPU-memory mapping for `G/HG`

### 3.1 `U3E0\G10`

Original generic builder payload:

```text
E0 03 00 00 00 0A 00 00 00 AB 00 FA
```

Captured working payload:

```text
00 00 0A 00 00 00 AB 00 00 00 E0 03 FA
```

Current iQ-R special-case builder payload:

```text
00 00 0A 00 00 00 AB 00 00 00 E0 03 FA
```

### 3.2 `U3E0\HG20`

Original generic builder payload:

```text
E0 03 00 00 00 14 00 00 00 2E 00 FA
```

Captured working payload:

```text
00 00 14 00 00 00 2E 00 00 00 E0 03 FA
```

Current iQ-R special-case builder payload:

```text
00 00 14 00 00 00 2E 00 00 00 E0 03 FA
```

### 3.3 `U01\G22`

Original generic builder payload:

```text
01 00 00 00 00 16 00 00 AB F8
```

Captured working payload:

```text
00 00 16 00 00 AB 00 00 01 00 F8
```

Current repository payload:

```text
00 00 16 00 00 AB 00 00 01 00 F8
```

### 3.4 Full 4E Request Example (`U3E0\G10` Read)

Generic full request frame if the original builder order were used:

```text
54 00 34 11 00 00 00 FF FF 03 00 14 00 10 00 01 04 82 00 E0 03 00 00 00 0A 00 00 00 AB 00 FA 01 00
```

Captured working full request frame:

```text
54 00 34 11 00 00 00 FF FF 03 00 15 00 10 00 01 04 82 00 00 00 0A 00 00 00 AB 00 00 00 E0 03 FA 01 00
```

Current live repository request frame on the revalidated R120PCPU target:

```text
54 00 01 00 00 00 00 FF FF 03 00 15 00 10 00 01 04 82 00 00 00 0A 00 00 00 AB 00 00 00 E0 03 FA 01 00
```

Observed full-frame consequence:

- The outer 4E framing is normal in all three cases.
- The decisive difference is inside the request data payload after `0401/0082`.
- `request_data_length` changes from `0x0014` to `0x0015` because the working `G/HG` layout includes one additional zero byte.
- The current repository frame now matches the captured working request layout apart from ordinary runtime fields such as serial number.

## 4. Byte-Level Interpretation

The original generic builder arranged bytes as:

```text
[extension_specification:2]
[extension_specification_modification:1]
[device_modification_index:1]
[device_modification_flags:1]
[device_spec:6]
[direct_memory_specification:1]
```

The captured working `G/HG` layout arranged bytes as:

```text
[extension_specification_modification:1]
[device_modification_index:1]
[device_spec:6]
[device_modification_flags:1]
[reserved_zero:1]
[extension_specification:2]
[direct_memory_specification:1]
```

Observed consequence:

- `extension_specification` moved from the head of the payload to the tail.
- `device_spec` moved forward.
- One additional zero byte appeared before `extension_specification`.
- The generic field order that worked for normal extension devices did not match the working `G/HG` frames.

## 5. Practical Conclusion

- The implementation problem was not the meaning of `G/HG` alone.
- The real blocker was the accepted wire layout for the Extended Specification payload.
- The manual provided a usable field vocabulary, but the working byte order had to be recovered from packet captures.
- After reproducing that captured layout, unit tests now cover both the iQ-R `U3E0\G10` / `U3E0\HG20` path and the Q/L-style `U01\G22` path.
- Live smoke checks succeeded for single-word `U3E0\G10` and `U3E0\HG20`.

## 6. Other Extended Specification Exception Candidates

Current status by evidence level:

- Confirmed builder exception:
  - `G/HG` Extended Specification requests that use the captured reordered payload:
    - iQ-R `U3E0\G10` / `U3E0\HG20` style (`0082`, `0xFA`)
    - Q/L-style `U01\G22` (`0080`, `0xF8`)
- Unresolved within the same confirmed layout family:
  - manual-aligned `U4\G0` / `U4\HG0` style trials with `direct_memory=0xF8` and `extension_specification=0x0004` or `0x0040`
  - these still returned `0xC061` in the older probe set, so the remaining question is target-specific applicability, not whether `G/HG` needs reordered bytes
- No current evidence of another layout exception in this repository:
  - normal Extended Specification device examples such as `W100`
  - link-direct `J` path examples
  - generic extension helpers outside `G/HG`

Practical reading:

- `G/HG` is the only family that currently requires a dedicated builder branch in this repository.
- The dedicated branch now has capture evidence in both `0082/0xFA` and `0080/0xF8` forms.
- Other Extended Specification failures seen so far are still best treated as unresolved environment/path problems, not as proven alternative wire layouts.

## 7. Remaining Work

- Confirm whether the extra zero byte is always required for all practical `G/HG` Extended Specification targets or only for the targets captured so far.
- Check whether the same layout applies to:
  - multi-point `0401/1401`
  - `0403/1402`
  - `0406/1406`
  - additional Q/L and iQ-R unit numbers such as `U4\G0`
  - `HG` outside the current iQ-R capture set
