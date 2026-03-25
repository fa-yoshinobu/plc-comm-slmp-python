# PLC Setting Change Log Template

Use this template whenever PLC-side settings that can affect communication behavior are changed.

This includes:

- device ranges
- enabled/disabled device families
- module routing / target header information
- labels / files / remote-operation permissions
- CPU buffer / extension-related setup

## 1. Change Summary

- Date:
- Changed by:
- PLC / CPU:
- Host / port:
- Reason for change:
- Source evidence:
  - screenshot path:
  - project file / version:
  - manual / note reference:

## 2. Settings Changed

| Area | Old value | New value | Expected impact |
| --- | --- | --- | --- |
| device range | | | |
| enabled device families | | | |
| target/module settings | | | |
| label/file/remote settings | | | |

## 3. Required Re-Verification

Run the minimum applicable set:

1. Basic connection
```powershell
python scripts/slmp_connection_check.py --host <HOST> --port <PORT> --transport tcp --series iqr --read-device D1000 --points 1
```

2. Device range boundary probe
```powershell
python scripts/slmp_device_range_probe.py --host <HOST> --port <PORT> --transport tcp --series iqr --spec-file <SPEC_FILE> --include-writeback
```

3. Open-item recheck
```powershell
python scripts/slmp_open_items_recheck.py --host <HOST> --port <PORT> --transport tcp --series iqr
```

4. Special device probe if `LT/LST` or `G/HG` related settings changed
```powershell
python scripts/slmp_special_device_probe.py --host <HOST> --port <PORT> --transport tcp --series iqr
```

5. Other-station probe if target header or route assumptions changed
```powershell
python scripts/slmp_other_station_check.py --host <HOST> --port <PORT> --transport tcp --series iqr --target-file <TARGET_FILE>
```

## 4. Re-Verification Result

| Check | Result | Report / note |
| --- | --- | --- |
| connection check | | |
| device range probe | | |
| open items | | |
| special device probe | | |
| other station | | |

## 5. Conclusions

- What improved:
- What did not change:
- New failures:
- Documents updated:

## 6. Follow-Up Actions

1. Update `internal_docsrc/plc_device_range_expectations.md` if the configured ranges changed.
2. Update `internal_docsrc/open_items.md` if pass/fail conclusions changed.
3. Update `internal_docsrc/communication_test_record.md` with the new live verification date and result.

