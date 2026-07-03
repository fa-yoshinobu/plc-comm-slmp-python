# Profiles

Use one canonical profile in `plc_profile` for each connection. The profile selects the SLMP frame type, access mode, and device-range catalog.

For cross-profile capability and device-range details, see the [SLMP Profile Reference](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/profile-reference/).

## Profiles

| Canonical profile | Human label | Frame | Mode | Notes |
| --- | --- | --- | --- | --- |
| `melsec:iq-f` | MELSEC iQ-F | 3E | Legacy `ql` | `X`/`Y` text is octal. |
| `melsec:iq-r` | MELSEC iQ-R | 4E | iQR `iqr` | `X`/`Y` text is hexadecimal. |
| `melsec:iq-l` | MELSEC iQ-L | 4E | iQR `iqr` | Use for MELSEC iQ-L targets. |
| `melsec:mx-f` | MELSEC MX-F | 4E | iQR `iqr` | Use for MELSEC MX-F targets. |
| `melsec:mx-r` | MELSEC MX-R | 4E | iQR `iqr` | Use for MELSEC MX-R targets. |
| `melsec:qcpu` | MELSEC QCPU | 3E | Legacy `ql` | Q CPU profile. Use direct or random device commands for normal access. |
| `melsec:lcpu` | MELSEC LCPU | 3E | Legacy `ql` | Legacy L CPU profile. |
| `melsec:qnu` | MELSEC QnU | 3E | Legacy `ql` | QnU profile. Use direct or random device commands for normal access. |
| `melsec:qnudv` | MELSEC QnUDV | 3E | Legacy `ql` | QnUDV profile. Use direct or random device commands for normal access. |

## How to select

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
