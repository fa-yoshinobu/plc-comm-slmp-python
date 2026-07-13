# Usage guide

## Recommended entry points

| Entry point | Signature | Use |
| --- | --- | --- |
| `SlmpConnectionOptions` | `SlmpConnectionOptions(host: str, plc_profile: object, port: int, transport: str, default_target: SlmpTarget, timeout: float = 3.0, monitoring_timer: int = 16, raise_on_error: bool = True)` | Store stable connection settings. Port, transport, profile, and the complete four-field route are required. |
| `open_and_connect` | `async def open_and_connect(options: SlmpConnectionOptions) -> QueuedAsyncSlmpClient` | Open one queued async connection. |
| `open_and_connect_sync` | `def open_and_connect_sync(options: SlmpConnectionOptions) -> SlmpClient` | Open one synchronous connection. |
| `read_typed` | `async def read_typed(client, device, dtype) -> int | float | bool` | Read one typed value. |
| `write_typed` | `async def write_typed(client, device, dtype, value: int | float | bool) -> None` | Write one typed value. |
| `read_named` | `async def read_named(client, addresses) -> dict[str, int | float | bool]` | Read a mixed snapshot. |
| `write_named` | `async def write_named(client, updates) -> None` | Write one word/DWord family or one bit family in one random-write request. |
| `read_words_single_request` | `async def read_words_single_request(client, device, count) -> list[int]` | Read one contiguous 16-bit range in one request. |
| `read_dwords_single_request` | `async def read_dwords_single_request(client, device, count) -> list[int]` | Read one contiguous 32-bit range in one request. |
| `write_bit_in_word` | `async def write_bit_in_word(client, device, bit_index, value) -> None` | Set or clear one bit in a word device. |
| `poll` | `async def poll(client, addresses, interval)` | Yield repeated mixed snapshots. |
| `SlmpClient.read_devices` | `read_devices(device, count, *, bit_unit)` | Generic direct read; an explicit Boolean bit/word unit is mandatory. |
| `SlmpClient.write_devices` | `write_devices(device, values, *, bit_unit)` | Generic direct write; an explicit Boolean bit/word unit is mandatory. |
| `SlmpClient.read_devices_ext` | `read_devices_ext(qualified_device, count, *, bit_unit)` | Read routed devices such as `Un\G...` and `Jn\...`; bit/word unit is mandatory. |
| `SlmpClient.write_devices_ext` | `write_devices_ext(qualified_device, values, *, bit_unit)` | Write routed devices such as `Un\G...` and `Jn\...`; bit/word unit is mandatory. |

The synchronous helpers use the same names with `_sync`.

`read_named` sends exactly one random-read request. Every entry must be
representable in that request; direct/block/long-timer fallback routes and
oversized batches are rejected before transport. Use the explicit typed or
long-device API when another command family is required.

`write_named` also has a one-request contract. Word and DWord entries may be
combined in one random-word request, or bit entries may be combined in one
random-bit request. Mixing those command families is rejected. `.n`
bit-in-word updates are rejected by `write_named`; call `write_bit_in_word`
explicitly because that helper is an intentional read-modify-write operation
consisting of one read followed by one write.

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
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
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
[SLMP Troubleshooting & Codes](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/slmp/troubleshooting-codes/)
page.

## Routing / target station

Every connection explicitly supplies all four target fields. The own-station
values shown above are suitable only when that is the intended route. Change
them when your PLC network targets another station, CPU, or multidrop route.

`SlmpTarget` controls the SLMP destination header. It is not a device family
selector; routed devices such as `Un\Gn` and `Jn\...` still need their own
address syntax.

```python
from slmp import ModuleIONo, SlmpConnectionOptions, SlmpTarget

options = SlmpConnectionOptions(
    host="192.168.250.100",
    port=1025,
    transport="tcp",
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
target = SlmpTarget(network=0, station=0xFF, module_io=ModuleIONo.MULTIPLE_CPU_2, multidrop=0)
```

