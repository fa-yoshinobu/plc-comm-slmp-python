# Device Access Matrix

- Generated: 2026-03-13 20:45:00
- Source: `internal_docsrc/iqr_r08cpu/device_access_matrix.csv`

## Summary

- bit_read_OK: 24
- bit_write_NG: 1
- bit_write_OK: 23
- dword_read_OK: 4
- dword_write_OK: 4
- extension_cpu_buffer_read_NG: 2
- extension_cpu_buffer_write_SKIP: 2
- extension_only_read_SKIP: 2
- extension_only_write_SKIP: 2
- manual_write_OK: 38
- word_read_OK: 11
- word_write_OK: 11

## Results

| Device Code | Device | Kind | Unsupported | Read | Write | Manual Write | Note | Manual Write Note |
|---|---|---|---|---|---|---|---|---|
| B | B100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| CC | CC10 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| CN | CN10 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| CS | CS10 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| D | D1000 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| DX | DX100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| DY | DY100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| F | F100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| G | N/A | extension_only | YES | SKIP | SKIP |  | Blocked in typed APIs; re-evaluate after accepted U\G / Extended Specification condition is identified |  |
| HG | N/A | extension_only | YES | SKIP | SKIP |  | Blocked in typed APIs; re-evaluate after accepted CPU-buffer / Extended Specification condition is identified |  |
| L | L1000 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| LCC | LCC10 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| LCN | LCN10 | dword |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| LCS | LCS10 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| LSTC | LSTC10 | bit |  | OK | OK | OK | Supported spec path uses LSTN decode (coil bit) and 1402 random bit write; direct 0401 read returns 0x4030 on the validated target | human temporary write verified and restored on 2026-03-13 via helper-backed read + 1402 random bit write |
| LSTN | LSTN10 | dword |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| LSTS | LSTS10 | bit |  | OK | OK | OK | Supported spec path uses LSTN decode (contact bit) and 1402 random bit write; direct 0401 read returns 0x4030 on the validated target | human temporary write verified and restored on 2026-03-13 via helper-backed read + 1402 random bit write |
| LTC | LTC10 | bit |  | OK | OK | OK | Supported spec path uses LTN decode (coil bit) and 1402 random bit write; direct 0401 read returns 0x4030 on the validated target | human temporary write verified and restored on 2026-03-13 via helper-backed read + 1402 random bit write |
| LTN | LTN10 | dword |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| LTS | LTS10 | bit |  | OK | OK | OK | Supported spec path uses LTN decode (contact bit) and 1402 random bit write; direct 0401 read returns 0x4030 on the validated target | human temporary write verified and restored on 2026-03-13 via helper-backed read + 1402 random bit write |
| LZ | LZ1 | dword |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| M | M1000 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| R | R1000 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| RD | RD1000 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| S | S100 | bit | YES | OK | NG |  | Blocked in typed APIs; read OK but write returned 0x4030 on the validated target |  |
| SB | SB100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| SD | SD100 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| SM | SM100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| STC | STC10 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| STN | STN10 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| STS | STS10 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| SW | SW100 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| TC | TC10 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| TN | TN10 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| TS | TS10 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| V | V100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| W | W100 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| X | X100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| Y | Y100 | bit |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| Z | Z10 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| ZR | ZR1000 | word |  | OK | OK | OK | representative verification address | human temporary write verified and restored on 2026-03-13 |
| G | G0 | extension_cpu_buffer | YES | NG | SKIP |  | Blocked in typed APIs; Extended Specification read returned 0xC061 on the validated target |  |
| HG | HG0 | extension_cpu_buffer | YES | NG | SKIP |  | Blocked in typed APIs; Extended Specification read returned 0xC061 on the validated target |  |

