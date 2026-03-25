#!/usr/bin/env python
"""iQ-L series master validation script."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries


def iql_master_validation(host: str = "192.168.250.100", port: int = 1025) -> None:
    """Run the master validation matrix for iQ-L."""

    print(f"Master Command Validation Matrix for iQ-L ({host}:{port})")
    print("Settings: 4E Frame + Modern (iQR) Mode\n")
    print("| Code | Command Category | Command Name | Result | Detail/EndCode |")
    print("|:---:|:---|:---|:---:|:---|")

    # Use Modern (iQR) mode for iQ-series
    with SlmpClient(host, port, frame_type=FrameType.FRAME_4E, plc_series=PLCSeries.IQR, timeout=2.0) as client:

        def run_test(code: str, cat: str, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
            try:
                func(*args, **kwargs)
                print(f"| {code} | {cat} | {name} | PASS | - |")
            except Exception as e:
                print(f"| {code} | {cat} | {name} | FAIL | {e} |")

        # --- 1. System/Diagnostic ---
        run_test("0101", "System", "Read Type Name", client.read_type_name)
        run_test("0619", "Diagnostic", "Self Test", client.request, 0x0619, 0x0000, b"\x04\x00\x11\x22\x33\x44")
        run_test("1617", "Diagnostic", "Clear Error", client.request, 0x1617, 0x0000, b"")

        # --- 2. Basic Device Access ---
        run_test("0401", "Device", "Read Words (D130)", client.read_devices, "D130", 1)
        run_test("0401", "Device", "Read Bits (M120)", client.read_devices, "M120", 1, bit_unit=True)
        run_test("1401", "Device", "Write Words (D130)", client.write_devices, "D130", [0])
        run_test("1401", "Device", "Write Bits (M120)", client.write_devices, "M120", [False], bit_unit=True)

        # --- 3. Random Access ---
        run_test("0403", "Device", "Read Random Words", client.read_random, word_devices=["D130", "D131"])
        run_test("1402", "Device", "Write Random Words", client.write_random_words, word_values=[("D135", 0)])
        run_test("1402", "Device", "Write Random Bits", client.write_random_bits, bit_values=[("M125", False)])

        # --- 4. Block Access (Modern Extensions) ---
        run_test("0406", "Device", "Read Block", client.read_block, word_blocks=[("D140", 1)])
        run_test("1406", "Device", "Write Block", client.write_block, word_blocks=[("D140", [0])])

        # --- 5. Monitor Function ---
        try:
            # Step 1: Register (Modern 8-byte format)
            client.request(0x0801, 0x0000, b"\x01\x00\x82\x00\x00\x00\xa8\x00")  # D130
            print("| 0801 | Monitor | Entry Monitor Device | PASS | - |")
            # Step 2: Execute
            run_test("0802", "Monitor", "Execute Monitor", client.request, 0x0802, 0x0000, b"")
        except Exception as e:
            print(f"| 0801 | Monitor | Entry/Execute | FAIL | {e} |")

        # --- 6. Remote Control ---
        run_test("1001", "Remote", "Remote Run", client.request, 0x1001, 0x0000, b"\x01\x00\x00\x00")
        run_test("1002", "Remote", "Remote Stop", client.request, 0x1002, 0x0000, b"\x01\x00")

        # --- 7. Buffer Memory ---
        run_test("0613", "Memory", "Buffer Memory Read", client.memory_read_words, 0, 1)
        run_test("1613", "Memory", "Buffer Memory Write", client.memory_write_words, 0, [0])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.250.100")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()
    iql_master_validation(host=args.host, port=args.port)
