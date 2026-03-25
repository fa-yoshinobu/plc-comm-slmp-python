# Read Cycle Probe Report

- Date: 2026-03-13 17:05:00
- PLC: Mitsubishi MELSEC iQ-R `R08CPU`
- Host: `192.168.250.101`
- Series: `iqr`
- Device: `SD420`
- Method: single-client repeated `0401` word read at fixed device

## Scope

This report compares practical repeated-read cycle speed for the current validated target in both `STOP` and `RUN`.

Conditions:

- one client only
- one `0401` word read per cycle
- fixed address `SD420`
- `5000` cycles per transport and per CPU state
- no intentional delay between cycles
- state transition method:
  - `1001` remote run
  - `1002` remote stop

## Important Note About `SD420`

`SD420` did not stay constant during the probe.

Observed values changed continuously in both `STOP` and `RUN`, so this report should be read as a transport/timing comparison, not a fixed-value stability test.

## Result

| CPU State | Transport | Port | Cycles | Errors | Avg Cycle | P95 | P99 | Max | Effective Rate |
|---|---|---|---|---|---|---|---|---|---|
| STOP | TCP | 1025 | 5000 | 0 | `3.632 ms` | `3.721 ms` | `3.874 ms` | `10.566 ms` | `275.3 cycles/s` |
| STOP | UDP | 1027 | 5000 | 0 | `3.574 ms` | `3.656 ms` | `3.733 ms` | `9.284 ms` | `279.7 cycles/s` |
| RUN | TCP | 1025 | 5000 | 0 | `3.641 ms` | `3.727 ms` | `3.896 ms` | `9.134 ms` | `274.5 cycles/s` |
| RUN | UDP | 1027 | 5000 | 0 | `3.578 ms` | `3.667 ms` | `3.763 ms` | `9.118 ms` | `279.4 cycles/s` |

## Practical Conclusion

- under this exact test condition, practical repeated read speed was about `3.6 ms` per cycle in both `STOP` and `RUN`
- effective repeated-read rate stayed around `275` to `280` cycles per second
- no meaningful speed difference was observed between `STOP` and `RUN`
- `UDP` remained slightly faster on average than `TCP`, but the difference was still small

## Delta Summary

- `TCP`
  - `STOP`: `3.632 ms`
  - `RUN`: `3.641 ms`
  - delta: `+0.009 ms`
- `UDP`
  - `STOP`: `3.574 ms`
  - `RUN`: `3.578 ms`
  - delta: `+0.004 ms`

These deltas are small enough that they should not be treated as a meaningful behavioral change for this environment.
