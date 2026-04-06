# `U4\\G0` Probe Report

- Date: `2026-03-13`
- Target: direct `R08CPU`
- Host: `192.168.250.100`
- Transport: `TCP 1025`
- Assumption supplied during verification:
  - engineering-tool notation `U4\\G0`
  - unit `U4` corresponds to start I/O `XY40`
  - two practical SLMP-side interpretations were tested:
    - manual-aligned protocol extension specification `0x0004` (`0040H` -> upper 3 digits)
    - exploratory raw value `0x0040`

## Tested Paths

1. `0601` extend-unit read/writeback with `module_no=0x0040`
2. `0601` extend-unit read/writeback with `module_no=0x0004`
3. Extended Specification `0401/0082` with:
   - extension specification `0x0004` (manual-aligned) and `0x0040` (exploratory)
   - direct memory `0xF8` (`U\\G` module access)
   - direct memory `0xFA` (CPU buffer style comparison)
   - target header `module_io=0x03FF` and `module_io=0x0040`
4. Extended Specification block access with `0406/0082` and `1406/0082`
   - one word block at `G0`
   - manual-aligned `ext=0x0004`, `direct=0xF8`
   - exploratory candidate field orders were also checked

## Results

| Path | Parameters | Result | Detail |
| --- | --- | --- | --- |
| `0601` | `module_no=0x0040`, `head=0x00000000` | NG | `0x4043` |
| `0601` | `module_no=0x0040`, `head=0x00000002` | NG | `0x4043` |
| `0601` | `module_no=0x0040`, `head=0x00000004` | NG | `0x4043` |
| `0601/1601` | `module_no=0x0004`, `head=0x00000000` | OK | `before=3d 86`, same-value writeback preserved |
| `0601/1601` | `module_no=0x0004`, `head=0x00000002` | OK | `before=96 00`, same-value writeback preserved |
| `0601/1601` | `module_no=0x0004`, `head=0x00000004` | OK | `before=43 68`, same-value writeback preserved |
| `0401/0082` | `target.module_io=0x03FF`, `ext=0x0004`, `direct=0xF8`, `G0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x03FF`, `ext=0x0004`, `direct=0xF8`, `HG0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x0004`, `ext=0x0004`, `direct=0xF8`, `G0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x0004`, `ext=0x0004`, `direct=0xF8`, `HG0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x03FF`, `ext=0x0004`, `direct=0xFA`, `G0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x03FF`, `ext=0x0004`, `direct=0xFA`, `HG0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x0004`, `ext=0x0004`, `direct=0xFA`, `G0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x0004`, `ext=0x0004`, `direct=0xFA`, `HG0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x03FF`, `ext=0x0040`, `direct=0xF8`, `G0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x03FF`, `ext=0x0040`, `direct=0xF8`, `HG0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x0040`, `ext=0x0040`, `direct=0xF8`, `G0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x0040`, `ext=0x0040`, `direct=0xF8`, `HG0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x03FF`, `ext=0x0040`, `direct=0xFA`, `G0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x03FF`, `ext=0x0040`, `direct=0xFA`, `HG0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x0040`, `ext=0x0040`, `direct=0xFA`, `G0` | NG | `0xC061` |
| `0401/0082` | `target.module_io=0x0040`, `ext=0x0040`, `direct=0xFA`, `HG0` | NG | `0xC061` |
| `0406/0082` | `target.module_io=0x03FF`, current implementation layout, `ext=0x0004`, `direct=0xF8`, `G0 x1` | NG | `0xC061` |
| `0406/0082` | `target.module_io=0x03FF`, manual-tail candidate layout, `ext=0x0004`, `direct=0xF8`, `G0 x1` | NG | `0xC061` |
| `0406/0082` | `target.module_io=0x0040`, current implementation layout, `ext=0x0004`, `direct=0xF8`, `G0 x1` | NG | `0xC061` |
| `0406/0082` | `target.module_io=0x0040`, manual-tail candidate layout, `ext=0x0004`, `direct=0xF8`, `G0 x1` | NG | `0xC061` |
| `1406/0082` | `target.module_io=0x03FF`, current implementation layout, `ext=0x0004`, `direct=0xF8`, `G0 x1` | NG | `0xC061` |
| `1406/0082` | `target.module_io=0x03FF`, manual-tail candidate layout, `ext=0x0004`, `direct=0xF8`, `G0 x1` | NG | `0xC061` |
| `1406/0082` | `target.module_io=0x0040`, current implementation layout, `ext=0x0004`, `direct=0xF8`, `G0 x1` | NG | `0xC061` |
| `1406/0082` | `target.module_io=0x0040`, manual-tail candidate layout, `ext=0x0004`, `direct=0xF8`, `G0 x1` | NG | `0xC061` |

## Current Interpretation

- Treating `U4` as start I/O `0x0040` did not work for `0601`; it returned `0x4043`.
- This matches the current manual reading only partially:
  - for Extended Specification `U\\G`, the manual says to use the upper 3 digits of the start I/O number in the extension specification
  - therefore `0x0004` is the manual-aligned Extended Specification interpretation for `U4`
- Treating `U4` as unit number `0x0004` did work for `0601/1601`; read and same-value writeback were both successful.
- However, the returned values did not match the live `GX Works` display of `U4\\G0` (`U4\\G0=0`, `U4\\G15=FFFF` at the time of comparison).
- Extended Specification `U\\G` style trials still returned `0xC061` for both `0x0004` and `0x0040`.
- Extended Specification block access (`0406/1406`) also remained `0xC061` for the tested one-block `G0` forms.
- Current practical conclusion:
  - `0601/1601 module_no=0x0004` is not enough to claim equivalence with engineering-tool `U4\\G0`.
  - The direct Extended Specification `U\\G` request format for `U4\\G0` remains unresolved even when using the manual-aligned extension value `0x0004`.
  - Trying block commands (`0406/1406`) does not currently improve acceptance on this PLC.
