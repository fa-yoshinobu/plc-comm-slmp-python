[![CI](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/plc-comm-slmp.svg)](https://pypi.org/project/plc-comm-slmp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/fa-yoshinobu/plc-comm-slmp-python/blob/main/LICENSE)

# MELSEC SLMP for Python

Python library for MELSEC SLMP (Binary 3E/4E) PLC communication.

## PLC Comm Family

This library is part of the plc-comm family. See the [package matrix](https://fa-yoshinobu.github.io/plc-comm-docs-site/package-matrix/) for protocol, language, registry, and install-command mapping.

## Supported PLC profiles

The maintained profile table is in [PLC profiles](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/python/PROFILES/). Choose one exact canonical PLC profile from that table.

Sync and async public clients always enforce the selected PLC profile. Point limits and read-only write policies are also enforced before transport.

## Supported device types

The maintained device and range tables are in the [SLMP Profile Reference](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/profile-reference/). Use that page for supported device families, address syntax, and profile-specific notes.

## Installation

```bash
pip install plc-comm-slmp
```

## Quick example

```python
import asyncio
from slmp import SlmpConnectionOptions, SlmpTarget, open_and_connect, read_typed

async def main() -> None:
    options = SlmpConnectionOptions(
        host="192.168.250.100",
        port=1025,
        transport="tcp",
        plc_profile="melsec:iq-r",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
    )
    async with await open_and_connect(options) as client:
        value = await read_typed(client, "D100", "U")
        print(f"D100={value}")

asyncio.run(main())
```

## Documentation

| Page | Use it for |
| --- | --- |
| [Full documentation site](https://fa-yoshinobu.github.io/plc-comm-docs-site/) | Unified docs for all PLC communication libraries. |
| [Getting started](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/python/GETTING_STARTED/) | Install the package, connect to your PLC, and run your first SLMP read/write. |
| [Usage guide](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/python/USAGE_GUIDE/) | Use the high-level API and common SLMP workflows. |
| [SLMP profile reference](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/profile-reference/) | Check profile parameters, device families, address syntax, and numbering rules. |
| [PLC profiles](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/python/PROFILES/) | Choose the canonical MELSEC profile and frame behavior. |
| [Examples](https://github.com/fa-yoshinobu/plc-comm-slmp-python/blob/main/samples/README.md) | Run maintained Python samples. |

## License and registry

| Item | Value |
| --- | --- |
| License | [MIT](https://github.com/fa-yoshinobu/plc-comm-slmp-python/blob/main/LICENSE) |
| Registry | [PyPI](https://pypi.org/project/plc-comm-slmp/) |
| Package | `plc-comm-slmp` |

## Commercial support

If you plan to embed this library in a paid or commercial product, please consider a separate support agreement or supporting the project as a sponsor.

Contact: <https://fa-labo.com/contact.html>
