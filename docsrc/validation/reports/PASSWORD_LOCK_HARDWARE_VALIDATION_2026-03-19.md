# Password Lock Hardware Validation

- Date: 2026-03-19
- Validated target: `iQ-R R08CPU`
- Host: `192.168.250.101`
- Transport: `TCP 1025`
- Series mode: `iqr`

## Scope

This report formalizes the current live evidence for the remote password family:

- `1630` Unlock
- `1631` Lock

## Confirmed Result

The validated live sequence confirmed:

- `1630 unlock (pre)` -> `OK`, `end_code=0x0000`
- `1631 lock` -> `OK`, `end_code=0x0000`
- `1630 unlock` -> `OK`, `end_code=0x0000`

Additional observed behavior while locked:

- unauthenticated `0101` and normal `0401` returned `0xC201`
- wrong password returned `0xC810`
- correct password restored normal access

## Practical Conclusion

- Password lock and unlock are hardware-confirmed on the validated `R08CPU` target.
- The observed post-lock behavior is consistent with the expected access restriction model:
  - normal access is blocked while locked
  - wrong credentials are explicitly rejected
  - correct unlock restores ordinary communication

## Source Evidence

- `docsrc/maintainer/iqr_r08cpu/pending_live_verification_latest.md`
- `docsrc/maintainer/communication_test_record.md`
- `docsrc/maintainer/iqr_r08cpu/README.md`

