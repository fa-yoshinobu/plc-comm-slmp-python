# Supported Device Write-Read Probe Report

- Date: 2026-03-13 20:38:02
- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Series: iqr
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Matrix: `internal_docsrc/iqr_r08cpu/device_access_matrix.csv`
- Families tested: 38
- Requested addresses per family: 10
- Boundary spec file: `internal_docsrc/iqr_r08cpu/current_plc_boundary_specs_20260313.txt`
- Summary: OK=371, NG=0
- Family summary: B:10 tested/0 NG, CC:10 tested/0 NG, CN:10 tested/0 NG, CS:10 tested/0 NG, D:10 tested/0 NG, DX:10 tested/0 NG, DY:10 tested/0 NG, F:10 tested/0 NG, L:10 tested/0 NG, LCC:10 tested/0 NG, LCN:10 tested/0 NG, LCS:10 tested/0 NG, LSTC:10 tested/0 NG, LSTN:10 tested/0 NG, LSTS:10 tested/0 NG, LTC:10 tested/0 NG, LTN:10 tested/0 NG, LTS:10 tested/0 NG, LZ:1 tested/0 NG, M:10 tested/0 NG, R:10 tested/0 NG, RD:10 tested/0 NG, SB:10 tested/0 NG, SD:10 tested/0 NG, SM:10 tested/0 NG, STC:10 tested/0 NG, STN:10 tested/0 NG, STS:10 tested/0 NG, SW:10 tested/0 NG, TC:10 tested/0 NG, TN:10 tested/0 NG, TS:10 tested/0 NG, V:10 tested/0 NG, W:10 tested/0 NG, X:10 tested/0 NG, Y:10 tested/0 NG, Z:10 tested/0 NG, ZR:10 tested/0 NG
- Scope: all currently supported device families except typed-API-blocked `G`, `HG`, and `S`
- Note: `LTC/LTS/LSTC/LSTS` use helper-backed read and `1402` random bit write in this probe

| Item | Status | Detail |
|---|---|---|
| B B100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| B B109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CC CC19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CN CN10 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN11 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN12 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN13 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN14 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN15 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN16 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN17 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN18 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CN CN19 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| CS CS10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| CS CS19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| D D1000 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1001 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1002 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1003 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1004 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1005 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1006 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1007 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1008 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| D D1009 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| DX DX100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DX DX109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| DY DY109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| F F109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1000 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1001 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1002 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1003 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1004 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1005 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1006 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1007 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1008 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| L L1009 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCC LCC19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCN LCN10 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN11 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN12 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN13 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN14 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN15 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN16 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN17 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN18 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCN LCN19 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LCS LCS10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LCS LCS19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTC LSTC19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTN LSTN10 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN11 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN12 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN13 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN14 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN15 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN16 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN17 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN18 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTN LSTN19 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LSTS LSTS10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LSTS LSTS19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTC LTC19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTN LTN10 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN11 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN12 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN13 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN14 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN15 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN16 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN17 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN18 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTN LTN19 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| LTS LTS10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LTS LTS19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| LZ LZ1 | OK | before=0x00000000 (0), test=0x00000001 (1), after=0x00000001 (1), restored=0x00000000 (0) |
| M M1000 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1001 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1002 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1003 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1004 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1005 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1006 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1007 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1008 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| M M1009 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| R R1000 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1001 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1002 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1003 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1004 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1005 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1006 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1007 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1008 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| R R1009 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1000 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1001 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1002 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1003 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1004 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1005 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1006 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1007 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1008 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| RD RD1009 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SB SB100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SB SB109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SD SD100 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD101 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD102 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD103 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD104 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD105 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD106 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD107 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD108 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SD SD109 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SM SM100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SM SM109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STC STC19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STN STN10 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN11 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN12 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN13 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN14 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN15 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN16 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN17 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN18 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STN STN19 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| STS STS10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| STS STS19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| SW SW100 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW101 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW102 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW103 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW104 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW105 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW106 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW107 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW108 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| SW SW109 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TC TC10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TC TC19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TN TN10 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN11 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN12 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN13 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN14 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN15 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN16 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN17 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN18 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TN TN19 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| TS TS10 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS11 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS12 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS13 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS14 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS15 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS16 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS17 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS18 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| TS TS19 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| V V109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| W W100 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W101 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W102 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W103 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W104 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W105 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W106 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W107 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W108 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| W W109 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| X X100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| X X109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y100 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y101 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y102 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y103 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y104 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y105 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y106 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y107 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y108 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Y Y109 | OK | before=OFF, test=ON, after=ON, restored=OFF |
| Z Z10 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z11 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z12 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z13 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z14 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z15 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z16 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z17 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z18 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| Z Z19 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1000 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1001 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1002 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1003 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1004 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1005 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1006 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1007 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1008 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |
| ZR ZR1009 | OK | before=0x0000 (0), test=0x0001 (1), after=0x0001 (1), restored=0x0000 (0) |

