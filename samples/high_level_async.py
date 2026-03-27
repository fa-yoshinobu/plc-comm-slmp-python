# ruff: noqa: E402
"""
SLMP High-Level Asynchronous Utilities Sample
==============================================
Demonstrates every high-level *async* helper shipped with the slmp package,
including explicit profile selection and QueuedAsyncSlmpClient for concurrent-safe multi-task usage.

Usage
-----
    python samples/high_level_async.py --host 192.168.250.100 --port 1025 --series iqr --frame-type 4e

Common port values
------------------
  1025  iQ-R / iQ-F built-in Ethernet SLMP port (default)
  5000  GX Works3 / GX Works2 simulator
  5007  Q/L series built-in Ethernet SLMP port
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from slmp import (
    AsyncSlmpClient,
    QueuedAsyncSlmpClient,
    poll,
    read_dwords,
    read_named,
    read_typed,
    read_words,
    write_bit_in_word,
    write_named,
    write_typed,
)
from slmp.errors import SlmpError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SLMP asynchronous high-level utilities sample",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--host", required=True, help="PLC IP address or hostname")
    p.add_argument(
        "--port",
        type=int,
        default=1025,
        help=(
            "SLMP port number\n"
            "  1025  iQ-R/iQ-F built-in Ethernet SLMP (default)\n"
            "  5000  GX Works3/GX Works2 simulator\n"
            "  5007  Q/L series built-in Ethernet"
        ),
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Socket timeout in seconds (default 3.0)",
    )
    p.add_argument(
        "--series",
        choices=("iqr", "ql"),
        default="iqr",
        help=("PLC device-encoding family\n  iqr  iQ-R / iQ-F series (default)\n  ql   Q / L series"),
    )
    p.add_argument(
        "--frame-type",
        choices=("3e", "4e"),
        default="4e",
        help="SLMP frame type to use for the entire session (default 4e)",
    )
    p.add_argument(
        "--poll-count",
        type=int,
        default=3,
        help="Number of poll snapshots to capture (default 3)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Demos
# ---------------------------------------------------------------------------


def build_client(host: str, port: int, timeout: float, series: str, frame_type: str) -> AsyncSlmpClient:
    return AsyncSlmpClient(
        host,
        port=port,
        timeout=timeout,
        plc_series=series,
        frame_type=frame_type,
    )


async def demo_explicit_connect(host: str, port: int, timeout: float, series: str, frame_type: str) -> None:
    """
    Explicit connection settings for one SLMP session.

    Parameters:
        host    - PLC IP / hostname
        port    - SLMP port (for example 1025 for iQ-R hardware or 5007 for Q/L hardware)
        timeout - connection timeout in seconds
        series  - explicit PLC series profile ("iqr" or "ql")
        frame_type - explicit SLMP frame type ("4e" or "3e")

    Use case: application code and validation scripts where the PLC profile is
              known and should remain stable for the full session.
    """
    client = build_client(host, port, timeout, series, frame_type)
    await client.connect()
    print(f"[connect] frame={client.frame_type!s}  series={client.plc_series!s}")
    await client.close()


async def demo_typed_rw(client: AsyncSlmpClient) -> None:
    """
    read_typed / write_typed - single device with automatic type conversion.

    dtype codes:
        "U"  unsigned 16-bit int  (1 word)
        "S"  signed 16-bit int    (1 word)
        "D"  unsigned 32-bit int  (2 words)
        "L"  signed 32-bit int    (2 words)
        "F"  IEEE-754 float32     (2 words)

    Use case: reading a float32 sensor value from D200-D201 or writing a
              signed counter preset to D300.
    """
    val_u = await read_typed(client, "D100", "U")
    val_f = await read_typed(client, "D200", "F")
    val_l = await read_typed(client, "D202", "L")
    print(f"[read_typed] D100(U)={val_u}  D200(F)={val_f}  D202(L)={val_l}")

    await write_typed(client, "D100", "U", 42)
    await write_typed(client, "D200", "F", 3.14)
    await write_typed(client, "D202", "L", -100)
    print("[write_typed] Wrote 42->D100, 3.14->D200, -100->D202")


async def demo_chunked_reads(client: AsyncSlmpClient) -> None:
    """
    read_words / read_dwords - contiguous block reads.

    max_per_request: maximum words per SLMP request (protocol limit 960).
    allow_split=True: auto-split requests larger than max_per_request.
                      Without this flag a ValueError is raised immediately
                      when count > max_per_request.

    Use case: reading a recipe table of 1000 words that exceeds the 960-word
              SLMP limit in a single pass.
    """
    words = await read_words(client, "D0", 10)
    print(f"[read_words]  D0-D9 = {words}")

    dwords = await read_dwords(client, "D0", 4)
    print(f"[read_dwords] D0-D7 (as 4 x uint32) = {dwords}")

    large = await read_words(client, "D0", 1000, allow_split=True)
    print(f"[read_words allow_split] D0-D999: {len(large)} words")


async def demo_bit_in_word(client: AsyncSlmpClient) -> None:
    """
    write_bit_in_word - set/clear one bit inside a word device.

    Performs a read-modify-write: reads the word, flips bit_index, writes back.
    bit_index 0 = LSB, 15 = MSB.

    Use case: toggling a single request flag in a PLC control word without
              disturbing the other 15 flag bits.
    """
    await write_bit_in_word(client, "D50", bit_index=3, value=True)
    print("[write_bit_in_word] Set   bit 3 of D50")
    await write_bit_in_word(client, "D50", bit_index=3, value=False)
    print("[write_bit_in_word] Clear bit 3 of D50")


async def demo_named_rw(client: AsyncSlmpClient) -> None:
    """
    read_named / write_named - multi-device mixed-type access by address string.

    Address notation:
        "D100"    unsigned 16-bit (default)
        "D100:F"  float32
        "D100:S"  signed 16-bit
        "D100:D"  unsigned 32-bit
        "D100:L"  signed 32-bit
        "D100.3"  bit 3 inside D100 (bool); bit index is hexadecimal (0-F)

    Use case: dashboard-style read of a heterogeneous parameter set
              (speed as float, error code as int, alarm bit as bool) in one call.
    """
    snapshot = await read_named(
        client,
        [
            "D100",
            "D200:F",
            "D202:L",
            "D50.3",
        ],
    )
    for addr, value in snapshot.items():
        print(f"[read_named]  {addr} = {value!r}")

    await write_named(
        client,
        {
            "D100": 99,
            "D200:F": 1.5,
            "D202:L": -200,
            "D50.3": True,
        },
    )
    print("[write_named] Wrote mixed-type values")


async def demo_poll(client: AsyncSlmpClient, count: int) -> None:
    """
    poll - async generator that yields a snapshot dict every *interval* seconds.

    Use case: background monitoring loop in an asyncio application where the
              main coroutine can concurrently process PLC data while the
              poll generator handles timing.
    """
    print(f"\nPolling {count} snapshots (Ctrl+C to abort early):")
    try:
        i = 0
        async for snap in poll(client, ["D100", "D200:F", "D50.3"], interval=1.0):
            print(f"  [{i + 1}] {snap}")
            i += 1
            if i >= count:
                break
    except asyncio.CancelledError:
        pass


async def demo_queued_client(host: str, port: int, timeout: float, series: str, frame_type: str) -> None:
    """
    QueuedAsyncSlmpClient - thread-safe wrapper for shared async use.

    Returns a queued client that serializes all helper calls so that multiple
    coroutines (e.g. a background poller + a foreground writer) can share one
    TCP connection without interleaving protocol frames.

    Use case: any asyncio application where more than one task needs to
              issue SLMP requests on the same connection simultaneously.
    """
    async with QueuedAsyncSlmpClient(build_client(host, port, timeout, series, frame_type)) as queued:
        # Launch two concurrent tasks that both use the shared connection.
        async def task_a() -> None:
            v = await read_typed(queued, "D100", "U")  # type: ignore[arg-type]
            print(f"[queued task-A] D100 = {v}")

        async def task_b() -> None:
            v = await read_typed(queued, "D200", "F")  # type: ignore[arg-type]
            print(f"[queued task-B] D200:F = {v}")

        await asyncio.gather(task_a(), task_b())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run(args: argparse.Namespace) -> None:
    # 1. Connect once with explicit stable settings
    await demo_explicit_connect(args.host, args.port, args.timeout, args.series, args.frame_type)

    # 2-5. high-level helpers - connect once, run all demos
    async with build_client(args.host, args.port, args.timeout, args.series, args.frame_type) as client:
        await demo_typed_rw(client)
        await demo_chunked_reads(client)
        await demo_bit_in_word(client)
        await demo_named_rw(client)
        await demo_poll(client, args.poll_count)

    # 6. QueuedAsyncSlmpClient
    await demo_queued_client(args.host, args.port, args.timeout, args.series, args.frame_type)

    print("Done.")


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except SlmpError as e:
        print(f"SLMP error: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
