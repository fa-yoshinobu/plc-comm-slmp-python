# G/HG Extended Specification Recheck Report

- Date: 2026-03-19 09:13:16
- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Series: iqr
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- CPU I/O: 0x03E0
- G device: U3E0\G10 (preferred write=0x001E)
- HG device: U3E0\HG20 (preferred write=0x0032)
- Restore enabled: yes
- Summary: OK=2, NG=0, SKIP=0

| Item | Status | Detail |
|---|---|---|
| G extended_device read/write/readback | OK | device=U3E0\G10, before=0x0000, write=0x001E, readback=0x001E, restored=0x0000, restore=ok |
| HG extended_device read/write/readback | OK | device=U3E0\HG20, before=0x0000, write=0x0032, readback=0x0032, restored=0x0000, restore=ok |

