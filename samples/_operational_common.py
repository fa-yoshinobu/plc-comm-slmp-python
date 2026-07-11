# ruff: noqa: E402
"""Shared helpers for read-only operational SLMP samples."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from slmp import SlmpConnectionOptions, SlmpTarget, open_and_connect, read_named
from slmp.async_client import AsyncSlmpClient
from slmp.errors import SlmpError

PLC_PROFILES = (
    "melsec:iq-f",
    "melsec:iq-r",
    "melsec:iq-r:rj71en71",
    "melsec:iq-l",
    "melsec:mx-f",
    "melsec:mx-r",
    "melsec:qcpu:qj71e71-100",
    "melsec:lcpu",
    "melsec:lcpu:lj71e71-100",
    "melsec:qnu",
    "melsec:qnu:qj71e71-100",
    "melsec:qnudv",
    "melsec:qnudv:qj71e71-100",
)

RETRYABLE_ERRORS = (OSError, ConnectionError, TimeoutError, EOFError, asyncio.TimeoutError)

SnapshotHandler = Callable[["PlcEndpoint", Mapping[str, object]], Awaitable[None]]


@dataclass(frozen=True)
class TagSpec:
    """One read-only tag in an operational polling sample."""

    name: str
    address: str


@dataclass(frozen=True)
class PlcEndpoint:
    """Connection and polling settings for one PLC."""

    name: str
    host: str
    plc_profile: str
    port: int
    transport: str
    timeout: float = 3.0
    interval: float = 1.0


async def ignore_snapshot(_endpoint: PlcEndpoint, _snapshot: Mapping[str, object]) -> None:
    """Use when console logging is enough and no additional output is required."""


def positive_float(value: str) -> float:
    """Parse a positive floating-point CLI value."""

    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def positive_int(value: str) -> int:
    """Parse a positive integer CLI value."""

    parsed = int(value, 0)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def normalize_tag_name(address: str) -> str:
    """Create a readable tag name from an address string."""

    return address.replace("\\", "_").replace(":", "_").replace(".", "_").replace("-", "_").replace("/", "_").lower()


def parse_tag_spec(value: str) -> TagSpec:
    """Parse NAME=ADDRESS or ADDRESS into a tag specification."""

    name, separator, address = value.partition("=")
    if separator:
        if not name or not address:
            raise argparse.ArgumentTypeError("expected NAME=ADDRESS")
        return TagSpec(name=name, address=address)
    return TagSpec(name=normalize_tag_name(value), address=value)


def validate_profile(profile: str) -> str:
    """Validate a canonical PLC profile string."""

    if profile not in PLC_PROFILES:
        choices = ", ".join(PLC_PROFILES)
        raise argparse.ArgumentTypeError(f"unknown PLC profile {profile!r}; choose one of: {choices}")
    return profile


def parse_plc_spec(
    value: str,
    *,
    default_port: int | None,
    default_transport: str | None,
    default_timeout: float,
    default_interval: float,
) -> PlcEndpoint:
    """Parse NAME=HOST,PROFILE[,PORT[,TRANSPORT]] for multi-PLC samples."""

    name, separator, rest = value.partition("=")
    if not separator or not name or not rest:
        raise argparse.ArgumentTypeError("expected NAME=HOST,PROFILE[,PORT[,TRANSPORT]]")

    parts = [part.strip() for part in rest.split(",")]
    if len(parts) < 2 or len(parts) > 4:
        raise argparse.ArgumentTypeError("expected NAME=HOST,PROFILE[,PORT[,TRANSPORT]]")

    host = parts[0]
    profile = validate_profile(parts[1])
    port = int(parts[2], 0) if len(parts) >= 3 and parts[2] else default_port
    transport = parts[3].lower() if len(parts) == 4 and parts[3] else default_transport
    if port is None:
        raise argparse.ArgumentTypeError("port is required either in --plc or --port")
    if isinstance(port, bool) or not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be in range 1..65535")
    if transport not in {"tcp", "udp"}:
        raise argparse.ArgumentTypeError("transport is required either in --plc or --transport")

    return PlcEndpoint(
        name=name,
        host=host,
        plc_profile=profile,
        port=port,
        transport=transport,
        timeout=default_timeout,
        interval=default_interval,
    )


def log_state(plc_name: str, state: str, message: str) -> None:
    """Print a timestamped monitoring state line."""

    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"{timestamp} [{plc_name}] [{state}] {message}", flush=True)


def describe_error(exc: BaseException) -> str:
    """Return a concise error string, including SLMP end codes when present."""

    if isinstance(exc, SlmpError) and exc.end_code is not None:
        return f"{exc} (end_code=0x{exc.end_code:04X})"
    return str(exc) or exc.__class__.__name__


def is_retryable(exc: BaseException) -> bool:
    """Return true for transport-level failures that should reconnect."""

    if isinstance(exc, RETRYABLE_ERRORS):
        return True
    return isinstance(exc, SlmpError) and exc.end_code is None


async def close_quietly(client: Any | None) -> None:
    """Close a client while suppressing cleanup errors."""

    if client is None:
        return
    try:
        await client.close()
    except Exception:
        pass


def build_options(endpoint: PlcEndpoint) -> SlmpConnectionOptions:
    """Build high-level connection options for one endpoint."""

    return SlmpConnectionOptions(
        host=endpoint.host,
        port=endpoint.port,
        transport=endpoint.transport,
        timeout=endpoint.timeout,
        plc_profile=endpoint.plc_profile,
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
    )


def format_snapshot(snapshot: Mapping[str, object]) -> str:
    """Format a snapshot for compact console output."""

    return ", ".join(f"{name}={value!r}" for name, value in snapshot.items())


async def monitor_endpoint(
    endpoint: PlcEndpoint,
    tags: Sequence[TagSpec],
    *,
    cycles: int | None,
    initial_backoff: float,
    max_backoff: float,
    handle_snapshot: SnapshotHandler,
) -> None:
    """Poll one PLC forever or for a fixed number of successful cycles."""

    if not tags:
        raise ValueError("at least one tag is required")

    options = build_options(endpoint)
    addresses = [tag.address for tag in tags]
    client: Any | None = None
    completed = 0
    backoff = initial_backoff
    connected_once = False

    try:
        while cycles is None or completed < cycles:
            if client is None:
                log_state(
                    endpoint.name,
                    "reconnecting",
                    f"{endpoint.transport} {endpoint.host}:{endpoint.port} profile={endpoint.plc_profile}",
                )
                try:
                    client = await open_and_connect(options)
                except Exception as exc:
                    if not is_retryable(exc):
                        raise
                    log_state(endpoint.name, "reconnecting", f"connect failed: {describe_error(exc)}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, max_backoff)
                    continue

                log_state(endpoint.name, "recovered" if connected_once else "connected", f"{len(tags)} tags")
                connected_once = True
                backoff = initial_backoff

            try:
                raw_snapshot = await read_named(cast(AsyncSlmpClient, client), addresses)
                snapshot = {tag.name: raw_snapshot[tag.address] for tag in tags}
                log_state(endpoint.name, "read", format_snapshot(snapshot))
                await handle_snapshot(endpoint, snapshot)
                completed += 1
                if cycles is None or completed < cycles:
                    await asyncio.sleep(endpoint.interval)
            except Exception as exc:
                if not is_retryable(exc):
                    raise
                log_state(endpoint.name, "lost", describe_error(exc))
                await close_quietly(client)
                client = None
                log_state(endpoint.name, "reconnecting", f"retry in {backoff:.1f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, max_backoff)
    finally:
        await close_quietly(client)
