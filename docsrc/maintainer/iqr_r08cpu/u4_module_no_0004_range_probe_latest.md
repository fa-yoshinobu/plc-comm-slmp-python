# `U4` Practical Range Probe (`module_no=0x0004`)

- Date: `2026-03-13`
- Target: direct `R08CPU`
- Host: `192.168.250.101`
- Transport: `TCP 1025`
- Method: `0601/1601` via raw extend-unit access
- Note: this report only shows that `module_no=0x0004` is readable/writable at low addresses. It does not prove equivalence with engineering-tool `U4\G*`.

| Head | Result | Detail |
| --- | --- | --- |
| `0x00000000` | OK | before=0x863D, after=0x863D |
| `0x00000002` | OK | before=0x0096, after=0x0096 |
| `0x00000004` | OK | before=0x6843, after=0x6843 |
| `0x00000006` | OK | before=0x0000, after=0x0000 |
| `0x00000008` | OK | before=0xFFF8, after=0xFFF8 |
| `0x0000000A` | OK | before=0x005F, after=0x005F |
| `0x0000000C` | OK | before=0x0000, after=0x0000 |
| `0x0000000E` | OK | before=0x0020, after=0x0020 |
| `0x00000010` | OK | before=0x1DFF, after=0x1DFF |
| `0x00000012` | OK | before=0x0016, after=0x0016 |
| `0x00000014` | OK | before=0x0003, after=0x0003 |
| `0x00000016` | OK | before=0x0000, after=0x0000 |
| `0x00000018` | OK | before=0x0000, after=0x0000 |
| `0x0000001A` | OK | before=0x0000, after=0x0000 |
| `0x0000001C` | OK | before=0x0000, after=0x0000 |
| `0x0000001E` | OK | before=0x0000, after=0x0000 |
| `0x00000020` | OK | before=0x0000, after=0x0000 |
