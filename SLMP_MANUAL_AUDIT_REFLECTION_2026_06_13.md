# SLMP Manual Audit Reflection - 2026-06-13

This repository keeps the Python-specific record of the SLMP manual audit so
the external memo repository is not required to understand the current state.

Audit basis:

- Manual: MELSEC SLMP reference manual SH-080931-R.
- Live target used for the final decisions: R120PCPU at `192.168.250.101:1025`.
- Q/L password check: `melsec-q` route with password `1234`.
- Cross-stack confirmation date: 2026-06-13.

## Decisions Reflected In This Repository

| ID | Decision | Python status |
|---|---|---|
| A-1 Remote Reset `1006` | Use `1006/0000 + 01 00`. Payload-less reset returned `0xC061`; `01 00` reset succeeded when remote reset was allowed on the PLC. | Reflected in high-level request builders and shared vectors. |
| A-2 Random bit write `1402/0003` | Keep ON as `01 00`. The manual-like `00 01` returned success but did not turn the bit ON in live readback. | No code change. Existing behavior is retained. |
| A-3 Remote Stop `1002` | High-level Remote Stop sends only fixed `01 00`. The old force variant is not a manual branch. | Force argument removed from sync/async high-level APIs. |
| A-4 Remote Password `1630/1631` | iQ-R/iQ-L use little-endian length plus ASCII password; Q/L uses `04 00 + 4 ASCII bytes`. | Q/L 4-byte format is implemented. |
| A-5 ZR address radix | ZR device numbers are decimal. The manual table entry that looks hexadecimal is treated as unreliable. | No code change. |
| A-6 Step relay `S` | R120PCPU can read and monitor `S`, but write failed and GX Works cannot monitor it in the user workflow. | Not exposed as a public high-level device. |
| A-7 Self Test `0619` | High-level API follows the manual: 1..960 bytes and ASCII `0`-`9` / `A`-`F` only. | Reflected. |
| A-8 Link Direct `J` | Keep the current 11-byte layout and `0080/0081`; `0082/0083` failed with `0xC061` on iQ-R. | No code change. |
| A-9 `G` / `HG` extension layout | Keep the current capture-compatible layout. The manual order failed with `0xC061` on R120PCPU. | No code change. |
| A-10 point limits | Add manual preflight checks for continuous, random, block, memory, and helper-layer requests. | Reflected. |

## Verification Result

The cross-stack rerun recorded for the audit was:

```text
python -m pytest -q
229 passed, 122 subtests passed
```

The Python implementation was also checked for:

- Remote Reset wire form `1006/0000/0001`.
- Remote Stop no-force high-level API.
- Shared golden vectors including `remote_reset_fixed_data`.
- Manual point-limit preflight checks before transport.
- TCP_NODELAY on sync and async TCP transports.

## Notes To Keep With This Repository

- `Self Test` payloads from 256 to 960 bytes are allowed by the manual-facing
  API, but R120PCPU live testing showed imperfect loopback data for that range.
  Keep the API limit at 960 and document the device-specific behavior.
- Q/L legacy point limits are based on the manual formulas and cross-stack
  reflection. They were not fully live-verified on every Q/L model.
- The core Python encoder enforces Q/L passwords as exactly 4 bytes and
  iQ-R/iQ-L passwords as 6..32 bytes.
- Raw low-level APIs remain intentional escape hatches; document that they can
  bypass high-level manual preflight checks.
