from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from slmp import AsyncSlmpClient, SlmpClient, SlmpError, SlmpTarget, SlmpTimeoutError
from slmp.async_client import SLMPDatagramProtocol
from slmp.constants import Command, FrameType
from slmp.core import decode_4e_response
from slmp.errors import SlmpOutcomeUnknownError, SlmpOutcomeUnknownReason

TARGET = SlmpTarget(network=0x01, station=0x02, module_io=0x1234, multidrop=0x03)
ROUTE_FIELDS = ("network", "station", "module_io", "multidrop")
FRAME_PROFILES = ((FrameType.FRAME_3E, "melsec:qnu"), (FrameType.FRAME_4E, "melsec:iq-r"))
CORRELATION_PROFILES = ((*FRAME_PROFILES[0], 0x0000), (*FRAME_PROFILES[1], 0x0002))
ERROR_INFO_MISMATCHES = (*ROUTE_FIELDS, "command", "subcommand")
ACK_COMMANDS = (
    Command.DEVICE_WRITE,
    Command.DEVICE_WRITE_RANDOM,
    Command.DEVICE_ENTRY_MONITOR,
    Command.DEVICE_WRITE_BLOCK,
    Command.LABEL_ARRAY_WRITE,
    Command.LABEL_WRITE_RANDOM,
    Command.MEMORY_WRITE,
    Command.EXTEND_UNIT_WRITE,
    Command.REMOTE_RUN,
    Command.REMOTE_STOP,
    Command.REMOTE_PAUSE,
    Command.REMOTE_LATCH_CLEAR,
    Command.REMOTE_PASSWORD_LOCK,
    Command.REMOTE_PASSWORD_UNLOCK,
    Command.CLEAR_ERROR,
)


def _request_identity(frame: bytes, frame_type: FrameType) -> tuple[int, SlmpTarget]:
    if frame_type == FrameType.FRAME_4E:
        return (
            int.from_bytes(frame[2:4], "little"),
            SlmpTarget(frame[6], frame[7], int.from_bytes(frame[8:10], "little"), frame[10]),
        )
    return 0, SlmpTarget(frame[2], frame[3], int.from_bytes(frame[4:6], "little"), frame[6])


def _response_data(frame_type: FrameType, serial: int, target: SlmpTarget, data: bytes) -> bytes:
    body = b"\x00\x00" + data
    route = (
        target.network.to_bytes(1, "little")
        + target.station.to_bytes(1, "little")
        + int(target.module_io).to_bytes(2, "little")
        + target.multidrop.to_bytes(1, "little")
    )
    if frame_type == FrameType.FRAME_4E:
        return b"\xd4\x00" + serial.to_bytes(2, "little") + b"\x00\x00" + route + len(body).to_bytes(2, "little") + body
    return b"\xd0\x00" + route + len(body).to_bytes(2, "little") + body


def _response(frame_type: FrameType, serial: int, target: SlmpTarget, value: int) -> bytes:
    return _response_data(frame_type, serial, target, value.to_bytes(2, "little"))


def _error_response(
    frame_type: FrameType,
    serial: int,
    target: SlmpTarget,
    *,
    command: int,
    subcommand: int,
    extra: bytes = b"",
    error_target: SlmpTarget | None = None,
) -> bytes:
    route = (
        target.network.to_bytes(1, "little")
        + target.station.to_bytes(1, "little")
        + int(target.module_io).to_bytes(2, "little")
        + target.multidrop.to_bytes(1, "little")
    )
    embedded = error_target or target
    error_route = (
        embedded.network.to_bytes(1, "little")
        + embedded.station.to_bytes(1, "little")
        + int(embedded.module_io).to_bytes(2, "little")
        + embedded.multidrop.to_bytes(1, "little")
    )
    error_info = error_route + command.to_bytes(2, "little") + subcommand.to_bytes(2, "little") + extra
    body = b"\x51\xc0" + error_info
    if frame_type == FrameType.FRAME_4E:
        return b"\xd4\x00" + serial.to_bytes(2, "little") + b"\x00\x00" + route + len(body).to_bytes(2, "little") + body
    return b"\xd0\x00" + route + len(body).to_bytes(2, "little") + body


def _foreign_target(target: SlmpTarget, field: str) -> SlmpTarget:
    maximum = 0xFFFF if field == "module_io" else 0xFF
    return replace(target, **{field: (int(getattr(target, field)) + 1) & maximum})