Always confirm the explicit target against the PLC routing setup.

For iQ-R multi-CPU `U3En\HG...` access, the qualified device never changes the
SLMP request target automatically. Select the destination CPU explicitly when
a write must be reflected there. A write can return a normal end code without
changing the intended CPU buffer when the selected request target identifies a
different CPU or Own Station. Cross-CPU reads remain valid. See the shared
[iQ-R target guidance](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/slmp/iq-r/#multi-cpu-cpu-buffer-target).

## Extended device access

Use the extended-device APIs for routed device forms such as `Un\G...`,
`Un\HG...`, and `Jn\...`. Normal typed and named helpers cover ordinary
device families such as `D`, `M`, `X`, and `Y`.

`SlmpTarget` controls the SLMP destination header. It does not replace routed
device notation: `Un\G...` and `Jn\...` still need their own address syntax.

The public Extended Device methods derive the module/network selector,
direct-memory kind, and fixed protocol fields from the qualified address.
They do not accept a raw extension-field object. For Z, LZ, or word-device
indirect modification, wrap the qualified text in `SlmpExtendedDevice` with
`SlmpIndexZ`, `SlmpIndexLz`, or `SlmpIndirect`. Invalid combinations, such as
LZ on a Q/L access profile or an index modifier on `Jn\...`, are rejected
before transport.

### Module buffer access

Use `read_devices_ext()` and `write_devices_ext()` for intelligent module
buffer memory.

| Notation | Description | Example |
| --- | --- | --- |
| `Un\G` | Buffer memory word access | `U3\G100` |
| `Un\HG` | Extended buffer memory word access | `U3E0\HG1000` |

```python
from slmp import SlmpClient, SlmpTarget


with SlmpClient("192.168.250.100", 1025, transport="tcp", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0), plc_profile="melsec:iq-r") as client:
    values = client.read_devices_ext("U3\\G100", 4, bit_unit=False)
    client.write_devices_ext("U3\\G100", [1, 2, 3, 4], bit_unit=False)
    print(values)
```

`Un` is the module number in hexadecimal text, for example `U3` or `U3E0`.

Typed modification example:

```python
from slmp import SlmpExtendedDevice, SlmpIndexZ


device = SlmpExtendedDevice("U3\\D100", SlmpIndexZ(2))
values = client.read_devices_ext(device, 1, bit_unit=False)
```

Extended random-read results retain the full route:

```python
result = client.read_random_ext(word_devices=[r"U3E0\HG0", r"U3E1\HG0"])
print(result.word[r"U3E0\HG0"])
print(result.word[r"U3E1\HG0"])
```

## Monitor, self-test, and Clear Error

Monitor registration and each monitor cycle are separate one-request
operations. Supply the registered Word and DWord counts on every cycle; the
client does not auto-register, retry, or infer counts. Running a cycle before
the PLC has monitor registration sends the cycle request and returns the PLC
response or error unchanged. The combined expected count must be nonzero and
cannot exceed the selected profile's monitor-registration limit.

```python
client.register_monitor_devices(word_devices=["D120"], dword_devices=["D200"])
result = client.run_monitor_cycle(word_points=1, dword_points=1)

echo = client.self_test_loopback(b"A1B2C3D4")
client.clear_error()
```

Self-test accepts only 1–960 ASCII `0-9/A-F` bytes and requires the returned
declared length, actual length, and echo bytes to match exactly. `clear_error`
always sends the fixed command with an empty payload.

### Link direct device access

Use link direct device notation for devices on a CC-Link IE network routed
through the connected PLC.

| Access type | Example |
| --- | --- |
| Word read/write | `J2\SW10`, `J1\W13` |
| Bit read/write | `J1\X10`, `J1\SB10` |

```python
from slmp import SlmpClient, SlmpTarget


with SlmpClient("192.168.250.100", 1025, transport="tcp", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0), plc_profile="melsec:iq-r") as client:
    value = client.read_devices_ext("J2\\SW10", 1, bit_unit=False)
    bits = client.read_devices_ext("J1\\X10", 16, bit_unit=True)
    client.write_devices_ext("J1\\SW14", [2], bit_unit=False)
    client.write_devices_ext("J1\\X11", [True], bit_unit=True)
    print(value, bits)
```

The available link direct device families depend on the PLC route and link
module configuration.

## SLMP response end codes

When the PLC returns a non-zero SLMP end code, the high-level APIs raise `SlmpError`.
Read `end_code` for the PLC response code and `error_info` when the PLC returned the structured error-information block.

```python
from slmp import SlmpError


try:
    value = await read_typed(client, "D100", "U")
    print(f"D100={value}")
except SlmpError as exc:
    if exc.end_code is not None:
        print(f"SLMP end_code=0x{exc.end_code:04X}")
    if exc.error_info is not None:
        print(f"command=0x{exc.error_info.command:04X}")
        print(f"subcommand=0x{exc.error_info.subcommand:04X}")
```

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
from slmp import SlmpConnectionOptions, open_and_connect, read_typed, SlmpTarget


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
    async with await open_and_connect(options) as client:
        value = await read_typed(client, "D100", "U")
        print(f"D100={value}")


asyncio.run(main())
```

## Write a single value

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, read_typed, write_typed, SlmpTarget


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
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
from slmp import SlmpConnectionOptions, open_and_connect, read_named, SlmpTarget


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
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
    read_dwords_single_request,
    read_words_single_request,
)


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
    async with await open_and_connect(options) as client:
        words = await read_words_single_request(client, "D0", 10)
        dwords = await read_dwords_single_request(client, "D200", 4)
        print(f"words={len(words)} dwords={len(dwords)}")


asyncio.run(main())
```

Contiguous helpers issue exactly one request and reject counts above the
protocol limit. If multiple snapshots are acceptable, split them explicitly
in application code so their different acquisition times remain visible.

## Packed bit-device word access

Bit-device families such as `M`, `B`, `X`, and `Y` can be read or written as
packed 16-bit word values. The device code stays the same; the command
subcommand and interpretation unit decide whether the result is one bit per
point or one packed 16-bit value.

If `M1000=1`, `M1001=0`, `M1002=1`, and `M1003=0`, the packed word beginning
at `M1000` is `0x0005`.

| Family | Bit read example | Packed word read example | Address number format |
| --- | --- | --- | --- |
| `M` | `read_named(client, ["M1000:BIT"])` | `read_typed(client, "M1000", "U")` | decimal |
| `B` | `read_named(client, ["B20:BIT"])` | `read_typed(client, "B20", "U")` | hexadecimal |
| `X` | `read_named(client, ["X20:BIT"])` | `read_typed(client, "X20", "U")` | profile-dependent |
| `Y` | `read_named(client, ["Y20:BIT"])` | `read_typed(client, "Y20", "U")` | profile-dependent |

Every semantic device address is interpreted with an exact `plc_profile`.
`DeviceRef(code, number, plc_profile)` therefore stores the profile as part of
the value, and `parse_device(text, plc_profile=...)` requires it explicitly.
A `DeviceRef` created for one profile is rejected by a client configured for a
different profile before any request is sent.

This is especially visible for `X` and `Y`: `melsec:iq-f` uses octal text,
while the other supported profiles use hexadecimal text. For example,
`X10` means numeric address 8 for `melsec:iq-f` and numeric address 16 for
`melsec:iq-r`. Binding the profile prevents a previously parsed address from
silently changing meaning when passed to another client.

The same packed-unit rule applies when writing one word value to a bit-device
group:

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, write_typed, SlmpTarget


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
    async with await open_and_connect(options) as client:
        await write_typed(client, "M1000", "U", 0x0005)


asyncio.run(main())
```

This writes the packed pattern for `M1000..M1015`. Use bit access when you
want individual boolean states; use packed word access when you want one
16-bit snapshot from a bit-device group.

## Bit in word

Use `write_bit_in_word` when a PLC stores flags inside a word register. Use `.n` notation when reading or writing mixed named values.

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, read_named, write_bit_in_word, SlmpTarget


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
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
from slmp import SlmpConnectionOptions, open_and_connect, poll, SlmpTarget


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
    async with await open_and_connect(options) as client:
        index = 0
        async for snapshot in poll(client, ["D100:U", "D200:F", "D50.3"], interval=1.0):
            print(f"snapshot={snapshot}")
            index += 1
            if index >= 3:
                break


asyncio.run(main())
```

## Operational recipes

The repository includes two read-only operational samples for application
shapes that come up after the first connection test.

### Multiple PLC monitoring

Use `samples/multi_plc_monitor.py` when several PLCs should be watched at the
same time. Each PLC runs in its own async task with its own connection and
reconnect loop, so one offline PLC does not block the others.

```powershell
python samples/multi_plc_monitor.py `
  --plc line-a=192.168.250.100,melsec:iq-r,1035,udp `
  --plc line-b=192.168.250.101,melsec:iq-r,1035,udp `
  --tag d100=D100:U `
  --tag temperature=D200:F `
  --cycles 3 `
  --dry-run
```

This sample only calls read helpers. For cable-pull recovery checks, prefer
UDP on the PLC-side UDP port so reconnect behavior is not delayed by TCP socket
cleanup.

### Config-file polling

Use `samples/config_polling.py` when tag lists and PLC endpoints should live
in a config file instead of Python code.

```powershell
python samples/config_polling.py --config samples/config_polling.example.json --dry-run
```

Config files are JSON by default. YAML files are accepted when `PyYAML` is
installed. CSV output is optional and uses long rows:
`timestamp,plc,tag,value`.
Remove `--dry-run` when you are ready to open PLC connections.

```json
{
  "defaults": {
    "transport": "udp",
    "port": 1035,
    "timeout": 3.0,
    "interval": 1.0
  },
  "output": {
    "csv": "config_polling_output.csv"
  },
  "plcs": [
    {
      "name": "line-a",
      "host": "192.168.250.100",
      "plc_profile": "melsec:iq-r",
      "tags": [
        { "name": "d100", "address": "D100:U" },
        { "name": "temperature", "address": "D200:F" }
      ]
    }
  ]
}
```

## Device range catalog

`read_device_range_catalog()` reads live device range bounds from the SD registers for the canonical profile selected on the client. It does not auto-discover the PLC model.
The catalog is for diagnostics and application-layer validation. Normal read/write helpers do not use it to reject addresses by configured upper bound before sending a request.
The source rules for this catalog are maintained in the shared [SLMP device ranges](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/profile-reference/device-ranges/) reference.

```python
import asyncio
from slmp import SlmpConnectionOptions, open_and_connect, SlmpTarget


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
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
from slmp import SlmpConnectionOptions, open_and_connect, read_named, SlmpTarget


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, transport="tcp", plc_profile="melsec:iq-r", default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
    async with await open_and_connect(options) as client:
        values = await read_named(client, ["LCN0:L", "LZ0:D"])
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
Empty named read, write, and polling collections are rejected. Numeric write
values must have the exact documented type and range; values are never
truncated, wrapped, parsed from strings, or converted by truthiness.

`remote_reset` returns after the complete request frame is sent and then
closes the transport. This prevents a possible reset NG response from being
mistaken for the next 3E response. Open a new connection and verify the PLC
state before continuing; the return value confirms transmission, not PLC
execution.
## Traffic statistics

Call `client.traffic_stats()` for an immutable client-lifetime snapshot of `request_count`,
`tx_bytes`, and `rx_bytes`. Complete sends and complete received frames are counted; close and
reconnect do not reset the snapshot.
