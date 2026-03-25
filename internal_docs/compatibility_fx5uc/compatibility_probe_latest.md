# Compatibility Probe Report

- Date: 2026-03-19 15:33:55
- PLC Label: FX5UC
- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Requested series: auto
- Requested frame: auto
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Risk groups: safe
- Commands: 0101, 0401, 0403, 0801, 0802, 0406, 0619, 0613
- Summary: OK=9, PARTIAL=0, NG=23, SKIP=0
- JSON: internal_docs\compatibility_fx5uc\compatibility_probe_latest.json

| Item | Status | Detail |
|---|---|---|
| 3e/ql 0101 Read Type Name | OK | type_name=OK (model=FX5UC-32MT/D, model_code=0x4A91 (19089)) |
| 3e/ql 0401 Batch Read | OK | word_read=OK (device=D130, values=[0]); bit_read=OK (device=M120, values=[False]) |
| 3e/ql 0403 Random Read | OK | random_read=OK (devices=['D130', 'D131'], values={'D130': 0, 'D131': 0}) |
| 3e/ql 0801 Monitor Entry | NG | monitor_entry=NG (SLMP error end_code=0xC059 command=0x0801 subcommand=0x0000) |
| 3e/ql 0802 Monitor Execute | NG | monitor_execute=NG (SLMP error end_code=0xC059 command=0x0801 subcommand=0x0000) |
| 3e/ql 0406 Block Read | OK | block_read_word_only=OK (device=D140, result=[DeviceBlockResult(device='D140', values=[0])]); block_read_bit_only=OK (device=M140, result=[DeviceBlockResult(device='M140', values=[0])]); block_read_mixed=OK (word_device=D140, bit_device=M140, result=BlockReadResult(word_blocks=[DeviceBlockResult(device='D140', values=[0])], bit_blocks=[DeviceBlockResult(device='M140', values=[0])])) |
| 3e/ql 0619 Self Test | OK | self_test=OK (end_code=0x0000, data_len=6) |
| 3e/ql 0613 Buffer Read | NG | memory_read=NG (SLMP error end_code=0xC059 command=0x0613 subcommand=0x0000) |
| 3e/iqr 0101 Read Type Name | OK | type_name=OK (model=FX5UC-32MT/D, model_code=0x4A91 (19089)) |
| 3e/iqr 0401 Batch Read | NG | word_read=NG (SLMP error end_code=0xC059 command=0x0401 subcommand=0x0002); bit_read=NG (SLMP error end_code=0xC059 command=0x0401 subcommand=0x0003) |
| 3e/iqr 0403 Random Read | NG | random_read=NG (SLMP error end_code=0xC059 command=0x0403 subcommand=0x0002) |
| 3e/iqr 0801 Monitor Entry | NG | monitor_entry=NG (SLMP error end_code=0xC059 command=0x0801 subcommand=0x0002) |
| 3e/iqr 0802 Monitor Execute | NG | monitor_execute=NG (SLMP error end_code=0xC059 command=0x0801 subcommand=0x0002) |
| 3e/iqr 0406 Block Read | NG | block_read_word_only=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002); block_read_bit_only=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002); block_read_mixed=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002) |
| 3e/iqr 0619 Self Test | OK | self_test=OK (end_code=0x0000, data_len=6) |
| 3e/iqr 0613 Buffer Read | NG | memory_read=NG (SLMP error end_code=0xC059 command=0x0613 subcommand=0x0000) |
| 4e/ql 0101 Read Type Name | NG | type_name=NG (connection closed while receiving data) |
| 4e/ql 0401 Batch Read | NG | word_read=NG (connection closed while receiving data); bit_read=NG (connection closed while receiving data) |
| 4e/ql 0403 Random Read | NG | random_read=NG (connection closed while receiving data) |
| 4e/ql 0801 Monitor Entry | NG | monitor_entry=NG (connection closed while receiving data) |
| 4e/ql 0802 Monitor Execute | NG | monitor_execute=NG (connection closed while receiving data) |
| 4e/ql 0406 Block Read | NG | block_read_word_only=NG (connection closed while receiving data); block_read_bit_only=NG (connection closed while receiving data); block_read_mixed=NG (connection closed while receiving data) |
| 4e/ql 0619 Self Test | NG | self_test=NG (connection closed while receiving data) |
| 4e/ql 0613 Buffer Read | NG | memory_read=NG (connection closed while receiving data) |
| 4e/iqr 0101 Read Type Name | OK | type_name=OK (model=FX5UC-32MT/D, model_code=0x4A91 (19089)) |
| 4e/iqr 0401 Batch Read | NG | word_read=NG (SLMP error end_code=0xC059 command=0x0401 subcommand=0x0002); bit_read=NG (SLMP error end_code=0xC059 command=0x0401 subcommand=0x0003) |
| 4e/iqr 0403 Random Read | NG | random_read=NG (SLMP error end_code=0xC059 command=0x0403 subcommand=0x0002) |
| 4e/iqr 0801 Monitor Entry | NG | monitor_entry=NG (SLMP error end_code=0xC059 command=0x0801 subcommand=0x0002) |
| 4e/iqr 0802 Monitor Execute | NG | monitor_execute=NG (SLMP error end_code=0xC059 command=0x0801 subcommand=0x0002) |
| 4e/iqr 0406 Block Read | NG | block_read_word_only=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002); block_read_bit_only=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002); block_read_mixed=NG (SLMP error end_code=0xC059 command=0x0406 subcommand=0x0002) |
| 4e/iqr 0619 Self Test | OK | self_test=OK (end_code=0x0000, data_len=6) |
| 4e/iqr 0613 Buffer Read | NG | memory_read=NG (SLMP error end_code=0xC059 command=0x0613 subcommand=0x0000) |
