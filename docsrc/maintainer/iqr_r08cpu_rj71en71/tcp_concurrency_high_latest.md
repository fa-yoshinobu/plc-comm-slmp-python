# TCP Concurrency Report

- Date: 2026-03-13 16:31:49
- Host: 192.168.250.100
- Port: 1025
- Series: iqr
- Device: D1000
- Points: 1
- Bit unit: False
- Client levels: 64, 128
- Rounds per client: 20
- Address allocation: each client uses a distinct offset range to avoid same-address access

| Item | Status | Detail |
|---|---|---|
| clients=64 | NG | count=0, elapsed_s=20.181, errors=ConnectionRefusedError=1 |
| clients=64 sample error 1 | NG | [WinError 10061] Connection refused by the target computer. |
| clients=128 | NG | count=0, elapsed_s=20.701, errors=ConnectionRefusedError=65 |
| clients=128 sample error 1 | NG | [WinError 10061] Connection refused by the target computer. |
| clients=128 sample error 2 | NG | [WinError 10061] Connection refused by the target computer. |
| clients=128 sample error 3 | NG | [WinError 10061] Connection refused by the target computer. |
