# Getting started

## Start here

Use this page to make your first safe SLMP read and write with the high-level API. Start with one `D` register before trying routed devices, module buffers, or long timer families.

## Prerequisites

| Requirement | Value |
| --- | --- |
| Python | `>=3.10` |
| PLC host | `192.168.250.100` |
| TCP port | `1025` |
| First profile | `melsec:iq-r` |
| First read target | `D100` |

## Install

```bash
pip install slmp-connect-python
```

## Choose your PLC profile

`plc_profile` in `SlmpConnectionOptions` is the only required PLC selector for the public helper layer. The library derives the frame type and access mode from it.
This is intentional. `ReadTypeName` and model-code data are diagnostic only because some PLCs or communication paths cannot return a useful type name. If a model-to-profile conversion guesses wrong, the library can use the wrong address grammar or device-range catalog. Let a human, configuration file, or UI choose the canonical `plc_profile`.

```python
options = SlmpConnectionOptions(
    host="192.168.250.100",
    port=1025,
    plc_profile="melsec:iq-r",
)
```

## First read

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

Expected output:

```text
D100=0
```

Your value may be different because it is read from your PLC.

## First write

Only write to an address that your PLC program reserves for testing.

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, read_typed, write_typed


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        await write_typed(client, "D100", "U", 42)
        value = await read_typed(client, "D100", "U")
        print(f"D100={value}")


asyncio.run(main())
```

Expected output:

```text
D100=42
```

## Confirm success

1. Confirm your PLC accepts a TCP connection to `192.168.250.100:1025`.
2. Confirm `plc_profile` matches your PLC family.
3. Confirm the first read uses a simple word register such as `D100`.
4. Confirm writes use only a known-safe test address.
5. Confirm the value read back matches the test value you wrote.

## If it does not work

| Symptom | Check |
| --- | --- |
| The PLC returns an end code error | `plc_profile` must match the actual PLC hardware. A wrong profile can cause end code errors. |
| The connection uses the wrong frame | Do not set `frame_type` manually. It is derived from `plc_profile`. |
| The first read fails on an advanced family | Start with `D` word reads. Do not start with `G`, `HG`, `LTN`, or `LCN`. |

## Next pages

| Page | Link |
| --- | --- |
| Usage guide | [USAGE_GUIDE.md](USAGE_GUIDE.md) |
| Supported registers | [SUPPORTED_REGISTERS.md](SUPPORTED_REGISTERS.md) |
