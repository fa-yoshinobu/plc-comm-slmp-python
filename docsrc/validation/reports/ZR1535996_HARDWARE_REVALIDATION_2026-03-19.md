# ZR1535996 Hardware Revalidation

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Goal: confirm that the repository can directly read and write `ZR1535996` on the target PLC

## 2. Live Command

Executed from the repository working tree:

```python
from slmp.client import SlmpClient

HOST = "192.168.250.100"
PORT = 1025
DEVICE = "ZR1535996"
WRITE_VALUE = 1234

with SlmpClient(HOST, port=PORT, transport="tcp", plc_series="ql") as cli:
    before = cli.read_devices(DEVICE, 1, bit_unit=False, series="ql")[0]
    cli.write_devices(DEVICE, [WRITE_VALUE], bit_unit=False, series="ql")
    after = cli.read_devices(DEVICE, 1, bit_unit=False, series="ql")[0]
```

## 3. Observed Result

- host: `192.168.250.100`
- port: `1025`
- transport: `tcp`
- series: `ql`
- device: `ZR1535996`
- before: `658` (`0x0292`)
- written: `1234` (`0x04D2`)
- readback: `1234` (`0x04D2`)
- readback match: `yes`
- restore: `not performed`, per operator request

## 4. Practical Conclusion

- The current repository can directly read and write `ZR1535996` on the validated live target.
- This is no longer only a capture-derived assumption.
- The result confirms that large decimal `ZR` addresses can be operational on a suitable PLC environment.
- PLC-side device availability must still be treated as target-specific and parameter-dependent.

## 5. Relationship to Earlier Evidence

- `docsrc/validation/reports/ZR1535996_CAPTURE_2026-03-19.md` recorded packet-capture evidence for direct `0401/1401` access to the same device.
- This report adds repository-driven live confirmation through the current Python client implementation.

