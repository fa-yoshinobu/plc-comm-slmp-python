# Gotchas

Use this page only for library-specific caveats.

Shared SLMP setup, profile, point-limit, and end-code symptoms live in the shared
[SLMP Troubleshooting & Codes](https://plc-comm-docs-site.fa-labo.com/plc-setup/slmp/troubleshooting-codes/)
page. For profile limits and device availability, use the shared
[SLMP Profile Parameters](https://plc-comm-docs-site.fa-labo.com/slmp/profile-reference/parameters/)
page.

## Current library-specific caveats

| Area | Symptom | Guidance |
| --- | --- | --- |
| IPv6 endpoint | Client construction rejects an IPv6 literal, or connection fails because a hostname has no IPv4 result. | Sync and async TCP/UDP clients are IPv4-only. Use an IPv4 literal or a hostname with an IPv4 result; the first IPv4 result is used and there is no IPv6 fallback. |
| Request ordering | Several callers share one client. | Ordinary sync and async clients process valid operations in FIFO order. Async cancellation while queued removes that operation without sending; `close()` rejects the active and queued generation. Do not add a second queue wrapper. |
| Aggregate size | `read_named` or `poll` exceeds one random-read request. | The complete plan is rejected before transport. Split it into explicit application calls and define the required snapshot/consistency behavior. |
| Ambiguous write result | A state-changing operation fails after send may have started. | Catch `SlmpOutcomeUnknownError`, inspect `reason` and `cause`, verify PLC state, and do not retry blindly. |
| Malformed ACK | An ACK-only API raises `SlmpOutcomeUnknownError` with reason `PROTOCOL`. | The PLC returned unexpected success data or another response-identity defect. The transport has been retired; reconcile PLC state before opening a new generation. Use `raw_command()` only for an intentionally data-bearing vendor command. |

```python
values = await asyncio.gather(
    read_typed(client, "D100", "U"),
    read_typed(client, "D101", "U"),
)
```
