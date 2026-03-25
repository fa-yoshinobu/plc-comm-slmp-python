# TCP Concurrency Report

- Date: 2026-03-23 16:45:39
- Host: 192.168.250.100
- Port: 1025
- Series: ql
- Device: D1000
- Points: 1
- Bit unit: False
- Client levels: 1, 2, 4, 8, 16, 32
- Rounds per client: 100
- Address allocation: each client uses a distinct offset range to avoid same-address access

| Item | Status | Detail |
|---|---|---|
| clients=1 | NG | count=100, avg_ms=0.040, p95_ms=0.070, p99_ms=0.174, max_ms=0.240, rate_per_s=5755.6, errors=SlmpError=100 |
| clients=1 sample error 1 | NG | D1000: connection closed while receiving data |
| clients=1 sample error 2 | NG | D1001: connection closed while receiving data |
| clients=1 sample error 3 | NG | D1002: connection closed while receiving data |
| clients=2 | NG | count=200, avg_ms=1.003, p95_ms=2.123, p99_ms=2.291, max_ms=2.501, rate_per_s=944.0, errors=SlmpError=100 |
| clients=2 sample error 1 | NG | D1100: connection closed while receiving data |
| clients=2 sample error 2 | NG | D1101: connection closed while receiving data |
| clients=2 sample error 3 | NG | D1102: connection closed while receiving data |
| clients=4 | NG | count=400, avg_ms=0.583, p95_ms=2.102, p99_ms=2.364, max_ms=2.589, rate_per_s=1864.4, errors=SlmpError=300 |
| clients=4 sample error 1 | NG | D1200: connection closed while receiving data |
| clients=4 sample error 2 | NG | D1201: connection closed while receiving data |
| clients=4 sample error 3 | NG | D1202: connection closed while receiving data |
| clients=8 | NG | count=800, avg_ms=0.527, p95_ms=2.033, p99_ms=2.336, max_ms=6.064, rate_per_s=3622.1, errors=SlmpError=700 |
| clients=8 sample error 1 | NG | D1500: connection closed while receiving data |
| clients=8 sample error 2 | NG | D1501: connection closed while receiving data |
| clients=8 sample error 3 | NG | D1502: connection closed while receiving data |
| clients=16 | NG | count=1600, avg_ms=0.712, p95_ms=2.025, p99_ms=3.759, max_ms=31.014, rate_per_s=6401.8, errors=SlmpError=1500 |
| clients=16 sample error 1 | NG | D1500: connection closed while receiving data |
| clients=16 sample error 2 | NG | D1501: connection closed while receiving data |
| clients=16 sample error 3 | NG | D1502: connection closed while receiving data |
| clients=32 | NG | count=3200, avg_ms=0.949, p95_ms=1.267, p99_ms=5.379, max_ms=116.442, rate_per_s=9260.9, errors=SlmpError=3100 |
| clients=32 sample error 1 | NG | D1600: connection closed while receiving data |
| clients=32 sample error 2 | NG | D1601: connection closed while receiving data |
| clients=32 sample error 3 | NG | D1602: connection closed while receiving data |
