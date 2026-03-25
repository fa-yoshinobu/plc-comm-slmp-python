# SLMP Connect Python User Guide

Efficient SLMP (MC Protocol) communication library for Mitsubishi PLCs.

## Installation

```bash
pip install slmp-connect
```

## Quick Start

```python
from slmp import SlmpClient
from slmp.constants import FrameType, PLCSeries

# iQ-R series (R04/R08/R16…) → FRAME_4E + IQR
# Q/L series                  → FRAME_3E + QL
client = SlmpClient(
    host="192.168.1.10",
    port=1025,
    frame_type=FrameType.FRAME_4E,
    plc_series=PLCSeries.IQR,
)

with client:
    # Read 1 word from D100
    data = client.read_devices("D100", 1)
    print(f"D100: {data[0]}")

    # Read 4 bits from M0
    bits = client.read_devices("M0", 4, bit_unit=True)
    print(f"M0..M3: {bits}")

    # Write a value to D200
    client.write_devices("D200", [42])
```

!!! note "How to choose frame_type / plc_series"
    | PLC Family | frame_type | plc_series |
    |---|---|---|
    | iQ-R (e.g. R04CPU) | `FRAME_4E` | `PLCSeries.IQR` |
    | Q / L Series | `FRAME_3E` | `PLCSeries.QL` |
    | If unknown | — | — |

    If unknown, you can auto-detect using `resolve_profile()` below.

### Profile Auto-Detection (sync)

```python
from slmp import SlmpClient

client = SlmpClient(host="192.168.1.10", port=1025)
rec = client.resolve_profile()
print(f"detected: frame={rec.frame_type}, series={rec.plc_series}, confident={rec.is_confident}")

with client:
    data = client.read_devices("D100", 1)
    print(f"D100: {data[0]}")
```

### Profile Auto-Detection + Connect (async)

```python
import asyncio
from slmp import open_and_connect

async def main():
    # Auto-detect frame_type / plc_series and connect
    async with await open_and_connect("192.168.1.10", port=1025) as client:
        data = await client.read_devices("D100", 1)
        print(f"D100: {data[0]}")

asyncio.run(main())
```

---

## Core Concepts

### Device Address Strings

Devices are specified using strings.

```python
client.read_devices("D100", 10)              # Read 10 words from D100
client.read_devices("M0", 8, bit_unit=True)  # Read 8 bits from M0
client.write_devices("D200", [0, 1, 2])      # Write to D200..D202
```

Example supported devices: `D`, `W`, `R`, `ZR`, `M`, `L`, `B`, `X`, `Y`, `SM`, `SD`, etc.
See `slmp.core.DEVICE_CODES` for a full list of devices.

### Word vs Bit

- `bit_unit=False` (default): Read/write in word units. Returns `list[int]`.
- `bit_unit=True`: Read/write bit devices (M, X, Y, etc.) in bit units. Returns `list[int]` (0 or 1).

### Target Specification

You can target specific CPUs, such as in multiple CPU configurations.

```python
from slmp import SlmpTarget

target = SlmpTarget(module_io="MULTIPLE_CPU_1")
data = client.read_devices("D100", 1, target=target)
```

---

## Typed Read / Write

`read_devices` returns raw 16-bit words. Use utility functions for float32 or signed integers. Both sync and async clients are supported.

| dtype | Type | Words |
|---|---|---|
| `"U"` | unsigned 16-bit int | 1 |
| `"S"` | signed 16-bit int | 1 |
| `"D"` | unsigned 32-bit int | 2 |
| `"L"` | signed 32-bit int | 2 |
| `"F"` | float32 | 2 |

### read_typed / read_typed_sync — Read one device with type conversion

```python
# async
from slmp.utils import read_typed
f = await read_typed(client, "D100", "F")   # float32

# sync
from slmp.utils import read_typed_sync
f = read_typed_sync(client, "D100", "F")
```

### write_typed / write_typed_sync — Write one device with type conversion

```python
from slmp.utils import write_typed_sync
write_typed_sync(client, "D100", "F", 3.14)
write_typed_sync(client, "D102", "L", -50000)
```

### read_named / read_named_sync — Batch read using address strings

Read multiple devices at once using type codes embedded in addresses.

```python
# async
from slmp.utils import read_named
result = await read_named(client, ["D100", "D101:F", "D102:S", "D0.3"])

# sync
from slmp.utils import read_named_sync
result = read_named_sync(client, ["D100", "D101:F", "D102:S", "D0.3"])
# result = {"D100": 42, "D101:F": 3.14, "D102:S": -1, "D0.3": True}
```

### write_named / write_named_sync — Batch write using address strings

Write multiple devices at once using the same notation as `read_named`.

```python
# async
from slmp.utils import write_named
await write_named(client, {
    "D100": 42,
    "D101:F": 3.14,
    "D0.3": True,
})

# sync
from slmp.utils import write_named_sync
write_named_sync(client, {
    "D100": 42,
    "D101:F": 3.14,
    "D0.3": True,
})
```

---

## Random / Block Read

Read non-contiguous devices in a single command. More efficient than repeating `read_devices`.

### Random Read

```python
from slmp import DeviceRef

result = client.read_random(
    word_devices=["D100", "D200", "W10"],
    dword_devices=["D300"],  # Read as 2-word value
)
# result.word  = {"D100": 1, "D200": 2, "W10": 3}
# result.dword = {"D300": 100000}
```

### Block Read

Read multiple contiguous blocks in a single command.

