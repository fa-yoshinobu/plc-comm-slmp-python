"""Cross-cutting operation queue, aggregate, and error-contract tests."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from slmp._operation_queue import _AsyncFifoOperationQueue, _SyncFifoOperationQueue
from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.client import _classify_exchange_failure as classify_sync_failure
from slmp.constants import Command
from slmp.core import RandomReadResult, SlmpResponse, SlmpTarget
from slmp.errors import (
    SlmpClosedError,
    SlmpNotConnectedError,
    SlmpOutcomeUnknownError,
    SlmpOutcomeUnknownReason,
    SlmpTimeoutError,
    SlmpTransportError,
)
from slmp.utils import read_named_sync, write_bit_in_word, write_bit_in_word_sync


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


def test_named_read_chunks_hold_one_exclusive_turn_and_preserve_order() -> None:
    client = _AggregateClient()

    def competing_operation() -> None:
        assert client.first_chunk.wait(timeout=1)
        with client._operation_queue.turn():  # noqa: SLF001 - verifies helper/client ownership
            client.calls.append("external")

    competitor = threading.Thread(target=competing_operation)
    competitor.start()
    addresses = [f"D{index}:U" for index in range(97)]
    result = read_named_sync(client, addresses)
    competitor.join(timeout=1)

    assert not competitor.is_alive()
    assert client.calls == ["chunk", "chunk", "external"]
    assert list(result) == addresses
    assert result["D96:U"] == 96


class _SyncRmwClient(SlmpClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            1025,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
        )
        self.calls: list[int] = []
        self.read_started = threading.Event()

    def _request_unlocked(self, command, subcommand, data, **kwargs):  # type: ignore[no-untyped-def]
        del subcommand, data, kwargs
        self.calls.append(int(command))
        if int(command) == int(Command.DEVICE_READ):
            self.read_started.set()
            time.sleep(0.02)
            response_data = b"\x00\x00"
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


class _AsyncRmwClient(AsyncSlmpClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            1025,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
        )
        self.calls: list[int] = []
        self.read_started = asyncio.Event()
        self.release_read = asyncio.Event()

    async def _request_unlocked(self, command, subcommand, data, **kwargs):  # type: ignore[no-untyped-def]
        del subcommand, data, kwargs
        self.calls.append(int(command))
        if int(command) == int(Command.DEVICE_READ):
            self.read_started.set()
            await self.release_read.wait()
            response_data = b"\x00\x00"
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
