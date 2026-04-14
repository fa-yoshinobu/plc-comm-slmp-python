"""Tests for CPU operation state helpers."""

from __future__ import annotations

import unittest

from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.core import CpuOperationStatus


class _FakeSyncClient(SlmpClient):
    def __init__(self) -> None:
        super().__init__("127.0.0.1")
        self.calls: list[tuple[str, int, bool]] = []
        self.next_words: list[int] = [0]

    def read_devices(self, device, points, *, bit_unit=False, series=None):  # type: ignore[override]
        del series
        self.calls.append((str(device), int(points), bool(bit_unit)))
        return list(self.next_words)


class _FakeAsyncClient(AsyncSlmpClient):
    def __init__(self) -> None:
        super().__init__("127.0.0.1")
        self.calls: list[tuple[str, int, bool]] = []
        self.next_words: list[int] = [0]

    async def read_devices(self, device, points, *, bit_unit=False, series=None):  # type: ignore[override]
        del series
        self.calls.append((str(device), int(points), bool(bit_unit)))
        return list(self.next_words)


class TestSyncCpuOperationState(unittest.TestCase):
    def test_masks_upper_bits_of_sd203(self) -> None:
        client = _FakeSyncClient()
        client.next_words = [0x00A2]

        state = client.read_cpu_operation_state()

        self.assertEqual(client.calls, [("SD203", 1, False)])
        self.assertEqual(state.status, CpuOperationStatus.Stop)
        self.assertEqual(state.raw_status_word, 0x00A2)
        self.assertEqual(state.raw_code, 0x02)


class TestAsyncCpuOperationState(unittest.IsolatedAsyncioTestCase):
    async def test_returns_unknown_for_unhandled_code(self) -> None:
        client = _FakeAsyncClient()
        client.next_words = [0x00F5]

        state = await client.read_cpu_operation_state()

        self.assertEqual(client.calls, [("SD203", 1, False)])
        self.assertEqual(state.status, CpuOperationStatus.Unknown)
        self.assertEqual(state.raw_status_word, 0x00F5)
        self.assertEqual(state.raw_code, 0x05)
