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
        plc_family="iq-f",
        port=1025,
    )
    async with await open_and_connect(options) as client:
        before = await read_named(client, ["D100", "D200:F", "D50.3"])
        print("before:", before)

        await write_typed(client, "D100", "U", 42)

        after = await read_named(client, ["D100", "D200:F", "D50.3"])
        print("after:", after)


asyncio.run(main())
```

Choose canonical `plc_family` explicitly.
In the recommended high-level helper layer, the only PLC selector is `plc_family`.

## High-Level PLC Selection

For normal application code:

- set `plc_family`
- let the library derive the fixed frame type, access profile, `X` / `Y` text rule, and device-range family
- do not pass raw `frame_type`, `plc_series`, or `device_family`

| `plc_family` | Derived `frame_type` | Derived `access_profile` | `X` / `Y` text | Derived range family | Notes |
| --- | --- | --- | --- | --- | --- |
| `iq-f` | `3e` | `ql` | octal | `iq-f` | live-validated |
| `iq-r` | `4e` | `iqr` | hexadecimal | `iq-r` | live-validated |
| `iq-l` | `4e` | `iqr` | hexadecimal | `iq-r` | live-validated on `L16HCPU` |
| `mx-f` | `4e` | `iqr` | hexadecimal | `mx-f` | provisional; review in `TODO.md` |
| `mx-r` | `4e` | `iqr` | hexadecimal | `mx-r` | provisional; review in `TODO.md` |
| `qcpu` | `3e` | `ql` | hexadecimal | `qcpu` | retained path |
| `lcpu` | `3e` | `ql` | hexadecimal | `lcpu` | retained path |
| `qnu` | `3e` | `ql` | hexadecimal | `qnu` | retained path |
| `qnudv` | `3e` | `ql` | hexadecimal | `qnudv` | retained path |

Low-level compatibility tools may still work with raw `frame_type` / `plc_series`, but that is not the normal public helper path.

High-level accepted `plc_family` values:

| Canonical | Typical target | Notes |
| --- | --- | --- |
| `iq-f` | FX5 / iQ-F | `X` / `Y` use manual octal text |
| `iq-r` | iQ-R | `X` / `Y` use hexadecimal text |
| `iq-l` | iQ-L | mapped to the `iq-r` range rules; live-validated on `L16HCPU` |
| `mx-f` | MX-F | pending live validation |
| `mx-r` | MX-R | pending live validation |
| `qcpu` | QCPU | `3e/ql` fixed profile |
| `lcpu` | LCPU | `3e/ql` fixed profile |
| `qnu` | QnU | `3e/ql` fixed profile |
| `qnudv` | QnUDV | `3e/ql` fixed profile |

Practical rules:

- non-`iQ-F` `X` / `Y`: text such as `X20` / `Y20` is interpreted as hexadecimal
- `iQ-F` / FX5 `X` / `Y`: text such as `X100` / `Y100` is interpreted as manual octal notation and encoded to the binary numeric value
- example: `X100` on `iQ-F` becomes binary device number `0x40`
- if you pass a numeric `DeviceRef`, string notation is already resolved, so `plc_family` is not needed for that one address
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
print(normalize_address("x100", plc_family="iq-f"))  # X100
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
For communication, `X` / `Y` string addresses require explicit `plc_family`.

### Device Range Catalog

Use `plc_family` and read the derived family SD block once.

```python
from slmp import SlmpClient

with SlmpClient("192.168.250.100", 1025, plc_family="qnu") as client:
    catalog = client.read_device_range_catalog()
    for entry in catalog.entries:
        print(entry.device, entry.point_count, entry.address_range)
```

This path does not call `read_type_name()`. The client uses the fixed range family derived from `plc_family`.

## Development

```bash
run_ci.bat
build_docs.bat
release_check.bat
```

## License

Distributed under the [MIT License](LICENSE).
