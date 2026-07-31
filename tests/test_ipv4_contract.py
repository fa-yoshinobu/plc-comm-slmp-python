"""IPv4-only connection contract tests."""

from __future__ import annotations

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from slmp._network import select_first_ipv4_endpoint
from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.core import SlmpTarget

TARGET = SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0)


@pytest.mark.parametrize("host", ["::1", "[::1]", "::ffff:127.0.0.1"])
@pytest.mark.parametrize("transport", ["tcp", "udp"])
def test_sync_and_async_clients_reject_ipv6_before_socket_creation(host: str, transport: str) -> None:
    with patch("socket.socket", side_effect=AssertionError("must not create socket")):
        with pytest.raises(ValueError, match="IPv6 is unsupported"):
            SlmpClient(host, 1025, transport=transport, default_target=TARGET, plc_profile="melsec:iq-r")
        with pytest.raises(ValueError, match="IPv6 is unsupported"):
            AsyncSlmpClient(host, 1025, transport=transport, default_target=TARGET, plc_profile="melsec:iq-r")


def test_endpoint_selection_uses_first_ipv4_and_rejects_ipv6_only_results() -> None:
    endpoints = [
        (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("::1", 1025, 0, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.0.2.10", 1025)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.0.2.11", 1025)),
    ]
    assert select_first_ipv4_endpoint(endpoints, socket.SOCK_STREAM) == ("192.0.2.10", 1025)
    with pytest.raises(socket.gaierror, match="did not resolve"):
        select_first_ipv4_endpoint(endpoints[:1], socket.SOCK_STREAM)


def test_sync_tcp_and_udp_connect_to_the_resolved_ipv4_endpoint() -> None:
    for transport, socket_type in (("tcp", socket.SOCK_STREAM), ("udp", socket.SOCK_DGRAM)):
        raw_socket = MagicMock()
        client = SlmpClient(
            "plc.local",
            1025,
            transport=transport,
            default_target=TARGET,
            plc_profile="melsec:iq-r",
        )
        with (
            patch("slmp.client.resolve_ipv4_endpoint", return_value=("192.0.2.10", 1025)) as resolve,
            patch("slmp.client.socket.socket", return_value=raw_socket) as create_socket,
            patch("slmp.client.configure_tcp_keepalive"),
        ):
            client.connect()
        resolve.assert_called_once_with("plc.local", 1025, socket_type)
        create_socket.assert_called_once_with(socket.AF_INET, socket_type)
        raw_socket.connect.assert_called_once_with(("192.0.2.10", 1025))


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["tcp", "udp"])
async def test_async_connect_uses_ipv4_resolution_for_tcp_and_udp(transport: str) -> None:
    client = AsyncSlmpClient(
        "plc.local",
        1025,
        transport=transport,
        default_target=TARGET,
        plc_profile="melsec:iq-r",
    )
    endpoint = ("192.0.2.10", 1025)
    resolver = AsyncMock(return_value=endpoint)
    if transport == "tcp":
        writer = MagicMock()
        writer.get_extra_info.return_value = MagicMock()
        writer.wait_closed = AsyncMock()
        connector = AsyncMock(return_value=(MagicMock(), writer))
        with (
            patch("slmp.async_client.resolve_ipv4_endpoint_async", resolver),
            patch("slmp.async_client.asyncio.open_connection", connector),
            patch("slmp.async_client.configure_tcp_keepalive"),
        ):
            await client.connect()
        connector.assert_awaited_once_with(endpoint[0], endpoint[1], family=socket.AF_INET)
    else:
        transport_object = MagicMock()
        loop = MagicMock()
        loop.create_datagram_endpoint = AsyncMock(return_value=(transport_object, MagicMock()))
        with (
            patch("slmp.async_client.resolve_ipv4_endpoint_async", resolver),
            patch("slmp.async_client.asyncio.get_running_loop", return_value=loop),
        ):
            await client.connect()
        _, kwargs = loop.create_datagram_endpoint.await_args
        assert kwargs["remote_addr"] == endpoint
        assert kwargs["family"] == socket.AF_INET

    resolver.assert_awaited_once_with(
        "plc.local",
        1025,
        socket.SOCK_STREAM if transport == "tcp" else socket.SOCK_DGRAM,
    )
