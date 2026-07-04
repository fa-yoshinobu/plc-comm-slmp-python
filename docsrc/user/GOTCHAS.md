# Gotchas

Use this page only for library-specific caveats.

Shared SLMP setup, profile, point-limit, and end-code symptoms live in the shared
[SLMP Troubleshooting & Codes](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/slmp/troubleshooting-codes/)
page. For profile limits and device availability, use the shared
[SLMP Profile Parameters](https://fa-yoshinobu.github.io/plc-comm-docs-site/slmp/profile-reference/parameters/)
page.

## Current library-specific caveats

| Area | Symptom | Guidance |
| --- | --- | --- |
| Request ordering | Several coroutines sharing one raw client can produce mismatched responses or intermittent failures. | A raw client is one frame stream and not a multi-caller scheduler. Use `open_and_connect`, which returns a queued async client that serializes calls. |

```python
values = await asyncio.gather(
    read_typed(client, "D100", "U"),
    read_typed(client, "D101", "U"),
)
```
