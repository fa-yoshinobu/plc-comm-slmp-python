[![CI](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-slmp-python/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-slmp-python/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)

# SLMP Protocol for Python

![Illustration](docsrc/assets/melsec.png)

High-level SLMP helpers for Mitsubishi PLC communication over Binary 3E and 4E frames.

This repository now treats the high-level helper layer as the recommended user surface:

- `AsyncSlmpClient`
- `QueuedAsyncSlmpClient`
- `SlmpClient`
- `read_typed` / `write_typed`
- `read_words` / `read_dwords`
- `write_bit_in_word`
- `read_named` / `write_named`
- `poll`

Low-level protocol methods still exist for maintainers and validation work, but they are not the primary user path.

## Installation

```bash
pip install slmp-connect-python
```

## Quick Start

Recommended async path:

```python
import asyncio

from slmp import AsyncSlmpClient, read_named, write_typed


async def main() -> None:
    async with AsyncSlmpClient(
        "192.168.250.100",
        port=1025,
        plc_series="iqr",
        frame_type="4e",
    ) as client:
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

Recommended sync path:

```python
from slmp import SlmpClient, read_named_sync, write_typed_sync

with SlmpClient(
    "192.168.250.100",
    port=1025,
    plc_series="iqr",
    frame_type="4e",
) as client:
    print(read_named_sync(client, ["D100", "D200:F", "D50.3"]))
    write_typed_sync(client, "D100", "U", 42)
```

## High-Level API Guide

### Single typed values

```python
from slmp import read_typed, write_typed

temperature = await read_typed(client, "D200", "F")
counter = await read_typed(client, "D300", "L")
await write_typed(client, "D100", "U", 1234)
```

### Mixed reads with one call

```python
from slmp import read_named

snapshot = await read_named(
    client,
    [
        "D100",
        "D200:F",
        "D300:L",
        "D50.3",
    ],
)
```

Use `.bit` notation only with word devices such as `D50.3`.
Address bit devices directly as `M1000`, `M1001`, ... rather than `M1000.0`.

### Mixed writes with one call

```python
from slmp import write_named

await write_named(
    client,
    {
        "D100": 42,
        "D200:F": 3.14,
        "D300:L": -200,
        "D50.3": True,
    },
)
```

### Chunked word and dword reads

```python
from slmp import read_words, read_dwords

words = await read_words(client, "D0", 1000, allow_split=True)
dwords = await read_dwords(client, "D200", 120, allow_split=True)
```

### Polling

```python
from slmp import poll

async for snapshot in poll(client, ["D100", "D200:F", "D50.3"], interval=1.0):
    print(snapshot)
```

### Shared connection for multiple coroutines

```python
from slmp import AsyncSlmpClient, QueuedAsyncSlmpClient

inner = AsyncSlmpClient("192.168.250.100", port=1025, plc_series="iqr", frame_type="4e")
async with QueuedAsyncSlmpClient(inner) as client:
    first = await read_named(client, ["D100", "D200:F"])
    second = await read_named(client, ["D300", "D50.3"])
```

## Sample Programs

The buildable sample files with the richest high-level examples are:

- [`samples/high_level_sync.py`](samples/high_level_sync.py)
  - typed reads and writes
  - chunked word and dword reads
  - bit-in-word writes
  - mixed `read_named_sync` / `write_named_sync`
  - polling
- [`samples/high_level_async.py`](samples/high_level_async.py)
  - explicit `AsyncSlmpClient`
  - typed reads and writes
  - chunked reads
  - `read_named` / `write_named`
  - polling
  - shared queued connection example

Run them from the repository root:

```bash
python samples/high_level_sync.py --host 192.168.250.100 --port 1025 --series iqr
python samples/high_level_async.py --host 192.168.250.100 --port 1025 --series iqr --frame-type 4e
```

More sample commands are listed in [docsrc/user/SAMPLES.md](docsrc/user/SAMPLES.md).

## Documentation

User-facing documents:

- [User Guide](docsrc/user/USER_GUIDE.md)
- [Samples](docsrc/user/SAMPLES.md)
- [Error Codes](docsrc/user/ERROR_CODES.md)

Maintainer and validation material remains in `docsrc/maintainer/` and `docsrc/validation/`.

## Development

```bash
run_ci.bat
build_docs.bat
release_check.bat
```

`run_ci.bat` validates the package and also builds the single-file CLI tool in `publish/`.

## License

Distributed under the [MIT License](LICENSE).
