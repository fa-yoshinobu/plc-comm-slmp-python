# Getting Started

## Start Here

Use this package when you want the shortest Python path to Mitsubishi SLMP communication through the public high-level API.

Recommended first path:

1. Install `slmp-connect-python`.
2. Set canonical `plc_family`.
3. Let the library derive the fixed frame type, access profile, and range rules.
4. Open one connection with `open_and_connect`.
5. Read one safe `D` word.
6. Write only to a known-safe test word or bit after the first read is stable.

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
    plc_family="iq-f",
    port=1025,
)
```

These settings mean different things:

- `plc_family`: the only high-level PLC selector for application code
- derived `frame_type`: fixed by `plc_family`
- derived `access_profile`: fixed by `plc_family`
- derived string/range rules: fixed by `plc_family`

Current fixed mapping:

| `plc_family` | `frame_type` | `access_profile` | `X` / `Y` text | range family |
| --- | --- | --- | --- | --- |
| `iq-f` | `3e` | `ql` | octal | `iq-f` |
| `iq-r` | `4e` | `iqr` | hexadecimal | `iq-r` |
| `iq-l` | `4e` | `iqr` | hexadecimal | `iq-r` |
| `mx-f` | `4e` | `iqr` | hexadecimal | `mx-f` |
| `mx-r` | `4e` | `iqr` | hexadecimal | `mx-r` |
| `qcpu` | `3e` | `ql` | hexadecimal | `qcpu` |
| `lcpu` | `3e` | `ql` | hexadecimal | `lcpu` |
| `qnu` | `3e` | `ql` | hexadecimal | `qnu` |
| `qnudv` | `3e` | `ql` | hexadecimal | `qnudv` |

This library does not auto-detect the public helper profile.
Short aliases are rejected.

## First Successful Run

Recommended order:

1. `read_typed(client, "D100", "U")`
2. `write_typed(client, "D100", "U", value)` only on a safe test word
3. `read_named(client, ["D100", "D200:F", "D50.3"])`

## Common Beginner Checks

If the first read fails, check these in order:

- correct host and port
- correct `plc_family`
- start with `D` instead of a routed, module, or future-tracked family

## Next Pages

- [Supported PLC Registers](./SUPPORTED_REGISTERS.md)
- [Latest Communication Verification](./LATEST_COMMUNICATION_VERIFICATION.md)
- [User Guide](./USER_GUIDE.md)
