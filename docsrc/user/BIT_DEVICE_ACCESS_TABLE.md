# Bit device packed access

This note explains the packed 16-bit behavior used when bit-device families
such as `M`, `B`, `X`, and `Y` are read or written as word values.

For the full device family list, see [Supported registers](SUPPORTED_REGISTERS.md).

## Key rule

The device code stays the same. What changes is:

1. command
2. subcommand
3. interpretation unit

For bit devices:

- normal bit read returns one value per bit
- normal word read returns one packed 16-bit value per point
- block bit read also returns one packed 16-bit value per point

## Packed 16-bit meaning

If the device state is:

- `M1000 = 1`
- `M1001 = 0`
- `M1002 = 1`
- `M1003 = 0`

then the packed value beginning at `M1000` is `0x0005`.

The same rule applies to `B`, `X`, and `Y`.

## Device group notes

| Family | Number format | Example start |
| --- | --- | --- |
| `M` | decimal | `M1000` |
| `B` | hexadecimal | `B20` |
| `X` | profile-dependent | `X20` / `X100` |
| `Y` | profile-dependent | `Y20` / `Y100` |

For communication, this library does not auto-detect the PLC profile for
`X` / `Y`. Set canonical `plc_profile` explicitly.

`melsec:iq-f` uses octal text for `X` and `Y`; every other profile uses
hexadecimal text. See [Supported registers](SUPPORTED_REGISTERS.md) for the
current addressing notes.

## Access mapping

| Family | Operation | Command | High-level example | Point meaning | Returned value |
| --- | --- | --- | --- | --- | --- |
| `M` | bit read | `0401` | `read_named(client, ["M1000:BIT", "M1001:BIT", "M1002:BIT", "M1003:BIT"])` | `4` bit devices | `{"M1000:BIT": True, ...}` |
| `M` | packed word read | `0401` | `read_typed(client, "M1000", "U")` | `1` packed 16-bit unit | `0x0005` |
| `B` | bit read | `0401` | `read_named(client, ["B20:BIT", "B21:BIT", "B22:BIT", "B23:BIT"])` | `4` bit devices | `{"B20:BIT": True, ...}` |
| `B` | packed word read | `0401` | `read_typed(client, "B20", "U")` | `1` packed 16-bit unit | `0x0005` |
| `X` | bit read | `0401` | `read_named(client, ["X20:BIT", "X21:BIT", "X22:BIT", "X23:BIT"])` | `4` bit devices | `{"X20:BIT": True, ...}` |
| `X` | packed word read | `0401` | `read_typed(client, "X20", "U")` | `1` packed 16-bit unit | `0x0005` |
| `Y` | bit read | `0401` | `read_named(client, ["Y20:BIT", "Y21:BIT", "Y22:BIT", "Y23:BIT"])` | `4` bit devices | `{"Y20:BIT": True, ...}` |
| `Y` | packed word read | `0401` | `read_typed(client, "Y20", "U")` | `1` packed 16-bit unit | `0x0005` |

## Practical interpretation

For `M/B/X/Y`, block read does not mean "boolean array block" in this library.

Instead:

- `bit_blocks=[("M1000", 1)]` means one packed 16-bit unit
- `bit_blocks=[("M1000", 2)]` means two packed 16-bit units
- `bit_blocks=[("M1000", 705)]` means `705` packed 16-bit units, not
  `705` individual bits

## Write-side reminder

The same packed-unit rule applies when you write one word value to a bit-device
group:

```python
import asyncio

from slmp import SlmpConnectionOptions, open_and_connect, write_typed


async def main() -> None:
    options = SlmpConnectionOptions(host="192.168.250.100", port=1025, plc_profile="melsec:iq-r")
    async with await open_and_connect(options) as client:
        await write_typed(client, "M1000", "U", 0x0005)


asyncio.run(main())
```

This writes the packed pattern for `M1000..M1015`.

## When to use which form

- Use bit read when you want individual bit states.
- Use word read when you want one packed 16-bit snapshot from a bit device.
- Use block bit read when you want multiple packed 16-bit snapshots in one
  `0406` request.

## Related documents

- [Supported registers](SUPPORTED_REGISTERS.md)
- [Usage guide](USAGE_GUIDE.md)
- [Extended device access](EXTENDED_DEVICE_ACCESS.md)
