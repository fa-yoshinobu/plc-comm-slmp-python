# Error codes

This page explains how to inspect SLMP end codes returned by the PLC.

## 1. Where errors come from

| Layer | Python result | Example |
| --- | --- | --- |
| Client-side validation | `ValueError` | Invalid device text or unsupported argument shape. |
| PLC-side rejection | `SlmpError` | Normal SLMP response frame with `end_code != 0`. |
| Transport failure | `TimeoutError`, `ConnectionRefusedError`, or another `OSError` | Timeout, connection refused, or route failure. |

## 2. Message text

The library does not embed localized SLMP end-code descriptions.

`SlmpError.end_code` exposes the numeric PLC value. `SlmpError.end_code_name` exposes a stable code-derived key such as `slmp_end_code_c201`. Resolve that key in an application-owned catalog when user-facing text is required.

`get_end_code_message()` is retained as a compatibility hook and returns `None`.

## 3. How to inspect the raw `end_code`

```python
from slmp import SlmpClient
from slmp.errors import SlmpError


with SlmpClient("192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r") as client:
    try:
        client.read_devices("D100", 1)
    except SlmpError as exc:
        print(f"end_code: 0x{exc.end_code:04X}")
        print(f"end_code_name: {exc.end_code_name}")

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
