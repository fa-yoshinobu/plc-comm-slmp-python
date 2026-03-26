# Error Codes Guide

This file is the quick end-code table for users of the library.

The maintainer-facing error-code reference is kept in the source checkout under
`docsrc/maintainer/`.

## 1. Where Errors Come From

There are three different failure layers:

1. client-side validation failure
   - example: invalid device text or unsupported argument shape
   - Python result: `ValueError`
2. PLC-side rejection
   - normal SLMP response frame, but `end_code != 0`
   - Python result: `SlmpError`
3. transport failure
   - example: timeout, connection refused, route failure
   - Python result: `TimeoutError`, `ConnectionRefusedError`, or another `OSError`

## 2. Common End Codes on the Validated iQ-R Target

| End code | Practical meaning in this project | Common example |
| --- | --- | --- |
| `0x0000` | success | valid request accepted |
| `0x4013` | operation rejected in the current PLC state | `1005` remote latch clear outside the accepted state |
| `0x4030` | selected device/path rejected | `S0` bit write, direct `LTC/LTS/LSTC/LSTS` read |
| `0x4031` | configured range or allocation mismatch | start address outside the enabled range |
| `0x4043` | extend-unit argument invalid | `0601` with `module_no=0x0000` |
| `0x4080` | target/module mismatch | `0601` with `module_no=0x03FF` |
| `0x40C0` | label-side condition failure | label missing or external access disabled |
| `0x413E` | environment-specific operation rejection | target-dependent path rejected on the current endpoint |
| `0xC051` | word-count or unit rule violation | `LZ1 x1` write, some long-counter writes |
| `0xC059` | request family not accepted by the current endpoint | unsupported request family on the current target |
| `0xC05B` | direct `G/HG` path rejected | normal `0401` read of `G0` / `HG0` |
| `0xC061` | request content/path not accepted in the current environment | Extended Specification CPU buffer access |
| `0xC207` | environment-specific operation rejection | target-dependent path rejected on the current endpoint |

## 3. How to Inspect the Raw `end_code`

```python
from slmp import SlmpClient
from slmp.errors import SlmpError

with SlmpClient("192.168.250.100", port=1025, transport="tcp", plc_series="iqr") as cli:
    try:
        cli.read_devices("D100", 1)
    except SlmpError as e:
        print(f"end_code: 0x{e.end_code:04X}")

    # Or suppress the exception and inspect manually:
    response = cli.raw_command(0x0401, subcommand=0x0002, payload=b"...", raise_on_error=False)
    print(hex(response.end_code))
```

High-level APIs raise `SlmpError` by default. Use `raise_on_error=False` when you need the raw response.

For error handling implementation examples, see the [User Guide  EError Handling](USER_GUIDE.md).

## 4. Reading the Result Correctly

- `0x0000` means the PLC accepted the request, not that the operator-visible effect was what you expected
- the same end code can appear in more than one context
- target-specific conditions matter, especially for labels, Extended Specification, and remote control

## 5. Related Documents

- [User Guide](USER_GUIDE.md)
- Maintainer-only testing and internal error-reference notes are kept in the
  source checkout under `docsrc/maintainer/`.

Note for `0xC051`:

- the current project treats it as manual-confirmed for word-count / unit violations
