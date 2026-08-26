"""Cross-cutting operation queue, aggregate, and error-contract tests."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from slmp import _operations
from slmp._operation_queue import _AsyncFifoOperationQueue, _SyncFifoOperationQueue
from slmp.async_client import AsyncSlmpClient, SLMPDatagramProtocol
from slmp.client import SlmpClient
from slmp.client import _classify_exchange_failure as classify_sync_failure
from slmp.constants import Command, FrameType
from slmp.core import RandomReadResult, SlmpResponse, SlmpTarget
from slmp.errors import (
    SlmpClosedError,
    SlmpError,
    SlmpNotConnectedError,
    SlmpOutcomeUnknownError,
    SlmpOutcomeUnknownReason,
    SlmpProfileFeatureError,
    SlmpTimeoutError,
    SlmpTransportError,
)
from slmp.utils import read_named_sync, write_bit_in_word, write_bit_in_word_sync


def _completed_4e_response(*, end_code: int = 0, data: bytes = b"") -> bytes:
    target = SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0)
    route = (
        bytes((target.network, target.station)) + target.module_io.to_bytes(2, "little") + bytes((target.multidrop,))
    )
    body = end_code.to_bytes(2, "little") + data
    return b"\xd4\x00\x00\x00\x00\x00" + route + len(body).to_bytes(2, "little") + body


class _CompletedSyncClient(SlmpClient):
    def __init__(self, response: bytes, *, transport: str, trace_hook=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(
            "127.0.0.1",
            1025,
            transport=transport,
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
            _maintainer_trace_hook=trace_hook,
        )
        self.response = response

    def _send_and_receive(self, _frame: bytes) -> bytes:
        return self.response


class _CompletedAsyncClient(AsyncSlmpClient):
    def __init__(self, response: bytes, *, transport: str, trace_hook=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(
            "127.0.0.1",
            1025,
            transport=transport,
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
            _maintainer_trace_hook=trace_hook,
        )
        self.response = response

    async def _send_and_receive(self, _frame: bytes) -> bytes:
        return self.response


class _CloseInterruptSocket:
    def __init__(self) -> None:
        self.receive_started = threading.Event()
        self.closed = threading.Event()
        self.timeout: float | None = None

    def settimeout(self, timeout: float | None) -> None:
        self.timeout = timeout

    def sendall(self, _data: bytes) -> None:
        return None

    def send(self, data: bytes) -> int:
        return len(data)

    def recv_into(self, _view: memoryview) -> int:
        self.receive_started.set()
        assert self.closed.wait(timeout=1)
        raise OSError("socket closed locally")

    def recv(self, _size: int) -> bytes:
        self.receive_started.set()
        assert self.closed.wait(timeout=1)
        raise OSError("socket closed locally")

    def close(self) -> None:
        self.closed.set()


def test_sync_operation_queue_is_fifo() -> None:
    queue = _SyncFifoOperationQueue()
    order: list[int] = []
    threads: list[threading.Thread] = []

    def worker(index: int) -> None:
        with queue.turn():
            order.append(index)

    with queue.turn():
        for index in range(5):
            thread = threading.Thread(target=worker, args=(index,))
            thread.start()
            threads.append(thread)
            deadline = time.monotonic() + 1
            while len(queue._waiters) != index + 1:  # noqa: SLF001 - contract test
                assert time.monotonic() < deadline
                time.sleep(0.001)

    for thread in threads:
        thread.join(timeout=1)
        assert not thread.is_alive()
    assert order == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_async_operation_queue_is_fifo_and_cancelled_waiter_is_removed() -> None:
    queue = _AsyncFifoOperationQueue()
    order: list[int] = []

    async def worker(index: int) -> None:
        async with queue.turn():
            order.append(index)

    await queue.lock.acquire()
    tasks = [asyncio.create_task(worker(index)) for index in range(4)]
    await asyncio.sleep(0)
    tasks[1].cancel()
    with pytest.raises(asyncio.CancelledError):
        await tasks[1]
    queue.lock.release()
    await asyncio.gather(tasks[0], tasks[2], tasks[3])

    assert order == [0, 2, 3]


def test_close_generation_rejects_active_and_queued_sync_turns() -> None:
    queue = _SyncFifoOperationQueue()
    with queue.turn():
        queue.invalidate()
        with pytest.raises(SlmpClosedError, match="closed during the active operation"):
            queue.ensure_current()


def test_state_change_timeout_after_possible_send_is_outcome_unknown() -> None:
    cause = TimeoutError("deadline")
    error = classify_sync_failure(cause, state_changing=True, attempted_send=True)

    assert isinstance(error, SlmpOutcomeUnknownError)
    assert error.reason is SlmpOutcomeUnknownReason.TIMEOUT
    assert error.cause is cause
    assert isinstance(classify_sync_failure(cause, state_changing=False, attempted_send=True), SlmpTimeoutError)


def test_public_transport_error_types_are_pairwise_distinct() -> None:
    types = {SlmpTimeoutError, SlmpClosedError, SlmpNotConnectedError, SlmpTransportError, SlmpOutcomeUnknownError}
    assert len(types) == 5


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_decoded_read_result_wins_close_after_publication(transport: str) -> None:
    client = _CompletedSyncClient(_completed_4e_response(data=b"\x34\x12"), transport=transport)
    original_ensure = client._operation_queue.ensure_current  # noqa: SLF001 - deterministic lifecycle barrier
    calls = 0

    def close_after_publication() -> None:
        nonlocal calls
        original_ensure()
        calls += 1
        if calls == 2:
            client.close()

    client._operation_queue.ensure_current = close_after_publication  # type: ignore[method-assign]  # noqa: SLF001

    assert client.read_devices("D0", 1, bit_unit=False) == [0x1234]


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_decoded_read_result_wins_close_generation_after_publication(transport: str) -> None:
    client = _CompletedAsyncClient(_completed_4e_response(data=b"\x34\x12"), transport=transport)
    original_ensure = client._operation_queue.ensure_current  # noqa: SLF001 - deterministic lifecycle barrier
    calls = 0

    def close_after_publication() -> None:
        nonlocal calls
        original_ensure()
        calls += 1
        if calls == 2:
            client._operation_queue.invalidate()  # noqa: SLF001 - close's linearization point

    client._operation_queue.ensure_current = close_after_publication  # type: ignore[method-assign]  # noqa: SLF001

    assert await client.read_devices("D0", 1, bit_unit=False) == [0x1234]


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_close_before_command_decode_keeps_read_incomplete(transport: str) -> None:
    client: _CompletedSyncClient
    client = _CompletedSyncClient(
        _completed_4e_response(data=b"\x34\x12"),
        transport=transport,
        trace_hook=lambda _trace: client.close(),
    )

    with pytest.raises(SlmpClosedError):
        client.read_devices("D0", 1, bit_unit=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_close_before_command_decode_keeps_read_incomplete(transport: str) -> None:
    client: _CompletedAsyncClient

    async def close_during_trace(_trace) -> None:  # type: ignore[no-untyped-def]
        await client.close()

    client = _CompletedAsyncClient(
        _completed_4e_response(data=b"\x34\x12"),
        transport=transport,
        trace_hook=close_during_trace,
    )

    with pytest.raises(SlmpClosedError):
        await client.read_devices("D0", 1, bit_unit=False)


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_close_during_command_decode_error_keeps_read_incomplete(
    transport: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CompletedSyncClient(_completed_4e_response(data=b""), transport=transport)
    original_decoder = _operations.decode_read_devices_response

    def close_before_decode_error(response, *, points: int, bit_unit: bool):  # type: ignore[no-untyped-def]
        client.close()
        return original_decoder(response, points=points, bit_unit=bit_unit)

    monkeypatch.setattr(_operations, "decode_read_devices_response", close_before_decode_error)

    with pytest.raises(SlmpClosedError):
        client.read_devices("D0", 1, bit_unit=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ("tcp", "udp"))
async def test_async_close_during_command_decode_error_keeps_read_incomplete(
    transport: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _CompletedAsyncClient(_completed_4e_response(data=b""), transport=transport)
    original_decoder = _operations.decode_read_devices_response

    def close_before_decode_error(response, *, points: int, bit_unit: bool):  # type: ignore[no-untyped-def]
        client._operation_queue.invalidate()  # noqa: SLF001 - close's linearization point
        return original_decoder(response, points=points, bit_unit=bit_unit)

    monkeypatch.setattr(_operations, "decode_read_devices_response", close_before_decode_error)

    with pytest.raises(SlmpClosedError):
        await client.read_devices("D0", 1, bit_unit=False)


@pytest.mark.parametrize("transport", ("tcp", "udp"))
@pytest.mark.parametrize("raise_on_error", (False, True))
def test_sync_framed_plc_error_and_acknowledged_write_win_concurrent_close(
    transport: str,
    raise_on_error: bool,
) -> None:
    error_client: _CompletedSyncClient
    error_client = _CompletedSyncClient(
        _completed_4e_response(end_code=0xC051),
        transport=transport,
        trace_hook=lambda _trace: error_client.close(),
    )
    error_client.raise_on_error = raise_on_error
    with pytest.raises(SlmpError) as raised:
        error_client.read_devices("D0", 1, bit_unit=False)
    assert raised.value.end_code == 0xC051

    write_client: _CompletedSyncClient
    write_client = _CompletedSyncClient(
        _completed_4e_response(),
        transport=transport,
        trace_hook=lambda _trace: write_client.close(),
    )
    write_client.write_devices("D0", [1], bit_unit=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ("tcp", "udp"))
@pytest.mark.parametrize("raise_on_error", (False, True))
async def test_async_framed_plc_error_and_acknowledged_write_win_concurrent_close(
    transport: str,
    raise_on_error: bool,
) -> None:
    error_client: _CompletedAsyncClient

    async def close_error_client(_trace) -> None:  # type: ignore[no-untyped-def]
        await error_client.close()

    error_client = _CompletedAsyncClient(
        _completed_4e_response(end_code=0xC051),
        transport=transport,
        trace_hook=close_error_client,
    )
    error_client.raise_on_error = raise_on_error
    with pytest.raises(SlmpError) as raised:
        await error_client.read_devices("D0", 1, bit_unit=False)
    assert raised.value.end_code == 0xC051

    write_client: _CompletedAsyncClient

    async def close_write_client(_trace) -> None:  # type: ignore[no-untyped-def]
        await write_client.close()

    write_client = _CompletedAsyncClient(
        _completed_4e_response(),
        transport=transport,
        trace_hook=close_write_client,
    )
    await write_client.write_devices("D0", [1], bit_unit=False)


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_local_close_during_receive_raises_typed_closed_error(transport: str) -> None:
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    sock = _CloseInterruptSocket()
    client._sock = sock  # type: ignore[assignment]  # noqa: SLF001
    failure: list[BaseException] = []

    def read() -> None:
        try:
            client.read_devices("D0", 1, bit_unit=False)
        except BaseException as error:
            failure.append(error)

    worker = threading.Thread(target=read)
    worker.start()
    assert sock.receive_started.wait(timeout=1)
    client.close()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert len(failure) == 1
    assert isinstance(failure[0], SlmpClosedError)


@pytest.mark.parametrize("transport", ("tcp", "udp"))
def test_sync_local_close_after_write_send_keeps_outcome_unknown(transport: str) -> None:
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport=transport,
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    sock = _CloseInterruptSocket()
    client._sock = sock  # type: ignore[assignment]  # noqa: SLF001
    failure: list[BaseException] = []

    def write() -> None:
        try:
            client.write_devices("D0", [1], bit_unit=False)
        except BaseException as error:
            failure.append(error)

    worker = threading.Thread(target=write)
    worker.start()
    assert sock.receive_started.wait(timeout=1)
    client.close()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert len(failure) == 1
    assert isinstance(failure[0], SlmpOutcomeUnknownError)
    assert failure[0].reason is SlmpOutcomeUnknownReason.CLOSED
    assert isinstance(failure[0].cause, SlmpClosedError)


@pytest.mark.asyncio
async def test_async_tcp_local_close_during_receive_raises_typed_closed_error() -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    receive_started = asyncio.Event()
    released = asyncio.Event()

    async def readexactly(_size: int) -> bytes:
        receive_started.set()
        await released.wait()
        raise asyncio.IncompleteReadError(b"", _size)

    reader = MagicMock()
    reader.readexactly = AsyncMock(side_effect=readexactly)
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.close.side_effect = released.set
    writer.wait_closed = AsyncMock()
    client._reader = reader  # noqa: SLF001
    client._writer = writer  # noqa: SLF001

    operation = asyncio.create_task(client.read_devices("D0", 1, bit_unit=False))
    await receive_started.wait()
    await client.close()

    with pytest.raises(SlmpClosedError):
        await operation


@pytest.mark.asyncio
async def test_async_udp_local_close_during_receive_raises_typed_closed_error() -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="udp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    send_started = asyncio.Event()
    protocol = SLMPDatagramProtocol(FrameType.FRAME_4E)
    transport = MagicMock()
    transport.sendto.side_effect = lambda _frame: send_started.set()
    client._udp_protocol = protocol  # noqa: SLF001
    client._udp_transport = transport  # noqa: SLF001

    operation = asyncio.create_task(client.read_devices("D0", 1, bit_unit=False))
    await send_started.wait()
    await client.close()

    with pytest.raises(SlmpClosedError):
        await operation


@pytest.mark.asyncio
async def test_async_udp_local_close_after_write_send_keeps_outcome_unknown() -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="udp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    send_started = asyncio.Event()
    protocol = SLMPDatagramProtocol(FrameType.FRAME_4E)
    transport = MagicMock()
    transport.sendto.side_effect = lambda _frame: send_started.set()
    client._udp_protocol = protocol  # noqa: SLF001
    client._udp_transport = transport  # noqa: SLF001

    operation = asyncio.create_task(client.write_devices("D0", [1], bit_unit=False))
    await send_started.wait()
    await client.close()

    with pytest.raises(SlmpOutcomeUnknownError) as raised:
        await operation
    assert raised.value.reason is SlmpOutcomeUnknownReason.CLOSED
    assert isinstance(raised.value.cause, SlmpClosedError)


def _sync_raw_client_with_receive_timeout() -> tuple[SlmpClient, MagicMock]:
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    sock = MagicMock()
    sock.recv_into.side_effect = TimeoutError("deadline")
    client._sock = sock
    return client, sock


def test_sync_unknown_raw_command_defaults_to_state_changing_after_send() -> None:
    client, sock = _sync_raw_client_with_receive_timeout()

    with pytest.raises(SlmpOutcomeUnknownError) as raised:
        client.raw_command(0x1829, subcommand=0, payload=b"")

    assert raised.value.reason is SlmpOutcomeUnknownReason.TIMEOUT
    sock.sendall.assert_called_once()


def test_sync_unknown_raw_command_can_be_explicitly_declared_read_only() -> None:
    client, sock = _sync_raw_client_with_receive_timeout()

    with pytest.raises(SlmpTimeoutError):
        client.raw_command(0x1829, subcommand=0, payload=b"", state_changing=False)

    sock.sendall.assert_called_once()


@pytest.mark.parametrize("value", (0, 1, "false", []))
def test_sync_raw_command_rejects_non_boolean_state_classification_before_transport(value: object) -> None:
    client, sock = _sync_raw_client_with_receive_timeout()

    with pytest.raises(ValueError, match="state_changing must be a boolean or None"):
        client.raw_command(0x1829, subcommand=0, payload=b"", state_changing=value)  # type: ignore[arg-type]

    sock.sendall.assert_not_called()


def test_sync_raw_command_cannot_downgrade_a_known_state_changing_command() -> None:
    client, sock = _sync_raw_client_with_receive_timeout()

    with pytest.raises(ValueError, match="cannot downgrade"):
        client.raw_command(Command.CLEAR_ERROR, subcommand=0, payload=b"", state_changing=False)

    sock.sendall.assert_not_called()


def _async_raw_client_with_receive_timeout() -> tuple[AsyncSlmpClient, MagicMock]:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    reader = MagicMock()
    reader.readexactly = AsyncMock(side_effect=TimeoutError("deadline"))
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    client._reader = reader
    client._writer = writer
    return client, writer


@pytest.mark.asyncio
async def test_async_unknown_raw_command_defaults_to_state_changing_after_send() -> None:
    client, writer = _async_raw_client_with_receive_timeout()

    with pytest.raises(SlmpOutcomeUnknownError) as raised:
        await client.raw_command(0x1829, subcommand=0, payload=b"")

    assert raised.value.reason is SlmpOutcomeUnknownReason.TIMEOUT
    writer.write.assert_called_once()


@pytest.mark.asyncio
async def test_async_unknown_raw_command_can_be_explicitly_declared_read_only() -> None:
    client, writer = _async_raw_client_with_receive_timeout()

    with pytest.raises(SlmpTimeoutError):
        await client.raw_command(0x1829, subcommand=0, payload=b"", state_changing=False)

    writer.write.assert_called_once()


@pytest.mark.asyncio
async def test_async_raw_command_rejects_non_boolean_state_classification_before_transport() -> None:
    client, writer = _async_raw_client_with_receive_timeout()

    with pytest.raises(ValueError, match="state_changing must be a boolean or None"):
        await client.raw_command(0x1829, subcommand=0, payload=b"", state_changing=1)  # type: ignore[arg-type]

    writer.write.assert_not_called()


@pytest.mark.asyncio
async def test_async_state_change_cancellation_after_send_is_outcome_unknown() -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    drain_started = asyncio.Event()

    async def drain() -> None:
        drain_started.set()
        await asyncio.Future()

    writer = MagicMock()
    writer.drain = AsyncMock(side_effect=drain)
    writer.wait_closed = AsyncMock()
    client._reader = MagicMock()
    client._writer = writer

    operation = asyncio.create_task(client.write_devices("D0", [1], bit_unit=False))
    await drain_started.wait()
    operation.cancel()
    with pytest.raises(SlmpOutcomeUnknownError) as raised:
        await operation

    assert raised.value.reason is SlmpOutcomeUnknownReason.CANCELLED
    assert isinstance(raised.value.cause, asyncio.CancelledError)
    writer.write.assert_called_once()


@pytest.mark.asyncio
async def test_async_close_after_state_change_send_reports_closed_outcome_unknown() -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    drain_started = asyncio.Event()
    release_drain = asyncio.Event()

    async def drain() -> None:
        drain_started.set()
        await release_drain.wait()

    writer = MagicMock()
    writer.drain = AsyncMock(side_effect=drain)
    writer.wait_closed = AsyncMock()
    client._reader = MagicMock()
    client._writer = writer

    operation = asyncio.create_task(client.write_devices("D0", [1], bit_unit=False))
    await drain_started.wait()
    await client.close()
    release_drain.set()
    with pytest.raises(SlmpOutcomeUnknownError) as raised:
        await operation

    assert raised.value.reason is SlmpOutcomeUnknownReason.CLOSED
    assert isinstance(raised.value.cause, SlmpClosedError)


class _AggregateClient(SlmpClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            1025,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
        )
        self.calls: list[str] = []
        self.first_chunk = threading.Event()

    def read_random(self, *, word_devices=(), dword_devices=()):  # type: ignore[no-untyped-def]
        assert not dword_devices
        self.calls.append("chunk")
        if len(self.calls) == 1:
            self.first_chunk.set()
            time.sleep(0.02)
        return RandomReadResult(word={str(device): device.number for device in word_devices}, dword={})


def test_named_read_uses_one_exclusive_turn_and_preserves_order() -> None:
    client = _AggregateClient()

    def competing_operation() -> None:
        assert client.first_chunk.wait(timeout=1)
        with client._operation_queue.turn():  # noqa: SLF001 - verifies helper/client ownership
            client.calls.append("external")

    competitor = threading.Thread(target=competing_operation)
    competitor.start()
    addresses = [f"D{index}:U" for index in range(3)]
    result = read_named_sync(client, addresses)
    competitor.join(timeout=1)

    assert not competitor.is_alive()
    assert client.calls == ["chunk", "external"]
    assert list(result) == addresses
    assert result["D2:U"] == 2


class _SyncRmwClient(SlmpClient):
    def __init__(self, plc_profile: str = "melsec:iq-r") -> None:
        super().__init__(
            "127.0.0.1",
            1025,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile=plc_profile,
        )
        self.calls: list[int] = []
        self.subcommands: list[int] = []
        self.payloads: list[bytes] = []
        self.deadlines: list[float | None] = []
        self.read_started = threading.Event()

    def _request_unlocked(self, command, subcommand, data, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        self.calls.append(int(command))
        self.subcommands.append(int(subcommand))
        self.payloads.append(bytes(data))
        self.deadlines.append(self._active_deadline)
        if int(command) == int(Command.DEVICE_READ):
            self.read_started.set()
            time.sleep(0.02)
            response_data = b"\x08\x00"
        else:
            response_data = b""
        return SlmpResponse(serial=0, target=self.default_target, end_code=0, data=response_data, raw=b"")


def test_sync_bit_in_word_rmw_preflights_and_holds_one_fifo_turn() -> None:
    client = _SyncRmwClient()
    with pytest.raises(ValueError, match="only valid for word devices"):
        write_bit_in_word_sync(client, "M0", 0, True)
    assert client.calls == []

    competitor = threading.Thread(
        target=lambda: client.raw_command(Command.SELF_TEST, subcommand=0, payload=b""),
    )

    def start_competitor() -> None:
        assert client.read_started.wait(timeout=1)
        competitor.start()

    starter = threading.Thread(target=start_competitor)
    starter.start()
    write_bit_in_word_sync(client, "D0", 3, True)
    starter.join(timeout=1)
    competitor.join(timeout=1)

    assert not starter.is_alive()
    assert not competitor.is_alive()
    assert client.calls == [int(Command.DEVICE_READ), int(Command.DEVICE_WRITE), int(Command.SELF_TEST)]
    assert client.deadlines[0] is not None
    assert client.deadlines[0] == client.deadlines[1]
    assert client.deadlines[2] is None
    assert client._active_deadline is None


@pytest.mark.parametrize(
    ("address", "profile"),
    [(r"U2\G100", "melsec:qnudv"), (r"J1\W0", "melsec:iq-f")],
)
def test_sync_bit_in_word_blocked_qualified_route_sends_nothing(address: str, profile: str) -> None:
    client = _SyncRmwClient(profile)

    with pytest.raises(SlmpProfileFeatureError):
        write_bit_in_word_sync(client, address, 3, True)

    assert client.calls == []
    assert client._active_deadline is None


@pytest.mark.parametrize(
    ("address", "expected_subcommand"),
    [(r"U1\G0", 0x0082), (r"J2\SW10", 0x0080)],
)
def test_sync_bit_in_word_preserves_each_qualified_route(address: str, expected_subcommand: int) -> None:
    invalid_client = _SyncRmwClient()
    with pytest.raises(ValueError, match="bit_index must be 0-15"):
        write_bit_in_word_sync(invalid_client, address, 16, True)
    assert invalid_client.calls == []

    client = _SyncRmwClient()

    write_bit_in_word_sync(client, address, 3, True)

    assert client.calls == [int(Command.DEVICE_READ), int(Command.DEVICE_WRITE)]
    assert client.subcommands == [expected_subcommand, expected_subcommand]
    assert client.payloads[1][:-2] == client.payloads[0]
    assert client.payloads[1][-2:] == b"\x08\x00"
    assert client.deadlines[0] is not None
    assert client.deadlines[0] == client.deadlines[1]


class _AsyncRmwClient(AsyncSlmpClient):
    def __init__(self, plc_profile: str = "melsec:iq-r") -> None:
        super().__init__(
            "127.0.0.1",
            1025,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile=plc_profile,
        )
        self.calls: list[int] = []
        self.subcommands: list[int] = []
        self.payloads: list[bytes] = []
        self.deadlines: list[float | None] = []
        self.read_started = asyncio.Event()
        self.release_read = asyncio.Event()

    async def _request_unlocked(self, command, subcommand, data, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        self.calls.append(int(command))
        self.subcommands.append(int(subcommand))
        self.payloads.append(bytes(data))
        self.deadlines.append(self._active_deadline)
        if int(command) == int(Command.DEVICE_READ):
            self.read_started.set()
            await self.release_read.wait()
            response_data = b"\x08\x00"
        else:
            response_data = b""
        return SlmpResponse(serial=0, target=self.default_target, end_code=0, data=response_data, raw=b"")


@pytest.mark.asyncio
async def test_async_bit_in_word_rmw_holds_one_fifo_turn() -> None:
    client = _AsyncRmwClient()
    rmw = asyncio.create_task(write_bit_in_word(client, "D0", 3, True))
    await client.read_started.wait()
    competitor = asyncio.create_task(client.raw_command(Command.SELF_TEST, subcommand=0, payload=b""))
    await asyncio.sleep(0)
    client.release_read.set()
    await asyncio.gather(rmw, competitor)

    assert client.calls == [int(Command.DEVICE_READ), int(Command.DEVICE_WRITE), int(Command.SELF_TEST)]
    assert client.deadlines[0] is not None
    assert client.deadlines[0] == client.deadlines[1]
    assert client.deadlines[2] is None
    assert client._active_deadline is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("address", "profile"),
    [(r"U2\G100", "melsec:qnudv"), (r"J1\W0", "melsec:iq-f")],
)
async def test_async_bit_in_word_blocked_qualified_route_sends_nothing(address: str, profile: str) -> None:
    client = _AsyncRmwClient(profile)

    with pytest.raises(SlmpProfileFeatureError):
        await write_bit_in_word(client, address, 3, True)

    assert client.calls == []
    assert client._active_deadline is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("address", "expected_subcommand"),
    [(r"U1\G0", 0x0082), (r"J2\SW10", 0x0080)],
)
async def test_async_bit_in_word_preserves_each_qualified_route(address: str, expected_subcommand: int) -> None:
    invalid_client = _AsyncRmwClient()
    invalid_client.release_read.set()
    with pytest.raises(ValueError, match="bit_index must be 0-15"):
        await write_bit_in_word(invalid_client, address, 16, True)
    assert invalid_client.calls == []

    client = _AsyncRmwClient()
    client.release_read.set()

    await write_bit_in_word(client, address, 3, True)

    assert client.calls == [int(Command.DEVICE_READ), int(Command.DEVICE_WRITE)]
    assert client.subcommands == [expected_subcommand, expected_subcommand]
    assert client.payloads[1][:-2] == client.payloads[0]
    assert client.payloads[1][-2:] == b"\x08\x00"
    assert client.deadlines[0] is not None
    assert client.deadlines[0] == client.deadlines[1]


@pytest.mark.asyncio
async def test_async_bit_in_word_cancellation_before_write_clears_compound_deadline() -> None:
    client = _AsyncRmwClient()
    rmw = asyncio.create_task(write_bit_in_word(client, "D0", 3, True))
    await client.read_started.wait()

    rmw.cancel()
    with pytest.raises(asyncio.CancelledError):
        await rmw

    assert client.calls == [int(Command.DEVICE_READ)]
    assert client._active_deadline is None
