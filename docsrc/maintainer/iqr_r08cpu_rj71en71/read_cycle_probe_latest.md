# Read Cycle Probe Report

- Date: 2026-03-13 16:38:04
- PLC path under test: R08CPU + RJ71EN71
- Host: `192.168.250.101`
- Series: `iqr`
- Device: `SD420`
- CPU state assumption during measurement: `RUN`
- Method: single-client repeated `0401` word read at fixed device

## Scope

This report measures practical repeated-read cycle speed through the `RJ71EN71` path and compares it with the direct-connect `R08CPU` RUN baseline.

Conditions:

- one client only
- one `0401` word read per cycle
- fixed address `SD420`
- `5000` cycles per transport
- no intentional delay between cycles
- no remote RUN/STOP command was issued during this measurement

## Important Note About `SD420`

`SD420` is intentionally used as a changing system value, so this report should be read as a timing comparison, not a fixed-value stability test.

## Result

| Transport | Port | Cycles | Errors | Avg Cycle | P95 | P99 | Max | Effective Rate | Top Observed Values |
|---|---|---|---|---|---|---|---|---|---|
| TCP | 1025 | 5000 | 0 | `6.844 ms` | `8.710 ms` | `9.635 ms` | `16.570 ms` | `145.8 cycles/s` | `6328 x2, 8734 x2, 8987 x2, 9029 x2, 9825 x2` |
| UDP | 1027 | 5000 | 0 | `5.709 ms` | `6.834 ms` | `7.118 ms` | `16.330 ms` | `175.1 cycles/s` | `29479 x3, 20505 x2, 21171 x2, 22340 x2, 23196 x2` |

## Comparison Against Direct `R08CPU` RUN Baseline

| Transport | Direct RUN Avg | RJ71EN71 Avg | Delta Avg | Direct RUN Rate | RJ71EN71 Rate | Delta Rate |
|---|---|---|---|---|---|---|
| TCP | `3.641 ms` | `6.844 ms` | `+3.203 ms` | `274.5 cycles/s` | `145.8 cycles/s` | `-128.7 cycles/s` |
| UDP | `3.578 ms` | `5.709 ms` | `+2.131 ms` | `279.4 cycles/s` | `175.1 cycles/s` | `-104.3 cycles/s` |

## Practical Conclusion

- TCP: direct RUN avg `3.641 ms` -> RJ71EN71 avg `6.844 ms` (delta `+3.203 ms`), rate delta `-128.7 cycles/s`
- UDP: direct RUN avg `3.578 ms` -> RJ71EN71 avg `5.709 ms` (delta `+2.131 ms`), rate delta `-104.3 cycles/s`
