# Samples

This folder contains runnable examples for the public high-level helpers and a few protocol-focused lower-level demonstrations.

## How to run

Run samples from the repository root. Use TCP port `1025` for the standard getting-started target and UDP port `1035` when you explicitly choose UDP.

```powershell
python samples/high_level_async.py --host 192.168.250.100 --port 1025 --plc-profile melsec:iq-r
python samples/high_level_sync.py --host 192.168.250.100 --port 1025 --plc-profile melsec:iq-r
python samples/08_async_sample.py 192.168.250.100:1025
```

## Sample index

| File | Focus | API level |
| --- | --- | --- |
| `high_level_async.py` | Async connection, typed reads and writes, named snapshots, polling, queued shared connection use. | High-level helpers |
| `high_level_sync.py` | Sync connection, typed reads and writes, named snapshots, polling, contiguous reads. | High-level helpers |
| `08_async_sample.py` | Async client reads from one or more PLC endpoints concurrently. | Async client |
| `01_read_type_name.py` | Read PLC type name and model code. | Sync client |
| `02_device_reads.py` | Read normal word and bit devices. | Sync client |
| `03_random_and_block.py` | Read random devices and block groups. | Sync client |
| `05_target_header.py` | Use an explicit SLMP target header. | Sync client |
| `06_label_reads.py` | Read random labels and array labels. | Sync client |
| `07_verify_3e_4e.py` | Compare manually selected 3E and 4E frames with trace output. | Low-level client |

## Recommended first sample

Start with `high_level_async.py` against `D100`, then use `high_level_sync.py` if your application is synchronous.
