# Usage guide

## Recommended entry points

| Entry point | Signature | Use |
| --- | --- | --- |
| `SlmpConnectionOptions` | `SlmpConnectionOptions(host: str, plc_profile: object, port: int \| None = None, transport: str = "tcp", timeout: float = 3.0, default_target: SlmpTarget \| None = None, monitoring_timer: int = 16, raise_on_error: bool = True, trace_hook: Any \| None = None)` | Store stable connection settings. Omitted ports resolve to `1025` for TCP and `1035` for UDP. |
| `open_and_connect` | `async def open_and_connect(options: SlmpConnectionOptions) -> QueuedAsyncSlmpClient` | Open one queued async connection. |
| `open_and_connect_sync` | `def open_and_connect_sync(options: SlmpConnectionOptions) -> SlmpClient` | Open one synchronous connection. |
| `read_typed` | `async def read_typed(client, device, dtype) -> int | float | bool` | Read one typed value. |
| `write_typed` | `async def write_typed(client, device, dtype, value: int | float | bool) -> None` | Write one typed value. |
| `read_named` | `async def read_named(client, addresses) -> dict[str, int | float | bool]` | Read a mixed snapshot. |
| `write_named` | `async def write_named(client, updates) -> None` | Write mixed values. |
| `read_words_single_request` | `async def read_words_single_request(client, device, count) -> list[int]` | Read one contiguous 16-bit range in one request. |
| `read_words_chunked` | `async def read_words_chunked(client, device, count, max_per_request=960) -> list[int]` | Read a large 16-bit range with explicit chunking. |
| `read_dwords_single_request` | `async def read_dwords_single_request(client, device, count) -> list[int]` | Read one contiguous 32-bit range in one request. |
| `read_dwords_chunked` | `async def read_dwords_chunked(client, device, count, max_dwords_per_request=480) -> list[int]` | Read a large 32-bit range with explicit chunking. |
| `write_bit_in_word` | `async def write_bit_in_word(client, device, bit_index, value) -> None` | Set or clear one bit in a word device. |
| `poll` | `async def poll(client, addresses, interval)` | Yield repeated mixed snapshots. |

The synchronous helpers use the same names with `_sync`.

## Connection

```python
import asyncio
from slmp import SlmpConnectionOptions, SlmpTarget, open_and_connect


async def main() -> None:
    options = SlmpConnectionOptions(
        host="192.168.250.100",
        port=1025,
        transport="tcp",
        timeout=3.0,
        plc_profile="melsec:iq-r",
        default_target=SlmpTarget(),
        monitoring_timer=0x0010,
        raise_on_error=True,
    )
async with await open_and_connect(options) as client:
    print(f"connected profile={client.plc_profile}")


asyncio.run(main())
```

## Remote password

Remote password lock/unlock commands are available through the async and sync clients.
The Python high-level connection does not automatically unlock or lock a remote password.
If your PLC route uses remote password protection, unlock after opening the connection
and lock before closing it.

```python
async with await open_and_connect(options) as client:
    await client.remote_password_unlock("secret")
    try:
        value = await read_typed(client, "D100", "U")
    finally:
        await client.remote_password_lock("secret")
```

For `C200`-series password end codes, see the shared
[SLMP Troubleshooting & End Codes](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/profile-reference/troubleshooting-end-codes/)
page.

## Routing / target station

Most applications keep the default target, which means the directly connected
own station/control CPU. Change the target only when your PLC network is
configured for another station, multi-CPU module I/O, or multidrop access.

`SlmpTarget` controls the SLMP destination header. It is not a device family
selector; routed devices such as `Un\Gn` and `Jn\...` still need their own
address syntax.

```python
from slmp import SlmpConnectionOptions, SlmpTarget

options = SlmpConnectionOptions(
    host="192.168.250.100",
    port=1025,
    plc_profile="melsec:iq-r",
    default_target=SlmpTarget(
        network=0x01,
        station=0x02,
        module_io=0x03FF,
        multidrop=0x00,
    ),
)
```

For a multi-CPU self target, you can also use the named module I/O helpers:

```python
target = SlmpTarget(module_io="MULTIPLE_CPU_2")
```

