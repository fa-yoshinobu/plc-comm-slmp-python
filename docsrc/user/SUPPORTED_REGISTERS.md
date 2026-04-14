# Supported PLC Registers

This page is the canonical public register table for the Python high-level API.

## Supported Bit Devices

| Family | Kind | Example | Numbering |
| --- | --- | --- | --- |
| `SM` | bit | `SM400` | decimal |
| `X` | bit | `X20` / `X100` | explicit family required; non-`iQ-F` text is hexadecimal, `iQ-F` text is octal |
| `Y` | bit | `Y20` / `Y100` | explicit family required; non-`iQ-F` text is hexadecimal, `iQ-F` text is octal |
| `M` | bit | `M1000` | decimal |
| `L` | bit | `L100` | decimal |
| `F` | bit | `F10` | decimal |
| `V` | bit | `V10` | decimal |
| `B` | bit | `B20` | hexadecimal |
| `TS` | bit | `TS10` | decimal |
| `TC` | bit | `TC10` | decimal |
| `STS` | bit | `STS10` | decimal |
| `STC` | bit | `STC10` | decimal |
| `CS` | bit | `CS10` | decimal |
| `CC` | bit | `CC10` | decimal |
| `SB` | bit | `SB20` | hexadecimal |
| `DX` | bit | `DX20` | hexadecimal |
| `DY` | bit | `DY20` | hexadecimal |

## Supported Word Devices

| Family | Kind | Example | Numbering |
| --- | --- | --- | --- |
| `SD` | word | `SD100` | decimal |
| `D` | word | `D100` | decimal |
| `W` | word | `W20` | hexadecimal |
| `TN` | word | `TN10` | decimal |
| `LTN` | word | `LTN10` | decimal |
| `STN` | word | `STN10` | decimal |
| `LSTN` | word | `LSTN10` | decimal |
| `CN` | word | `CN10` | decimal |
| `LCN` | word | `LCN10` | decimal |
| `SW` | word | `SW20` | hexadecimal |
| `Z` | word | `Z10` | decimal |
| `R` | word | `R100` | decimal |
| `ZR` | word | `ZR100` | decimal |
| `RD` | word | `RD100` | decimal |

## High-Level Views

| Form | Example | Meaning |
| --- | --- | --- |
| plain word | `D100` | unsigned 16-bit word |
| signed view | `D100:S` | signed 16-bit value |
| dword view | `D200:D` | unsigned 32-bit value |
| long view | `D300:L` | signed 32-bit value |
| float view | `D200:F` | float32 value |
| bit in word | `D50.3` | one bit inside a word |

## Addressing Notes

- Start with `D` for the first smoke test.
- `B`, `W`, `SB`, `SW`, `DX`, and `DY` use hexadecimal device numbers.
- `X` and `Y` require explicit `device_family` for communication.
- device-range catalog reads require the same explicit canonical `family` definition.
- non-`iQ-F` `X` / `Y` text such as `X20` uses hexadecimal numbering.
- `iQ-F` / FX5 `X` / `Y` text such as `X100` uses manual octal notation and is converted to the binary numeric value before transmission.
- canonical family values are `iq-f`, `iq-r`, `mx-f`, `mx-r`, `qcpu`, `lcpu`, `qnu`, and `qnudv`.
- Most other families use decimal numbers.
- `.bit` is valid only on word devices such as `D50.3`.
- `LTN`, `LSTN`, and `LCN` default to 32-bit current-value access in the public high-level helpers.

## Not Currently in the Public Surface

- `LTS`
- `LTC`
- `LSTS`
- `LSTC`
- `LCS`
- `LCC`
- `LZ`
- `G`
- `HG`

If a family is not listed above, do not treat it as publicly supported by the current high-level API.
