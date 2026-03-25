#!/usr/bin/env python
"""Q-series matrix sweep script."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries


def sweep_combinations(host: str = "192.168.250.101", port: int = 1025) -> None:
    """Sweep through different frame types and PLC series combinations for Q-series."""

    combinations = [
        (FrameType.FRAME_4E, PLCSeries.IQR, "4E + Modern (Default)"),
        (FrameType.FRAME_4E, PLCSeries.QL, "4E + Legacy"),
        (FrameType.FRAME_3E, PLCSeries.IQR, "3E + Modern"),
        (FrameType.FRAME_3E, PLCSeries.QL, "3E + Legacy (Correct)"),
    ]

    print(f"Target: Q06UDV at {host}:{port}\n")
    print("| No | Frame | Series | Mode Name | Result | Error/Details |")
    print("|---|---|---|---|---|---|")

    for i, (frame, series, name) in enumerate(combinations, 1):
        result = "???"
        detail = ""
        try:
            # Short timeout for failed cases
            with SlmpClient(host, port, frame_type=frame, plc_series=series, timeout=1.0) as client:
                # Try a simple Word Read (D130)
                client.read_devices("D130", 1)
                result = "PASS"
                detail = "Communication Successful"
        except Exception as e:
            result = "FAIL"
            detail = str(e)

        print(f"| {i} | {frame.name} | {series.name} | {name} | {result} | {detail} |")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.250.101")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()
    sweep_combinations(host=args.host, port=args.port)
