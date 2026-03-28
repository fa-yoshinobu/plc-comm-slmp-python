# Bit Device Access Table

This note explains how bit-device families such as `M`, `B`, `X`, and `Y` behave across the main read forms used in this project.

## Key Rule

The device code stays the same. What changes is:

1. command
2. subcommand
3. interpretation unit

For bit devices:

- normal bit read returns one value per bit
- normal word read returns one packed 16-bit value per point
- block bit read also returns one packed 16-bit value per point

## Packed 16-Bit Meaning

If the device state is:

- `M1000 = 1`
- `M1001 = 0`
- `M1002 = 1`
- `M1003 = 0`

then the packed value beginning at `M1000` is `0x0005`.

The same rule applies to `B`, `X`, and `Y`.

## Device Family Notes

| Family | Number Format | Example Start |
|---|---|---|
| `M` | decimal | `M1000` |
| `B` | hexadecimal | `B20` |
| `X` | hexadecimal | `X20` |
| `Y` | hexadecimal | `Y20` |

## Access Mapping

| Family | Operation | Command | High-Level Example | Point Meaning | Returned Value |
|---|---|---|---|---|---|
| `M` | bit read | `0401` | `read_named(client, ["M1000", "M1001", "M1002", "M1003"])` | `4` bit devices | `{"M1000": True, ...}` |
| `M` | packed word read | `0401` | `read_typed(client, "M1000", "U")` | `1` packed 16-bit unit | `0x0005` |
| `B` | bit read | `0401` | `read_named(client, ["B20", "B21", "B22", "B23"])` | `4` bit devices | `{"B20": True, ...}` |
| `B` | packed word read | `0401` | `read_typed(client, "B20", "U")` | `1` packed 16-bit unit | `0x0005` |
| `X` | bit read | `0401` | `read_named(client, ["X20", "X21", "X22", "X23"])` | `4` bit devices | `{"X20": True, ...}` |
| `X` | packed word read | `0401` | `read_typed(client, "X20", "U")` | `1` packed 16-bit unit | `0x0005` |
| `Y` | bit read | `0401` | `read_named(client, ["Y20", "Y21", "Y22", "Y23"])` | `4` bit devices | `{"Y20": True, ...}` |
| `Y` | packed word read | `0401` | `read_typed(client, "Y20", "U")` | `1` packed 16-bit unit | `0x0005` |

## Practical Interpretation

For `M/B/X/Y`, block read does not mean "boolean array block" in this library.

Instead:

- `bit_blocks=[("M1000", 1)]` means one packed 16-bit unit
- `bit_blocks=[("M1000", 2)]` means two packed 16-bit units
- `bit_blocks=[("M1000", 705)]` means `705` packed 16-bit units, not `705` individual bits

## Write-Side Reminder

The same packed-unit rule applies when you write one word value to a bit-device family:

```python
await write_typed(client, "M1000", "U", 0x0005)
```

This writes the packed pattern for `M1000..M1015`.

## When To Use Which Form

- Use bit read when you want individual bit states.
- Use word read when you want one packed 16-bit snapshot from a bit device.
- Use block bit read when you want multiple packed 16-bit snapshots in one `0406` request.

---

## Supported Device Code Reference

Comprehensive list of device codes accepted by the parser. Actual availability depends on PLC model and firmware.

### Bit Devices

Commonly addressed through `read_named`, `write_named`, `read_typed`, and `write_typed`.

| Symbol | Device Name | Address Base | Notes |
|--------|-------------|-------------|-------|
| SM | Special relay | Decimal | |
| X | Input relay | Hex | |
| Y | Output relay | Hex | |
| M | Internal relay | Decimal | |
| L | Latch relay | Decimal | |
| F | Annunciator | Decimal | |
| V | Edge relay | Decimal | |
| B | Link relay | Hex | |
| SB | Link special relay | Hex | |
| DX | Direct input | Hex | |
| DY | Direct output | Hex | |
| TS | Timer contact | Decimal | |
| TC | Timer coil | Decimal | |
| STS | Retentive timer contact | Decimal | |
| STC | Retentive timer coil | Decimal | |
| CS | Counter contact | Decimal | |
| CC | Counter coil | Decimal | |
| LTS | Long timer contact | Decimal | iQ-R |
| LTC | Long timer coil | Decimal | iQ-R |
| LSTS | Long retentive timer contact | Decimal | iQ-R |
| LSTC | Long retentive timer coil | Decimal | iQ-R |
| LCS | Long counter contact | Decimal | iQ-R |
| LCC | Long counter coil | Decimal | iQ-R |

> `S` (step relay) is present in the device code table but is intentionally disabled.

### Word Devices

Accessed via `read_words()` / `write_words()`.

| Symbol | Device Name | Address Base | Notes |
|--------|-------------|-------------|-------|
| SD | Special register | Decimal | |
| D | Data register | Decimal | |
| W | Link register | Hex | |
| SW | Link special register | Hex | |
| TN | Timer current value | Decimal | |
| STN | Retentive timer current value | Decimal | |
| CN | Counter current value | Decimal | |
| Z | Index register | Decimal | |
| LZ | Long index register | Decimal | iQ-R |
| R | File register | Decimal | |
| ZR | File register (extended) | Decimal | |
| RD | Refresh data register | Decimal | |
| LTN | Long timer current value | Decimal | iQ-R; prefer `read_long_timer()` |
| LSTN | Long retentive timer current value | Decimal | iQ-R; prefer `read_long_retentive_timer()` |
| LCN | Long counter current value | Decimal | iQ-R |

---

## Long Timer / Retentive Timer Helpers (iQ-R)

