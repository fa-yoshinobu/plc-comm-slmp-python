"""Internal socket policy shared by synchronous and asynchronous clients."""

from __future__ import annotations

import socket
from typing import Any


def configure_tcp_keepalive(sock: Any, *, idle_seconds: int = 30) -> None:
    """Enable TCP keepalive and request the common 30-second idle threshold."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    if hasattr(socket, "TCP_KEEPIDLE"):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, idle_seconds)
        return
    if hasattr(socket, "TCP_KEEPALIVE"):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, idle_seconds)
        return
    if hasattr(socket, "SIO_KEEPALIVE_VALS") and hasattr(sock, "ioctl"):
        sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, idle_seconds * 1000, 1000))
        return
    raise OSError("platform cannot configure the required TCP keepalive idle threshold")
