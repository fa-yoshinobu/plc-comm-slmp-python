#!/usr/bin/env python
"""Script to discover FX5 PLC connection combinations."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries


def fx5_discovery(host: str = "192.168.250.100", port: int = 1025) -> None:
    """Test various connection combinations for FX5 PLC."""

    # Discovery combinations specifically for FX5
    combinations = [
        (FrameType.FRAME_4E, PLCSeries.QL, "4E + Legacy (Sub 0000)"),
        (FrameType.FRAME_3E, PLCSeries.QL, "3E + Legacy (Sub 0000)"),
        (FrameType.FRAME_4E, PLCSeries.IQR, "4E + Modern (Sub 0002)"),
        (FrameType.FRAME_3E, PLCSeries.IQR, "3E + Modern (Sub 0002)"),
    ]

    print(f"Target: FX5UC at {host}:{port}\n")

    for frame, series, name in combinations:
        try:
            # Longer timeout for FX series handshake
            with SlmpClient(host, port, frame_type=frame, plc_series=series, timeout=3.0) as client:
                client.read_devices("D130", 1)
                print(f"PASS: {name}")
        except Exception as e:
            print(f"FAIL: {name} -> {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.250.100")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()
    fx5_discovery(host=args.host, port=args.port)
