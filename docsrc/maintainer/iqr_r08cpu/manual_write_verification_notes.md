# Manual Write Verification Notes

This note records how to run the interactive temporary write check for the current validated target.

## Target

- PLC: Mitsubishi MELSEC iQ-R `R08CPU`
- Host: `192.168.250.100`
- Transport: `TCP`
- Port: `1025`
- Series: `iqr`
- Matrix: `internal_docsrc/iqr_r08cpu/device_access_matrix.csv`

## Purpose

Use `scripts/slmp_manual_write_verification.py` when:

- a human operator will watch the PLC in GX Works or another engineering tool
- the repository matrix already contains representative verification addresses
- a temporary write and restore check is required

The script:

1. reads the current value
2. writes a temporary test value
3. waits for human judgement as `Y`, `N`, or `Skip`
4. restores the original value unless `--keep-written-value` is specified

## Basic Example

Check one representative `D` device:

```powershell
python scripts/slmp_manual_write_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --matrix internal_docsrc/iqr_r08cpu/device_access_matrix.csv --device-code D --limit 1
```

Check several device families in one run:

```powershell
python scripts/slmp_manual_write_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --matrix internal_docsrc/iqr_r08cpu/device_access_matrix.csv --device-code D --device-code M --device-code W --device-code ZR
```

Resume later and skip rows already judged in an earlier report:

```powershell
python scripts/slmp_manual_write_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --matrix internal_docsrc/iqr_r08cpu/device_access_matrix.csv --resume-from-report internal_docsrc/iqr_r08cpu/manual_write_verification_latest.md
```

Focused check for `LTC` / `LTS` / `LSTC` / `LSTS`:

```powershell
python scripts/slmp_manual_write_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --matrix internal_docsrc/iqr_r08cpu/device_access_matrix.csv --device-code LTC
```

Notes for this special case:

- these rows are not part of the normal sweep because direct read is `NG`
- the script uses `read_ltc_states(...)`, `read_lts_states(...)`, `read_lstc_states(...)`, or `read_lsts_states(...)` for the temporary before/restore state
- the temporary write is sent with `1402` random bit write to the direct device code

## Operator Input

At runtime, the script asks for:

- `Press Enter to write temporarily, or type 'skip' to skip this row`
- `Human check result [Y/N/Skip]`

Meaning:

- `Y`
  - the human confirmed that the temporary value was reflected as expected
- `N`
  - the human confirmed that the expected reflection did not match
- `Skip`
  - no final human judgement was entered for that row

## Output

Default report:

- `internal_docsrc/iqr_r08cpu/manual_write_verification_latest.md`

Each run also writes a timestamped copy under:

- `internal_docsrc/iqr_r08cpu/archive/`

## Current Confirmed Example

The following command was executed successfully:

```powershell
python scripts/slmp_manual_write_verification.py --host 192.168.250.100 --port 1025 --transport tcp --series iqr --matrix internal_docsrc/iqr_r08cpu/device_access_matrix.csv --device-code D --limit 1
```

Observed result:

- target row: `D D1000`
- temporary write: `0x0000 -> 0x0001`
- restore: `0x0000`
- report status: `SKIP`

This confirms that the temporary write and restore flow works on the validated target. The human visual confirmation step still depends on the operator at execution time.

