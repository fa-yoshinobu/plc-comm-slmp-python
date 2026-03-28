# SLMP Python User Guide

This guide documents the recommended high-level helper APIs.

For normal application code, start here instead of the low-level protocol methods.

## Recommended Entry Points

### Async connection with explicit profile selection

```python
import asyncio

from slmp import AsyncSlmpClient, read_named


async def main() -> None:
    async with AsyncSlmpClient(
        "192.168.250.100",
        port=1025,
        plc_series="iqr",
        frame_type="4e",
    ) as client:
        snapshot = await read_named(client, ["D100", "D200:F", "D50.3"])
        print(snapshot)


asyncio.run(main())
```

Use this when:

- you are writing an async application
- you already know the target frame/profile pair
- you want the shortest path to `read_named`, `write_typed`, and `poll`

### Async shared connection

```python
import asyncio

from slmp import AsyncSlmpClient, QueuedAsyncSlmpClient, read_named


async def main() -> None:
    inner = AsyncSlmpClient(
        "192.168.250.100",
        port=1025,
        plc_series="iqr",
        frame_type="4e",
    )
    async with QueuedAsyncSlmpClient(inner) as client:
        first = await read_named(client, ["D100", "D200:F"])
        second = await read_named(client, ["D300", "D50.3"])
        print(first)
        print(second)


asyncio.run(main())
```

Use this when multiple coroutines share one PLC connection.

### Sync application code

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

For sync code, the recommended pattern is:

1. open a `SlmpClient`
2. use the `*_sync` helper functions

## High-Level Helper Set

### `read_typed` / `read_typed_sync`

Read one logical value with type conversion.

Supported dtype values:

| dtype | Meaning | Words |
| --- | --- | --- |
| `U` | unsigned 16-bit | 1 |
| `S` | signed 16-bit | 1 |
| `D` | unsigned 32-bit | 2 |
| `L` | signed 32-bit | 2 |
| `F` | float32 | 2 |

```python
value_u = await read_typed(client, "D100", "U")
value_f = await read_typed(client, "D200", "F")
value_l = await read_typed(client, "D300", "L")
```

### `write_typed` / `write_typed_sync`

Write one logical value with type conversion.

```python
await write_typed(client, "D100", "U", 1234)
await write_typed(client, "D200", "F", 3.14)
await write_typed(client, "D300", "L", -1000)
```

### `write_bit_in_word` / `write_bit_in_word_sync`

Set or clear one bit inside a word device.

```python
await write_bit_in_word(client, "D50", bit_index=3, value=True)
await write_bit_in_word(client, "D50", bit_index=3, value=False)
```

Use this when a PLC stores flags inside a control word and you need to toggle only one bit.

### `read_named` / `read_named_sync`

Read multiple values with one high-level call.

Address notation:

| Form | Meaning |
| --- | --- |
| `D100` | one unsigned 16-bit word |
| `D200:S` | signed 16-bit |
| `D300:D` | unsigned 32-bit |
| `D400:L` | signed 32-bit |
| `D500:F` | float32 |
| `D50.3` | bit 3 inside D50 |

```python
snapshot = await read_named(
    client,
    [
        "D100",
        "D200:S",
        "D300:D",
        "D400:L",
        "D500:F",
        "D50.3",
    ],
)
```

Use `.bit` notation only with word devices such as `D50.3`.
Address bit devices directly as `M1000`, `M1001`, `X20`, or `Y20`.

Long-device notes for the high-level helper layer:

- `LTN`, `LSTN`, and `LCN` default to 32-bit current-value access
- `LTS`, `LTC`, `LSTS`, and `LSTC` are resolved through the corresponding `LTN` / `LSTN` helper-backed 4-word decode instead of direct state reads

This is the most useful helper for dashboards, logging, and application polling.

### `write_named` / `write_named_sync`

Write multiple logical values using the same address notation.

```python
await write_named(
    client,
    {
        "D100": 42,
        "D200:S": -1,
        "D300:D": 123456,
        "D400:L": -5000,
        "D500:F": 1.25,
        "D50.3": True,
    },
)
```

Plain `LTN`, `LSTN`, and `LCN` addresses are treated as 32-bit current values in the high-level write helper too.

### `read_words` / `read_words_sync`

Read a contiguous word range.

```python
words = await read_words(client, "D0", 10)
large_words = await read_words(client, "D0", 1000, allow_split=True)
```

Use `allow_split=True` when the requested length exceeds one SLMP request.

### `read_dwords` / `read_dwords_sync`

Read contiguous 32-bit values.

```python
dwords = await read_dwords(client, "D200", 8)
large_dwords = await read_dwords(client, "D200", 200, allow_split=True)
```

### `poll` / `poll_sync`

Yield repeated snapshots at a fixed interval.

```python
async for snapshot in poll(client, ["D100", "D200:F", "D50.3"], interval=1.0):
    print(snapshot)
```

Sync variant:

```python
for snapshot in poll_sync(client, ["D100", "D200:F", "D50.3"], interval=1.0):
    print(snapshot)
```

## Practical Example Sets

### Example 1: process values

```python
snapshot = await read_named(
    client,
    [
        "D100:F",   # temperature
        "D102:F",   # pressure
        "D200",     # recipe number
        "D50.0",    # run flag
        "D50.1",    # alarm flag
    ],
)
```

### Example 2: recipe download

```python
await write_named(
    client,
    {
        "D100": 10,
        "D101": 20,
        "D102": 30,
        "D200:F": 12.5,
        "D202:F": 6.75,
    },
)
```

### Example 3: large historian read

```python
history_words = await read_words(client, "D1000", 1200, allow_split=True)
history_dwords = await read_dwords(client, "D2000", 240, allow_split=True)
```

### Example 4: one shared async connection

```python
inner = AsyncSlmpClient("192.168.250.100", port=1025, plc_series="iqr", frame_type="4e")
async with QueuedAsyncSlmpClient(inner) as client:
    a = await read_named(client, ["D100", "D200:F"])
    b = await read_named(client, ["D300", "D50.3"])
```

## Sample Programs

The most complete examples are:

- `samples/high_level_sync.py`
- `samples/high_level_async.py`

They are designed to be directly runnable and syntax-check clean.

Run them from the repository root:

```powershell
python samples/high_level_sync.py --host 192.168.250.100 --port 1025 --series iqr
python samples/high_level_async.py --host 192.168.250.100 --port 1025 --series iqr --frame-type 4e
```

See also:

- [Samples](SAMPLES.md)
- [Error Codes](ERROR_CODES.md)
