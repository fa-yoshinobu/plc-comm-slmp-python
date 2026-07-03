[![CI](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/slmp-connect-python.svg)](https://pypi.org/project/slmp-connect-python/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

# MELSEC SLMP for Python

Python library for MELSEC SLMP (Binary 3E/4E) PLC communication.

## Supported PLC profiles

The maintained profile table is in [PLC profiles](docsrc/user/PROFILES.md). Choose one exact canonical PLC profile from that table.

The library embeds built-in Ethernet capability profiles from `plc-comm-slmp-profiles` v1.0.0. Sync and async clients use `strict_profile=True` by default; with a known profile, high-level APIs reject features marked `blocked` or `unverified` before transport by raising `SlmpProfileFeatureError`. Set `strict_profile=False` only when you intentionally want to send that request and let the PLC answer. Point limits and read-only write policies are always enforced.

## Supported device types

The maintained device and range tables are in [Supported registers](docsrc/user/SUPPORTED_REGISTERS.md). Use that page for supported device families, address syntax, and profile-specific notes.

## Installation

```bash
pip install slmp-connect-python
```

## Quick example

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, read_typed

async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        value = await read_typed(client, "D100", "U")
        print(f"D100={value}")

asyncio.run(main())
```

## Documentation

| Page | Use it for |
| --- | --- |
| [Full documentation site](https://fa-yoshinobu.github.io/plc-comm-docs-site/) | Unified docs for all PLC communication libraries. |
| [Getting started](docsrc/user/GETTING_STARTED.md) | Install the package, connect to your PLC, and run your first SLMP read/write. |
| [Usage guide](docsrc/user/USAGE_GUIDE.md) | Use the high-level API and common SLMP workflows. |
| [Supported registers](docsrc/user/SUPPORTED_REGISTERS.md) | Check supported device families, address syntax, and numbering rules. |
| [PLC profiles](docsrc/user/PROFILES.md) | Choose the canonical MELSEC profile and frame behavior. |
| [Examples](samples/README.md) | Run maintained Python samples. |

## Hardware verified

Live-device verification is maintained in [Latest communication verification](docsrc/user/LATEST_COMMUNICATION_VERIFICATION.md).
See that page for verified PLC models, transports, dates, limitations, and retained validation notes.

## License and registry

| Item | Value |
| --- | --- |
| License | [MIT](LICENSE) |
| Registry | [PyPI](https://pypi.org/project/slmp-connect-python/) |
| Package | `slmp-connect-python` |

## Commercial support

If you plan to embed this library in a paid or commercial product, please consider a separate support agreement or supporting the project as a sponsor.

Contact: <https://fa-labo.com/contact.html>
