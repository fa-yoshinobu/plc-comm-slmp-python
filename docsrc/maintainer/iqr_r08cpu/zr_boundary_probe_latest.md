# ZR Boundary Probe Report

- Date: 2026-03-13 12:53:27
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Focus: ZR upper-bound behavior around `ZR163839` / `ZR163840`
- Observation target: determine whether rejection depends on request span or only on start address

| Item | End code | Detail |
|---|---|---|
| read ZR27FFD x3 | 0x0000 | [0, 0, 0] |
| read ZR163838 x2 | 0x0000 | [0, 0] |
| read ZR163838 x3 | 0x0000 | [0, 0, 0] |
| read ZR163839 x1 | 0x0000 | [0] |
| read ZR163839 x2 | 0x0000 | [0, 0] |
| read ZR163839 x3 | 0x0000 | [0, 0, 0] |
| read ZR163839 x16 | 0x0000 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| read ZR163839 x64 | 0x0000 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| read ZR163840 x1 | 0x4031 | None |
| read ZR163840 x2 | 0x4031 | None |
| write ZR163838 x3 | 0x0000 | [0, 0, 0] |
| write ZR163839 x2 | 0x0000 | [0, 0] |
| write ZR163839 x3 | 0x0000 | [0, 0, 0] |
| write ZR163839 x16 | 0x0000 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| write ZR163839 x64 | 0x0000 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| write ZR163840 x1 | 0x4031 | [0] |
| write ZR163840 x2 | 0x4031 | [0, 0] |
