# Communication Test Record

## Test Target

- date: 2026-03-14
- PLC: Mitsubishi MELSEC iQ-R `R08CPU`
- host: `192.168.250.100`
- ports: `TCP 1025`, `UDP 1027`
- library mode: `4E`, binary, `series=iqr`

## Baseline Successes

Confirmed successful on the validated target:

- `0101` Read Type Name over `TCP` and `UDP`
- normal device read/write
- random read/write
- block access
- monitor entry/execute
- `0613` memory read
- `0619` self test
- `read_long_timer(...)`
- `read_long_retentive_timer(...)`

Observed example values:

- model: `R08CPU`
- model code: `0x4801`
- `D1000..D1003` write/readback: `[0x1234, 0xABCD, 0x0001, 0x0002]`

## Important Fixes and Rechecks

### 1. Random bit write encoding

- issue: iQ-R bit set value encoding was wrong
- fix: ON=`01 00`, OFF=`00 00`
- result: `1402` random bit write became OK

### 2. Mixed block compatibility

- issue: the validated PLC rejected some one-request mixed block writes
- fix: the client exposes opt-in mixed-block compatibility fallbacks:
  - `split_mixed_blocks=True`
  - `retry_mixed_on_error=True` for `write_block(...)` on known mixed-write rejection end codes
- 2026-03-14 live comparison result:
  - `readBlock words+bits` on `D300 x2 + M200 x1 packed` -> `0x0000`
  - `writeBlock words only` on `D300 x2` -> `0x0000`
  - `writeBlock bits only` on `M200 x1 packed` -> `0x0000`
  - first one-request `writeBlock mixed` on `D300 x2 + M200 x1 packed` -> `0xC05B`
  - the first failed mixed write left PLC memory unchanged
  - `retry_mixed_on_error=True` then produced `0xC05B -> 0x0000 -> 0x0000`
- 2026-03-19 additional live comparison results:
  - `L16HCPU` first one-request mixed `writeBlock` -> `0xC056`
  - `FX5UC-32MT/D` first one-request mixed `writeBlock` -> `0xC061`
  - `R08CPU + RJ71EN71` first one-request mixed `writeBlock` -> `0xC05B`
- result: no current live-verified hardware path in this project accepts the first one-request mixed `1406` write
- practical record: keep the one-request form implemented, but prefer `split_mixed_blocks=True` for reliable real-hardware operation

### 3. PLC setting changes

After PLC-side setting updates:

- `STN0` read/write became OK
- `LSTN0` read and helper access became OK
- `R0` and `ZR0` read/write became OK

## 2026-03-13 Focused Verification Highlights

### Label family

- `041A`, `141A`, `041C`, `141B` are now confirmed with real external-device-accessible labels
- verified examples:
  - random: `DDD[0]`, `EEE[0,0]`, `FFF[0,0,0]`
  - array: `DDD[0]:1:20`, `EEE[0,0]:1:20`, `FFF[0,0,0]:1:20`
- earlier `0x40C0` results were caused by placeholder or non-eligible labels

### Remote control family

- confirmed OK:
  - `1001` remote run
  - `1002` remote stop
  - `1003` remote pause
- `1005` remote latch clear is state-dependent:
  - `0x4013` observed outside the accepted condition
  - `0x0000` confirmed with the PLC in `STOP`
- `1006` remote reset is intentionally excluded from routine live verification

### Password lock/unlock

- lock and unlock both confirmed
- while locked:
  - unauthenticated `0101` and normal `0401` returned `0xC201`
- wrong password returned `0xC810`
- correct password restored normal access

### Extend-unit and CPU-buffer path

- `0601/1601` are confirmed on the narrow helper-backed path:
  - `module_no=0x03E0`
  - `head=0x00000000`
- this does not yet prove full `G/HG` equivalence

### File family

- current `18xx` result on the validated target:
  - `1810`, `1811`, `1824` -> `0xC061`
  - `1820`, `1827`, `1825`, `1822` -> `0x413E`
  - `1826` -> `0xC207`
- practical conclusion:
  - file commands remain environment-dependent and unresolved

### `1617` clear error

- request acceptance confirmed: `0x0000`
- operator-visible effect still not pinned down

## Current Follow-Up Documents

- [open_items.md](open_items.md)
- [manual_implementation_differences.md](manual_implementation_differences.md)
- [iqr_r08cpu/pending_live_verification_latest.md](iqr_r08cpu/pending_live_verification_latest.md)
- [iqr_r08cpu/special_device_probe_latest.md](iqr_r08cpu/special_device_probe_latest.md)
- [iqr_r08cpu/manual_write_verification_latest.md](iqr_r08cpu/manual_write_verification_latest.md)
- [iqr_r08cpu/manual_label_verification_latest.md](iqr_r08cpu/manual_label_verification_latest.md)
- [iqr_r08cpu/mixed_block_compare_latest.md](iqr_r08cpu/mixed_block_compare_latest.md)
