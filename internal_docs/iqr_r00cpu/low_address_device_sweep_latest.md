# Low-Address Device Sweep

- Date: 2026-03-19 12:35:47
- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Series: iqr
- Target: network=0x01, station=0x02, module_io=0x03FF, multidrop=0x00
- Model: R00CPU
- Scope: low-address read-only sweep with one representative point per family; LT/LST state devices use helper-backed normal access; `S0` uses raw 0401 because typed APIs intentionally disable `S` on this project; `G/HG` use Extended Specification CPU-buffer read.
- Summary: ok=40, ng=1

| Code | Device | Path | Status | Detail |
|---|---|---|---|---|
| SM | SM0 | direct-0401 | OK | bit_unit=True, values=[True] |
| SD | SD0 | direct-0401 | OK | bit_unit=False, values=[4240] |
| X | X0 | direct-0401 | OK | bit_unit=True, values=[False] |
| Y | Y0 | direct-0401 | OK | bit_unit=True, values=[False] |
| M | M0 | direct-0401 | OK | bit_unit=True, values=[False] |
| L | L0 | direct-0401 | OK | bit_unit=True, values=[False] |
| F | F0 | direct-0401 | OK | bit_unit=True, values=[False] |
| V | V0 | direct-0401 | OK | bit_unit=True, values=[False] |
| B | B0 | direct-0401 | OK | bit_unit=True, values=[False] |
| D | D0 | direct-0401 | OK | bit_unit=False, values=[0] |
| W | W0 | direct-0401 | OK | bit_unit=False, values=[0] |
| TS | TS0 | direct-0401 | OK | bit_unit=True, values=[False] |
| TC | TC0 | direct-0401 | OK | bit_unit=True, values=[False] |
| TN | TN0 | direct-0401 | OK | bit_unit=False, values=[0] |
| LTS | LTS0 | helper-read_lts_states | OK | values=[False] |
| LTC | LTC0 | helper-read_ltc_states | OK | values=[False] |
| LTN | LTN0 | direct-0401 | OK | bit_unit=False, values=[0] |
| STS | STS0 | direct-0401 | OK | bit_unit=True, values=[False] |
| STC | STC0 | direct-0401 | OK | bit_unit=True, values=[False] |
| STN | STN0 | direct-0401 | OK | bit_unit=False, values=[0] |
| LSTS | LSTS0 | helper-read_lsts_states | OK | values=[False] |
| LSTC | LSTC0 | helper-read_lstc_states | OK | values=[False] |
| LSTN | LSTN0 | direct-0401 | OK | bit_unit=False, values=[0] |
| CS | CS0 | direct-0401 | OK | bit_unit=True, values=[False] |
| CC | CC0 | direct-0401 | OK | bit_unit=True, values=[False] |
| CN | CN0 | direct-0401 | OK | bit_unit=False, values=[0] |
| LCS | LCS0 | direct-0401 | OK | bit_unit=True, values=[False] |
| LCC | LCC0 | direct-0401 | OK | bit_unit=True, values=[False] |
| LCN | LCN0 | direct-0401 | OK | bit_unit=False, values=[0] |
| SB | SB0 | direct-0401 | OK | bit_unit=True, values=[False] |
| SW | SW0 | direct-0401 | OK | bit_unit=False, values=[0] |
| DX | DX0 | direct-0401 | OK | bit_unit=True, values=[False] |
| DY | DY0 | direct-0401 | OK | bit_unit=True, values=[False] |
| S | S0 | direct-0401 | OK | bit_unit=True, values=[False] |
| Z | Z0 | direct-0401 | OK | bit_unit=False, values=[0] |
| LZ | LZ0 | direct-0401 | OK | bit_unit=False, values=[0] |
| R | R0 | direct-0401 | OK | bit_unit=False, values=[0] |
| ZR | ZR0 | direct-0401 | OK | bit_unit=False, values=[0] |
| RD | RD0 | direct-0401 | OK | bit_unit=False, values=[0] |
| G | U3E0\G0 | extended_device-0401/0082 | OK | direct=0xFA, values=[0] |
| HG | U3E0\HG0 | extended_device-0401/0082 | NG | end_code=0x4031 |

