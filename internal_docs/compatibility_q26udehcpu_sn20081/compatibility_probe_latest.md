# Compatibility Probe Report

- Date: 2026-03-19 15:21:14
- PLC Label: Q26UDEHCPU_SN20081
- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Requested series: auto
- Requested frame: auto
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Risk groups: safe
- Commands: 0101, 0401, 0403, 0801, 0802, 0406, 0619, 0613
- Summary: OK=4, PARTIAL=0, NG=28, SKIP=0
- JSON: internal_docs\compatibility_q26udehcpu_sn20081\compatibility_probe_latest.json

| Item | Status | Detail |
|---|---|---|
| 3e/ql 0101 Read Type Name | NG | type_name=NG (SLMP error end_code=0xC059 command=0x0101 subcommand=0x0000) |
| 3e/ql 0401 Batch Read | OK | word_read=OK (device=D130, values=[0]); bit_read=OK (device=M120, values=[False]) |
| 3e/ql 0403 Random Read | OK | random_read=OK (devices=['D130', 'D131'], values={'D130': 0, 'D131': 0}) |
| 3e/ql 0801 Monitor Entry | OK | monitor_entry=OK (word_device=D130) |
| 3e/ql 0802 Monitor Execute | OK | monitor_execute=OK (word_device=D130, values=[0]) |
| 3e/ql 0406 Block Read | NG | block_read_word_only=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0000); block_read_bit_only=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0000); block_read_mixed=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0000) |
| 3e/ql 0619 Self Test | NG | self_test=NG (end_code=0xC059, data_len=9) |
| 3e/ql 0613 Buffer Read | NG | memory_read=NG (SLMP error end_code=0xC059 command=0x0613 subcommand=0x0000) |
| 3e/iqr 0101 Read Type Name | NG | type_name=NG (SLMP error end_code=0xC059 command=0x0101 subcommand=0x0000) |
| 3e/iqr 0401 Batch Read | NG | word_read=NG (SLMP error end_code=0xC059 command=0x0401 subcommand=0x0002); bit_read=NG (SLMP error end_code=0xC059 command=0x0401 subcommand=0x0003) |
| 3e/iqr 0403 Random Read | NG | random_read=NG (SLMP error end_code=0xC059 command=0x0403 subcommand=0x0002) |
| 3e/iqr 0801 Monitor Entry | NG | monitor_entry=NG (SLMP error end_code=0xC059 command=0x0801 subcommand=0x0002) |
| 3e/iqr 0802 Monitor Execute | NG | monitor_execute=NG (SLMP error end_code=0xC059 command=0x0801 subcommand=0x0002) |
| 3e/iqr 0406 Block Read | NG | block_read_word_only=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002); block_read_bit_only=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002); block_read_mixed=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002) |
| 3e/iqr 0619 Self Test | NG | self_test=NG (end_code=0xC059, data_len=9) |
| 3e/iqr 0613 Buffer Read | NG | memory_read=NG (SLMP error end_code=0xC059 command=0x0613 subcommand=0x0000) |
| 4e/ql 0101 Read Type Name | NG | type_name=NG (timed out) |
| 4e/ql 0401 Batch Read | NG | word_read=NG (timed out); bit_read=NG (timed out) |
| 4e/ql 0403 Random Read | NG | random_read=NG (timed out) |
| 4e/ql 0801 Monitor Entry | NG | monitor_entry=NG (timed out) |
| 4e/ql 0802 Monitor Execute | NG | monitor_execute=NG (timed out) |
| 4e/ql 0406 Block Read | NG | block_read_word_only=NG (timed out); block_read_bit_only=NG (timed out); block_read_mixed=NG (timed out) |
| 4e/ql 0619 Self Test | NG | self_test=NG (timed out) |
| 4e/ql 0613 Buffer Read | NG | memory_read=NG (timed out) |
| 4e/iqr 0101 Read Type Name | NG | type_name=NG (timed out) |
| 4e/iqr 0401 Batch Read | NG | word_read=NG (timed out); bit_read=NG (timed out) |
| 4e/iqr 0403 Random Read | NG | random_read=NG (timed out) |
| 4e/iqr 0801 Monitor Entry | NG | monitor_entry=NG (timed out) |
| 4e/iqr 0802 Monitor Execute | NG | monitor_execute=NG (timed out) |
| 4e/iqr 0406 Block Read | NG | block_read_word_only=NG (timed out); block_read_bit_only=NG (timed out); block_read_mixed=NG (timed out) |
| 4e/iqr 0619 Self Test | NG | self_test=NG (timed out) |
| 4e/iqr 0613 Buffer Read | NG | memory_read=NG (timed out) |
