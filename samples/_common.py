# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from slmp import SlmpClient, SlmpTarget


def int_auto(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer value: {value}") from exc


def add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True, help="PLC or Ethernet module host name / IP")
    parser.add_argument("--port", type=int, default=1025, help="SLMP port number")
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp", help="Transport protocol")
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr", help="PLC device encoding family")
    parser.add_argument("--timeout", type=float, default=3.0, help="Socket timeout in seconds")
    parser.add_argument(
        "--monitoring-timer",
        type=int_auto,
        default=0x0010,
        help="SLMP monitoring timer as decimal or 0x-prefixed hex",
    )


def add_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--network", type=int_auto, default=0x00, help="Target network number")
    parser.add_argument("--station", type=int_auto, default=0xFF, help="Target station number")
    parser.add_argument("--module-io", type=int_auto, default=0x03FF, help="Target module I/O number")
    parser.add_argument("--multidrop", type=int_auto, default=0x00, help="Target multidrop station number")


def create_client_from_args(
    args: argparse.Namespace,
    *,
    default_target: SlmpTarget | None = None,
) -> SlmpClient:
    return SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        monitoring_timer=args.monitoring_timer,
        default_target=default_target,
    )


def build_target_from_args(args: argparse.Namespace) -> SlmpTarget:
    return SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )


def parse_device_points(value: str) -> tuple[str, int]:
    device, sep, points_text = value.partition(":")
    if not sep:
        raise argparse.ArgumentTypeError("expected DEVICE:POINTS")
    points = int_auto(points_text)
    if points < 1:
        raise argparse.ArgumentTypeError("points must be >= 1")
    return device, points
