#!/usr/bin/env python
"""SLMP Ultra Fast Device Monitor (Asynchronous)
The most convenient CLI tool to monitor Mitsubishi PLC devices in real-time.
"""

from __future__ import annotations

import asyncio

# Add project root to path
import os
import sys
from argparse import ArgumentParser
from datetime import datetime
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slmp import AsyncSlmpClient, SlmpError, parse_device


class DeviceMonitor:
    def __init__(self, host: str, port: int, series: str, transport: str, interval: float):
        self.host = host
        self.port = port
        self.series = series
        self.transport = transport
        self.interval = interval
        self.targets: list[dict[str, Any]] = []
        self.prev_values: dict[str, Any] = {}
        self.running = True

    def add_target(self, device_str: str) -> None:
        """Parse device string or range like D100-110."""
        if "-" in device_str:
            start_str, end_val_str = device_str.split("-")
            start_ref = parse_device(start_str)
            end_val = int(end_val_str)
            count = end_val - start_ref.number + 1
            if count <= 0:
                raise ValueError(f"Invalid range: {device_str}")
            self.targets.append(
                {
                    "label": f"{start_ref.code}{start_ref.number}-{end_val}",
                    "device": start_ref,
                    "count": count,
                    "is_bit": start_ref.code in {"X", "Y", "M", "L", "F", "B", "S"},
                }
            )
        else:
            ref = parse_device(device_str)
            self.targets.append(
                {
                    "label": device_str,
                    "device": ref,
                    "count": 1,
                    "is_bit": ref.code in {"X", "Y", "M", "L", "F", "B", "S"},
                }
            )

    async def run(self) -> None:
        print("\033[2J\033[H")  # Clear screen
        print("=== SLMP Async Monitor ===")
        print(f"Target: {self.host}:{self.port} ({self.transport.upper()})")
        print(f"Interval: {self.interval}s")
        print(f"Monitoring {len(self.targets)} group(s)...")
        print("-" * 50)

        async with AsyncSlmpClient(
            self.host, self.port, transport=self.transport, plc_series=self.series, timeout=self.interval
        ) as cli:
            while self.running:
                try:
                    start_time = asyncio.get_running_loop().time()

                    # Concurrent reading of all target groups
                    tasks = [cli.read_devices(t["device"], t["count"], bit_unit=t["is_bit"]) for t in self.targets]
                    results = await asyncio.gather(*tasks)

                    # Update display
                    print("\033[H")  # Move cursor to top
                    print(f"=== SLMP Async Monitor | {datetime.now().strftime('%H:%M:%S.%f')[:-3]} ===")
                    print("Status: \033[92mONLINE\033[0m | Press Ctrl+C to stop")
                    print("-" * 70)
                    print(f"{'DEVICE':<15} | {'DEC':<10} | {'HEX':<10} | {'BITS/STATE'}")
                    print("-" * 70)

                    for target, values in zip(self.targets, results, strict=False):
                        target["label"]
                        for i, val in enumerate(values):
                            addr = f"{target['device'].code}{target['device'].number + i}"

                            # Change detection
                            changed = False
                            if addr in self.prev_values and self.prev_values[addr] != val:
                                changed = True
                            self.prev_values[addr] = val

                            # Formatting
                            color_start = "\033[93m" if changed else ""
                            color_end = "\033[0m" if changed else ""

                            if target["is_bit"]:
                                state = "ON " if val else "OFF"
                                print(f"{color_start}{addr:<15} | {'-':<10} | {'-':<10} | {state}{color_end}")
                            else:
                                h_val = f"0x{val:04X}"
                                b_val = format(val, "016b")
                                # Show 4-bit grouped binary for better readability
                                b_formatted = " ".join([b_val[i : i + 4] for i in range(0, 16, 4)])
                                print(f"{color_start}{addr:<15} | {val:<10} | {h_val:<10} | {b_formatted}{color_end}")

                    # Sleep to maintain interval
                    elapsed = asyncio.get_running_loop().time() - start_time
                    await asyncio.sleep(max(0, self.interval - elapsed))

                except SlmpError as e:
                    print(f"\n\033[91mSLMP Error: {e}\033[0m")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"\n\033[91mError: {e}\033[0m")
                    await asyncio.sleep(1)


def main() -> None:
    parser = ArgumentParser(description="World's best SLMP device monitor")
    parser.add_argument("host", help="PLC IP Address")
    parser.add_argument("devices", nargs="+", help="Devices to monitor (e.g. D100 D200-210 M0)")
    parser.add_argument("--port", type=int, default=5000, help="Port number (default: 5000)")
    parser.add_argument("--series", default="iqr", choices=["ql", "iqr"], help="PLC Series")
    parser.add_argument("--transport", default="tcp", choices=["tcp", "udp"], help="Transport protocol")
    parser.add_argument("--interval", type=float, default=0.5, help="Refresh interval in seconds")

    args = parser.parse_args()

    monitor = DeviceMonitor(args.host, args.port, args.series, args.transport, args.interval)
    try:
        for d in args.devices:
            monitor.add_target(d)
    except Exception as e:
        print(f"Configuration error: {e}")
        return

    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()
