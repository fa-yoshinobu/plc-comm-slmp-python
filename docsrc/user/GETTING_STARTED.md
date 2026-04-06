# Getting Started

## Start Here

Use this package when you want the shortest Python path to Mitsubishi SLMP communication through the public high-level API.

Recommended first path:

1. Install `slmp-connect-python`.
2. Set `plc_series` and `frame_type` explicitly.
3. Open one connection with `open_and_connect`.
4. Read one safe `D` word.
5. Write only to a known-safe test word or bit after the first read is stable.

## First PLC Registers To Try

Start with these first:

- `D100`
- `D200:F`
- `D300:L`
- `D50.3`
- `M1000`

Do not start with these:

- module/extension routing
- large chunked reads
- future-tracked families such as `G`, `HG`, `LTS`, `LTC`, `LSTS`, `LSTC`, `LCS`, `LCC`, `LZ`

## Minimal Connection Pattern

```python
from slmp import SlmpConnectionOptions

options = SlmpConnectionOptions(
    host="192.168.250.100",
    port=1025,
    plc_series="iqr",
    frame_type="4e",
)
```

## First Successful Run

Recommended order:

1. `read_typed(client, "D100", "U")`
2. `write_typed(client, "D100", "U", value)` only on a safe test word
3. `read_named(client, ["D100", "D200:F", "D50.3"])`

## Common Beginner Checks

If the first read fails, check these in order:

- correct host and port
- correct frame type
- correct PLC series
- start with `D` instead of a routed, module, or future-tracked family

## Next Pages

- [Supported PLC Registers](./SUPPORTED_REGISTERS.md)
- [Latest Communication Verification](./LATEST_COMMUNICATION_VERIFICATION.md)
- [User Guide](./USER_GUIDE.md)
