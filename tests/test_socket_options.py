"""Socket-policy regression tests."""

from __future__ import annotations

import socket

from slmp._socket_options import configure_tcp_keepalive


class _CaptureSocket:
    def __init__(self) -> None:
        self.options: list[tuple[int, int, int]] = []
        self.ioctls: list[tuple[int, tuple[int, int, int]]] = []

    def setsockopt(self, level: int, option: int, value: int) -> None:
        self.options.append((level, option, value))

    def ioctl(self, command: int, value: tuple[int, int, int]) -> None:
        self.ioctls.append((command, value))


def test_tcp_keepalive_enables_socket_and_uses_30_second_idle() -> None:
    captured = _CaptureSocket()
    configure_tcp_keepalive(captured, idle_seconds=30)

    assert (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) in captured.options
    if hasattr(socket, "TCP_KEEPIDLE"):
        assert (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30) in captured.options
    elif hasattr(socket, "TCP_KEEPALIVE"):
        assert (socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 30) in captured.options
    elif hasattr(socket, "SIO_KEEPALIVE_VALS"):
        assert (socket.SIO_KEEPALIVE_VALS, (1, 30_000, 1000)) in captured.ioctls
