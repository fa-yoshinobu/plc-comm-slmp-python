# Error codes

This file is the quick end-code table for users of the library.

## 1. Where errors come from

| Layer | Python result | Example |
| --- | --- | --- |
| Client-side validation | `ValueError` | Invalid device text or unsupported argument shape. |
| PLC-side rejection | `SlmpError` | Normal SLMP response frame with `end_code != 0`. |
| Transport failure | `TimeoutError`, `ConnectionRefusedError`, or another `OSError` | Timeout, connection refused, or route failure. |

## 2. Common end codes on the validated iQ-R target

| End code | Practical meaning in this project | Common example |
| --- | --- | --- |
| `0x0000` | Success | Valid request accepted. |
| `0x4013` | Operation rejected in the current PLC state | Remote latch clear outside the accepted state. |
| `0x4030` | Selected device or path rejected | Direct long timer state read. |
| `0x4031` | Configured range or allocation mismatch | Start address outside the enabled range. |
| `0x4043` | Extend-unit argument invalid | `0601` with `module_no=0x0000`. |
| `0x4080` | Target or module mismatch | `0601` with `module_no=0x03FF`. |
| `0x40C0` | Label-side condition failure | Label missing or external access disabled. |
| `0x413E` | Environment-specific operation rejection | Target-dependent path rejected on the current endpoint. |
| `0xC051` | Word-count or unit rule violation | Some long-counter writes. |
| `0xC059` | Request family not accepted by the endpoint | Unsupported request family on the current target. |
| `0xC05B` | Direct `G`/`HG` path rejected | Normal `0401` read of `G0` or `HG0`. |
| `0xC061` | Request content or path not accepted | Extended Specification CPU buffer access. |
| `0xC207` | Environment-specific operation rejection | Target-dependent path rejected on the current endpoint. |

## 3. How to inspect the raw `end_code`

```python
from slmp import SlmpClient
from slmp.errors import SlmpError


with SlmpClient("192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r") as client:
    try:
        client.read_devices("D100", 1)
    except SlmpError as exc:
        print(f"end_code: 0x{exc.end_code:04X}")

    response = client.raw_command(0x0401, subcommand=0x0002, payload=b"...", raise_on_error=False)
    print(f"raw end_code: 0x{response.end_code:04X}")
```

High-level APIs raise `SlmpError` by default. Use `raise_on_error=False` when you need the raw response.

## 4. Reading the result correctly

| Rule | Meaning |
| --- | --- |
| `0x0000` means accepted | It does not prove the operator-visible effect was what you expected. |
| The same end code can appear in more than one context | Check the command, device family, and PLC state. |
| Target-specific conditions matter | Labels, Extended Specification, and remote control paths are especially environment-dependent. |

## 5. Related documents

| Page | Link |
| --- | --- |
| Usage guide | [USAGE_GUIDE.md](USAGE_GUIDE.md) |
| Gotchas | [GOTCHAS.md](GOTCHAS.md) |
