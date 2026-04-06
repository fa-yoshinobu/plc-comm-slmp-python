# Remote Control Hardware Validation

- Date: 2026-03-19
- Validated target: `iQ-R R08CPU`
- Host: `192.168.250.100`
- Transport: `TCP 1025`
- Series mode: `iqr`

## Scope

This report formalizes the current live evidence for the remote-control family:

- `1001` Remote Run
- `1002` Remote Stop
- `1003` Remote Pause
- `1005` Remote Latch Clear

## Confirmed Result

The following commands are confirmed on the validated target:

- `1001 remote run` -> `OK`, `end_code=0x0000`
- `1002 remote stop` -> `OK`, `end_code=0x0000`
- `1003 remote pause` -> `OK`, `end_code=0x0000`
- `1002 remote stop (restore)` -> `OK`, `end_code=0x0000`

`1005 remote latch clear` is state-dependent:

- `0x4013` was observed outside the accepted condition
- `0x0000` was later confirmed with the PLC in `STOP`

`1006 remote reset` remains intentionally excluded from routine live verification because it is disruptive.

## Practical Conclusion

- Normal remote run/stop/pause control is hardware-confirmed on the validated `R08CPU` target.
- Remote latch clear must not be treated as unconditional; the PLC state matters.
- Remote reset is not part of the routine validation baseline.

## Source Evidence

- `internal_docs/maintainer/iqr_r08cpu/pending_live_verification_latest.md`
- `internal_docs/maintainer/communication_test_record.md`
- `internal_docs/maintainer/iqr_r08cpu/README.md`

