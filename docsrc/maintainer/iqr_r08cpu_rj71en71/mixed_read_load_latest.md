# Mixed Read Load Report

- Date: 2026-03-13 16:21:56
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Base device: D1000
- Rotate span: 200
- Rounds: 2000
- Direct points: 1
- Random word count: 2
- Block points: 16
- Block offset: 100

| Item | Status | Detail |
|---|---|---|
| overall | OK | count=6000, avg_ms=5.502, p95_ms=6.500, p99_ms=6.958, max_ms=16.325, rate_per_s=180.9, errors=0 |
| 0401 direct read | OK | count=2000, avg_ms=5.463, p95_ms=6.495, p99_ms=6.904, max_ms=8.166, rate_per_s=183.1, errors=none |
| 0403 random read | OK | count=2000, avg_ms=5.538, p95_ms=6.418, p99_ms=6.970, max_ms=16.325, rate_per_s=180.6, errors=none |
| 0406 block read | OK | count=2000, avg_ms=5.506, p95_ms=6.557, p99_ms=6.990, max_ms=10.971, rate_per_s=181.6, errors=none |
