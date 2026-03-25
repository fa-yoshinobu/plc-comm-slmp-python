# Mixed Block Comparison Report

- Date: 2026-03-14 19:50:32
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Model: R08CPU
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Word block: D300 x2 -> [0x87F7, 0x80BE]
- Bit block: M200 x1 packed -> [0x6DFE]
- Mixed write options: split_mixed_blocks=False, retry_mixed_on_error=True
- Keep written value: False
- First-pass comparison recommendation: keep both mixed-write fallback options disabled so the first PLC response is preserved
- Note: if retry_mixed_on_error=True triggers an internal retry, the reported memory-changed state is the post-call state, not an observation between the first failed request and the retry

| Scenario | Status | End codes | Memory changed | Trace count | Notes |
|---|---|---|---|---|---|
| readBlock words+bits | OK | 0x0000 | n/a | 1 | words=[0x0000, 0x0000], bits=[0x0000] |
| writeBlock words only | OK | 0x0000 | yes | 1 | after=[0x87F7, 0x80BE], restore=OK |
| writeBlock bits only | OK | 0x0000 | yes | 1 | after=[0x6DFE], restore=OK |
| writeBlock mixed | OK | 0xC05B -> 0x0000 -> 0x0000 | yes | 3 | after_words=[0x87F7, 0x80BE], after_bits=[0x6DFE], request_count=3 |

## readBlock words+bits

- API: read_block(word_blocks=[('D300', 2)], bit_blocks=[('M200', 1)], split_mixed_blocks=False)
- Devices: word=D300 x2, bit=M200 x1 packed
- Warnings: none
- Error: none
- Returned words: [0x0000, 0x0000]
- Returned bits: [0x0000]

```text
attempt 1: end_code=0x0000
request: 54 00 03 00 00 00 00 FF FF 03 00 18 00 10 00 06 04 02 00 01 01 2C 01 00 00 A8 00 02 00 C8 00 00 00 90 00 01 00
response: D4 00 03 00 00 00 00 FF FF 03 00 08 00 00 00 00 00 00 00 00 00
```

## writeBlock words only

- API: write_block(word_blocks=[('D300', [0x87F7, 0x80BE])], bit_blocks=[])
- Before words: [0x0000, 0x0000]
- Test words: [0x87F7, 0x80BE]
- After words: [0x87F7, 0x80BE]
- Restore status: OK
- Restored words: [0x0000, 0x0000]
- Warnings: none
- Error: none

```text
attempt 1: end_code=0x0000
request: 54 00 04 00 00 00 00 FF FF 03 00 14 00 10 00 06 14 02 00 01 00 2C 01 00 00 A8 00 02 00 F7 87 BE 80
response: D4 00 04 00 00 00 00 FF FF 03 00 02 00 00 00
```

## writeBlock bits only

- API: write_block(word_blocks=[], bit_blocks=[('M200', [0x6DFE])])
- Before bits: [0x0000]
- Test bits: [0x6DFE]
- After bits: [0x6DFE]
- Restore status: OK
- Restored bits: [0x0000]
- Warnings: none
- Error: none

```text
attempt 1: end_code=0x0000
request: 54 00 08 00 00 00 00 FF FF 03 00 12 00 10 00 06 14 02 00 00 01 C8 00 00 00 90 00 01 00 FE 6D
response: D4 00 08 00 00 00 00 FF FF 03 00 02 00 00 00
```

## writeBlock mixed

- API: write_block(word_blocks=[('D300', [0x87F7, 0x80BE])], bit_blocks=[('M200', [0x6DFE])], split_mixed_blocks=False, retry_mixed_on_error=True)
- Before words: [0x0000, 0x0000]
- Before bits: [0x0000]
- Test words: [0x87F7, 0x80BE]
- Test bits: [0x6DFE]
- After words: [0x87F7, 0x80BE]
- After bits: [0x6DFE]
- Request count: 3
- Restore status: OK
- Restored words: [0x0000, 0x0000]
- Restored bits: [0x0000]
- Warnings: mixed block write was rejected with 0xC05B; retrying as separate word-only and bit-only block writes
- Error: none

```text
attempt 1: end_code=0xC05B
request: 54 00 0C 00 00 00 00 FF FF 03 00 1E 00 10 00 06 14 02 00 01 01 2C 01 00 00 A8 00 02 00 C8 00 00 00 90 00 01 00 F7 87 BE 80 FE 6D
response: D4 00 0C 00 00 00 00 FF FF 03 00 0B 00 5B C0 00 FF FF 03 00 06 14 02 00

attempt 2: end_code=0x0000
request: 54 00 0D 00 00 00 00 FF FF 03 00 14 00 10 00 06 14 02 00 01 00 2C 01 00 00 A8 00 02 00 F7 87 BE 80
response: D4 00 0D 00 00 00 00 FF FF 03 00 02 00 00 00

attempt 3: end_code=0x0000
request: 54 00 0E 00 00 00 00 FF FF 03 00 12 00 10 00 06 14 02 00 00 01 C8 00 00 00 90 00 01 00 FE 6D
response: D4 00 0E 00 00 00 00 FF FF 03 00 02 00 00 00
```
