# Label Family Hardware Validation

- Date: 2026-03-19
- Validated target: `iQ-R R08CPU`
- Host: `192.168.250.100`
- Transport: `TCP 1025`
- Series mode: `iqr`

## Scope

This report formalizes the existing live evidence for the label command family:

- `041A` Array Label Read
- `141A` Array Label Write
- `041C` Random Label Read
- `141B` Random Label Write

## Confirmed Result

The label family is confirmed on real external-device-accessible labels.

Confirmed examples:

- random labels:
  - `LabelB`
  - `LabelW`
  - `DDD[0]`
  - `EEE[0,0]`
  - `FFF[0,0,0]`
- array labels:
  - `DDD[0]:1:20`
  - `EEE[0,0]:1:20`
  - `FFF[0,0,0]:1:20`

## Evidence Summary

From the pending live verification run:

- `041A label array read` -> `OK`
- `141A label array write` -> `OK`
- `041C label random read` -> `OK`
- `141B label random write` -> `OK`

From the manual label verification run:

- `8` rows processed
- summary: `OK=8`, `NG=0`, `SKIP=0`
- each checked label completed:
  - read current value
  - temporary write
  - observed readback
  - restore to the original value

## Practical Conclusion

- The label family is hardware-confirmed on the validated `R08CPU` target when the labels are real external-device-accessible labels.
- Earlier `0x40C0` failures are interpreted as label-definition or external-access eligibility problems, not as a protocol implementation gap in the confirmed cases.

## Source Evidence

- `internal_docs/maintainer/iqr_r08cpu/pending_live_verification_latest.md`
- `internal_docs/maintainer/iqr_r08cpu/manual_label_verification_latest.md`
- `internal_docs/maintainer/communication_test_record.md`