Use the default target unless the PLC routing setup gives you specific values.

## Read a single value

| Type suffix | Meaning | Words |
| --- | --- | --- |
| `U` | Unsigned 16-bit integer | 1 |
| `S` | Signed 16-bit integer | 1 |
| `D` | Unsigned 32-bit integer | 2 |
| `L` | Signed 32-bit integer | 2 |
| `F` | IEEE-754 float32 | 2 |

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

## Write a single value

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, read_typed, write_typed


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        original = await read_typed(client, "D100", "U")
        try:
            await write_typed(client, "D100", "U", 42)
            print("wrote D100")
        finally:
            await write_typed(client, "D100", "U", original)


asyncio.run(main())
```

## Named snapshot

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, read_named


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        snapshot = await read_named(client, ["D100:U", "D101:S", "D200:F", "D202:L", "D50.3"])
        print(f"snapshot={snapshot}")


asyncio.run(main())
```

## Block reads

```python
import asyncio
from slmp import (
    SlmpConnectionOptions,
    open_and_connect,
    read_dwords_chunked,
    read_dwords_single_request,
    read_words_chunked,
    read_words_single_request,
)


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        words = await read_words_single_request(client, "D0", 10)
        dwords = await read_dwords_single_request(client, "D200", 4)
        large_words = await read_words_chunked(client, "D0", 1000)
        large_dwords = await read_dwords_chunked(client, "D200", 120)
        print(f"words={len(words)} dwords={len(dwords)} large={len(large_words)}/{len(large_dwords)}")


asyncio.run(main())
```

## Bit in word

Use `write_bit_in_word` when a PLC stores flags inside a word register. Use `.n` notation when reading or writing mixed named values.

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, read_named, write_bit_in_word


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        original = await read_named(client, ["D50.3"])
        try:
            await write_bit_in_word(client, "D50", bit_index=3, value=True)
            snapshot = await read_named(client, ["D50.3"])
            print(f"D50.3={snapshot['D50.3']}")
        finally:
            await write_bit_in_word(client, "D50", bit_index=3, value=bool(original["D50.3"]))


asyncio.run(main())
```

## Polling

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, poll


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        index = 0
        async for snapshot in poll(client, ["D100:U", "D200:F", "D50.3"], interval=1.0):
            print(f"snapshot={snapshot}")
            index += 1
            if index >= 3:
                break


asyncio.run(main())
```

## Device range catalog

`read_device_range_catalog()` reads live device range bounds from the SD registers for the canonical profile selected on the client. It does not auto-discover the PLC model.
The catalog is for diagnostics and application-layer validation. Normal read/write helpers do not use it to reject addresses by configured upper bound before sending a request.

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        catalog = await client.read_device_range_catalog()
        entry = next(item for item in catalog.entries if item.device == "D")
        print(f"{entry.device}: {entry.address_range}")


asyncio.run(main())
```

## Long device families

`LTN`, `LSTN`, `LCN`, and `LZ` are 32-bit current-value families. Always request `:D` or `:L` intent when you document or review these addresses.

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, read_named


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        values = await read_named(client, ["LTN0:D", "LCN0:L"])
        print(f"values={values}")


asyncio.run(main())
```

> **Caution:** 16-bit word views for `LTN`, `LSTN`, `LCN`, and `LZ` are rejected. Use `:D` or `:L` for these current-value families.

## Address reference

| Form | Example | Meaning | Helper behavior |
| --- | --- | --- | --- |
| `:BIT` | `M1000:BIT` | Boolean bit value | One bit. |
| `:U` | `D100:U` | Unsigned 16-bit word | One word. |
| `:S` | `D100:S` | Signed 16-bit word | One word. |
| `:D` | `D200:D` | Unsigned 32-bit value | Two words, little-endian word order. |
| `:L` | `D202:L` | Signed 32-bit value | Two words, little-endian word order. |
| `:F` | `D204:F` | Float32 value | Two words, little-endian word order. |
| `.n` | `D50.3` | One bit inside a word | Hex bit index from `0` to `F`. |

Named addresses used with `read_named`, `write_named`, and `poll` must include the intended type, for example `D100:U` or `M1000:BIT`.
