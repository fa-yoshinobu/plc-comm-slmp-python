# High-Level Samples

The recommended sample entry points are the two buildable high-level examples in `samples/`.

## `samples/high_level_sync.py`

Run:

```powershell
python samples/high_level_sync.py --host 192.168.250.100 --port 1025 --series iqr
```

What it demonstrates:

- `SlmpConnectionOptions`
- `open_and_connect_sync`
- `read_typed_sync`
- `write_typed_sync`
- `read_words_single_request_sync`
- `read_dwords_single_request_sync`
- `read_words_chunked_sync`
- `read_dwords_chunked_sync`
- `write_bit_in_word_sync`
- `read_named_sync`
- `write_named_sync`
- `poll_sync`

Example scenarios inside the sample:

- read one `ushort`, one `short`, one `float32`, and one signed 32-bit value
- write a typed recipe value
- read contiguous areas through explicit `single_request` and `chunked` helpers
- set and clear one bit inside a control word
- read a mixed snapshot such as `["D100", "D200:F", "D202:L", "D50.3"]`
- poll the same snapshot repeatedly

## `samples/high_level_async.py`

Run:

```powershell
python samples/high_level_async.py --host 192.168.250.100 --port 1025
```

What it demonstrates:

- `SlmpConnectionOptions`
- `open_and_connect`
- `read_typed`
- `write_typed`
- `read_words_single_request`
- `read_dwords_single_request`
- `read_words_chunked`
- `read_dwords_chunked`
- `write_bit_in_word`
- `read_named`
- `write_named`
- `poll`
- queued shared connection usage

Example scenarios inside the sample:

- connect with an explicit frame/profile pair
- read and write typed scalar values
- read large arrays with explicit chunked helpers
- update one flag inside a word
- read and write mixed logical values by address string
- poll a snapshot every second
- share one connection across multiple concurrent tasks

## Notes

- These two samples are the recommended user path.
- Older numbered samples remain in the repository for protocol-focused demonstrations, but the user manual now centers on the high-level helper layer.
