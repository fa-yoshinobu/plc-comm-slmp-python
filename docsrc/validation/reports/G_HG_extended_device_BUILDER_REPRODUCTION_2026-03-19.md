# G/HG Extended Specification Builder Reproduction

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Area: typed Extended Specification `_ext` builders for `G` and `HG`
- Goal: reproduce the captured iQ-R `U3E0\G10` and `U3E0\HG20` request payload layout without enabling direct normal-device `G/HG` access

## 2. Implemented Change

- `encode_extended_device_spec(...)` now uses a dedicated iQ-R `G/HG` layout that matches the captured payload order.
- Typed direct APIs still reject `G/HG`.
- Typed Extended Specification `_ext` APIs now allow `G/HG` and reuse the same capture-aligned builder across:
  - `read_devices_ext`, `write_devices_ext`
  - `read_random_ext`
  - `write_random_words_ext`, `write_random_bits_ext`
  - `register_monitor_devices_ext`

## 3. Expected Payloads

- `G10` read: `00 00 0A 00 00 00 AB 00 00 00 E0 03 FA 01 00`
- `HG20` write one word `0x0032`: `00 00 14 00 00 00 2E 00 00 00 E0 03 FA 01 00 32 00`

## 4. Verification

Commands:

```powershell
python -m pytest tests/test_slmp.py -q
python -m ruff check slmp tests
python -m mypy slmp
```

Unit-test coverage added:

- `encode_extended_device_spec(...)` for `G10` and `HG20`
- `read_devices_ext("G10", ...)` payload shape
- `write_devices_ext("HG20", ...)` payload shape
- direct `read_devices("G0", ...)` and `read_devices("HG0", ...)` still rejected

## 5. Remaining Risk

- This report proves builder reproduction and API gating behavior in unit tests only.
- Live PLC validation is still required because previous hardware runs returned `0xC061` with the old generic builder.
