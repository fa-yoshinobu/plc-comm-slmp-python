#!/usr/bin/env python
"""Q-series validation script for Python SLMP library."""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from slmp import SlmpTarget
from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries


def test_q_series(host: str = "192.168.250.100", port: int = 1025) -> None:
    """Run validation tests for Q-series."""

    print(f"Connecting to {host}:{port} (3E Frame, QL Series)...")

    # Testing different targets if needed
    # Default is network=0, station=255, module_io=0x03FF, multidrop=0
    target = SlmpTarget(network=0, station=255, module_io=0x03FF, multidrop=0)

    try:
        with SlmpClient(
            host, port, frame_type=FrameType.FRAME_3E, plc_series=PLCSeries.QL, default_target=target, timeout=2.0
        ) as client:
            print("\n--- 1. Read Type Name (0101) ---")
            try:
                info = client.read_type_name()
                print(f"SUCCESS: Model={info.model}, Code=0x{info.model_code:04X}")
            except Exception as e:
                print(f"FAILED: {e}")

            print("\n--- 2. Read Devices (0401) ---")
            try:
                # D130 - Word Read
                val_w = client.read_devices("D130", 2)
                print(f"SUCCESS: D130-131={val_w}")

                # M120 - Bit Read
                val_b = client.read_devices("M120", 1, bit_unit=True)
                print(f"SUCCESS: M120={val_b}")
            except Exception as e:
                print(f"FAILED: {e}")

            print("\n--- 3. Write Devices (1401) ---")
            try:
                client.write_devices("D130", [1234, 5678])
                print("SUCCESS: Wrote to D130-131")

                client.write_devices("M120", [True], bit_unit=True)
                print("SUCCESS: Wrote to M120")
            except Exception as e:
                print(f"FAILED: {e}")

            print("\n--- 4. Random Write (1402) ---")
            try:
                # Word Random
                client.write_random_words(word_values=[("D135", 9999)])
                print("SUCCESS: Random Write D135")

                # Bit Random (The fix we just applied in C++ version)
                client.write_random_bits(bit_values=[("M125", True)])
                print("SUCCESS: Random Write M125")
            except Exception as e:
                print(f"FAILED: {e}")

            print("\n--- 5. Block Read (0406) ---")
            try:
                # This might fail on internal port
                res = client.read_block(word_blocks=[("D140", 2)], bit_blocks=[("M140", 16)])
                print(f"SUCCESS: Block Read Result={res}")
            except Exception as e:
                print(f"EXPECTED FAILURE (if unsupported): {e}")

    except Exception as e:
        print(f"Connection Error: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.250.100")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()
    test_q_series(host=args.host, port=args.port)
