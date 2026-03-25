# G/HG Extended Specification Hardware Revalidation

Date: 2026-03-19

## 1. Scope

- Repository: `plc-comm-slmp-python`
- Target PLC: `R120PCPU`
- Goal: revalidate the current iQ-R capture-aligned Extended Specification `G/HG` builder on real hardware

## 2. Command

```powershell
python scripts/slmp_g_hg_extended_device_recheck.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --g-device U3E0\G10 --hg-device U3E0\HG20
```

## 3. Result

- `G10`: `before=0x0000`, temporary write `0x001E`, readback `0x001E`, restored `0x0000`
- `HG20`: `before=0x0000`, temporary write `0x0032`, readback `0x0032`, restored `0x0000`
- Summary: `OK=2`, `NG=0`, `SKIP=0`
- The qualified device strings `U3E0\G10` and `U3E0\HG20` were accepted by the current `_ext` APIs.

## 4. Generated Local Evidence

- Report: `internal_docsrc/iqr_r120pcpu/g_hg_extended_device_recheck_latest.md`
- Frame dumps: `internal_docsrc/iqr_r120pcpu/frame_dumps_extended_device_g_hg_recheck/`

## 5. Conclusion

- The current iQ-R capture-aligned Extended Specification builder is operational on the tested R120PCPU target for:
  - single-word `0401/0082` read
  - single-word `1401/0082` write
  - readback verification
  - restore to the original value
- In the user's current multi-CPU environment, `U3E0`, `U3E1`, `U3E2`, and `U3E3` are the expected `G/HG` CPU-memory qualifiers for CPU No.1..No.4.
- Lower `U**` values must not be read as CPU-memory selectors by default; they remain ordinary I/O unit addresses unless the target environment defines otherwise.
- This does not yet prove broader equivalence across:
  - other addresses
  - multi-point requests
  - UDP / alternate frame types
  - other PLC families


