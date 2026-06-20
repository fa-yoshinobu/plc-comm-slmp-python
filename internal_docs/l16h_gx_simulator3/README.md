# GX Simulator 3 L16H Target

This folder records the local GX Simulator 3 quick connection check for the
user-specified L16H simulation endpoint.

## Target

- Simulator: GX Simulator 3
- GX Works3 version: 1.125F
- Target machine: L16H simulation, as specified by the operator
- Host: 127.0.0.1
- TCP port: 5511
- Scope: quick SLMP profile availability check
- Required GX Works3/GX Simulator 3 setting for write-capable SLMP tests:
  `Enable/Disable Online Change: Enable All (SLMP)`

## Result

SLMP communication was confirmed for all four tested low-level frame/subcommand
combinations.

The full command matrix was then run with the primary L-compatible combination:
3E frame + Q/L compatible device subcommands (`0000`/`0001`).

## Reports

- [slmp_connection_result_latest.md](slmp_connection_result_latest.md)
- [gx_simulator3_command_availability_latest.md](gx_simulator3_command_availability_latest.md)
