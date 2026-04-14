[![CI](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-slmp-python/)
[![PyPI](https://img.shields.io/pypi/v/slmp-connect-python.svg)](https://pypi.org/project/slmp-connect-python/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)

# SLMP Protocol for Python

![Illustration](https://raw.githubusercontent.com/fa-yoshinobu/plc-comm-slmp-python/main/docsrc/assets/melsec.png)

High-level SLMP helpers for Mitsubishi PLC communication over Binary 3E and 4E frames.

This repository treats the high-level helper layer as the recommended user surface:

- `SlmpConnectionOptions`
- `open_and_connect` / `open_and_connect_sync`
- `AsyncSlmpClient`
- `QueuedAsyncSlmpClient`
- `SlmpClient`
- `normalize_address`
- `read_typed` / `write_typed`
- `read_words_single_request` / `read_dwords_single_request`
- `read_words_chunked` / `read_dwords_chunked`
- `write_bit_in_word`
- `read_named` / `write_named`
- `poll`

## Installation

```bash
pip install slmp-connect-python
```

The latest release lives at <https://pypi.org/project/slmp-connect-python/>, where wheel and tarball downloads and metadata are available.

## Quick Start

Recommended async path:

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, read_named, write_typed


async def main() -> None:
    options = SlmpConnectionOptions(
        host="192.168.250.100",
        port=1025,
        plc_series="iqr",
        frame_type="4e",
        device_family="iq-f",
    )
    async with await open_and_connect(options) as client:
        before = await read_named(client, ["D100", "D200:F", "D50.3"])
        print("before:", before)

        await write_typed(client, "D100", "U", 42)

        after = await read_named(client, ["D100", "D200:F", "D50.3"])
        print("after:", after)


asyncio.run(main())
```

Choose a validated communication profile explicitly.
In this library, the communication profile and the address family are separate settings.

## Meaning of Each Explicit Setting

| Setting | Where Used | What It Controls | Examples |
| --- | --- | --- | --- |
| `frame_type` | client / connection options | SLMP frame envelope on the wire | `3e`, `4e` |
| `plc_series` | client / connection options | command/access profile used by the library | `ql`, `iqr` |
| `device_family` | client / connection options | how string device addresses are interpreted | `iq-f`, `qcpu`, `qnudv` |
| `family` argument | `read_device_range_catalog_for_family(...)` | which SD window and range rules are used for device-range catalog reads | `iq-f`, `qnu`, `qnudv` |

Important separation:

- `frame_type` and `plc_series` are communication settings
- `device_family` and device-range `family` are address/range settings
- the last two use the same explicit family vocabulary
- the library does not auto-detect any of them for the public helper layer

When you communicate with `X` / `Y` by string address, set canonical `device_family` explicitly.
When you read the device-range catalog, pass the matching canonical `family` argument to `read_device_range_catalog_for_family(...)`.

Only these canonical family values are accepted:

| Canonical | Typical target | `X` / `Y` text |
| --- | --- | --- |
| `iq-f` | FX5 / iQ-F | octal |
| `iq-r` | iQ-R | hexadecimal |
| `mx-f` | MX-F | hexadecimal |
| `mx-r` | MX-R | hexadecimal |
| `qcpu` | QCPU | hexadecimal |
| `lcpu` | LCPU | hexadecimal |
| `qnu` | QnU | hexadecimal |
| `qnudv` | QnUDV | hexadecimal |

Practical rules:

- non-`iQ-F` `X` / `Y`: text such as `X20` / `Y20` is interpreted as hexadecimal
- `iQ-F` / FX5 `X` / `Y`: text such as `X100` / `Y100` is interpreted as manual octal notation and encoded to the binary numeric value
- example: `X100` on `iQ-F` becomes binary device number `0x40`
- if you pass a numeric `DeviceRef`, string notation is already resolved, so `device_family` is not needed for that one address
- short aliases such as `iqf`, `iqr`, `q`, `l`, and `qnudvcpu` are rejected

## Supported PLC Registers

Start with these public high-level families first:

- word devices: `D`, `SD`, `R`, `ZR`, `TN`, `CN`
- bit devices: `M`, `X`, `Y`, `SM`, `B`
- typed forms: `D200:F`, `D300:L`, `D100:S`
- mixed snapshot forms: `D50.3`, `D100`, `D200:F`
- current-value long families: `LTN`, `LSTN`, `LCN`

See the full public table in [Supported PLC Registers](docsrc/user/SUPPORTED_REGISTERS.md).

## Public Documentation

- [Getting Started](docsrc/user/GETTING_STARTED.md)
- [Supported PLC Registers](docsrc/user/SUPPORTED_REGISTERS.md)
- [Latest Communication Verification](docsrc/user/LATEST_COMMUNICATION_VERIFICATION.md)
- [User Guide](docsrc/user/USER_GUIDE.md)
- [Samples](docsrc/user/SAMPLES.md)
- [Error Codes](docsrc/user/ERROR_CODES.md)

Maintainer-only notes and retained evidence live under `internal_docs/`.

## High-Level API Guide

### Address Normalization

```python
from slmp import normalize_address

print(normalize_address("x20"))   # X20
print(normalize_address("d200"))  # D200
print(normalize_address("x100", family="iq-f"))  # X100
```

### Single Typed Values

```python
from slmp import read_typed, write_typed

temperature = await read_typed(client, "D200", "F")
counter = await read_typed(client, "D300", "L")
await write_typed(client, "D100", "U", 1234)
```

Use `.bit` notation only with word devices such as `D50.3`.
Address bit devices directly as `M1000`, `M1001`, `X20`, or `Y20`.
For communication, `X` / `Y` string addresses require explicit `device_family`.

### Device Range Catalog

Use an explicit PLC family and read the family SD block once.

```python
from slmp import SlmpClient, SlmpDeviceRangeFamily

with SlmpClient("192.168.250.100", 1025, plc_series="ql", frame_type="3e") as client:
    catalog = client.read_device_range_catalog_for_family(SlmpDeviceRangeFamily.QnU)
    for entry in catalog.entries:
        print(entry.device, entry.point_count, entry.address_range)
```

This path does not call `read_type_name()`. The caller must choose the range `family` explicitly, using the same family definition as `device_family`.

### Device Range Catalog

Use an explicit PLC family and read the family SD block once.

```python
from slmp import SlmpClient, SlmpDeviceRangeFamily

with SlmpClient("192.168.250.100", 1025, plc_series="ql", frame_type="3e") as client:
    catalog = client.read_device_range_catalog_for_family(SlmpDeviceRangeFamily.QnU)
    for entry in catalog.entries:
        print(entry.device, entry.point_count, entry.address_range)
```

This path does not call `read_type_name()`. The caller chooses the family such as `IqF`, `QnU`, `QnUDV`, or `LCpu`.

## Development

```bash
run_ci.bat
build_docs.bat
release_check.bat
```

## License

Distributed under the [MIT License](LICENSE).
