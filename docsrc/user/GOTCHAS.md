# Gotchas

## LTN/LSTN/LCN/LZ reads return wrong values

These are 32-bit current-value families. Do not read them as 16-bit word values.

Fix: use `read_typed(client, "LTN0", "D")` inside your async client context.

## LCS/LCC reads look incorrect

`LCS` and `LCC` state bits use direct bit read. Writes use random bit write (`0x1402`).

Fix: use `write_typed` or `write_bit_in_word`.

## LTS/LTC/LSTS/LSTC write rejected

Direct bit write is rejected for these families.

Fix: use `write_typed(client, "LTS0", "BIT", True)` or `write_named(client, {"LTS0": True})` for long state devices. Use `write_bit_in_word` only when the bit is stored inside a normal word device such as `D50.3`.

## G or HG raises an error

`G` and `HG` are not in the public high-level API.

Fix: use the low-level or extended-device client methods for module buffer access.

```python
import asyncio
from slmp import ExtensionSpec
from slmp.async_client import AsyncSlmpClient


async def main() -> None:
    async with AsyncSlmpClient("192.168.250.100", 1025, plc_profile="melsec:iq-r") as client:
        values = await client.read_devices_ext("U3\\G100", 4, extension=ExtensionSpec())
        print(f"values={values}")


asyncio.run(main())
```

## Mixed write fails with PLC error

The PLC can reject command `0x1406` for word and bit combinations.

Fix: split word writes and bit writes into separate `write_named` calls.

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

## DX or DY fails on melsec:iq-f

`DX` and `DY` are not valid for `melsec:iq-f`.

Fix: use `X` and `Y` instead.

## plc_profile not set causes an error

`plc_profile` is required for the standard connection route. There is no default.

Fix: always set `plc_profile` in `SlmpConnectionOptions`.

```python
options = SlmpConnectionOptions(
    host="192.168.250.100",
    port=1025,
    plc_profile="melsec:iq-r",
)
```

## X or Y uses the wrong address

`X` and `Y` string addresses use different text numbering by profile.

Fix: use `melsec:iq-f` for octal `X`/`Y` text and any non-iQ-F profile for hexadecimal `X`/`Y` text.