class _SyncScriptSocket:
    def __init__(
        self,
        frame_type: FrameType,
        response_factory: Callable[[int, SlmpTarget], list[bytes]],
        *,
        transport: str,
    ) -> None:
        self.frame_type = frame_type
        self.response_factory = response_factory
        self.transport = transport
        self.timeout: float | None = None
        self.closed = False
        self._stream = bytearray()
        self._datagrams: list[bytes] = []

    def _send(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        responses = self.response_factory(serial, target)
        if self.transport == "tcp":
            self._stream.extend(b"".join(responses))
        else:
            self._datagrams.extend(responses)

    def sendall(self, data: bytes) -> None:
        self._send(data)

    def send(self, data: bytes) -> int:
        self._send(data)
        return len(data)

    def recv_into(self, view: memoryview) -> int:
        if not self._stream:
            raise TimeoutError("script exhausted")
        size = min(len(view), len(self._stream))
        view[:size] = self._stream[:size]
        del self._stream[:size]
        return size

    def recv(self, _size: int) -> bytes:
        if not self._datagrams:
            raise TimeoutError("script exhausted")
        return self._datagrams.pop(0)

    def settimeout(self, timeout: float | None) -> None:
        self.timeout = timeout

    def gettimeout(self) -> float | None:
        return self.timeout

    def close(self) -> None:
        self.closed = True


class _AsyncReader:
    def __init__(self) -> None:
        self.data = bytearray()

    async def readexactly(self, size: int) -> bytes:
        if len(self.data) < size:
            await asyncio.Future()
        result = bytes(self.data[:size])
        del self.data[:size]
        return result


class _AsyncWriter:
    def __init__(
        self,
        reader: _AsyncReader,
        frame_type: FrameType,
        response_factory: Callable[[int, SlmpTarget], list[bytes]],
    ) -> None:
        self.reader = reader
        self.frame_type = frame_type
        self.response_factory = response_factory
        self.closed = False

    def write(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        self.reader.data.extend(b"".join(self.response_factory(serial, target)))

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class _AsyncDatagramTransport:
    def __init__(
        self,
        protocol: SLMPDatagramProtocol,
        frame_type: FrameType,
        response_factory: Callable[[int, SlmpTarget], list[bytes]],
    ) -> None:
        self.protocol = protocol
        self.frame_type = frame_type
        self.response_factory = response_factory
        self.closed = False

    def sendto(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        for response in self.response_factory(serial, target):
            self.protocol.datagram_received(response, ("127.0.0.1", 1025))

    def close(self) -> None:
        self.closed = True


def _sync_client(
    frame_type: FrameType,
    profile: str,
    transport: str,
    factory: Callable[[int, SlmpTarget], list[bytes]],
    *,
    timeout: float = 0.1,
) -> tuple[SlmpClient, _SyncScriptSocket]:
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=TARGET,
        plc_profile=profile,
        timeout=timeout,
    )
    sock = _SyncScriptSocket(frame_type, factory, transport=transport)
    client._sock = sock  # type: ignore[assignment]
    return client, sock


def _async_client(
    frame_type: FrameType,
    profile: str,
    transport: str,
    factory: Callable[[int, SlmpTarget], list[bytes]],
    *,
    timeout: float = 0.1,
) -> tuple[AsyncSlmpClient, Any]:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=TARGET,
        plc_profile=profile,
        timeout=timeout,
    )
    if transport == "tcp":
        reader = _AsyncReader()
        writer = _AsyncWriter(reader, frame_type, factory)
        client._reader = reader  # type: ignore[assignment]
        client._writer = writer  # type: ignore[assignment]
        return client, writer
    protocol = SLMPDatagramProtocol(frame_type)
    udp_transport = _AsyncDatagramTransport(protocol, frame_type, factory)
    client._udp_protocol = protocol
    client._udp_transport = udp_transport  # type: ignore[assignment]
    return client, udp_transport


def _install_clean_async_transport(
    client: AsyncSlmpClient,
    frame_type: FrameType,
    transport: str,
    *,
    value: int = 0x3333,
) -> Any:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [_response(frame_type, serial, target, value)]

    if transport == "tcp":
        reader = _AsyncReader()
        writer = _AsyncWriter(reader, frame_type, factory)
        client._reader = reader  # type: ignore[assignment]
        client._writer = writer  # type: ignore[assignment]
        return writer
    protocol = SLMPDatagramProtocol(frame_type)
    udp_transport = _AsyncDatagramTransport(protocol, frame_type, factory)
    client._udp_protocol = protocol
    client._udp_transport = udp_transport  # type: ignore[assignment]
    return udp_transport


@pytest.mark.asyncio
async def test_async_udp_protocol_retains_only_the_active_matching_response() -> None:
    protocol = SLMPDatagramProtocol(FrameType.FRAME_4E)
    matching = _response(FrameType.FRAME_4E, 7, TARGET, 0x1234)
    foreign = _response(FrameType.FRAME_4E, 8, TARGET, 0x5678)

    for _ in range(100):
        protocol.datagram_received(foreign, ("127.0.0.1", 1025))
    assert protocol._response_waiter is None
    assert not hasattr(protocol, "queue")

    waiter = protocol.begin_response_wait((7, TARGET))
    protocol.datagram_received(foreign, ("127.0.0.1", 1025))
    assert not waiter.done()
    protocol.datagram_received(matching, ("127.0.0.1", 1025))
    assert await waiter == matching
    protocol.forget_response_wait(waiter)

    protocol.datagram_received(matching, ("127.0.0.1", 1025))
    assert protocol._response_waiter is None


@pytest.mark.asyncio
async def test_async_udp_protocol_reports_malformed_active_datagram_without_retaining_it() -> None:
    protocol = SLMPDatagramProtocol(FrameType.FRAME_4E)
    waiter = protocol.begin_response_wait((7, TARGET))

    protocol.datagram_received(b"bad", ("127.0.0.1", 1025))

    with pytest.raises(SlmpError):
        await waiter
    protocol.forget_response_wait(waiter)
    assert protocol._response_waiter is None


@pytest.mark.parametrize(("frame_type", "profile"), FRAME_PROFILES)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
@pytest.mark.parametrize("field", ROUTE_FIELDS)
def test_sync_discards_each_foreign_route_field_then_accepts_match(
    frame_type: FrameType, profile: str, transport: str, field: str
) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [
            _response(frame_type, serial, _foreign_target(target, field), 0x1111),
            _response(frame_type, serial, target, 0x2222),
        ]

    client, _sock = _sync_client(frame_type, profile, transport, factory)
    assert client.read_devices("D0", 1, bit_unit=False) == [0x2222]
    stats = client.traffic_stats()
    assert stats.rx_bytes == sum(len(item) for item in factory(0, TARGET))


@pytest.mark.parametrize(("frame_type", "profile"), FRAME_PROFILES)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
@pytest.mark.parametrize("field", ROUTE_FIELDS)
async def test_async_discards_each_foreign_route_field_then_accepts_match(
    frame_type: FrameType, profile: str, transport: str, field: str
) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [
            _response(frame_type, serial, _foreign_target(target, field), 0x1111),
            _response(frame_type, serial, target, 0x2222),
        ]

    client, _transport = _async_client(frame_type, profile, transport, factory)
    assert await client.read_devices("D0", 1, bit_unit=False) == [0x2222]
    stats = client.traffic_stats()
    assert stats.rx_bytes == sum(len(item) for item in factory(0, TARGET))


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_4e_discards_wrong_serial_then_accepts_match(transport: str) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [
            _response(FrameType.FRAME_4E, (serial + 1) & 0xFFFF, target, 0x1111),
            _response(FrameType.FRAME_4E, serial, target, 0x2222),
        ]

    client, _sock = _sync_client(FrameType.FRAME_4E, "melsec:iq-r", transport, factory)
    assert client.read_devices("D0", 1, bit_unit=False) == [0x2222]


@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_4e_discards_wrong_serial_then_accepts_match(transport: str) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [
            _response(FrameType.FRAME_4E, (serial + 1) & 0xFFFF, target, 0x1111),
            _response(FrameType.FRAME_4E, serial, target, 0x2222),
        ]

    client, _transport = _async_client(FrameType.FRAME_4E, "melsec:iq-r", transport, factory)
    assert await client.read_devices("D0", 1, bit_unit=False) == [0x2222]


@pytest.mark.parametrize(("frame_type", "profile", "subcommand"), CORRELATION_PROFILES)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
@pytest.mark.parametrize("state_changing", (False, True))
@pytest.mark.parametrize("mismatch", ERROR_INFO_MISMATCHES)
def test_sync_rejects_mismatched_error_information_and_invalidates_transport(
    frame_type: FrameType,
    profile: str,
    subcommand: int,
    transport: str,
    state_changing: bool,
    mismatch: str,
) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [
            _error_response(
                frame_type,
                serial,
                target,
                command=0xFFFF if mismatch == "command" else (0x1401 if state_changing else 0x0401),
                subcommand=0xFFFF if mismatch == "subcommand" else subcommand,
                error_target=_foreign_target(target, mismatch) if mismatch in ROUTE_FIELDS else target,
            )
        ]

    client, sock = _sync_client(frame_type, profile, transport, factory)
    error_type = SlmpOutcomeUnknownError if state_changing else SlmpError
    with pytest.raises(error_type) as caught:
        if state_changing:
            client.write_devices("D0", [1], bit_unit=False)
        else:
            client.read_devices("D0", 1, bit_unit=False)
    if state_changing:
        assert caught.value.reason == SlmpOutcomeUnknownReason.PROTOCOL
    assert sock.closed
    assert client._sock is None


@pytest.mark.parametrize(("frame_type", "profile", "subcommand"), CORRELATION_PROFILES)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
@pytest.mark.parametrize("state_changing", (False, True))
@pytest.mark.parametrize("mismatch", ERROR_INFO_MISMATCHES)
async def test_async_rejects_mismatched_error_information_and_invalidates_transport(
    frame_type: FrameType,
    profile: str,
    subcommand: int,
    transport: str,
    state_changing: bool,
    mismatch: str,
) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [
            _error_response(
                frame_type,
                serial,
                target,
                command=0xFFFF if mismatch == "command" else (0x1401 if state_changing else 0x0401),
                subcommand=0xFFFF if mismatch == "subcommand" else subcommand,
                error_target=_foreign_target(target, mismatch) if mismatch in ROUTE_FIELDS else target,
            )
        ]

    client, transport_state = _async_client(frame_type, profile, transport, factory)
    error_type = SlmpOutcomeUnknownError if state_changing else SlmpError
    with pytest.raises(error_type) as caught:
        if state_changing:
            await client.write_devices("D0", [1], bit_unit=False)
        else:
            await client.read_devices("D0", 1, bit_unit=False)
    if state_changing:
        assert caught.value.reason == SlmpOutcomeUnknownReason.PROTOCOL
    assert transport_state.closed
    if transport == "tcp":
        assert client._writer is None
    else:
        assert client._udp_transport is None


@pytest.mark.parametrize(
    ("frame_type", "profile", "subcommand"), ((*FRAME_PROFILES[0], 0x0000), (*FRAME_PROFILES[1], 0x0002))
)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_accepts_matching_error_information_with_trailing_details(
    frame_type: FrameType, profile: str, subcommand: int, transport: str
) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [
            _error_response(
                frame_type,
                serial,
                target,
                command=0x0401,
                subcommand=subcommand,
                extra=b"\xaa\xbb",
            )
        ]

    client, sock = _sync_client(frame_type, profile, transport, factory)
    with pytest.raises(SlmpError) as caught:
        client.read_devices("D0", 1, bit_unit=False)
    assert caught.value.end_code == 0xC051
    assert caught.value.data.endswith(b"\xaa\xbb")
    assert not sock.closed


@pytest.mark.parametrize(
    ("frame_type", "profile", "subcommand"),
    ((*FRAME_PROFILES[0], 0x0000), (*FRAME_PROFILES[1], 0x0002)),
)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_accepts_matching_error_information_with_trailing_details(
    frame_type: FrameType, profile: str, subcommand: int, transport: str
) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        return [
            _error_response(
                frame_type,
                serial,
                target,
                command=0x0401,
                subcommand=subcommand,
                extra=b"\xaa\xbb",
            )
        ]

    client, transport_state = _async_client(frame_type, profile, transport, factory)
    with pytest.raises(SlmpError) as caught:
        await client.read_devices("D0", 1, bit_unit=False)
    assert caught.value.end_code == 0xC051
    assert caught.value.data.endswith(b"\xaa\xbb")
    assert not transport_state.closed


@pytest.mark.parametrize("command", ACK_COMMANDS)
@pytest.mark.parametrize("response_data", (b"", b"\xaa"))
def test_sync_all_standard_ack_command_families_require_empty_success_data(
    command: Command, response_data: bytes
) -> None:
    client, sock = _sync_client(FrameType.FRAME_4E, "melsec:iq-r", "tcp", lambda _serial, _target: [])

    def exchange(frame: bytes) -> bytes:
        serial, target = _request_identity(frame, FrameType.FRAME_4E)
        return _response_data(FrameType.FRAME_4E, serial, target, response_data)

    client._send_and_receive = exchange  # type: ignore[method-assign]
    if response_data:
        with pytest.raises(SlmpOutcomeUnknownError) as caught:
            client._request(command, 0, b"")
        assert caught.value.reason == SlmpOutcomeUnknownReason.PROTOCOL
        assert sock.closed
    else:
        assert client._request(command, 0, b"").data == b""
        assert not sock.closed


@pytest.mark.parametrize("command", ACK_COMMANDS)
@pytest.mark.parametrize("response_data", (b"", b"\xaa"))
async def test_async_all_standard_ack_command_families_require_empty_success_data(
    command: Command, response_data: bytes
) -> None:
    client, transport_state = _async_client(
        FrameType.FRAME_4E,
        "melsec:iq-r",
        "tcp",
        lambda _serial, _target: [],
    )

    async def exchange(frame: bytes) -> bytes:
        serial, target = _request_identity(frame, FrameType.FRAME_4E)
        return _response_data(FrameType.FRAME_4E, serial, target, response_data)

    client._send_and_receive = exchange  # type: ignore[method-assign]
    if response_data:
        with pytest.raises(SlmpOutcomeUnknownError) as caught:
            await client._request(command, 0, b"")
        assert caught.value.reason == SlmpOutcomeUnknownReason.PROTOCOL
        assert transport_state.closed
    else:
        assert (await client._request(command, 0, b"")).data == b""
        assert not transport_state.closed


@pytest.mark.parametrize(("frame_type", "profile"), FRAME_PROFILES)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_nonempty_standard_ack_is_outcome_unknown_and_invalidates_transport(
    frame_type: FrameType, profile: str, transport: str
) -> None:
    client, sock = _sync_client(
        frame_type,
        profile,
        transport,
        lambda serial, target: [_response(frame_type, serial, target, 0x2222)],
    )
    with pytest.raises(SlmpOutcomeUnknownError) as caught:
        client.write_devices("D0", [1], bit_unit=False)
    assert caught.value.reason == SlmpOutcomeUnknownReason.PROTOCOL
    assert sock.closed
    assert client._sock is None


@pytest.mark.parametrize(("frame_type", "profile"), FRAME_PROFILES)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_nonempty_standard_ack_is_outcome_unknown_and_invalidates_transport(
    frame_type: FrameType, profile: str, transport: str
) -> None:
    client, transport_state = _async_client(
        frame_type,
        profile,
        transport,
        lambda serial, target: [_response(frame_type, serial, target, 0x2222)],
    )
    with pytest.raises(SlmpOutcomeUnknownError) as caught:
        await client.write_devices("D0", [1], bit_unit=False)
    assert caught.value.reason == SlmpOutcomeUnknownReason.PROTOCOL
    assert transport_state.closed


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_raw_command_retains_data_bearing_success_escape_hatch(transport: str) -> None:
    client, sock = _sync_client(
        FrameType.FRAME_4E,
        "melsec:iq-r",
        transport,
        lambda serial, target: [_response(FrameType.FRAME_4E, serial, target, 0x2222)],
    )
    response = client.raw_command(0x1401, subcommand=0x0000, payload=b"", state_changing=True)
    assert response.data == b"\x22\x22"
    assert not sock.closed


@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_raw_command_retains_data_bearing_success_escape_hatch(transport: str) -> None:
    client, transport_state = _async_client(
        FrameType.FRAME_4E,
        "melsec:iq-r",
        transport,
        lambda serial, target: [_response(FrameType.FRAME_4E, serial, target, 0x2222)],
    )
    response = await client.raw_command(0x1401, subcommand=0x0000, payload=b"", state_changing=True)
    assert response.data == b"\x22\x22"
    assert not transport_state.closed


@pytest.mark.parametrize("reserved", (b"\x01\x00", b"\x00\x01", b"\xff\xff"))
def test_direct_4e_decoder_rejects_each_nonzero_reserved_field(reserved: bytes) -> None:
    response = bytearray(_response(FrameType.FRAME_4E, 1, TARGET, 0x2222))
    response[4:6] = reserved
    with pytest.raises(SlmpError, match="reserved field"):
        decode_4e_response(bytes(response))


@pytest.mark.parametrize("transport", ("tcp", "udp"))
@pytest.mark.parametrize("state_changing", (False, True))
def test_sync_4e_nonzero_reserved_response_field_invalidates_transport(transport: str, state_changing: bool) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        response = bytearray(_response(FrameType.FRAME_4E, serial, target, 0x2222))
        response[4] = 1
        return [bytes(response)]

    client, sock = _sync_client(FrameType.FRAME_4E, "melsec:iq-r", transport, factory)
    error_type = SlmpOutcomeUnknownError if state_changing else SlmpError
    with pytest.raises(error_type) as caught:
        if state_changing:
            client.write_devices("D0", [1], bit_unit=False)
        else:
            client.read_devices("D0", 1, bit_unit=False)
    if state_changing:
        assert caught.value.reason == SlmpOutcomeUnknownReason.PROTOCOL
    assert sock.closed


@pytest.mark.parametrize("transport", ("tcp", "udp"))
@pytest.mark.parametrize("state_changing", (False, True))
async def test_async_4e_nonzero_reserved_response_field_invalidates_transport(
    transport: str, state_changing: bool
) -> None:
    def factory(serial: int, target: SlmpTarget) -> list[bytes]:
        response = bytearray(_response(FrameType.FRAME_4E, serial, target, 0x2222))
        response[5] = 1
        return [bytes(response)]

    client, transport_state = _async_client(FrameType.FRAME_4E, "melsec:iq-r", transport, factory)
    error_type = SlmpOutcomeUnknownError if state_changing else SlmpError
    with pytest.raises(error_type) as caught:
        if state_changing:
            await client.write_devices("D0", [1], bit_unit=False)
        else:
            await client.read_devices("D0", 1, bit_unit=False)
    if state_changing:
        assert caught.value.reason == SlmpOutcomeUnknownReason.PROTOCOL
    assert transport_state.closed


class _DelayedMatchingSyncSocket(_SyncScriptSocket):
    def __init__(self, frame_type: FrameType, mismatch: str, *, transport: str) -> None:
        super().__init__(frame_type, lambda _serial, _target: [], transport=transport)
        self.mismatch = mismatch
        self._pending: bytes | None = None

    def _send(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        if self.mismatch == "serial":
            first = _response(self.frame_type, (serial + 1) & 0xFFFF, target, 0x1111)
        else:
            first = _response(self.frame_type, serial, _foreign_target(target, "station"), 0x1111)
        self._pending = _response(self.frame_type, serial, target, 0x2222)
        if self.transport == "tcp":
            self._stream.extend(first)
        else:
            self._datagrams.append(first)

    def _release_pending(self) -> None:
        if self._pending is None:
            return
        time.sleep(0.02)
        pending, self._pending = self._pending, None
        if self.transport == "tcp":
            self._stream.extend(pending)
        else:
            self._datagrams.append(pending)

    def recv_into(self, view: memoryview) -> int:
        if not self._stream:
            self._release_pending()
        return super().recv_into(view)

    def recv(self, size: int) -> bytes:
        if not self._datagrams:
            self._release_pending()
        return super().recv(size)


@pytest.mark.parametrize(
    ("frame_type", "profile", "mismatch"),
    (
        (FrameType.FRAME_3E, "melsec:qnu", "route"),
        (FrameType.FRAME_4E, "melsec:iq-r", "serial"),
    ),
)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_delayed_matching_response_succeeds_within_original_deadline(
    frame_type: FrameType, profile: str, mismatch: str, transport: str
) -> None:
    client, _unused = _sync_client(frame_type, profile, transport, lambda _serial, _target: [], timeout=0.1)
    sock = _DelayedMatchingSyncSocket(frame_type, mismatch, transport=transport)
    client._sock = sock  # type: ignore[assignment]
    started = time.monotonic()
    assert client.read_devices("D0", 1, bit_unit=False) == [0x2222]
    assert time.monotonic() - started < 0.1


class _DelayedMatchingAsyncReader(_AsyncReader):
    def __init__(self) -> None:
        super().__init__()
        self.pending: bytes | None = None

    async def readexactly(self, size: int) -> bytes:
        if len(self.data) < size and self.pending is not None:
            await asyncio.sleep(0.02)
            self.data.extend(self.pending)
            self.pending = None
        return await super().readexactly(size)


class _DelayedMatchingAsyncWriter(_AsyncWriter):
    def __init__(self, reader: _DelayedMatchingAsyncReader, frame_type: FrameType, mismatch: str) -> None:
        super().__init__(reader, frame_type, lambda _serial, _target: [])
        self.mismatch = mismatch

    def write(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        if self.mismatch == "serial":
            first = _response(self.frame_type, (serial + 1) & 0xFFFF, target, 0x1111)
        else:
            first = _response(self.frame_type, serial, _foreign_target(target, "station"), 0x1111)
        self.reader.data.extend(first)
        assert isinstance(self.reader, _DelayedMatchingAsyncReader)
        self.reader.pending = _response(self.frame_type, serial, target, 0x2222)


class _DelayedMatchingDatagramTransport(_AsyncDatagramTransport):
    def __init__(self, protocol: SLMPDatagramProtocol, frame_type: FrameType, mismatch: str) -> None:
        super().__init__(protocol, frame_type, lambda _serial, _target: [])
        self.mismatch = mismatch

    def sendto(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        if self.mismatch == "serial":
            first = _response(self.frame_type, (serial + 1) & 0xFFFF, target, 0x1111)
        else:
            first = _response(self.frame_type, serial, _foreign_target(target, "station"), 0x1111)
        matching = _response(self.frame_type, serial, target, 0x2222)
        self.protocol.datagram_received(first, ("127.0.0.1", 1025))
        asyncio.get_running_loop().call_later(0.02, self.protocol.datagram_received, matching, ("127.0.0.1", 1025))


@pytest.mark.parametrize(
    ("frame_type", "profile", "mismatch"),
    (
        (FrameType.FRAME_3E, "melsec:qnu", "route"),
        (FrameType.FRAME_4E, "melsec:iq-r", "serial"),
    ),
)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_delayed_matching_response_succeeds_within_original_deadline(
    frame_type: FrameType, profile: str, mismatch: str, transport: str
) -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=TARGET,
        plc_profile=profile,
        timeout=0.1,
    )
    if transport == "tcp":
        reader = _DelayedMatchingAsyncReader()
        client._reader = reader  # type: ignore[assignment]
        client._writer = _DelayedMatchingAsyncWriter(reader, frame_type, mismatch)  # type: ignore[assignment]
    else:
        protocol = SLMPDatagramProtocol(frame_type)
        client._udp_protocol = protocol
        client._udp_transport = _DelayedMatchingDatagramTransport(  # type: ignore[assignment]
            protocol, frame_type, mismatch
        )
    loop = asyncio.get_running_loop()
    started = loop.time()
    assert await client.read_devices("D0", 1, bit_unit=False) == [0x2222]
    assert loop.time() - started < 0.1


class _TimedWrongSyncSocket(_SyncScriptSocket):
    def __init__(self, *, transport: str) -> None:
        super().__init__(FrameType.FRAME_4E, lambda _serial, _target: [], transport=transport)
        self.serial = 0
        self.target = TARGET

    def _send(self, data: bytes) -> None:
        self.serial, self.target = _request_identity(data, FrameType.FRAME_4E)

    def _wrong(self) -> bytes:
        time.sleep(0.02)
        return _response(FrameType.FRAME_4E, (self.serial + 1) & 0xFFFF, self.target, 0x1111)

    def recv(self, _size: int) -> bytes:
        return self._wrong()

    def recv_into(self, view: memoryview) -> int:
        if not self._stream:
            self._stream.extend(self._wrong())
        return super().recv_into(view)


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_wrong_serial_flood_does_not_extend_absolute_deadline(transport: str) -> None:
    client, _unused = _sync_client(FrameType.FRAME_4E, "melsec:iq-r", transport, lambda _s, _t: [], timeout=0.08)
    sock = _TimedWrongSyncSocket(transport=transport)
    client._sock = sock  # type: ignore[assignment]
    started = time.monotonic()
    with pytest.raises(SlmpTimeoutError, match="SLMP communication timeout"):
        client.read_devices("D0", 1, bit_unit=False)
    elapsed = time.monotonic() - started
    assert 0.06 <= elapsed < 0.20
    assert sock.closed
    assert client._sock is None
    timed_out_rx_bytes = client.traffic_stats().rx_bytes
    assert timed_out_rx_bytes > 0

    fresh = _SyncScriptSocket(
        FrameType.FRAME_4E,
        lambda serial, target: [_response(FrameType.FRAME_4E, serial, target, 0x3333)],
        transport=transport,
    )
    client._sock = fresh  # type: ignore[assignment]
    assert client.read_devices("D0", 1, bit_unit=False) == [0x3333]
    assert client.traffic_stats().request_count == 2
    assert client.traffic_stats().rx_bytes > timed_out_rx_bytes


class _TimedForeignSyncSocket(_SyncScriptSocket):
    def __init__(self, *, transport: str) -> None:
        super().__init__(FrameType.FRAME_3E, lambda _serial, _target: [], transport=transport)
        self.target = TARGET

    def _send(self, data: bytes) -> None:
        _serial, self.target = _request_identity(data, FrameType.FRAME_3E)

    def _foreign(self) -> bytes:
        time.sleep(0.02)
        return _response(FrameType.FRAME_3E, 0, _foreign_target(self.target, "station"), 0x1111)

    def recv(self, _size: int) -> bytes:
        return self._foreign()

    def recv_into(self, view: memoryview) -> int:
        if not self._stream:
            self._stream.extend(self._foreign())
        return super().recv_into(view)


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_foreign_route_flood_does_not_extend_absolute_deadline(transport: str) -> None:
    client, _unused = _sync_client(FrameType.FRAME_3E, "melsec:qnu", transport, lambda _s, _t: [], timeout=0.08)
    sock = _TimedForeignSyncSocket(transport=transport)
    client._sock = sock  # type: ignore[assignment]
    started = time.monotonic()
    with pytest.raises(SlmpTimeoutError, match="SLMP communication timeout"):
        client.read_devices("D0", 1, bit_unit=False)
    assert 0.06 <= time.monotonic() - started < 0.20
    assert sock.closed
    assert client._sock is None
    timed_out_rx_bytes = client.traffic_stats().rx_bytes
    assert timed_out_rx_bytes > 0

    fresh = _SyncScriptSocket(
        FrameType.FRAME_3E,
        lambda serial, target: [_response(FrameType.FRAME_3E, serial, target, 0x3333)],
        transport=transport,
    )
    client._sock = fresh  # type: ignore[assignment]
    assert client.read_devices("D0", 1, bit_unit=False) == [0x3333]
    assert client.traffic_stats().request_count == 2
    assert client.traffic_stats().rx_bytes > timed_out_rx_bytes


class _TimedWrongAsyncReader(_AsyncReader):
    def __init__(self, frame_type: FrameType) -> None:
        super().__init__()
        self.frame_type = frame_type

    async def readexactly(self, size: int) -> bytes:
        if len(self.data) < size:
            await asyncio.sleep(0.02)
            self.data.extend(_response(self.frame_type, 1, TARGET, 0x1111))
        return await super().readexactly(size)


class _TimedWrongAsyncWriter(_AsyncWriter):
    def write(self, _data: bytes) -> None:
        return None


class _TimedWrongDatagramTransport(_AsyncDatagramTransport):
    def sendto(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        loop = asyncio.get_running_loop()

        def emit() -> None:
            if not self.closed:
                self.protocol.datagram_received(
                    _response(self.frame_type, (serial + 1) & 0xFFFF, target, 0x1111), ("127.0.0.1", 1025)
                )

        for index in range(1, 16):
            loop.call_later(index * 0.02, emit)


@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_wrong_serial_flood_does_not_extend_absolute_deadline(transport: str) -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=TARGET,
        plc_profile="melsec:iq-r",
        timeout=0.08,
    )
    if transport == "tcp":
        reader = _TimedWrongAsyncReader(FrameType.FRAME_4E)
        writer = _TimedWrongAsyncWriter(reader, FrameType.FRAME_4E, lambda _serial, _target: [])
        client._reader = reader  # type: ignore[assignment]
        client._writer = writer  # type: ignore[assignment]
        transport_state: Any = writer
    else:
        protocol = SLMPDatagramProtocol(FrameType.FRAME_4E)
        transport_state = _TimedWrongDatagramTransport(protocol, FrameType.FRAME_4E, lambda _serial, _target: [])
        client._udp_protocol = protocol
        client._udp_transport = transport_state  # type: ignore[assignment]

    loop = asyncio.get_running_loop()
    started = loop.time()
    with pytest.raises(SlmpTimeoutError, match="SLMP communication timeout"):
        await client.read_devices("D0", 1, bit_unit=False)
    elapsed = loop.time() - started
    assert 0.06 <= elapsed < 0.20
    assert transport_state.closed
    if transport == "tcp":
        assert client._writer is None
    else:
        assert client._udp_transport is None
    timed_out_rx_bytes = client.traffic_stats().rx_bytes
    assert timed_out_rx_bytes > 0

    fresh = _install_clean_async_transport(client, FrameType.FRAME_4E, transport)
    assert await client.read_devices("D0", 1, bit_unit=False) == [0x3333]
    assert not fresh.closed
    assert client.traffic_stats().request_count == 2
    assert client.traffic_stats().rx_bytes > timed_out_rx_bytes


class _TimedForeignAsyncReader(_AsyncReader):
    async def readexactly(self, size: int) -> bytes:
        if len(self.data) < size:
            await asyncio.sleep(0.02)
            self.data.extend(_response(FrameType.FRAME_3E, 0, _foreign_target(TARGET, "station"), 0x1111))
        return await super().readexactly(size)


class _TimedForeignDatagramTransport(_AsyncDatagramTransport):
    def sendto(self, data: bytes) -> None:
        _serial, target = _request_identity(data, self.frame_type)
        loop = asyncio.get_running_loop()

        def emit() -> None:
            if not self.closed:
                self.protocol.datagram_received(
                    _response(self.frame_type, 0, _foreign_target(target, "station"), 0x1111),
                    ("127.0.0.1", 1025),
                )

        for index in range(1, 16):
            loop.call_later(index * 0.02, emit)


@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_foreign_route_flood_does_not_extend_absolute_deadline(transport: str) -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=TARGET,
        plc_profile="melsec:qnu",
        timeout=0.08,
    )
    if transport == "tcp":
        reader = _TimedForeignAsyncReader()
        writer = _TimedWrongAsyncWriter(reader, FrameType.FRAME_3E, lambda _serial, _target: [])
        client._reader = reader  # type: ignore[assignment]
        client._writer = writer  # type: ignore[assignment]
        transport_state: Any = writer
    else:
        protocol = SLMPDatagramProtocol(FrameType.FRAME_3E)
        transport_state = _TimedForeignDatagramTransport(protocol, FrameType.FRAME_3E, lambda _s, _t: [])
        client._udp_protocol = protocol
        client._udp_transport = transport_state  # type: ignore[assignment]

    loop = asyncio.get_running_loop()
    started = loop.time()
    with pytest.raises(SlmpTimeoutError, match="SLMP communication timeout"):
        await client.read_devices("D0", 1, bit_unit=False)
    assert 0.06 <= loop.time() - started < 0.20
    assert transport_state.closed
    if transport == "tcp":
        assert client._writer is None
    else:
        assert client._udp_transport is None
    timed_out_rx_bytes = client.traffic_stats().rx_bytes
    assert timed_out_rx_bytes > 0

    fresh = _install_clean_async_transport(client, FrameType.FRAME_3E, transport)
    assert await client.read_devices("D0", 1, bit_unit=False) == [0x3333]
    assert not fresh.closed
    assert client.traffic_stats().request_count == 2
    assert client.traffic_stats().rx_bytes > timed_out_rx_bytes


class _SplitDeadlineSyncSocket(_SyncScriptSocket):
    def __init__(self, delays: tuple[float, float]) -> None:
        super().__init__(FrameType.FRAME_4E, lambda _serial, _target: [], transport="tcp")
        self.delays = list(delays)
        self.chunks: list[bytes] = []

    def _send(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        response = _response(self.frame_type, serial, target, 0x2222)
        self.chunks = [response[:13], response[13:]]

    def recv_into(self, view: memoryview) -> int:
        delay = self.delays.pop(0)
        if self.timeout is not None and delay > self.timeout:
            time.sleep(self.timeout)
            raise TimeoutError("simulated socket deadline")
        time.sleep(delay)
        chunk = self.chunks.pop(0)
        assert len(chunk) == len(view)
        view[:] = chunk
        return len(chunk)


@pytest.mark.parametrize(("delays", "should_succeed"), (((0.01, 0.01), True), ((0.05, 0.05), False)))
def test_sync_tcp_header_and_body_share_one_absolute_deadline(
    delays: tuple[float, float], should_succeed: bool
) -> None:
    client, _unused = _sync_client(FrameType.FRAME_4E, "melsec:iq-r", "tcp", lambda _serial, _target: [], timeout=0.08)
    sock = _SplitDeadlineSyncSocket(delays)
    client._sock = sock  # type: ignore[assignment]
    if should_succeed:
        assert client.read_devices("D0", 1, bit_unit=False) == [0x2222]
        return
    started = time.monotonic()
    with pytest.raises(SlmpTimeoutError, match="SLMP communication timeout"):
        client.read_devices("D0", 1, bit_unit=False)
    assert 0.06 <= time.monotonic() - started < 0.2
    assert sock.closed


class _SplitDeadlineAsyncReader(_AsyncReader):
    def __init__(self, delays: tuple[float, float]) -> None:
        super().__init__()
        self.delays = list(delays)
        self.chunks: list[bytes] = []

    async def readexactly(self, size: int) -> bytes:
        await asyncio.sleep(self.delays.pop(0))
        chunk = self.chunks.pop(0)
        assert len(chunk) == size
        return chunk


class _SplitDeadlineAsyncWriter(_AsyncWriter):
    def write(self, data: bytes) -> None:
        serial, target = _request_identity(data, self.frame_type)
        response = _response(self.frame_type, serial, target, 0x2222)
        assert isinstance(self.reader, _SplitDeadlineAsyncReader)
        self.reader.chunks = [response[:13], response[13:]]


@pytest.mark.parametrize(("delays", "should_succeed"), (((0.01, 0.01), True), ((0.05, 0.05), False)))
async def test_async_tcp_header_and_body_share_one_absolute_deadline(
    delays: tuple[float, float], should_succeed: bool
) -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=TARGET,
        plc_profile="melsec:iq-r",
        timeout=0.08,
    )
    reader = _SplitDeadlineAsyncReader(delays)
    writer = _SplitDeadlineAsyncWriter(reader, FrameType.FRAME_4E, lambda _serial, _target: [])
    client._reader = reader  # type: ignore[assignment]
    client._writer = writer  # type: ignore[assignment]
    if should_succeed:
        assert await client.read_devices("D0", 1, bit_unit=False) == [0x2222]
        return
    loop = asyncio.get_running_loop()
    started = loop.time()
    with pytest.raises(SlmpTimeoutError, match="SLMP communication timeout"):
        await client.read_devices("D0", 1, bit_unit=False)
    assert 0.06 <= loop.time() - started < 0.2
    assert writer.closed


@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_cancellation_after_send_invalidates_transport_generation(transport: str) -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=TARGET,
        plc_profile="melsec:iq-r",
        timeout=1.0,
    )
    if transport == "tcp":
        reader = _AsyncReader()
        transport_state: Any = _AsyncWriter(reader, FrameType.FRAME_4E, lambda _serial, _target: [])
        client._reader = reader  # type: ignore[assignment]
        client._writer = transport_state  # type: ignore[assignment]
    else:
        protocol = SLMPDatagramProtocol(FrameType.FRAME_4E)
        transport_state = _AsyncDatagramTransport(protocol, FrameType.FRAME_4E, lambda _serial, _target: [])
        client._udp_protocol = protocol
        client._udp_transport = transport_state  # type: ignore[assignment]

    request = asyncio.create_task(client.read_devices("D0", 1, bit_unit=False))
    for _ in range(20):
        if client.traffic_stats().request_count == 1:
            break
        await asyncio.sleep(0)
    assert client.traffic_stats().request_count == 1
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request

    assert transport_state.closed
    assert client.traffic_stats().request_count == 1
    if transport == "tcp":
        assert client._reader is None
        assert client._writer is None
    else:
        assert client._udp_protocol is None
        assert client._udp_transport is None


@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_cancellation_while_waiting_for_request_lock_preserves_active_transport(transport: str) -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=TARGET,
        plc_profile="melsec:iq-r",
        timeout=1.0,
    )
    if transport == "tcp":
        reader = _AsyncReader()
        transport_state: Any = _AsyncWriter(reader, FrameType.FRAME_4E, lambda _serial, _target: [])
        client._reader = reader  # type: ignore[assignment]
        client._writer = transport_state  # type: ignore[assignment]
    else:
        protocol = SLMPDatagramProtocol(FrameType.FRAME_4E)
        transport_state = _AsyncDatagramTransport(protocol, FrameType.FRAME_4E, lambda _serial, _target: [])
        client._udp_protocol = protocol
        client._udp_transport = transport_state  # type: ignore[assignment]

    async def already_connected() -> None:
        return None

    client.connect = already_connected  # type: ignore[method-assign]
    await client._lock.acquire()
    request_frame = b"\x54\x00\x00\x00\x00\x00\x01\x02\x34\x12\x03"
    request = asyncio.create_task(client._send_and_receive(request_frame))
    try:
        await asyncio.sleep(0)
        assert not request.done()
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
    finally:
        client._lock.release()

    assert not transport_state.closed
    if transport == "tcp":
        assert client._reader is reader
        assert client._writer is transport_state
    else:
        assert client._udp_protocol is protocol
        assert client._udp_transport is transport_state