```python
result = client.read_block(
    word_blocks=[("D100", 10), ("W0", 5)],
    bit_blocks=[("M0", 16)],
)
# result.word_blocks[0].device = "D100", .values = [...]
# result.bit_blocks[0].device  = "M0",  .values = [...]
```

---

## Polling (poll / poll_sync)

Continuously read devices at a fixed interval. Supports the same address notation as `read_named`.

```python
# async
import asyncio
from slmp.utils import poll

async def main():
    async with await open_and_connect("192.168.1.10") as client:
        async for snapshot in poll(client, ["D100", "D101:F", "M0.0"], interval=1.0):
            print(snapshot)

asyncio.run(main())

# sync
from slmp.utils import poll_sync
from slmp import SlmpClient

with SlmpClient("192.168.1.10", 1025) as client:
    for snapshot in poll_sync(client, ["D100", "D101:F", "M0.0"], interval=1.0):
        print(snapshot)
        # {"D100": 42, "D101:F": 3.14, "M0.0": True}
```

Outputs snapshots every second until stopped with Ctrl+C.

---

## Sharing a single connection across multiple coroutines (QueuedAsyncSlmpClient)

If multiple coroutines (e.g., background poller and foreground writer) need to use the same connection, wrap it in `QueuedAsyncSlmpClient`. Communication is serialized via an internal lock.

```python
import asyncio
from slmp import AsyncSlmpClient, QueuedAsyncSlmpClient

async def poller(client, stop_event):
    while not stop_event.is_set():
        data = await client.read_devices("D100", 1)
        print(f"[poll] D100={data[0]}")
        await asyncio.sleep(1.0)

async def main():
    inner = AsyncSlmpClient("192.168.1.10", 1025)
    client = QueuedAsyncSlmpClient(inner)
    stop = asyncio.Event()

    async with client:
        poll_task = asyncio.create_task(poller(client, stop))
        await asyncio.sleep(5)
        stop.set()
        await poll_task

asyncio.run(main())
```

---

## async Advantages

`AsyncSlmpClient` is asyncio-based and does not block the event loop while waiting for PLC responses. While multiple requests to the same connection are serialized, **simultaneous connections to multiple PLCs** overlap in time, significantly reducing total processing time.

```python
# Read from multiple PLCs simultaneously
results = await asyncio.gather(
    read_one_plc("192.168.1.10", 1025),
    read_one_plc("192.168.1.11", 1025),
)
```

---

## Error Handling

### Exception Types

| Exception | Condition |
|---|---|
| `SlmpError` | PLC returned `end_code != 0` |
| `ValueError` | Invalid device name or argument format |
| `TimeoutError` | Response timeout |
| `ConnectionRefusedError` | Connection refused (wrong port or IP) |
| `OSError` | Other network failures |

```python
from slmp import SlmpClient
from slmp.errors import SlmpError

with SlmpClient("192.168.1.10", 1025) as client:
    try:
        data = client.read_devices("D100", 1)
    except SlmpError as e:
        print(f"PLC error: end_code=0x{e.end_code:04X}")
    except TimeoutError:
        print("Connection timeout — Check IP address and port number")
    except ConnectionRefusedError:
        print("Connection refused — Check port number and SLMP settings on the PLC")
```

### Get raw response without raising exceptions

Passing `raise_on_error=False` returns an `SlmpResponse` instead of raising an `SlmpError`.

```python
resp = client.raw_command(0x0401, subcommand=0x0002, payload=b"...", raise_on_error=False)
print(f"end_code: 0x{resp.end_code:04X}")
```

See the [Error Codes Guide](ERROR_CODES.md) for common end codes.

### Common Connection Failures and Solutions

| Symptom | Possible Cause | Solution |
|---|---|---|
| `ConnectionRefusedError` | Wrong port number | Check port in "SLMP Communication Setting" of GX Works3 |
| `TimeoutError` | Wrong IP or unreachable route | Verify connectivity with `ping` |
| `SlmpError` end_code=`0xC059` | `frame_type` / `plc_series` mismatch | Auto-detect using `resolve_profile()` or change the series |
| Data is clearly incorrect | Wrong `plc_series` (IQR vs QL) | Device encoding varies by series; please verify |

---

## Verification with GX Simulator 3

If you don't have a physical PLC, you can test on your local PC using GX Simulator 3 (included with GX Works3).

**Connection Settings**

| Item | Value |
|---|---|
| host | `127.0.0.1` |
| port | `5010` (GX Simulator 3 default) |
| frame_type | `FRAME_3E` |
| plc_series | `PLCSeries.QL` |

```python
client = SlmpClient(
    host="127.0.0.1",
    port=5010,
    frame_type=FrameType.FRAME_3E,
    plc_series=PLCSeries.QL,
)
```

!!! note
    GX Simulator 3 may respond with 3E frames even in iQ-R simulation. If you cannot connect, use `resolve_profile()` to auto-detect the profile.

---

## Performance Tips

!!! tip "Reuse connections"
    Reuse `SlmpClient` instances across multiple requests. Establishing a new TCP connection every time is very slow.

!!! tip "Use read_words for large reads"
    Continuous reads exceeding 960 words are automatically split by `read_words(allow_split=True)`.

    ```python
    # async
    from slmp.utils import read_words
    values = await read_words(client, "D0", 2000, allow_split=True)

    # sync
    from slmp.utils import read_words_sync
    values = read_words_sync(client, "D0", 2000, allow_split=True)
    ```

---

## API Overview

See the [API Reference](../api/client.md) for details.
