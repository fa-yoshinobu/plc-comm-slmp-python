# ruff: noqa: E402
"""Read-only polling sample with automatic reconnect.

The sample keeps reading one typed value, closes the connection after a
transport failure, and retries forever with exponential backoff.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from slmp import SlmpConnectionOptions, SlmpTarget, open_and_connect, plc_profile_descriptors, read_typed
from slmp.async_client import AsyncSlmpClient
from slmp.errors import SlmpError

RETRYABLE_ERRORS = (OSError, ConnectionError, TimeoutError, EOFError, asyncio.TimeoutError)


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read one SLMP value forever and reconnect after transport loss.")
    parser.add_argument("--host", required=True, help="PLC IP address or hostname")
    parser.add_argument("--port", type=int, required=True, help="SLMP port number")
    parser.add_argument("--transport", choices=("tcp", "udp"), required=True, help="Transport protocol")
    parser.add_argument(
        "--plc-profile",
        choices=tuple(profile.canonical_name for profile in plc_profile_descriptors() if profile.connectable),
        required=True,
        help="Required canonical PLC profile",
    )
    parser.add_argument("--device", default="D100", help="Device to poll (default D100)")
    parser.add_argument("--dtype", choices=("BIT", "U", "S", "D", "L", "F"), default="U", help="Read type")
    parser.add_argument("--interval", type=positive_float, default=1.0, help="Polling interval in seconds")
    parser.add_argument(
        "--timeout",
        type=positive_float,
        default=3.0,
        help="Per-connection timeout and absolute request deadline in seconds",
    )
    parser.add_argument("--initial-backoff", type=positive_float, default=1.0, help="First reconnect delay")
    parser.add_argument("--max-backoff", type=positive_float, default=30.0, help="Maximum reconnect delay")
    return parser.parse_args()


def log_state(state: str, message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"{timestamp} [{state}] {message}", flush=True)


def describe_error(exc: BaseException) -> str:
    if isinstance(exc, SlmpError) and exc.end_code is not None:
        return f"{exc} (end_code=0x{exc.end_code:04X})"
    return str(exc) or exc.__class__.__name__


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RETRYABLE_ERRORS):
        return True
    return isinstance(exc, SlmpError) and exc.end_code is None


async def close_quietly(client: Any | None) -> None:
    if client is None:
        return
    try:
        await client.close()
    except Exception:
        pass


async def sleep_backoff(seconds: float) -> None:
    await asyncio.sleep(seconds)


async def poll_forever(args: argparse.Namespace) -> None:
    options = SlmpConnectionOptions(
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_profile=args.plc_profile,
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
    )

    client: Any | None = None
    backoff = args.initial_backoff
    connected_once = False

    try:
        while True:
            if client is None:
                log_state("reconnecting", f"{args.transport} {args.host}:{args.port} profile={args.plc_profile}")
                try:
                    client = await open_and_connect(options)
                except Exception as exc:
                    if not is_retryable(exc):
                        raise
                    log_state("reconnecting", f"connect failed: {describe_error(exc)}; retry in {backoff:.1f}s")
                    await sleep_backoff(backoff)
                    backoff = min(backoff * 2.0, args.max_backoff)
                    continue

                if connected_once:
                    log_state("recovered", f"{args.device}:{args.dtype}")
                else:
                    log_state("connected", f"{args.device}:{args.dtype}")
                    connected_once = True
                backoff = args.initial_backoff

            try:
                value = await read_typed(cast(AsyncSlmpClient, client), args.device, args.dtype)
                log_state("read", f"{args.device}:{args.dtype}={value!r}")
                await asyncio.sleep(args.interval)
            except Exception as exc:
                if not is_retryable(exc):
                    raise
                log_state("lost", describe_error(exc))
                await close_quietly(client)
                client = None
                log_state("reconnecting", f"retry in {backoff:.1f}s")
                await sleep_backoff(backoff)
                backoff = min(backoff * 2.0, args.max_backoff)
    finally:
        await close_quietly(client)


def main() -> int:
    args = parse_args()
    if args.max_backoff < args.initial_backoff:
        raise SystemExit("--max-backoff must be greater than or equal to --initial-backoff")

    try:
        asyncio.run(poll_forever(args))
    except KeyboardInterrupt:
        log_state("closed", "interrupted by Ctrl+C")
        return 0
    except SlmpError as exc:
        log_state("lost", describe_error(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
