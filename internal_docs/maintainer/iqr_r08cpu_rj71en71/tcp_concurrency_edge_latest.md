# TCP Concurrency Report

- Date: 2026-03-13 16:33:32
- Host: 192.168.250.100
- Port: 1025
- Series: iqr
- Device: D1000
- Points: 1
- Bit unit: False
- Client levels: 60, 62, 63, 64
- Rounds per client: 20
- Address allocation: each client uses a distinct offset range to avoid same-address access

| Item | Status | Detail |
|---|---|---|
| clients=60 | OK | count=1200, avg_ms=216.966, p95_ms=241.928, p99_ms=270.081, max_ms=293.424, rate_per_s=254.0, errors=none |
| clients=62 | OK | count=1240, avg_ms=224.194, p95_ms=251.406, p99_ms=280.095, max_ms=314.255, rate_per_s=239.3, errors=none |
| clients=63 | OK | count=1260, avg_ms=225.977, p95_ms=252.191, p99_ms=304.971, max_ms=347.173, rate_per_s=240.0, errors=none |
| clients=64 | NG | count=0, elapsed_s=20.011, errors=ConnectionRefusedError=1 |
| clients=64 sample error 1 | NG | [WinError 10061] Connection refused by the target computer. |
