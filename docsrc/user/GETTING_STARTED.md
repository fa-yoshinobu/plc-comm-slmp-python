# Getting Started

## Start Here

Use this package when you want the shortest Python path to Mitsubishi SLMP communication through the public high-level API.

Recommended first path:

1. Install `slmp-connect-python`.
2. Set the communication profile explicitly: `frame_type` and `plc_series`.
3. If you use `X` / `Y` string addresses, set `device_family` explicitly too.
4. If you read the device-range catalog, choose the explicit range `family`.
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
    device_family="iq-f",
)
```

These settings mean different things:

- `frame_type`: SLMP frame envelope such as `3e` or `4e`
- `plc_series`: communication/access profile such as `ql` or `iqr`
- `device_family`: address family for string parsing such as `iq-f`, `qcpu`, or `qnudv`

If you will access `X` / `Y` by string address, set `device_family` explicitly.
If you will read the device-range catalog, pass the matching explicit `family` to `read_device_range_catalog_for_family(...)`.
This library does not auto-detect either one.
Only canonical family values are accepted: `iq-f`, `iq-r`, `mx-f`, `mx-r`, `qcpu`, `lcpu`, `qnu`, `qnudv`.

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
