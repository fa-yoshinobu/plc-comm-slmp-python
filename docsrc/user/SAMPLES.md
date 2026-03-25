# Samples

This page summarizes the runnable examples that ship with the repository.

The canonical source files live under the repository `samples/` directory in a
source checkout.

## How To Run

Run examples from the repository root:

```powershell
python samples/01_read_type_name.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr
```

## Safety

- all examples in this set are read-only
- label examples depend on PLC-side label configuration and `Access from External Device`

## Example List

### 01. Basic connection and type name

```powershell
python samples/01_read_type_name.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr
```

### 02. Normal device reads

```powershell
python samples/02_device_reads.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr --word-device D100 --word-points 2 --bit-device M100 --bit-points 5
```

### 03. Random and block reads

```powershell
python samples/03_random_and_block.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr
```

### 05. Explicit target header

```powershell
python samples/05_target_header.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr --network 0x00 --station 0xFF --module-io 0x03FF --multidrop 0x00
```

### 06. Label reads

```powershell
python samples/06_label_reads.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr --label-random LabelW --label-random LabelB
```

Array-label example:

```powershell
python samples/06_label_reads.py --host 192.168.250.101 --port 1025 --transport tcp --series iqr --label-array "ArrayLabel[0]:1:4"
```

!!! note
    Sample `04` is missing (it was not created).

### 07. 3E / 4E Frame Switching and Trace Hook

This demo shows how to switch frame types and inspect raw frames using a `trace_hook`. You can verify the content of transmitted frames even without a physical PLC.

```powershell
python samples/07_verify_3e_4e.py 192.168.250.101 1025
```

### 08. Asynchronous Simultaneous Reading from Multiple PLCs

This demo uses `AsyncSlmpClient` and `asyncio.gather` to simultaneously retrieve data from multiple PLCs.

```powershell
python samples/08_async_sample.py 192.168.1.10:1025 192.168.1.11:1025
```

If arguments are omitted, it connects to `127.0.0.1:5000` and `127.0.0.1:5001` (assuming local simulators).

For maintainer-oriented verification wrappers, use
[Script Reference](../maintainer/SCRIPT_REFERENCE.md).
