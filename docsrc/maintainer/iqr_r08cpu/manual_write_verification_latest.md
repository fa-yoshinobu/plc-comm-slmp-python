# Manual Write Verification Report

- Date: 2026-03-13 20:12:26
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Matrix: `internal_docsrc/iqr_r08cpu/device_access_matrix.csv`
- Rows processed: 38
- Summary: OK=38, NG=0, SKIP=0
- Behavior: each row writes a temporary value, waits for human confirmation, and restores the original value unless --keep-written-value is set
- Note: this latest file merges the initial run, the resumed run, the final LZ rerun, and the LT/LST special-case rerun executed on 2026-03-13

| Item | Status | Detail |
|---|---|---|
| D D1000 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| LCC LCC10 | OK | before=OFF, test=ON, restored=OFF |
| LCN LCN10 | OK | before=0x00000000 (0), test=0x00000001 (1), restored=0x00000000 (0) |
| LCS LCS10 | OK | before=OFF, test=ON, restored=OFF |
| LSTN LSTN10 | OK | before=0x00000000 (0), test=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN10 | OK | before=0x00000000 (0), test=0x00000001 (1), restored=0x00000000 (0) |
| M M1000 | OK | before=OFF, test=ON, restored=OFF |
| R R1000 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| W W100 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1000 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| B B100 | OK | before=OFF, test=ON, restored=OFF |
| CC CC10 | OK | before=OFF, test=ON, restored=OFF |
| CN CN10 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| CS CS10 | OK | before=OFF, test=ON, restored=OFF |
| DX DX100 | OK | before=OFF, test=ON, restored=OFF |
| DY DY100 | OK | before=OFF, test=ON, restored=OFF |
| F F100 | OK | before=OFF, test=ON, restored=OFF |
| L L1000 | OK | before=OFF, test=ON, restored=OFF |
| LZ LZ1 | OK | before=0x00000000 (0), test=0x00000001 (1), restored=0x00000000 (0) |
| RD RD1000 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| SB SB100 | OK | before=OFF, test=ON, restored=OFF |
| SD SD100 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| SM SM100 | OK | before=OFF, test=ON, restored=OFF |
| STC STC10 | OK | before=OFF, test=ON, restored=OFF |
| STN STN10 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| STS STS10 | OK | before=OFF, test=ON, restored=OFF |
| SW SW100 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| TC TC10 | OK | before=OFF, test=ON, restored=OFF |
| TN TN10 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| TS TS10 | OK | before=OFF, test=ON, restored=OFF |
| V V100 | OK | before=OFF, test=ON, restored=OFF |
| X X100 | OK | before=OFF, test=ON, restored=OFF |
| Y Y100 | OK | before=OFF, test=ON, restored=OFF |
| Z Z10 | OK | before=0x0000 (0), test=0x0001 (1), restored=0x0000 (0) |
| LSTC LSTC10 | OK | before=OFF, test=ON, restored=OFF |
| LSTS LSTS10 | OK | before=OFF, test=ON, restored=OFF |
| LTC LTC10 | OK | before=OFF, test=ON, restored=OFF |
| LTS LTS10 | OK | before=OFF, test=ON, restored=OFF |

