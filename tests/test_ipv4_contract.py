"""IPv4-only connection contract tests."""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from slmp._network import (
    resolve_ipv4_endpoint,
    resolve_ipv4_endpoint_async,
    select_first_ipv4_endpoint,
)
from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.core import SlmpTarget
from slmp.errors import SlmpTimeoutError, SlmpTransportError

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


@pytest.mark.asyncio
async def test_ipv4_literal_bypasses_sync_and_async_dns() -> None:
    with patch("socket.getaddrinfo", side_effect=AssertionError("literal must bypass DNS")):
        assert resolve_ipv4_endpoint("192.0.2.10", 1025, socket.SOCK_STREAM) == ("192.0.2.10", 1025)
        assert await resolve_ipv4_endpoint_async("192.0.2.10", 1025, socket.SOCK_DGRAM) == (
            "192.0.2.10",
            1025,
        )


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
        loop.time.return_value = 10.0
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


def test_sync_connect_deadline_covers_resolution_and_discards_late_socket() -> None:
    resolution_started = threading.Event()
    release_resolution = threading.Event()
    raw_socket = MagicMock()

    def resolve_late(_host: str, _port: int, _socket_type: int) -> tuple[str, int]:
        resolution_started.set()
        assert release_resolution.wait(timeout=1)
        return ("192.0.2.10", 1025)

    client = SlmpClient(
        "plc.local",
        1025,
        transport="tcp",
        default_target=TARGET,
        plc_profile="melsec:iq-r",
        timeout=0.03,
    )
    with (
        patch("slmp.client.resolve_ipv4_endpoint", side_effect=resolve_late),
        patch("slmp.client.socket.socket", return_value=raw_socket),
    ):
        with pytest.raises(SlmpTimeoutError, match="SLMP connection timeout"):
            client.connect()
        assert resolution_started.is_set()
        assert client._sock is None
        release_resolution.set()
        deadline = time.monotonic() + 1
        while not raw_socket.close.called:
            assert time.monotonic() < deadline
            time.sleep(0.001)

    raw_socket.connect.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("lazy_request", [False, True])
async def test_async_complete_operation_deadline_is_not_restarted_after_resolution(lazy_request: bool) -> None:
    async def delayed_resolution(*_args: object) -> tuple[str, int]:
        await asyncio.sleep(0.04)
        return ("192.0.2.10", 1025)

    async def delayed_connection(*_args: object, **_kwargs: object) -> tuple[MagicMock, MagicMock]:
        await asyncio.sleep(0.04)
        writer = MagicMock()
        writer.get_extra_info.return_value = MagicMock()
        writer.wait_closed = AsyncMock()
        return MagicMock(), writer

    client = AsyncSlmpClient(
        "plc.local",
        1025,
        transport="tcp",
        default_target=TARGET,
        plc_profile="melsec:iq-r",
        timeout=0.06,
    )
    with (
        patch("slmp.async_client.resolve_ipv4_endpoint_async", side_effect=delayed_resolution),
        patch("slmp.async_client.asyncio.open_connection", side_effect=delayed_connection),
    ):
        started = asyncio.get_running_loop().time()
        with pytest.raises(SlmpTimeoutError, match="SLMP connection timeout"):
            if lazy_request:
                await client.raw_command(0x1829, subcommand=0, payload=b"", state_changing=False)
            else:
                await client.connect()
        elapsed = asyncio.get_running_loop().time() - started

    # Windows' proactor clock can fire the final wait a scheduler tick early.
    assert 0.04 <= elapsed < 0.12
    assert client._writer is None


@pytest.mark.asyncio
async def test_async_transport_timeout_before_connection_deadline_remains_transport_error() -> None:
    client = AsyncSlmpClient(
        "192.0.2.10",
        1025,
        transport="tcp",
        default_target=TARGET,
        plc_profile="melsec:iq-r",
        timeout=1.0,
    )
    with patch("slmp.async_client.asyncio.open_connection", side_effect=TimeoutError("socket timed out")):
        with pytest.raises(SlmpTransportError, match="socket timed out"):
            await client.connect()
