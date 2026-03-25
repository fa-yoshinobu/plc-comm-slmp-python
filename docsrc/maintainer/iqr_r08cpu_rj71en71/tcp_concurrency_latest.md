# TCP Concurrency Report

- Date: 2026-03-13 16:34:46
- Host: 192.168.250.100
- Port: 1025
- Series: iqr
- Device: D1000
- Points: 1
- Bit unit: False
- Client levels: 1, 2, 4, 8, 16, 32, 40, 48, 56, 60, 62, 63, 64
- Rounds per client: 20
- Address allocation: each client uses a distinct offset range to avoid same-address access
- PLC TCP connection setting at measurement time: `63`

| Item | Status | Detail |
|---|---|---|
| clients=1 | OK | count=20, avg_ms=6.973, p95_ms=8.698, p99_ms=9.156, max_ms=9.270, rate_per_s=129.4, errors=none |
| clients=2 | OK | count=40, avg_ms=7.894, p95_ms=10.435, p99_ms=11.126, max_ms=11.320, rate_per_s=228.0, errors=none |
| clients=4 | OK | count=80, avg_ms=13.544, p95_ms=19.438, p99_ms=24.597, max_ms=28.247, rate_per_s=266.2, errors=none |
| clients=8 | OK | count=160, avg_ms=24.656, p95_ms=32.697, p99_ms=39.119, max_ms=46.025, rate_per_s=296.0, errors=none |
| clients=16 | OK | count=320, avg_ms=54.669, p95_ms=73.017, p99_ms=86.268, max_ms=95.820, rate_per_s=275.7, errors=none |
| clients=32 | OK | count=640, avg_ms=105.128, p95_ms=121.909, p99_ms=142.184, max_ms=161.162, rate_per_s=287.9, errors=none |
| clients=40 | OK | count=800, avg_ms=133.355, p95_ms=153.116, p99_ms=169.375, max_ms=197.747, rate_per_s=285.0, errors=none |
| clients=48 | OK | count=960, avg_ms=165.115, p95_ms=187.938, p99_ms=210.681, max_ms=232.003, rate_per_s=216.3, errors=none |
| clients=56 | OK | count=1120, avg_ms=200.415, p95_ms=224.283, p99_ms=268.325, max_ms=287.924, rate_per_s=265.1, errors=none |
| clients=60 | OK | count=1200, avg_ms=212.868, p95_ms=250.520, p99_ms=276.923, max_ms=308.151, rate_per_s=269.0, errors=none |
| clients=62 | OK | count=1240, avg_ms=219.517, p95_ms=243.851, p99_ms=278.172, max_ms=312.063, rate_per_s=243.0, errors=none |
| clients=63 | OK | count=1260, avg_ms=218.265, p95_ms=247.466, p99_ms=281.851, max_ms=300.734, rate_per_s=247.8, errors=none |
| clients=64 | NG | count=0, elapsed_s=20.012, errors=ConnectionRefusedError=1 |
| clients=64 sample error 1 | NG | [WinError 10061] No connection could be made because the target machine actively refused it. |
