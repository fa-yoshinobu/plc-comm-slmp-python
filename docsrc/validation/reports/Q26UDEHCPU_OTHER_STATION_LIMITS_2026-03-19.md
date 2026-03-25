# Q26UDEHCPU Other-Station Limits

- Date: 2026-03-19
- Scope: `scripts/slmp_other_station_check.py`
- Host: `192.168.250.101`
- Target PLC: `Q26UDEHCPU` built-in Ethernet

## Purpose

Record the observed behavior of `SELF` versus `NW1` and `NW2` other-station route probes from a Q-series built-in Ethernet endpoint.

## Observed Results

| Command | Result | Detail |
|---|---|---|
| `python scripts/slmp_other_station_check.py --host 192.168.250.101 --port 1025 --transport tcp --series auto --frame-type auto --target SELF` | PASS | `Resolved frame=3e`, `access_profile=ql`, `D1000` read succeeded with `values=[0]`, `read_type_name()` returned `SLMP error end_code=0xC059 command=0x0101 subcommand=0x0000` |
| `python scripts/slmp_other_station_check.py --host 192.168.250.101 --port 1025 --transport tcp --series auto --frame-type auto --target NW1-ST1` | FAIL | `timed out` |
| `python scripts/slmp_other_station_check.py --host 192.168.250.101 --port 1025 --transport tcp --series auto --frame-type auto --target NW1-ST2` | FAIL | `timed out` |
| `python scripts/slmp_other_station_check.py --host 192.168.250.101 --port 1025 --transport tcp --series auto --frame-type auto --target NW2-ST1` | FAIL | `timed out` |
| `python scripts/slmp_other_station_check.py --host 192.168.250.101 --port 1025 --transport tcp --series auto --frame-type auto --target NW2-ST2` | FAIL | `timed out` |

## Interpretation

- The validated Q-series endpoint accepted a self-target route probe.
- The same endpoint did not return successful responses for the tested `NW1` and `NW2` other-station route probes.
- This is evidence for a practical limitation on the validated path, not a blanket protocol claim for every Q-series configuration.

## Notes

- Separate live checks from an R-series origin reached `NW1-ST1` and `NW1-ST2` successfully and resolved them to `R08CPU` and `R00CPU`.
- Treat Q-series built-in Ethernet other-station support as path-dependent until routing evidence or manual citations confirm broader support.
