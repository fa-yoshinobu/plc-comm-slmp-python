"""Sample script to demonstrate asynchronous SLMP communication.

Key points:
- AsyncSlmpClient uses asyncio and does not block the event loop while waiting
  for a PLC response, so other coroutines can run in the meantime.
- Within a single connection, requests are serialized internally (the client
  holds an asyncio.Lock), so issuing multiple reads on the same client via
  asyncio.gather is safe but not faster per-connection.
- The real concurrency benefit is reading from MULTIPLE PLCs simultaneously:
  all network round-trips overlap in time.
"""

import asyncio
import os
import sys

# Add project root to path to import slmp
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from slmp.async_client import AsyncSlmpClient


async def read_one_plc(host: str, port: int) -> dict[str, object]:
    """Connect to a single PLC and return a snapshot of several devices."""
    async with AsyncSlmpClient(host, port, plc_family="iq-r") as cli:
        info = await cli.read_type_name()
        d100 = await cli.read_devices("D100", 1)
        m0 = await cli.read_devices("M0", 1, bit_unit=True)
        return {"host": host, "model": info.model, "D100": d100[0], "M0": bool(m0[0])}


async def main() -> None:
    """Demonstrate reading from multiple PLCs concurrently."""
    # --- Target configuration ------------------------------------------------
    # Edit these to match your environment.  The script accepts an optional
    # list of HOST:PORT pairs on the command line:
    #   python samples/08_async_sample.py 192.168.250.100:1025 192.168.1.11:1025
    targets: list[tuple[str, int]] = []

    for arg in sys.argv[1:]:
        host, _, port_str = arg.partition(":")
        targets.append((host.strip(), int(port_str) if port_str else 5000))

    if not targets:
        # Default: two local simulator instances on different ports
        targets = [("127.0.0.1", 5000), ("127.0.0.1", 5001)]

    # --- Read all PLCs concurrently ------------------------------------------
    # Each read_one_plc() call opens its OWN connection.  asyncio.gather lets
    # all network round-trips overlap in time; this is the async advantage.
    print(f"Reading {len(targets)} PLC(s) concurrently...")
    results = await asyncio.gather(
        *(read_one_plc(host, port) for host, port in targets),
        return_exceptions=True,
    )

    for result in results:
        if isinstance(result, BaseException):
            print(f"  Error: {result}")
        else:
            print(f"  [{result['host']}] model={result['model']}  D100={result['D100']}  M0={result['M0']}")


if __name__ == "__main__":
    asyncio.run(main())
