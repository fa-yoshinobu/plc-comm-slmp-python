# Mixed Read Load Report

- Date: 2026-03-13 16:05:44
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- CPU state during measurement: RUN
- Base device: D1000
- Rotate span: 200
- Rounds: 2000
- Direct points: 1
- Random word count: 2
- Block points: 16
- Block offset: 100

| Item | Status | Detail |
|---|---|---|
| overall | OK | count=6000, avg_ms=3.922, p95_ms=5.517, p99_ms=8.322, max_ms=16.363, rate_per_s=248.6, errors=0 |
| 0401 direct read | OK | count=2000, avg_ms=3.599, p95_ms=3.786, p99_ms=8.322, max_ms=10.212, rate_per_s=277.8, errors=none |
| 0403 random read | OK | count=2000, avg_ms=3.839, p95_ms=3.879, p99_ms=5.686, max_ms=16.133, rate_per_s=260.5, errors=none |
| 0406 block read | OK | count=2000, avg_ms=4.328, p95_ms=5.560, p99_ms=6.162, max_ms=16.363, rate_per_s=231.1, errors=none |
