# Register Boundary Comparison Report

- Date: 2026-03-13 12:56:13
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Families: D, W, SW, R, ZR
- Detected R last accepted start address: R32767
- Additional focused R checks:
  - `R32767` read/write `x2`, `x16`, `x64`: all `0x0000`
  - `R32768` read `x1`, `x2`, `x16`: all `0x4031`

| Family | Item | End code | Detail |
|---|---|---|---|
| D | D10239 read x1 | 0x0000 | [0] |
| D | D10239 read x2 | 0x4031 | None |
| D | D10240 read x1 | 0x4031 | None |
| D | D10239 write x1 | 0x0000 | [0] |
| D | D10240 write x1 | 0x4031 | [0] |
| W | W1FFF read x1 | 0x0000 | [0] |
| W | W1FFF read x2 | 0x4031 | None |
| W | W2000 read x1 | 0x4031 | None |
| W | W1FFF write x1 | 0x0000 | [0] |
| W | W2000 write x1 | 0x4031 | [0] |
| SW | SW7FF read x1 | 0x0000 | [0] |
| SW | SW7FF read x2 | 0x4031 | None |
| SW | SW800 read x1 | 0x4031 | None |
| SW | SW7FF write x1 | 0x0000 | [0] |
| SW | SW800 write x1 | 0x4031 | [0] |
| R | R32767 read x1 | 0x0000 | [0] |
| R | R32767 read x2 | 0x0000 | [0, 0] |
| R | R32767 read x16 | 0x0000 | [0 x16] |
| R | R32767 read x64 | 0x0000 | [0 x64] |
| R | R32768 read x1 | 0x4031 | None |
| R | R32768 read x2 | 0x4031 | None |
| R | R32768 read x16 | 0x4031 | None |
| R | R32767 write x1 | 0x0000 | [0] |
| R | R32767 write x2 | 0x0000 | [0, 0] |
| R | R32767 write x16 | 0x0000 | [0 x16] |
| R | R32767 write x64 | 0x0000 | [0 x64] |
| R | R32768 write x1 | 0x4031 | [0] |
| ZR | ZR163839 read x1 | 0x0000 | [0] |
| ZR | ZR163839 read x2 | 0x0000 | [0, 0] |
| ZR | ZR163840 read x1 | 0x4031 | None |
| ZR | ZR163839 write x1 | 0x0000 | [0] |
| ZR | ZR163840 write x1 | 0x4031 | [0] |
