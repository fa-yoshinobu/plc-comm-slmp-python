# Supported registers

This table lists the device families accepted by the current parser and explains how the high-level helper layer treats them.

## Bit device families

| Family | Unit | Numbering | Notes |
| --- | --- | --- | --- |
| `SM` | Bit | Decimal | Special relay. |
| `X` | Bit | Profile-dependent | Octal text for `melsec:iq-f`; hexadecimal text for every other profile. |
| `Y` | Bit | Profile-dependent | Octal text for `melsec:iq-f`; hexadecimal text for every other profile. |
| `M` | Bit | Decimal | Internal relay. |
| `L` | Bit | Decimal | Latch relay. |
| `F` | Bit | Decimal | Annunciator. |
| `V` | Bit | Decimal | Edge relay. |
| `S` | Bit | Decimal | Step relay; reads are supported and writes follow the selected profile's write policy. |
| `B` | Bit | Hexadecimal | Link relay. |
| `TS` | Bit | Decimal | Timer contact. |
| `TC` | Bit | Decimal | Timer coil. |
| `LTS` | Bit | Decimal | Long timer contact. |
| `LTC` | Bit | Decimal | Long timer coil. |
| `STS` | Bit | Decimal | Retentive timer contact. |
| `STC` | Bit | Decimal | Retentive timer coil. |
| `LSTS` | Bit | Decimal | Long retentive timer contact. |
| `LSTC` | Bit | Decimal | Long retentive timer coil. |
| `CS` | Bit | Decimal | Counter contact. |
| `CC` | Bit | Decimal | Counter coil. |
| `LCS` | Bit | Decimal | Long counter contact. |
| `LCC` | Bit | Decimal | Long counter coil. |
| `SB` | Bit | Hexadecimal | Link special relay. |
| `DX` | Bit | Hexadecimal | Direct input; not valid for `melsec:iq-f`. |
| `DY` | Bit | Hexadecimal | Direct output; not valid for `melsec:iq-f`. |

## Word device families

| Family | Unit | Numbering | Notes |
| --- | --- | --- | --- |
| `SD` | Word | Decimal | Special register. |
| `D` | Word | Decimal | Data register and recommended first read family. |
| `W` | Word | Hexadecimal | Link register. |
| `TN` | Word | Decimal | Timer current value. |
| `LTN` | Word | Decimal | Long timer current value; use 32-bit `:D` or `:L` intent. |
| `STN` | Word | Decimal | Retentive timer current value. |
| `LSTN` | Word | Decimal | Long retentive timer current value; use 32-bit `:D` or `:L` intent. |
| `CN` | Word | Decimal | Counter current value. |
| `LCN` | Word | Decimal | Long counter current value; use 32-bit `:D` or `:L` intent. |
| `SW` | Word | Hexadecimal | Link special register. |
| `Z` | Word | Decimal | Index register. |
| `LZ` | Word | Decimal | Long index register; use 32-bit `:D` or `:L` intent. |
| `R` | Word | Decimal | File register. |
| `ZR` | Word | Decimal | Extended file register; the device-range catalog reports it unsupported for `melsec:iq-f`. |
| `RD` | Word | Decimal | Refresh data register; the device-range catalog reports it unsupported for `melsec:iq-f`, `melsec:qcpu`, `melsec:lcpu`, `melsec:qnu`, and `melsec:qnudv`. |
| `G` | Word | Decimal | Module buffer family; use raw or extended-device API only. |
| `HG` | Word | Decimal | Extended module buffer family; use raw or extended-device API only. |

## Type suffixes

| Suffix | Example | Meaning | Words |
| --- | --- | --- | --- |
| `:U` | `D100:U` | Unsigned 16-bit value | 1 |
| `:S` | `D100:S` | Signed 16-bit value | 1 |
| `:D` | `D200:D` | Unsigned 32-bit value | 2 |
| `:L` | `D202:L` | Signed 32-bit value | 2 |
| `:F` | `D204:F` | IEEE-754 float32 value | 2 |
| `.n` | `D50.3` | One bit inside a word device | 1 word read-modify-write |

Named-address helpers require explicit type suffixes. Use `D100:U`, not plain `D100`; use `M1000:BIT`, not plain `M1000`.

## Addressing notes

| Topic | Rule |
| --- | --- |
| Long current families | `LTN`, `LSTN`, `LCN`, and `LZ` are 32-bit families. Do not request 16-bit word views; use `:D` or `:L`. |
| iQ-F direct devices | `DX` and `DY` are not valid for `melsec:iq-f`. |
| Module buffers | `G` and `HG` are raw or extended-device API families, not public high-level helper families. |
| Step relay | `S` writes follow the selected profile's write policy; iQ-F allows writes, while iQ-R/iQ-L/MX/Q/L profiles mark `S` read-only. |
| `X`/`Y` numbering | `melsec:iq-f` uses octal text for `X` and `Y`; every other profile uses hexadecimal text. |
| PLC profile selection | Use canonical values such as `melsec:iq-r`; short aliases are rejected. |
| Profile detection | The library does not infer the active profile from `ReadTypeName` or model codes. |
| Device range catalog | Device-range catalog reads follow the fixed range profile derived from `plc_profile`. |
| First smoke test | Start with a simple `D` word read such as `D100`. |
| Bit-in-word notation | `.n` is valid only on word devices and uses one hexadecimal bit index from `0` to `F`. |

## Profiles

See [PROFILES.md](PROFILES.md) for canonical profiles and profile-specific cautions.
