# Focused Special Device Probe Report

- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Series: ql
- Target header: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Alternative target header module I/O for G/HG checks: 0x03E0

| Category | Item | Status | Detail |
|---|---|---|---|
| LT/LST direct | LTC0 direct probe | SKIP | state devices are evaluated through helper-backed normal access on this project; use read_ltc_states(head_no=0, points=1) instead of direct 0401/0406 |
| LT/LST direct | LTS0 direct probe | SKIP | state devices are evaluated through helper-backed normal access on this project; use read_lts_states(head_no=0, points=1) instead of direct 0401/0406 |
| LT/LST direct | LSTC0 direct probe | SKIP | state devices are evaluated through helper-backed normal access on this project; use read_lstc_states(head_no=0, points=1) instead of direct 0401/0406 |
| LT/LST direct | LSTS0 direct probe | SKIP | state devices are evaluated through helper-backed normal access on this project; use read_lsts_states(head_no=0, points=1) instead of direct 0401/0406 |
| LT/LST alternative | LTN0 0401 word x4 | NG | SLMP error end_code=0xC05C command=0x0401 subcommand=0x0000 |
| LT/LST alternative | read_long_timer(head_no=0, points=1) | NG | connection closed while receiving data |
| LT/LST helper | read_ltc_states(head_no=0, points=1) | NG | connection closed while receiving data |
| LT/LST helper | read_lts_states(head_no=0, points=1) | NG | connection closed while receiving data |
| LT/LST alternative | LSTN0 0401 word x4 | NG | connection closed while receiving data |
| LT/LST alternative | read_long_retentive_timer(head_no=0, points=1) | NG | connection closed while receiving data |
| LT/LST helper | read_lstc_states(head_no=0, points=1) | NG | connection closed while receiving data |
| LT/LST helper | read_lsts_states(head_no=0, points=1) | NG | connection closed while receiving data |
| LT/LST manual write | LTC0 1402 bit random write with read_ltc_states readback | NG | connection closed while receiving data |
| LT/LST manual write | LTS0 1402 bit random write with read_lts_states readback | NG | connection closed while receiving data |
| LT/LST manual write | LSTC0 1402 bit random write with read_lstc_states readback | NG | connection closed while receiving data |
| LT/LST manual write | LSTS0 1402 bit random write with read_lsts_states readback | NG | connection closed while receiving data |
| LT/LST/LC manual write | LTN0 1402 dword random write | NG | connection closed while receiving data |
| LT/LST/LC manual write | LSTN0 1402 dword random write | NG | connection closed while receiving data |
| LT/LST/LC manual write | LCN0 1402 dword random write | NG | connection closed while receiving data |
| LC manual write | LCS0 1401 word bulk write | NG | connection closed while receiving data |
| LC manual write | LCC0 1401 bit bulk write | NG | connection closed while receiving data |
| LC manual write | LCC0 1402 bit random write | NG | connection closed while receiving data |
| LC manual write | LCN0 1401 word bulk write | NG | connection closed while receiving data |
| G/HG direct | G0 raw 0401 normal | NG | connection closed while receiving data |
| G/HG direct | HG0 raw 0401 normal | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x03E0 head=0x00000000 | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x03E0 head=0x00000002 | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x03E0 head=0x00000004 | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x0000 head=0x00000000 | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x0000 head=0x00000002 | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x0000 head=0x00000004 | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x03FF head=0x00000000 | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x03FF head=0x00000002 | NG | connection closed while receiving data |
| G/HG alternative | 0601 module=0x03FF head=0x00000004 | NG | connection closed while receiving data |
| G/HG helper | cpu_buffer_write_word writeback @0x00000000 | NG | connection closed while receiving data |
| G/HG helper | cpu_buffer_write_dword writeback @0x00000000 | NG | connection closed while receiving data |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x03E0 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x03E0 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x3E00 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x3E00 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x0000 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | cpu_default G0 raw 0401/0082 ext=0x0000 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x03E0 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x03E0 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x3E00 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x3E00 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x0000 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | cpu_default HG0 raw 0401/0082 ext=0x0000 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x03E0 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x03E0 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x3E00 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x3E00 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x0000 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | module_header G0 raw 0401/0082 ext=0x0000 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x03E0 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x03E0 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x3E00 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x3E00 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x0000 direct=0xFA | NG | mode=cpu_buffer, connection closed while receiving data |
| G/HG extended_device | module_header HG0 raw 0401/0082 ext=0x0000 direct=0xF8 | NG | mode=module_access, connection closed while receiving data |

