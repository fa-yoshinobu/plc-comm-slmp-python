"""Socket-policy regression tests."""

from __future__ import annotations

import socket
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from slmp._socket_options import configure_tcp_keepalive
from slmp.client import SlmpClient
from slmp.core import SlmpTarget
from slmp.errors import SlmpTransportError


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


def test_tcp_connect_closes_socket_when_required_keepalive_setup_fails() -> None:
    raw_socket = MagicMock()
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )

    with (
        patch("slmp.client.socket.socket", return_value=raw_socket),
        patch("slmp.client.configure_tcp_keepalive", side_effect=OSError("keepalive unavailable")),
    ):
        try:
            client.connect()
        except SlmpTransportError as error:
            assert str(error) == "SLMP connection failed: keepalive unavailable"
            assert isinstance(error.__cause__, OSError)
        else:  # pragma: no cover - protects the fail-closed contract
            raise AssertionError("keepalive setup failure was not raised")

    raw_socket.close.assert_called_once_with()
    raw_socket.connect.assert_not_called()
    assert client._sock is None


def test_keepalive_without_idle_configuration_support_fails_closed() -> None:
    captured = _CaptureSocket()
    unsupported_socket_module = SimpleNamespace(SOL_SOCKET=socket.SOL_SOCKET, SO_KEEPALIVE=socket.SO_KEEPALIVE)
    with patch("slmp._socket_options.socket", unsupported_socket_module):
        try:
            configure_tcp_keepalive(captured, idle_seconds=30)
        except OSError as error:
            assert "cannot configure" in str(error)
        else:  # pragma: no cover - protects the fail-closed contract
            raise AssertionError("missing keepalive idle support was accepted")
