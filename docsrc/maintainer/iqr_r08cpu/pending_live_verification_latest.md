# Pending Live Verification Report

- Date: 2026-03-13 21:34:30
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr

| Item | Status | Detail |
|---|---|---|
| 041A label array read | OK | DDD[0]:type=0x02,unit=1,array_len=20,data_len=20; EEE[0,0]:type=0x02,unit=1,array_len=20,data_len=20; FFF[0,0,0]:type=0x02,unit=1,array_len=20,data_len=20 |
| 141A label array write | OK | DDD[0]:type=0x02,unit=1,array_len=20,data_len=20; EEE[0,0]:type=0x02,unit=1,array_len=20,data_len=20; FFF[0,0,0]:type=0x02,unit=1,array_len=20,data_len=20 |
| 041C label random read | OK | DDD[0]:type=0x02,len=2,data_len=2; EEE[0,0]:type=0x02,len=2,data_len=2; FFF[0,0,0]:type=0x02,len=2,data_len=2 |
| 141B label random write | OK | DDD[0]:type=0x02,len=2,data_len=2; EEE[0,0]:type=0x02,len=2,data_len=2; FFF[0,0,0]:type=0x02,len=2,data_len=2 |
| 0601/1601 extend unit read/write | OK | module_no=0x03E0, head=0x00000000, data=b1 e9 |
| 1810 file read directory | NG | SLMP error end_code=0xC061 command=0x1810 subcommand=0x0000 |
| 1811 file search | NG | SLMP error end_code=0xC061 command=0x1811 subcommand=0x0000 |
| 1820 file new | NG | SLMP error end_code=0x413E command=0x1820 subcommand=0x0000 |
| 1827 file open | NG | SLMP error end_code=0x413E command=0x1827 subcommand=0x0000 |
| 1829 file write | SKIP | file handle unavailable |
| 1828 file read | SKIP | file handle unavailable |
| 182A file close | SKIP | file handle unavailable |
| 1825 file change state | NG | SLMP error end_code=0x413E command=0x1825 subcommand=0x0000 |
| 1826 file change date | NG | SLMP error end_code=0xC207 command=0x1826 subcommand=0x0000 |
| 1822 file delete | NG | SLMP error end_code=0x413E command=0x1822 subcommand=0x0000 |
| 1824 file copy | NG | end_code=0xC061 |
| 1002 remote stop | OK | end_code=0x0000 |
| 1001 remote run | OK | end_code=0x0000 |
| 1003 remote pause | OK | end_code=0x0000 |
| 1005 remote latch clear | NG | end_code=0x4013 |
| 1002 remote stop (restore) | OK | end_code=0x0000 |
| 1630 unlock (pre) | OK | end_code=0x0000 |
| 1631 lock | OK | end_code=0x0000 |
| 1630 unlock | OK | end_code=0x0000 |
| 1617 clear error | OK | end_code=0x0000 |
| 2101 ondemand | SKIP | manual-defined as PLC-initiated data; use receive_ondemand() with a PLC-side trigger |
| 1006 remote reset | SKIP | disabled by default; use --run-reset |
