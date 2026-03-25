# TCP Concurrency Report

- Date: 2026-03-13 16:50:52
- Host: 192.168.250.101
- Port: 1025
- Series: iqr
- Connection path under test: direct `R08CPU`
- PLC TCP connection setting at measurement time: `15`
- Recheck context: repeated after PLC restart
- Device: D1000
- Points: 1
- Bit unit: False
- Client levels: 1, 2, 4, 8, 12, 14, 15, 16
- Rounds per client: 20
- Address allocation: each client uses a distinct offset range to avoid same-address access

| Item | Status | Detail |
|---|---|---|
| clients=1 | OK | count=20, avg_ms=4.360, p95_ms=5.808, p99_ms=5.817, max_ms=5.819, rate_per_s=131.1, errors=none |
| clients=2 | NG | count=0, elapsed_s=20.516, errors=ConnectionRefusedError=1 |
| clients=2 sample error 1 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=4 | NG | count=0, elapsed_s=20.517, errors=ConnectionRefusedError=3 |
| clients=4 sample error 1 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=4 sample error 2 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=4 sample error 3 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=8 | NG | count=0, elapsed_s=20.572, errors=ConnectionRefusedError=7 |
| clients=8 sample error 1 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=8 sample error 2 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=8 sample error 3 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=12 | NG | count=0, elapsed_s=20.571, errors=ConnectionRefusedError=11 |
| clients=12 sample error 1 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=12 sample error 2 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=12 sample error 3 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=14 | NG | count=0, elapsed_s=20.507, errors=ConnectionRefusedError=13 |
| clients=14 sample error 1 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=14 sample error 2 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=14 sample error 3 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=15 | NG | count=0, elapsed_s=20.564, errors=ConnectionRefusedError=14 |
| clients=15 sample error 1 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=15 sample error 2 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=15 sample error 3 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=16 | NG | count=0, elapsed_s=20.034, errors=ConnectionRefusedError=15 |
| clients=16 sample error 1 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=16 sample error 2 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
| clients=16 sample error 3 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
