# Device Range Probe Report

- Date: 2026-03-23 16:45:24
- Host: 192.168.250.100
- Port: 1025
- Transport: tcp
- Series: ql
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Specs: 3
- Include writeback: False
- Include out-of-range write: False
- Summary: PASS=6, WARN=2, NG=1, SKIP=0

| Item | Status | Detail |
|---|---|---|
| D in-range read | PASS | device=D7999, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| D crossing read | PASS | device=D7999, points=2, expected=end_code!=0x0000, observed=end_code=0xC056 |
| D out-of-range read | PASS | device=D8000, points=1, expected=end_code!=0x0000, observed=end_code=0xC056 |
| M in-range read | PASS | device=M3071, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| M crossing read | WARN | device=M3071, points=2, expected=end_code!=0x0000, observed=end_code=0x0000, values=[False, False] |
| M out-of-range read | WARN | device=M3072, points=1, expected=end_code!=0x0000, observed=end_code=0x0000, values=[False] |
| R in-range read | PASS | device=R32767, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| R crossing read | PASS | device=R32767, points=2, expected=end_code!=0x0000, observed=end_code=0xC056 |
| R | NG | device=R32767, error=R device number out of supported range (0..32767): 32768 |