These helpers read device data in 4-word units (32-bit current value + 32-bit set value) and return `LongTimerResult` objects.

```python
results = client.read_long_timer(head_no=0, points=4)
for r in results:
    print(r.current_value, r.set_value, r.contact, r.coil)
```

| Method | Reads | Returns |
|--------|-------|---------|
| `read_long_timer(head_no, points)` | LTN | `list[LongTimerResult]` with `.current_value`, `.set_value`, `.contact` (LTS), `.coil` (LTC) |
| `read_long_retentive_timer(head_no, points)` | LSTN | `list[LongTimerResult]` for LST |
| `read_ltc_states(head_no, points)` | LTN -> LTC coil | `list[bool]` |
| `read_lts_states(head_no, points)` | LTN -> LTS contact | `list[bool]` |
| `read_lstc_states(head_no, points)` | LSTN -> LSTC coil | `list[bool]` |
| `read_lsts_states(head_no, points)` | LSTN -> LSTS contact | `list[bool]` |

`read_named` / `read_named_sync` follow the same practical rule:

- plain `LTN`, `LSTN`, and `LCN` addresses are treated as 32-bit current values
- `LTS`, `LTC`, `LSTS`, and `LSTC` are resolved through the corresponding `LTN` / `LSTN` helper-backed 4-word decode instead of direct state reads

> Long timer / retentive timer set values (LT, LST) are not direct device codes and can only be read via these helpers.

---

## Module Buffer Access (Intelligent Module)

Accessed via `read_devices_ext()` / `write_devices_ext()`.

| Notation | Description | Example |
|----------|-------------|---------|
| `Ux\G` | Buffer memory (word) | `U3\G100` |
| `Ux\HG` | Buffer memory extended (word) | `U3E0\HG1000` |

```python
from slmp import SlmpClient, ExtensionSpec

values = client.read_devices_ext("U3\\G100", 4, extension=ExtensionSpec())
client.write_devices_ext("U3\\G100", [1, 2, 3, 4], extension=ExtensionSpec())
```

`Ux` is the slot number in hex (e.g. `U3`, `U3E0`). Direct `G` / `HG` access without `Ux\` prefix is not supported.

---

## Link Direct Device (CC-Link IE)

Accessed via `read_devices_ext()` / `write_devices_ext()`. Targets devices on a CC-Link IE network via the connected PLC.

| Access Type | Subcommand | Example |
|-------------|-----------|---------|
| Word read/write | `0x0080` | `J2\SW10`, `J1\W13` |
| Bit read/write (16-point units) | `0x0081` | `J1\X10`, `J1\SB10` |

`PLCSeries.QL` is forced automatically for all link direct operations regardless of the client `plc_series` setting.

```python
from slmp import SlmpClient, ExtensionSpec

# Word read
val = client.read_devices_ext("J2\\SW10", 1, extension=ExtensionSpec())

# Bit read (16 points)
bits = client.read_devices_ext("J1\\X10", 16, extension=ExtensionSpec(), bit_unit=True)

# Word write
client.write_devices_ext("J1\\SW14", [2], extension=ExtensionSpec())

# Bit write
client.write_devices_ext("J1\\X11", [True], extension=ExtensionSpec(), bit_unit=True)
```

Known limitations:

| Device | End Code | Note |
|--------|----------|------|
| `J1\B0` (B device) | `0x4031` | Not supported on CC-Link IE; GOT returns the same error |

---

## Other Station Routing (Target Station)

By default, requests target the directly connected PLC (own station). To route to another station, specify `network` and `station` numbers via `SlmpTarget`.

```python
from slmp import SlmpClient, SlmpTarget, ModuleIONo

# Constructor default: all requests go to Network 1, Station 1
client = SlmpClient("192.168.250.100", default_target=SlmpTarget(network=0x01, station=0x01))

# Per-call override
target = SlmpTarget(network=0x01, station=0x01)
values = client.read_words("D100", 10, target=target)
```

`SlmpTarget` fields:

| Field | Default | Description |
|-------|---------|-------------|
| `network` | `0x00` | Network number (`0x00` = local network) |
| `station` | `0xFF` | Station number (`0xFF` = control CPU of self station) |
| `module_io` | `0x03FF` | Module I/O No. (`0x03FF` = own station / control CPU) |
| `multidrop` | `0x00` | Multidrop station No. (`0x00` = no multidrop) |

`ModuleIONo` enum shortcuts for `module_io`:

| Name | Value | Description |
|------|-------|-------------|
| `OWN_STATION` / `CONTROL_CPU` | `0x03FF` | Own station control CPU (default) |
| `MULTIPLE_CPU_1` / `REMOTE_HEAD_1` | `0x03E0` | Multiple CPU No.1 / Remote head No.1 |
| `MULTIPLE_CPU_2` / `REMOTE_HEAD_2` | `0x03E1` | Multiple CPU No.2 / Remote head No.2 |
| `MULTIPLE_CPU_3` | `0x03E2` | Multiple CPU No.3 |
| `MULTIPLE_CPU_4` | `0x03E3` | Multiple CPU No.4 |
| `CONTROL_SYSTEM_CPU` | `0x03D0` | Control system CPU (redundant system) |
| `STANDBY_SYSTEM_CPU` | `0x03D1` | Standby system CPU (redundant system) |

```python
# Access Multiple CPU No.2 on own station
target = SlmpTarget(module_io=ModuleIONo.MULTIPLE_CPU_2)
# Or by name string
target = SlmpTarget(module_io="MULTIPLE_CPU_2")
```

---

## Related Documents

- [User Guide](USER_GUIDE.md)
- Maintainer-only protocol and testing notes are kept in the source checkout
  under `docsrc/maintainer/`.






