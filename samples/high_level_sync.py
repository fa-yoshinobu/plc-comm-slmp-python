# ruff: noqa: E402
"""
SLMP High-Level Synchronous Utilities Sample
=============================================
Demonstrates every high-level *sync* helper shipped with the slmp package.
Run against a real PLC or the GX Works3 simulator.

Usage
-----
    python samples/high_level_sync.py --host 192.168.250.100 --port 1025
    python samples/high_level_sync.py --host 192.168.250.100 --port 1027 --transport udp

Common port values
------------------
  1025  iQ-R / iQ-F built-in Ethernet SLMP port, TCP (default)
  1027  iQ-R / iQ-F built-in Ethernet SLMP port, UDP
  5000  GX Works3 / GX Works2 simulator
  5007  Q/L series built-in Ethernet SLMP port
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from slmp import (
    SlmpConnectionOptions,
    normalize_address,
    open_and_connect_sync,
    poll_sync,
    read_dwords_chunked_sync,
    read_dwords_single_request_sync,
    read_named_sync,
    read_typed_sync,
    read_words_chunked_sync,
    read_words_single_request_sync,
    write_bit_in_word_sync,
    write_named_sync,
    write_typed_sync,
)
from slmp.errors import SlmpError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SLMP synchronous high-level utilities sample",
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
        "--series",
        choices=("iqr", "ql"),
        default="iqr",
        help=("PLC device-encoding family\n  iqr  iQ-R / iQ-F series (default)\n  ql   Q / L series"),
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Socket timeout in seconds (default 3.0)",
    )
    p.add_argument(
        "--monitoring-timer",
        type=lambda x: int(x, 0),
        default=0x0010,
        help=(
            "SLMP monitoring timer, units of 250 ms (default 0x0010 = 4 s).\n"
            "The PLC aborts the request after this interval if it cannot respond."
        ),
    )
    p.add_argument(
        "--poll-count",
        type=int,
        default=3,
        help="Number of poll snapshots to capture (default 3)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    print(f"[normalize_address] x20 -> {normalize_address('x20')}")

    # SlmpConnectionOptions:
    #   host             - PLC IP / hostname
    #   port             - SLMP port; depends on PLC hardware and firmware settings
    #   transport        - "tcp" (default) or "udp"
    #   timeout          - socket timeout in seconds; increase on slow networks
    #   plc_series       - "iqr" (iQ-R/iQ-F, 32-bit device numbers) or
    #                      "ql"  (Q/L series, 24-bit device numbers)
    #   frame_type       - "3E" or "4E"; set explicitly when the PLC requires
    #                      a specific frame/profile pairing
    #   monitoring_timer - how long (in 250 ms units) the PLC waits for a
    #                      response before aborting; 0x0010 = 4 s
    #   trace_hook       - optional callback(SlmpTraceFrame) for protocol tracing
    options = SlmpConnectionOptions(
        host=args.host,
        port=args.port,
        transport="tcp",
        timeout=args.timeout,
        plc_series=args.series,
        monitoring_timer=args.monitoring_timer,
    )

    with open_and_connect_sync(options) as client:
        print(f"Connected to {args.host}:{args.port} ({args.series})")

        # ---------------------------------------------------------------
        # 1. read_typed_sync / write_typed_sync
        #
        # Read or write a single device with automatic type conversion.
        # dtype codes: "U" unsigned-16, "S" signed-16,
        #              "D" unsigned-32, "L" signed-32, "F" float32
        #
        # Use case: reading a sensor value stored as float32 in D200-D201.
        # ---------------------------------------------------------------
        val_u = read_typed_sync(client, "D100", "U")  # unsigned 16-bit word
        val_s = read_typed_sync(client, "D101", "S")  # signed 16-bit word
        val_f = read_typed_sync(client, "D200", "F")  # float32 (2 words)
        val_l = read_typed_sync(client, "D202", "L")  # signed 32-bit (2 words)
        print(f"[read_typed_sync] D100(U)={val_u}  D101(S)={val_s}  D200(F)={val_f}  D202(L)={val_l}")

        write_typed_sync(client, "D100", "U", 42)
        write_typed_sync(client, "D200", "F", 3.14)
        write_typed_sync(client, "D202", "L", -100)
        print("[write_typed_sync] Wrote 42->D100, 3.14->D200, -100->D202")

        # ---------------------------------------------------------------
        # 2. explicit contiguous helpers
        #
        # Use *_single_request_sync when one logical request must stay one PLC request.
        # Use *_chunked_sync only when multi-request chunking is explicitly acceptable.
        #
        # Use case: reading a recipe table of 200 words in one call.
        # ---------------------------------------------------------------
        words = read_words_single_request_sync(client, "D0", 10)
        print(f"[read_words_single_request_sync]  D0-D9 = {words}")

        dwords = read_dwords_single_request_sync(client, "D0", 4)
        print(f"[read_dwords_single_request_sync] D0-D7 (as 4 x uint32) = {dwords}")

        large_words = read_words_chunked_sync(client, "D0", 1000)
        large_dwords = read_dwords_chunked_sync(client, "D200", 120)
        print(f"[read_words_chunked_sync] D0-D999: {len(large_words)} words read")
        print(f"[read_dwords_chunked_sync] D200-D439: {len(large_dwords)} dwords read")

        # ---------------------------------------------------------------
        # 3. write_bit_in_word_sync
        #
        # Set or clear a specific bit inside a word device (read-modify-write).
        # bit_index 0 = LSB, 15 = MSB.
        #
        # Use case: toggling a request bit in a control word without
        #           touching the other 15 bits.
        # ---------------------------------------------------------------
        write_bit_in_word_sync(client, "D50", bit_index=3, value=True)
        print("[write_bit_in_word_sync] Set bit 3 of D50")
        write_bit_in_word_sync(client, "D50", bit_index=3, value=False)
        print("[write_bit_in_word_sync] Cleared bit 3 of D50")

        # ---------------------------------------------------------------
        # 4. read_named_sync / write_named_sync
        #
        # Read/write multiple devices with mixed types in a single call.
        # Address notation:
        #   "D100"    - unsigned 16-bit (default)
        #   "D100:F"  - float32
        #   "D100:S"  - signed 16-bit
        #   "D100:D"  - unsigned 32-bit
        #   "D100:L"  - signed 32-bit
        #   "D100.3"  - bit 3 inside D100 (bool)
        #
        # Use case: reading the current state of a multi-type parameter block
        #           (speed as float, counts as int, alarm bit as bool).
        # ---------------------------------------------------------------
        snapshot = read_named_sync(
            client,
            [
                "D100",
                "D200:F",
                "D202:L",
                "D50.3",
            ],
        )
        for addr, value in snapshot.items():
            print(f"[read_named_sync]  {addr} = {value!r}")

        write_named_sync(
            client,
            {
                "D100": 99,
                "D200:F": 1.5,
                "D202:L": -200,
                "D50.3": True,
            },
        )
        print("[write_named_sync] Wrote mixed-type values to D100, D200:F, D202:L, D50.3")

        # ---------------------------------------------------------------
        # 5. poll_sync
        #
        # Yields a snapshot dict every *interval* seconds.
        # Use break or Ctrl+C to stop.
        #
        # Use case: lightweight periodic logging of process values from a
        #           script without a full monitoring framework.
        # ---------------------------------------------------------------
        print(f"\nPolling {args.poll_count} snapshots (press Ctrl+C to abort):")
        try:
            for i, snap in enumerate(poll_sync(client, ["D100", "D200:F", "D50.3"], interval=1.0)):
                print(f"  [{i + 1}] {snap}")
                if i + 1 >= args.poll_count:
                    break
        except KeyboardInterrupt:
            print("Poll interrupted.")

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except SlmpError as e:
        print(f"SLMP error: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)
