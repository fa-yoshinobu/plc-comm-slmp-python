#!/usr/bin/env python
"""FX5UC master validation script."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries


def fx5uc_master_validation(host: str = "192.168.250.101", port: int = 1025) -> None:
    """Run the master validation matrix for FX5UC."""

    print(f"Master Command Validation Matrix for FX5UC ({host}:{port})")
    print("Settings: 4E Frame + Legacy (QL) Mode\n")
    print("| Code | Command Category | Command Name | Result | Detail/EndCode |")
    print("|:---:|:---|:---|:---:|:---|")

    # Use the discovered "Golden Setting" for FX5UC
    with SlmpClient(host, port, frame_type=FrameType.FRAME_4E, plc_series=PLCSeries.QL, timeout=2.0) as client:

        def run_test(code: str, cat: str, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
            try:
                func(*args, **kwargs)
                print(f"| {code} | {cat} | {name} | PASS | - |")
            except Exception as e:
                print(f"| {code} | {cat} | {name} | FAIL | {e} |")

        # --- Tests ---
        run_test("0101", "System", "Read Type Name", client.read_type_name)
        run_test("0401", "Device", "Read Words (D130)", client.read_devices, "D130", 1)
        run_test("1401", "Device", "Write Words (D130)", client.write_devices, "D130", [0])
        run_test("1402", "Device", "Write Random Bits", client.write_random_bits, bit_values=[("M125", False)])
        run_test("0406", "Device", "Read Block", client.read_block, word_blocks=[("D140", 1)])
        run_test("1001", "Remote", "Remote Run", client.request, 0x1001, 0x0000, b"\x01\x00\x00\x00")
        run_test("0613", "Memory", "Buffer Memory Read", client.memory_read_words, 0, 1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.250.101")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()
    fx5uc_master_validation(host=args.host, port=args.port)
