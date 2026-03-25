# R/ZR Overlap Verification

- Timestamp: `2026-03-13 17:23:49 `
- Target: `direct R08CPU`, host `192.168.250.101`, `TCP 1025`
- Series: `iqr`
- Scope: verify whether writing `R` can be read back through the overlapping `ZR` alias, and vice versa

## Summary

- Result: `2/2 OK`
- Verified overlap aliases:
  - `R1000` <-> `ZR1000`: `OK`
  - `R32767` <-> `ZR32767`: `OK`

## Notes

- Each case used temporary writes in both directions and restored the original value at the end of the case.

## Detailed Results

| Case | R device | ZR device | Before R | Before ZR | Write via R | Read R after R write | Read ZR after R write | Write via ZR | Read R after ZR write | Read ZR after ZR write | Restore R | Restore ZR | Status | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| lower_shared_region | R1000 | ZR1000 | 0 | 0 | 4951 | 4951 | 4951 | 9320 | 9320 | 9320 | 0 | 0 | OK | shared lower-range alias at decimal device number 1000 |
| upper_shared_region_boundary | R32767 | ZR32767 | 0 | 0 | 4951 | 4951 | 4951 | 9320 | 9320 | 9320 | 0 | 0 | OK | shared upper boundary alias at decimal device number 32767 |
