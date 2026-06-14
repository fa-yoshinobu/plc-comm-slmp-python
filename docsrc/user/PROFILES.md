# Profiles

Use one canonical `plc_profile` string for each connection. The profile selects the SLMP frame type, access mode, string address family, and device-range catalog family.

## Profiles

| Profile string | Hardware | Frame | Mode | Notes |
| --- | --- | --- | --- | --- |
| `melsec:iq-f` | MELSEC iQ-F / FX5 | 3E | Legacy `ql` | Address profile `melsec:iq-f`; range profile `melsec:iq-f`; `X`/`Y` text is octal. |
| `melsec:iq-r` | MELSEC iQ-R | 4E | iQR `iqr` | Address profile `melsec:iq-r`; range profile `melsec:iq-r`; `X`/`Y` text is hexadecimal. |
| `melsec:iq-l` | MELSEC iQ-L | 4E | iQR `iqr` | Address profile `melsec:iq-l`; range profile `melsec:iq-l`; currently uses iQ-R-compatible address rules. |
| `melsec:mx-f` | MELSEC MX-F-compatible endpoint | 4E | iQR `iqr` | Address profile `melsec:mx-f`; range profile `melsec:mx-f`. |
| `melsec:mx-r` | MELSEC MX-R-compatible endpoint | 4E | iQR `iqr` | Address profile `melsec:mx-r`; range profile `melsec:mx-r`. |
| `melsec:qcpu` | MELSEC-Q CPU | 3E | Legacy `ql` | Address profile `melsec:qcpu`; range profile `melsec:qcpu`. |
| `melsec:lcpu` | MELSEC-L CPU | 3E | Legacy `ql` | Address profile `melsec:lcpu`; range profile `melsec:lcpu`. |
| `melsec:qnu` | MELSEC QnU CPU | 3E | Legacy `ql` | Address profile `melsec:qnu`; range profile `melsec:qnu`. |
| `melsec:qnudv` | MELSEC QnUDV CPU | 3E | Legacy `ql` | Address profile `melsec:qnudv`; range profile `melsec:qnudv`. |

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

## Profile-specific cautions

| Profile | Caution |
| --- | --- |
| `melsec:iq-f` | Frame 3E, legacy mode. `DX` and `DY` are not valid. `X`/`Y` addressing is octal. |
| `melsec:iq-r` | Frame 4E, iQR mode. `X`/`Y` addressing is hexadecimal. |
| `melsec:iq-l` | Frame 4E, iQR mode. Address parsing follows iQ-R rules while the range catalog uses iQ-L rules. |
| `melsec:qcpu` | Frame 3E, legacy mode. |
| `melsec:lcpu` | Frame 3E, legacy mode. |
| `melsec:qnu` | Frame 3E, legacy mode. |
| `melsec:qnudv` | Frame 3E, legacy mode. |
| `melsec:mx-f` | Frame 4E, iQR mode with MX-F range rules. |
| `melsec:mx-r` | Frame 4E, iQR mode with MX-R range rules. |