def test_sync_internal_exchange_rejects_request_without_response_identity_before_transport() -> None:
    client, sock = _sync_client(FrameType.FRAME_4E, "melsec:iq-r", "tcp", lambda _serial, _target: [])

    with pytest.raises(SlmpError, match="invalid 4E request frame"):
        client._send_and_receive(b"request")

    assert client.traffic_stats().request_count == 0
    assert not sock.closed


async def test_async_internal_exchange_rejects_request_without_response_identity_before_transport() -> None:
    client, transport_state = _async_client(FrameType.FRAME_4E, "melsec:iq-r", "tcp", lambda _serial, _target: [])

    with pytest.raises(SlmpError, match="invalid 4E request frame"):
        await client._send_and_receive(b"request")

    assert client.traffic_stats().request_count == 0
    assert not transport_state.closed


@pytest.mark.parametrize(("frame_type", "profile"), FRAME_PROFILES)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_malformed_response_invalidates_transport(frame_type: FrameType, profile: str, transport: str) -> None:
    malformed = b"\x00\x00" + b"\x00" * (11 if frame_type == FrameType.FRAME_4E else 7)
    client, sock = _sync_client(frame_type, profile, transport, lambda _serial, _target: [malformed])
    with pytest.raises(SlmpError):
        client.read_devices("D0", 1, bit_unit=False)
    assert sock.closed
    assert client._sock is None


@pytest.mark.parametrize(("frame_type", "profile"), FRAME_PROFILES)
@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_malformed_response_invalidates_transport(
    frame_type: FrameType, profile: str, transport: str
) -> None:
    malformed = b"\x00\x00" + b"\x00" * (11 if frame_type == FrameType.FRAME_4E else 7)
    client, transport_state = _async_client(frame_type, profile, transport, lambda _serial, _target: [malformed])
    with pytest.raises(SlmpError):
        await client.read_devices("D0", 1, bit_unit=False)
    assert transport_state.closed
    if transport == "tcp":
        assert client._writer is None
    else:
        assert client._udp_transport is None
