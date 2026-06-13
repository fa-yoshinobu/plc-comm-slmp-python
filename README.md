[![CI](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-slmp-python/)
[![PyPI](https://img.shields.io/pypi/v/slmp-connect-python.svg)](https://pypi.org/project/slmp-connect-python/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Release](https://img.shields.io/github/v/release/fa-yoshinobu/plc-comm-slmp-python?label=release)](https://github.com/fa-yoshinobu/plc-comm-slmp-python/releases/latest)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MkDocs](https://img.shields.io/badge/MkDocs-526CFE?logo=materialformkdocs&logoColor=white)](https://www.mkdocs.org/)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-222222?logo=githubpages&logoColor=white)](https://pages.github.com/)

# SLMP Protocol for Python

Python library for Mitsubishi SLMP (Binary 3E/4E) PLC communication.

## Supported PLC profiles

Set `plc_profile` once when you connect. The library derives the SLMP frame type, access mode, device parsing rules, and device-range profile from that profile.
`read_type_name()` and model-code data are diagnostic only; the library does not infer the active profile from PLC-reported model names because some PLCs cannot return a reliable type name and a wrong guess can select the wrong address grammar or range catalog.

| Profile string | Hardware | Frame | Notes |
| --- | --- | --- | --- |
| `melsec:iq-f` | MELSEC iQ-F / FX5 | 3E | Legacy `ql` mode; `X`/`Y` use octal text; `DX`/`DY` are not valid. |
| `melsec:iq-r` | MELSEC iQ-R | 4E | iQR mode; `X`/`Y` use hexadecimal text. |
| `melsec:iq-l` | MELSEC iQ-L | 4E | iQR mode; uses iQ-R address parsing and iQ-L range catalog rules. |
| `melsec:mx-f` | MELSEC MX-F-compatible endpoint | 4E | iQR mode; uses MX-F range catalog rules. |
| `melsec:mx-r` | MELSEC MX-R-compatible endpoint | 4E | iQR mode; uses MX-R range catalog rules. |
| `melsec:qcpu` | MELSEC-Q CPU | 3E | Legacy `ql` mode; `X`/`Y` use hexadecimal text. |
| `melsec:lcpu` | MELSEC-L CPU | 3E | Legacy `ql` mode; `X`/`Y` use hexadecimal text. |
| `melsec:qnu` | MELSEC QnU CPU | 3E | Legacy `ql` mode; `X`/`Y` use hexadecimal text. |
| `melsec:qnudv` | MELSEC QnUDV CPU | 3E | Legacy `ql` mode; `X`/`Y` use hexadecimal text. |

## Supported device types

See the full table in [Supported registers](docsrc/user/SUPPORTED_REGISTERS.md).

| Family | Use |
| --- | --- |
| `D` | Data registers for beginner word reads and writes. |
| `M` | Internal relays for direct bit reads and writes. |
| `X` | Input relays; octal text on `melsec:iq-f`, hexadecimal text on other profiles. |
| `Y` | Output relays; octal text on `melsec:iq-f`, hexadecimal text on other profiles. |
| `W` | Link registers with hexadecimal numbering. |
| `R` | File registers with decimal numbering. |
| `LTN` | Long timer current values; use 32-bit `:D` or `:L` access. |
| `LCN` | Long counter current values; use 32-bit `:D` or `:L` access. |

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

| Page | Link |
| --- | --- |
| Getting started | [docsrc/user/GETTING_STARTED.md](docsrc/user/GETTING_STARTED.md) |
| Usage guide | [docsrc/user/USAGE_GUIDE.md](docsrc/user/USAGE_GUIDE.md) |
| Supported registers | [docsrc/user/SUPPORTED_REGISTERS.md](docsrc/user/SUPPORTED_REGISTERS.md) |
| PLC profiles | [docsrc/user/PROFILES.md](docsrc/user/PROFILES.md) |
| Examples | [samples/README.md](samples/README.md) |

## Hardware verified

| Scope | Summary |
| --- | --- |
| Fully verified families | `iQ-R` and `iQ-L`. |
| Profile-limited families | `MELSEC-Q`, `MELSEC-L`, `iQ-F`, and third-party MC-compatible endpoints. |
| Stability coverage | Current helper layer across sync, async, mixed-frame, and concurrency scenarios. |
| Recommended first test | `D100`, `D200:F`, and `D50.3`. |

## License and registry

| Item | Link |
| --- | --- |
| License | [MIT](LICENSE) |
| Package registry | [slmp-connect-python on PyPI](https://pypi.org/project/slmp-connect-python/) |
