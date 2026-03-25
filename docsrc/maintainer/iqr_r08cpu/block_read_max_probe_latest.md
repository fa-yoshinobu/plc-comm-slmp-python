# Block Read Maximum Probe Report

- Date: 2026-03-13 16:31:00
- PLC: Mitsubishi MELSEC iQ-R `R08CPU`
- Host: `192.168.250.101`
- Transport: `TCP`
- Port: `1025`
- Series: `iqr`

## Scope

This probe checked the practical maximum for a single word block read on the current validated target.

Test target:

- command: `0406` block read
- block type: single word block
- start device: `D100`

The probe intentionally avoided head addresses such as `D0`.

## Result

Observed result:

| Points | Result | Detail |
|---|---|---|
| 512 | OK | accepted |
| 768 | OK | accepted |
| 896 | OK | accepted |
| 944 | OK | accepted |
| 960 | OK | accepted |
| 961 | NG | client-side `ValueError: read_block total device points out of range (<=960): 961` |

## Practical Conclusion

- current client-side block-read limit for one request is `<=960` total device points
- on the validated `R08CPU`, a single word block read remained valid through `960` points
- no lower practical PLC-side limit was observed within the maintained client limit
