# SLMP Python Quality-Overhaul Migration

This document records source migrations required by the cross-library quality overhaul. The approved rationale and acceptance history remain in the workspace decision records.

## Connection construction

Always provide `port`, `transport`, `plc_profile`, and a complete `SlmpTarget`. The library no longer chooses a destination port, TCP, a PLC family, or an own-station route when those values are missing.

## Profile-bound requests

Remove request-level `series=` arguments. Construct the client with the exact canonical PLC profile; device encoding, subcommand family, password shape, frame type, and address rules are derived from that profile.

`DeviceRef` is profile-bound. Construct it as `DeviceRef(code, number, plc_profile)`, or parse text with an explicit profile.

## Raw access

Replace direct `request()` calls and command-specific raw wrappers with one of the following:

- the semantic public method for the operation; or
- `raw_command(command, subcommand=..., payload=...)` for maintainer investigation.

All three raw command fields are required. The client owns 4E serial allocation and response correlation.

## Required operation choices

Specify choices that change the command meaning or destination: `bit_unit`, CPU-buffer `module_no`, remote run/pause mode arguments, and long-timer `head_no`/`points`.

## Multiple-request behavior

Replace chunked helpers and automatic mixed-block splitting with explicit application-controlled requests. If a logical read spans requests, the application must define snapshot/version checks. If a logical write spans requests, it must define partial-success and retry handling.

## Extended Device access

Use qualified device text such as `U3E0\G10`. For supported index/indirect modification, wrap it in `SlmpExtendedDevice` with `SlmpIndexZ`, `SlmpIndexLz`, or `SlmpIndirect`. Raw extension bitfields are no longer a public contract.
