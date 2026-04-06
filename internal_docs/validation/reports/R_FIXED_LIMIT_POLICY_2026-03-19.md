# R Fixed Limit Policy

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Goal: apply the workspace decision that `R` is capped at `32767` while other families must not inherit PLC-setting-dependent limits from one validated target

## 2. Implemented Rule

- `R32767` remains encodable
- `R32768` and above now raise `ValueError` at client-side device encoding time
- The rule is enforced through `encode_device_spec(...)`, so it applies consistently to:
  - direct read/write
  - random read/write
  - block read/write
  - monitor registration
  - sync and async clients

## 3. Non-Goals

- This change does not add PLC-setting-dependent hard limits for other device families.
- In particular, it does not add a `ZR` ceiling.
- `ZR` remains PLC-response-driven apart from protocol-format encoding limits.

## 4. Verification

Automated checks:

- `encode_device_spec("R32767", ...)` succeeds
- `encode_device_spec("R32768", ...)` raises `ValueError`
- `read_devices("R32768", ...)` raises `ValueError`
- `write_devices("R32768", ...)` raises `ValueError`

## 5. Practical Reading

- Treat the `R` family as a deliberate project policy exception.
- Do not generalize that exception to `ZR` or other device families.
