# Extended Specification Device Recheck Report

- Date: 2026-03-19 11:13:18
- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Series: iqr
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Base extension specification: 0x0000
- Default direct memory specification: 0xF8
- Restore enabled: yes
- Summary: OK=2, NG=6, SKIP=0
- Probe: cpu1_g, device=U3E0\G10, preferred_write=0x001E, direct_memory=0xFA
- Probe: cpu1_hg, device=U3E0\HG20, preferred_write=0x0032, direct_memory=0xFA
- Probe: cpu2_g, device=U3E1\G10, preferred_write=0x001E, direct_memory=0xFA
- Probe: cpu2_hg, device=U3E1\HG20, preferred_write=0x0032, direct_memory=0xFA
- Probe: cpu3_g, device=U3E2\G10, preferred_write=0x001E, direct_memory=0xFA
- Probe: cpu3_hg, device=U3E2\HG20, preferred_write=0x0032, direct_memory=0xFA
- Probe: cpu4_g, device=U3E3\G10, preferred_write=0x001E, direct_memory=0xFA
- Probe: cpu4_hg, device=U3E3\HG20, preferred_write=0x0032, direct_memory=0xFA

| Item | Status | Detail |
|---|---|---|
| cpu1_g | OK | device=U3E0\G10, before=0x0000, write=0x001E, readback=0x001E, restored=0x0000, restore=ok |
| cpu1_hg | OK | device=U3E0\HG20, before=0x0000, write=0x0032, readback=0x0032, restored=0x0000, restore=ok |
| cpu2_g | NG | SLMP error end_code=0x414A command=0x1401 subcommand=0x0082 |
| cpu2_hg | NG | device=U3E1\HG20, before=0x0000, write=0x0032, readback=0x0000, readback_mismatch=yes |
| cpu3_g | NG | SLMP error end_code=0x414A command=0x1401 subcommand=0x0082 |
| cpu3_hg | NG | device=U3E2\HG20, before=0x0000, write=0x0032, readback=0x0000, readback_mismatch=yes |
| cpu4_g | NG | SLMP error end_code=0x414A command=0x1401 subcommand=0x0082 |
| cpu4_hg | NG | device=U3E3\HG20, before=0x0000, write=0x0032, readback=0x0000, readback_mismatch=yes |
