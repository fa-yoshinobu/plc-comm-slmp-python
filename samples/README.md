# Samples

This folder contains runnable examples for the public high-level helpers and a few protocol-focused lower-level demonstrations.

Use only test addresses that are safe for your PLC program before you run any write example.

## How to run

Run samples from the repository root. Use TCP port `1025` for the standard getting-started target and UDP port `1035` when you explicitly choose UDP. For cable-pull reconnect checks, prefer UDP so the sample observes recovery without waiting for TCP socket cleanup.

```powershell
python samples/high_level_async.py --host 192.168.250.100 --port 1025 --plc-profile melsec:iq-r
python samples/high_level_sync.py --host 192.168.250.100 --port 1025 --plc-profile melsec:iq-r
python samples/polling_reconnect.py --host 192.168.250.100 --port 1025 --plc-profile melsec:iq-r
python samples/polling_reconnect.py --host 192.168.250.100 --port 1035 --transport udp --plc-profile melsec:iq-r
python samples/multi_plc_monitor.py --plc line-a=192.168.250.100,melsec:iq-r,1035,udp --plc line-b=192.168.250.101,melsec:iq-r,1035,udp --tag d100=D100:U --cycles 3 --dry-run
python samples/config_polling.py --config samples/config_polling.example.json --dry-run
python samples/07_async_sample.py 192.168.250.100:1025
```

## Sample index

| File | Focus | API level |
| --- | --- | --- |
| `high_level_async.py` | Async connection, typed reads and writes, named snapshots, polling, queued shared connection use. | High-level helpers |
| `high_level_sync.py` | Sync connection, typed reads and writes, named snapshots, polling, contiguous reads. | High-level helpers |
| `polling_reconnect.py` | Read-only polling loop with automatic reconnect and backoff after transport loss. | High-level helpers |
| `multi_plc_monitor.py` | Read-only monitoring of the same tag set across multiple PLCs, with one async task per PLC. | Operational recipe |
| `config_polling.py` | Read-only periodic collection from a JSON or YAML config file, with optional CSV output. | Operational recipe |
| `config_polling.example.json` | Example config for `config_polling.py`. | Operational recipe |
| `07_async_sample.py` | Async client reads from one or more PLC endpoints concurrently. | Async client |
| `01_read_type_name.py` | Read PLC type name and model code. | Sync client |
| `02_device_reads.py` | Read normal word and bit devices. | Sync client |
| `03_random_and_block.py` | Read random devices and block groups. | Sync client |
| `04_target_header.py` | Use an explicit SLMP target header. | Sync client |
| `05_label_reads.py` | Read random labels and array labels. | Sync client |
| `06_verify_3e_4e.py` | Compare manually selected 3E and 4E frames with trace output. | Low-level client |

## Recommended first sample

Start with `high_level_async.py` against `D100`, then use `high_level_sync.py` if your application is synchronous.

## High-level helper coverage

`high_level_async.py` demonstrates:

- `SlmpConnectionOptions`
- `open_and_connect`
- `read_typed` / `write_typed`
- `read_words_single_request` / `read_dwords_single_request`
- `read_words_chunked` / `read_dwords_chunked`
- `write_bit_in_word`
- `read_named` / `write_named`
- `poll`
- queued shared connection usage

`high_level_sync.py` demonstrates the synchronous equivalents:

- `open_and_connect_sync`
- `read_typed_sync` / `write_typed_sync`
- `read_words_single_request_sync` / `read_dwords_single_request_sync`
- `read_words_chunked_sync` / `read_dwords_chunked_sync`
- `write_bit_in_word_sync`
- `read_named_sync` / `write_named_sync`
- `poll_sync`

The older numbered samples remain for protocol-focused demonstrations. The
recommended user path is the high-level helper layer.

## Operational recipes

`multi_plc_monitor.py` is for live dashboards or watch windows where several
PLCs should be monitored independently. Each PLC has its own connection and
reconnect loop, so a timeout on one PLC does not pause reads from the others.
The sample is read-only and uses `read_named`.

`config_polling.py` is for periodic collection where tags should be changed
without editing Python code. JSON works with the Python standard library.
YAML files are also accepted when `PyYAML` is installed. CSV output uses long
rows: `timestamp,plc,tag,value`.

Use `--dry-run` with either operational recipe to validate arguments or config
without opening a PLC connection.
