[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/samples/)

# SLMP Python Samples

This folder contains runnable examples for the recommended high-level helper APIs.

## Recommended Samples

### `high_level_sync.py`

```powershell
python samples/high_level_sync.py --host 192.168.250.100 --port 1025 --series iqr
```

Included examples:

- typed scalar reads and writes
- chunked word and dword reads
- bit-in-word updates
- mixed `read_named_sync` / `write_named_sync`
- periodic polling

### `high_level_async.py`

```powershell
python samples/high_level_async.py --host 192.168.250.100 --port 1025
```

Included examples:

- `open_and_connect`
- typed scalar reads and writes
- chunked reads with `allow_split=True`
- bit-in-word updates
- mixed `read_named` / `write_named`
- `poll`
- shared queued connection usage

## Why these two samples are the primary path

They use the same helper set described in the user guide:

- `open_and_connect`
- `open_and_connect_queued`
- `read_typed` / `write_typed`
- `read_words` / `read_dwords`
- `write_bit_in_word`
- `read_named` / `write_named`
- `poll`

## Other Files

Older numbered sample files remain in this folder for protocol-focused demonstrations.
They are no longer the main user-facing examples.
