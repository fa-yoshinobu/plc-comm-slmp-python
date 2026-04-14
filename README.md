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
    )
    async with await open_and_connect(options) as client:
        before = await read_named(client, ["D100", "D200:F", "D50.3"])
        print("before:", before)

        await write_typed(client, "D100", "U", 42)

        after = await read_named(client, ["D100", "D200:F", "D50.3"])
        print("after:", after)


asyncio.run(main())
```

Choose the connection profile explicitly:

- `plc_series="iqr", frame_type="4e"` for iQ-R / iQ-F targets
- `plc_series="ql", frame_type="3e"` for Q / L targets

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
