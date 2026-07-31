"""IPv4-only endpoint validation and resolution."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Iterable
from ipaddress import ip_address
from typing import Any


def normalize_ipv4_host(host: object, *, name: str = "host") -> str:
    """Return a normalized IPv4 literal or hostname and reject IPv6 literals."""
    if not isinstance(host, str):
        raise ValueError(f"{name} must be a string")
    normalized = host.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")

    literal_text = normalized[1:-1] if normalized.startswith("[") and normalized.endswith("]") else normalized
    try:
        literal = ip_address(literal_text)
    except ValueError:
        return normalized
    if literal.version != 4:
        raise ValueError(f"{name} must be an IPv4 address or a hostname that resolves to IPv4; IPv6 is unsupported")
    return literal_text


def select_first_ipv4_endpoint(endpoints: Iterable[Any], socket_type: int) -> tuple[str, int]:
    """Select the first IPv4 endpoint in resolver order."""
    for family, resolved_type, _protocol, _canonical_name, sockaddr in endpoints:
        if family != socket.AF_INET or resolved_type != socket_type:
            continue
        address, port = sockaddr[0], sockaddr[1]
        if isinstance(address, str) and isinstance(port, int):
            return address, port
    raise socket.gaierror("host did not resolve to an IPv4 address")


def resolve_ipv4_endpoint(host: str, port: int, socket_type: int) -> tuple[str, int]:
    """Resolve one synchronous IPv4 endpoint without IPv6 fallback."""
    return select_first_ipv4_endpoint(
        socket.getaddrinfo(host, port, socket.AF_INET, socket_type),
        socket_type,
    )


async def resolve_ipv4_endpoint_async(host: str, port: int, socket_type: int) -> tuple[str, int]:
    """Resolve one asynchronous IPv4 endpoint without IPv6 fallback."""
    loop = asyncio.get_running_loop()
    endpoints = await loop.getaddrinfo(host, port, family=socket.AF_INET, type=socket_type)
    return select_first_ipv4_endpoint(endpoints, socket_type)
