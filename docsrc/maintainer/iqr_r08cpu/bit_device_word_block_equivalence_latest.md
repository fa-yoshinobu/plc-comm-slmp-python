# Bit Device Word-vs-Block Equivalence Report

- Date: 2026-03-13 17:15:58
- Path under test: direct `R08CPU`
- Host: `192.168.250.100`
- Port: `1025`
- Transport: `tcp`
- Series: `iqr`
- Source matrix: `internal_docsrc/iqr_r08cpu/device_access_matrix.csv`
- Test packed word pattern for writable devices: `0xA55A`
- Method:
  - compare `0401` word read and `0406` bit block read at the same base device
  - writable devices also receive the same pattern once via bit write and once via word write
  - all writable devices are restored to their original 16-bit image

## Result Summary

- OK: 20
- NG: 0

| Device Code | Device | Status | Detail |
|---|---|---|---|
| B | B100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| CC | CC10 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| CS | CS10 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| DX | DX100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| DY | DY100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| F | F100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| L | L1000 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| LCC | LCC10 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| LCS | LCS10 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| M | M1000 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| S | S100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, write_test=SKIP |
| SB | SB100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| SM | SM100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| STC | STC10 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| STS | STS10 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| TC | TC10 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| TS | TS10 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| V | V100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| X | X100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |
| Y | Y100 | OK | read_only=word:0x0000, block:0x0000, from_bits:0x0000, read_only_match=True, bit_write_word=0xa55a, bit_write_block=0xa55a, bit_write_match=True, word_write_word=0xa55a, word_write_block=0xa55a, word_write_match=True, restore_match=True |

