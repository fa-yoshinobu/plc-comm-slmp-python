# PLC profiles

Use one canonical profile in `plc_profile` for each connection. The profile selects the SLMP frame type, access mode, and device-range catalog.
Use `display_name(plc_profile)` for UI labels. Store the canonical profile
string from `plc_profile_canonical_name(plc_profile)`, not the display name.
The older `plc_profile_label(plc_profile)` name remains as a compatibility
alias. Use
`device_range_model_label(plc_profile)` only for the short model value in a
device-range catalog. `available_plc_profiles()` returns profiles accepted by
the standard connection helpers and excludes the base-only `melsec:qcpu`.

For cross-profile capability and device-range details, see the [SLMP Profile Reference](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/profile-reference/).

## Profiles

| Canonical profile | Display name | Frame | Mode | Notes |
| --- | --- | --- | --- | --- |
| `melsec:iq-f` | MELSEC iQ-F (built-in) | 3E | Legacy `ql` | `X`/`Y` text is octal. |
| `melsec:iq-r` | MELSEC iQ-R (built-in) | 4E | iQR `iqr` | `X`/`Y` text is hexadecimal. |
| `melsec:iq-r:rj71en71` | MELSEC iQ-R (RJ71EN71) | 4E | iQR `iqr` | Ethernet-unit profile using iQ-R address rules. |
| `melsec:iq-l` | MELSEC iQ-L (built-in) | 4E | iQR `iqr` | Use for MELSEC iQ-L targets. |
| `melsec:mx-f` | MELSEC MX-F (built-in) | 4E | iQR `iqr` | Use for MELSEC MX-F targets. |
| `melsec:mx-r` | MELSEC MX-R (built-in) | 4E | iQR `iqr` | Use for MELSEC MX-R targets. |
| `melsec:lcpu` | MELSEC-L (built-in) | 3E | Legacy `ql` | Legacy L CPU profile. |
| `melsec:lcpu:lj71e71-100` | MELSEC-L (LJ71E71-100) | 4E | Legacy `ql` | Ethernet-unit profile. |
| `melsec:qnu` | MELSEC QnU (built-in) | 3E | Legacy `ql` | QnU profile. Use direct or random device commands for normal access. |
| `melsec:qnu:qj71e71-100` | MELSEC QnU (QJ71E71-100) | 4E | Legacy `ql` | Ethernet-unit profile. |
| `melsec:qnudv` | MELSEC QnUDV (built-in) | 3E | Legacy `ql` | QnUDV profile. Use direct or random device commands for normal access. |
| `melsec:qnudv:qj71e71-100` | MELSEC QnUDV (QJ71E71-100) | 4E | Legacy `ql` | Ethernet-unit profile. |
| `melsec:qcpu:qj71e71-100` | MELSEC-Q (QJ71E71-100) | 4E | Legacy `ql` | Ethernet-unit profile. |

`melsec:qcpu` is base-only and remains as an internal profile for QCPU address and device-range behavior, but it is not a selectable connection profile. Use `melsec:qcpu:qj71e71-100` for QCPU Ethernet-unit communication.

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
