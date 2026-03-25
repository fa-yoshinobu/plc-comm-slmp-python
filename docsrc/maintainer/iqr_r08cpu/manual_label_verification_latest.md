# Manual Label Verification Report

- Date: 2026-03-13 21:44:17
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Monitoring timer: 0x0010
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Random labels: LabelB, LabelW, DDD[0], EEE[0,0], FFF[0,0,0]
- Array labels: DDD[0]:1:20, EEE[0,0]:1:20, FFF[0,0,0]:1:20
- Rows processed: 8
- Summary: OK=8, NG=0, SKIP=0
- Behavior: each row reads the current label value, writes a temporary value, waits for human confirmation, and restores the original value unless --keep-written-value is set

| Item | Status | Detail |
|---|---|---|
| random LabelB | OK | before=0x0000 (0), raw=00 00, test=0x0001 (1), raw=01 00, restored=0x0000 (0), raw=00 00 |
| random LabelW | OK | before=0x0000 (0), raw=00 00, test=0x0001 (1), raw=01 00, restored=0x0000 (0), raw=00 00 |
| random DDD[0] | OK | before=0x0000 (0), raw=00 00, test=0x0001 (1), raw=01 00, restored=0x0000 (0), raw=00 00 |
| random EEE[0,0] | OK | before=0x0000 (0), raw=00 00, test=0x0001 (1), raw=01 00, restored=0x0000 (0), raw=00 00 |
| random FFF[0,0,0] | OK | before=0x0000 (0), raw=00 00, test=0x0001 (1), raw=01 00, restored=0x0000 (0), raw=00 00 |
| array DDD[0]:1:20 | OK | before=raw=00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes), test=raw=01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes), restored=raw=00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes) |
| array EEE[0,0]:1:20 | OK | before=raw=00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes), test=raw=01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes), restored=raw=00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes) |
| array FFF[0,0,0]:1:20 | OK | before=raw=00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes), test=raw=01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes), restored=raw=00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ... (20 bytes) |
