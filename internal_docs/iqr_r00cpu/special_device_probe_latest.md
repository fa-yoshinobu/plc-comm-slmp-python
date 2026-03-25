# Focused Special Device Probe Report

- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Target header: network=0x01, station=0x02, module_io=0x03FF, multidrop=0x00
- Alternative target header module I/O for G/HG checks: 0x03E0

| Category | Item | Status | Detail |
|---|---|---|---|
| LT/LST direct | LTC0 direct probe | SKIP | state devices are evaluated through helper-backed normal access on this project; use read_ltc_states(head_no=0, points=1) instead of direct 0401/0406 |
| LT/LST direct | LTS0 direct probe | SKIP | state devices are evaluated through helper-backed normal access on this project; use read_lts_states(head_no=0, points=1) instead of direct 0401/0406 |
| LT/LST direct | LSTC0 direct probe | SKIP | state devices are evaluated through helper-backed normal access on this project; use read_lstc_states(head_no=0, points=1) instead of direct 0401/0406 |
| LT/LST direct | LSTS0 direct probe | SKIP | state devices are evaluated through helper-backed normal access on this project; use read_lsts_states(head_no=0, points=1) instead of direct 0401/0406 |
| LT/LST alternative | LTN0 0401 word x4 | OK | values=[0, 0, 0, 0] |
| LT/LST alternative | read_long_timer(head_no=0, points=1) | OK | [LongTimerResult(index=0, device='LTN0', current_value=0, contact=False, coil=False, status_word=0, raw_words=[0, 0, 0, 0])] |
| LT/LST helper | read_ltc_states(head_no=0, points=1) | OK | values=[False] |
| LT/LST helper | read_lts_states(head_no=0, points=1) | OK | values=[False] |
| LT/LST alternative | LSTN0 0401 word x4 | OK | values=[0, 0, 0, 0] |
| LT/LST alternative | read_long_retentive_timer(head_no=0, points=1) | OK | [LongTimerResult(index=0, device='LSTN0', current_value=0, contact=False, coil=False, status_word=0, raw_words=[0, 0, 0, 0])] |
| LT/LST helper | read_lstc_states(head_no=0, points=1) | OK | values=[False] |
| LT/LST helper | read_lsts_states(head_no=0, points=1) | OK | values=[False] |
| LT/LST manual write | LTC0 1402 bit random write with read_ltc_states readback | OK | before=False, test=True, after=True, restored=False |
| LT/LST manual write | LTS0 1402 bit random write with read_lts_states readback | OK | before=False, test=True, after=True, restored=False |
| LT/LST manual write | LSTC0 1402 bit random write with read_lstc_states readback | OK | before=False, test=True, after=True, restored=False |
| LT/LST manual write | LSTS0 1402 bit random write with read_lsts_states readback | OK | before=False, test=True, after=True, restored=False |
| LT/LST/LC manual write | LTN0 1402 dword random write | OK | before=0, test=1, after=1, restored=0 |
| LT/LST/LC manual write | LSTN0 1402 dword random write | OK | before=0, test=1, after=1, restored=0 |
| LT/LST/LC manual write | LCN0 1402 dword random write | OK | before=0, test=1, after=1, restored=0 |
| LC manual write | LCS0 1401 word bulk write | OK | before=0, test=1, after=1, restored=0 |
| LC manual write | LCC0 1401 bit bulk write | OK | before=False, test=True, after=True, restored=False |
| LC manual write | LCC0 1402 bit random write | OK | before=False, test=True, after=True, restored=False |
| LC manual write | LCN0 1401 word bulk write | OK | before=0, test=1, after=1, restored=0 |
| G/HG direct | G0 raw 0401 normal | NG | end_code=0xC05B |
| G/HG direct | HG0 raw 0401 normal | NG | end_code=0xC05B |
| G/HG alternative | 0601 module=0x03E0 head=0x00000000 | OK | data=50 6a |
| G/HG alternative | 0601 module=0x03E0 head=0x00000002 | OK | data=af 95 |
| G/HG alternative | 0601 module=0x03E0 head=0x00000004 | OK | data=a0 48 |
| G/HG alternative | 0601 module=0x0000 head=0x00000000 | NG | SLMP error end_code=0x4043 command=0x0601 subcommand=0x0000 |
| G/HG alternative | 0601 module=0x0000 head=0x00000002 | NG | SLMP error end_code=0x4043 command=0x0601 subcommand=0x0000 |
| G/HG alternative | 0601 module=0x0000 head=0x00000004 | NG | SLMP error end_code=0x4043 command=0x0601 subcommand=0x0000 |
| G/HG alternative | 0601 module=0x03FF head=0x00000000 | NG | SLMP error end_code=0x4080 command=0x0601 subcommand=0x0000 |
| G/HG alternative | 0601 module=0x03FF head=0x00000002 | NG | SLMP error end_code=0x4080 command=0x0601 subcommand=0x0000 |
| G/HG alternative | 0601 module=0x03FF head=0x00000004 | NG | SLMP error end_code=0x4080 command=0x0601 subcommand=0x0000 |
| G/HG helper | cpu_buffer_write_word writeback @0x00000000 | OK | before=0x6A50, after=0x6A50 |
| G/HG helper | cpu_buffer_write_dword writeback @0x00000000 | OK | before=0x95AF6A50, after=0x95AF6A50 |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x03E0 direct=0xFA | OK | mode=cpu_buffer, values=[0] |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x03E0 direct=0xF8 | OK | mode=module_access, values=[0] |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x3E00 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4031 |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x3E00 direct=0xF8 | NG | mode=module_access, end_code=0x4031 |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x0000 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4031 |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x0000 direct=0xF8 | NG | mode=module_access, end_code=0x4031 |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x03E0 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4031 |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x03E0 direct=0xF8 | NG | mode=module_access, end_code=0xC05B |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x3E00 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4030 |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x3E00 direct=0xF8 | NG | mode=module_access, end_code=0xC05B |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x0000 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4030 |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x0000 direct=0xF8 | NG | mode=module_access, end_code=0xC05B |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x03E0 direct=0xFA | OK | mode=cpu_buffer, values=[0] |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x03E0 direct=0xF8 | OK | mode=module_access, values=[0] |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x3E00 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4031 |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x3E00 direct=0xF8 | NG | mode=module_access, end_code=0x4031 |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x0000 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4031 |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x0000 direct=0xF8 | NG | mode=module_access, end_code=0x4031 |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x03E0 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4031 |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x03E0 direct=0xF8 | NG | mode=module_access, end_code=0xC05B |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x3E00 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4030 |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x3E00 direct=0xF8 | NG | mode=module_access, end_code=0xC05B |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x0000 direct=0xFA | NG | mode=cpu_buffer, end_code=0x4030 |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x0000 direct=0xF8 | NG | mode=module_access, end_code=0xC05B |

