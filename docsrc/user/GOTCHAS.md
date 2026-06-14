# Gotchas

Each entry starts with the symptom you are likely to see, then shows the root cause and a safe fix. The examples use TCP `192.168.250.100:1025` and the canonical `melsec:iq-r` profile.

## LTN/LSTN/LCN/LZ reads return wrong values

| Symptom | Root cause | Fix |
| --- | --- | --- |
| `LTN0`, `LSTN0`, `LCN0`, or `LZ0` looks truncated or is rejected. | These current-value families are 32-bit values, not normal 16-bit word values. | Use `:D` for unsigned 32-bit or `:L` for signed 32-bit. |

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, read_named


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        values = await read_named(client, ["LTN0:D", "LSTN0:D", "LCN0:L", "LZ0:D"])
        print(values)


asyncio.run(main())
```

## LCS/LCC reads look incorrect

| Symptom | Root cause | Fix |
| --- | --- | --- |
| `LCS0` or `LCC0` does not behave like a normal word read. | Long counter state devices are state bits. Reads use direct bit access, and writes are selected through random bit write (`0x1402`). | Use `read_named` or `write_typed` with `BIT`. |

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, read_named, write_typed


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        state = await read_named(client, ["LCS0", "LCC0"])
        await write_typed(client, "LCC0", "BIT", True)
        print(state)


asyncio.run(main())
```

## LTS/LTC/LSTS/LSTC write rejected

| Symptom | Root cause | Fix |
| --- | --- | --- |
| Direct bit writes to long timer or long retentive timer state devices are rejected. | These families need the helper route that selects the supported random bit write behavior. | Use `write_typed` or `write_named` for the state device. |

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, write_named


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        await write_named(client, {"LTS0": True, "LTC0": False})
        await write_named(client, {"LSTS0": True, "LSTC0": False})


asyncio.run(main())
```

## G/HG fails

| Symptom | Root cause | Fix |
| --- | --- | --- |
| `G100` or `HG1000` fails through the high-level typed helpers. | Module buffer access is not part of the public high-level typed surface. | Use the extended-device API and qualify the module with `Ux\G` or `Ux\HG`. |

```python
import asyncio

from slmp import AsyncSlmpClient, ExtensionSpec


async def main() -> None:
    async with AsyncSlmpClient("192.168.250.100", 1025, plc_profile="melsec:iq-r") as client:
        values = await client.read_devices_ext("U3\\G100", 4, extension=ExtensionSpec())
        print(values)


asyncio.run(main())
```

## Mixed word and bit write fails

| Symptom | Root cause | Fix |
| --- | --- | --- |
| A mixed write containing word devices and bit devices returns a PLC-side error. | Some PLCs reject command `0x1406` when word and bit blocks are combined. | Split word writes and bit writes into separate helper calls. |

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, write_named


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        await write_named(client, {"D100": 42, "D101": 43})
        await write_named(client, {"M100": True})


asyncio.run(main())
```

## DX/DY fails on melsec:iq-f

| Symptom | Root cause | Fix |
| --- | --- | --- |
| `DX` or `DY` raises an unsupported-device error with `melsec:iq-f`. | The iQ-F profile does not support `DX` and `DY`. | Use `X` and `Y` with `melsec:iq-f`; their text numbering is octal. |

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, read_named


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-f")
    async with await open_and_connect(options) as client:
        values = await read_named(client, ["X100", "Y100"])
        print(values)


asyncio.run(main())
```

## All reads return an end code

| Symptom | Root cause | Fix |
| --- | --- | --- |
| Simple reads such as `D100` connect but return an SLMP end code. | The selected `plc_profile` does not match the actual PLC family, so the frame type, access mode, or address grammar is wrong. | Choose the canonical profile from [PROFILES.md](PROFILES.md) in configuration or UI. |

```python
import asyncio

from slmp import SlmpConnectionOptions, SlmpError, open_and_connect, read_typed


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        try:
            value = await read_typed(client, "D100", "U")
            print(f"D100={value}")
        except SlmpError as exc:
            print(f"PLC rejected the request: 0x{exc.end_code:04X}")


asyncio.run(main())
```

## Missing or non-canonical plc_profile is rejected

| Symptom | Root cause | Fix |
| --- | --- | --- |
| Connection setup raises `ValueError` before any PLC request is sent. | `plc_profile` is required and only canonical profiles are accepted. There is no model-name auto-detection fallback. | Set an exact canonical profile such as `melsec:iq-r`. |

```python
from slmp import SlmpConnectionOptions


def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    print(options.plc_profile)


main()
```

## Concurrent callers crash or interleave responses

| Symptom | Root cause | Fix |
| --- | --- | --- |
| Several coroutines share one raw client and responses appear mismatched or fail intermittently. | A raw client represents one frame stream and is not a multi-caller scheduler. | Use `open_and_connect`, which returns a queued async client that serializes calls. |

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, read_typed


async def read_one(client: object, address: str) -> int | float:
    return await read_typed(client, address, "U")


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        values = await asyncio.gather(
            read_one(client, "D100"),
            read_one(client, "D101"),
        )
        print(values)


asyncio.run(main())
```

## X/Y uses the wrong address

| Symptom | Root cause | Fix |
| --- | --- | --- |
| `X20` or `Y20` points at a different physical address than expected. | `melsec:iq-f` uses octal `X`/`Y` text, while other profiles use hexadecimal text. | Select the correct canonical profile before parsing string addresses. |

```python
from slmp import normalize_address


def main() -> None:
    print(normalize_address("X100", plc_profile="melsec:iq-f"))
    print(normalize_address("X20", plc_profile="melsec:iq-r"))


main()
```
