# Register Boundary Probe Report

- Date: 2026-03-13 17:24:09
- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Series: iqr
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Specs: 5
- Spec source: internal_docsrc/iqr_r08cpu/current_register_boundary_focus_specs_20260313.txt
- Summary: OK=49, NG=0, SKIP=1

| Item | Status | Detail |
|---|---|---|
| Z read Z19 x1 | OK | end_code=0x0000, values=[0] |
| Z read Z19 x2 | OK | end_code=0x4031, values=None |
| Z read Z20 x1 | OK | end_code=0x4031, values=None |
| Z write Z19 x1 | OK | end_code=0x0000, values=[0] |
| Z write Z19 x2 | SKIP | same-value writeback skipped because read payload was unavailable: None |
| Z write Z20 x1 | OK | end_code=0x4031, values=[0] |
| LZ read LZ1 x1 | OK | end_code=0x0000, values=[0] |
| LZ read LZ1 x2 | OK | end_code=0x0000, values=[0, 0] |
| LZ read LZ2 x1 | OK | end_code=0x4031, values=None |
| LZ read LZ2 x2 | OK | end_code=0x4031, values=None |
| LZ write LZ1 x1 | OK | end_code=0xC051, values=[0] |
| LZ write LZ1 x2 | OK | end_code=0x0000, values=[0, 0] |
| LZ write LZ2 x1 | OK | end_code=0xC051, values=[0] |
| LZ write LZ2 x2 | OK | end_code=0x4031, values=[0, 0] |
| R read R32767 x1 | OK | end_code=0x0000, values=[0] |
| R read R32767 x2 | OK | end_code=0x0000, values=[0, 0] |
| R read R32767 x16 | OK | end_code=0x0000, values=len=16 [0, 0, 0, 0, ..., 0, 0] |
| R read R32767 x64 | OK | end_code=0x0000, values=len=64 [0, 0, 0, 0, ..., 0, 0] |
| R read R32768 x1 | OK | end_code=0x4031, values=None |
| R read R32768 x2 | OK | end_code=0x4031, values=None |
| R read R32768 x16 | OK | end_code=0x4031, values=None |
| R write R32767 x1 | OK | end_code=0x0000, values=[0] |
| R write R32767 x2 | OK | end_code=0x0000, values=[0, 0] |
| R write R32767 x16 | OK | end_code=0x0000, values=len=16 [0, 0, 0, 0, ..., 0, 0] |
| R write R32767 x64 | OK | end_code=0x0000, values=len=64 [0, 0, 0, 0, ..., 0, 0] |
| R write R32768 x1 | OK | end_code=0x4031, values=[0] |
| R write R32768 x2 | OK | end_code=0x4031, values=[0, 0] |
| R write R32768 x16 | OK | end_code=0x4031, values=len=16 [0, 0, 0, 0, ..., 0, 0] |
| ZR read ZR163839 x1 | OK | end_code=0x0000, values=[0] |
| ZR read ZR163839 x2 | OK | end_code=0x0000, values=[0, 0] |
| ZR read ZR163839 x3 | OK | end_code=0x0000, values=[0, 0, 0] |
| ZR read ZR163839 x16 | OK | end_code=0x0000, values=len=16 [0, 0, 0, 0, ..., 0, 0] |
| ZR read ZR163839 x64 | OK | end_code=0x0000, values=len=64 [0, 0, 0, 0, ..., 0, 0] |
| ZR read ZR163840 x1 | OK | end_code=0x4031, values=None |
| ZR read ZR163840 x2 | OK | end_code=0x4031, values=None |
| ZR write ZR163839 x1 | OK | end_code=0x0000, values=[0] |
| ZR write ZR163839 x2 | OK | end_code=0x0000, values=[0, 0] |
| ZR write ZR163839 x3 | OK | end_code=0x0000, values=[0, 0, 0] |
| ZR write ZR163839 x16 | OK | end_code=0x0000, values=len=16 [0, 0, 0, 0, ..., 0, 0] |
| ZR write ZR163839 x64 | OK | end_code=0x0000, values=len=64 [0, 0, 0, 0, ..., 0, 0] |
| ZR write ZR163840 x1 | OK | end_code=0x4031, values=[0] |
| ZR write ZR163840 x2 | OK | end_code=0x4031, values=[0, 0] |
| RD read RD524286 x1 | OK | end_code=0x0000, values=[0] |
| RD read RD524286 x2 | OK | end_code=0x0000, values=[0, 0] |
| RD read RD524287 x1 | OK | end_code=0x0000, values=[0] |
| RD read RD524287 x2 | OK | end_code=0x4031, values=None |
| RD write RD524286 x1 | OK | end_code=0x0000, values=[0] |
| RD write RD524286 x2 | OK | end_code=0x0000, values=[0, 0] |
| RD write RD524287 x1 | OK | end_code=0x0000, values=[0] |
| RD write RD524287 x2 | OK | end_code=0x4031, values=[0, 0] |

