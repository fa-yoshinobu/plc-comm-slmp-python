# Additional Register Boundary Probe Report

Historical note:
- This was an earlier ad hoc probe.
- `RD` conclusions in this file were later corrected by the repeatable `register_boundary_probe_latest.md` run on 2026-03-13.
- Use `internal_docsrc/iqr_r08cpu/register_boundary_probe_latest.md` as the current authoritative focused boundary report.

- Date: 2026-03-13 13:16:09
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Detected Z last accepted start address: Z19
- Detected LZ last accepted start address: LZ1
- Detected RD last accepted start address: RD524287

| Family | Item | End code | Detail |
|---|---|---|---|
| Z | read Z19 x1 | 0x0000 | [0] |
| Z | read Z19 x2 | 0x4031 | None |
| Z | read Z20 x1 | 0x4031 | None |
| Z | write Z19 x1 | 0x0000 | [0] |
| Z | write Z20 x1 | 0x4031 | [0] |
| LZ | read LZ1 x1 | 0x0000 | [0] |
| LZ | read LZ1 x2 | 0x0000 | [0, 0] |
| LZ | read LZ2 x1 | 0x4031 | None |
| LZ | write LZ1 x1 | 0xC051 | [0] |
| LZ | write LZ1 x2 | 0x0000 | [0, 0] |
| LZ | write LZ2 x1 | 0xC051 | [0] |
| LZ | write LZ2 x2 | 0x4031 | [0, 0] |
| RD | read RD524287 x1 | 0x0000 | [0] |
| RD | read RD524287 x2 | 0x0000 | len=2 |
| RD | read RD524287 x16 | 0x0000 | len=16 |
| RD | read RD524287 x64 | 0x0000 | len=64 |
| RD | read RD524288 x1 | 0x4031 | None |
| RD | read RD524288 x2 | 0x4031 | None |
| RD | read RD524288 x16 | 0x4031 | None |
| RD | write RD524287 x2 | 0x0000 | len=2 |
| RD | write RD524287 x16 | 0x0000 | len=16 |
| RD | write RD524287 x64 | 0x0000 | len=64 |

