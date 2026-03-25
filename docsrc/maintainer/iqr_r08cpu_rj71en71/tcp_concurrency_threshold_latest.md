# TCP Concurrency Report

- Date: 2026-03-13 16:32:40
- Host: 192.168.250.101
- Port: 1025
- Series: iqr
- Device: D1000
- Points: 1
- Bit unit: False
- Client levels: 40, 48, 56, 64
- Rounds per client: 20
- Address allocation: each client uses a distinct offset range to avoid same-address access

| Item | Status | Detail |
|---|---|---|
| clients=40 | OK | count=800, avg_ms=140.118, p95_ms=163.059, p99_ms=177.994, max_ms=205.407, rate_per_s=272.2, errors=none |
| clients=48 | OK | count=960, avg_ms=176.618, p95_ms=198.647, p99_ms=235.649, max_ms=250.436, rate_per_s=258.2, errors=none |
| clients=56 | OK | count=1120, avg_ms=209.520, p95_ms=251.787, p99_ms=276.913, max_ms=325.260, rate_per_s=255.5, errors=none |
| clients=64 | NG | count=0, elapsed_s=20.009, errors=ConnectionRefusedError=1 |
| clients=64 sample error 1 | NG | [WinError 10061] Connection refused by the target computer. |
