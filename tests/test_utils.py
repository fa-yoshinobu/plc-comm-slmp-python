"""Unit tests for slmp.utils sync and async utility functions."""

import struct
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from slmp.core import DeviceRef, LongTimerResult, RandomReadResult
from slmp.utils import (
    QueuedAsyncSlmpClient,
    SlmpConnectionOptions,
    _compile_read_plan,
    _parse_address,
    normalize_address,
    open_and_connect,
    poll_sync,
    read_bits_sync,
    read_dwords_chunked_sync,
    read_dwords_single_request_sync,
    read_dwords_sync,
    read_named_sync,
    read_typed_sync,
    read_words_chunked_sync,
    read_words_single_request_sync,
    read_words_sync,
    write_bit_in_word_sync,
    write_bits_sync,
    write_dwords_chunked_sync,
    write_dwords_single_request_sync,
    write_named,
    write_named_sync,
    write_typed_sync,
    write_words_chunked_sync,
    write_words_single_request_sync,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sync_client(*word_sequences: list[int]) -> MagicMock:
    """Return a mock SlmpClient whose read_devices returns each sequence in turn."""
    client = MagicMock()
    client.read_devices.side_effect = list(word_sequences)
    return client


def _make_async_client(*word_sequences: list[int]) -> MagicMock:
    """Return a mock AsyncSlmpClient whose read_devices coroutine returns sequences."""
    client = MagicMock()

    async def _read(*args, **kwargs):
        return client.read_devices.side_effect.pop(0)

    client.read_devices = MagicMock(side_effect=list(word_sequences))

    # Override to be an actual coroutine
    async def _coro_read(*a, **kw):
        return client._word_iter.__next__()

    client._word_iter = iter(word_sequences)
    client.read_devices = lambda *a, **kw: _make_coro(next(client._word_iter))
    return client


def _make_coro(value):
    async def _inner():
        return value

    return _inner()


# ---------------------------------------------------------------------------
# _parse_address
# ---------------------------------------------------------------------------


class TestParseAddress(unittest.TestCase):
    def test_plain_device(self):
        self.assertEqual(_parse_address("D100"), ("D100", "U", None))

    def test_dtype_suffix(self):
        self.assertEqual(_parse_address("D100:F"), ("D100", "F", None))
        self.assertEqual(_parse_address("D100:s"), ("D100", "S", None))

    def test_bit_in_word(self):
        base, dtype, idx = _parse_address("D0.3")
        self.assertEqual(base, "D0")
        self.assertEqual(dtype, "BIT_IN_WORD")
        self.assertEqual(idx, 3)

    def test_bit_in_word_hex(self):
        _, _, idx = _parse_address("D0.A")
        self.assertEqual(idx, 10)

    def test_normalize_address(self):
        self.assertEqual(normalize_address("d100"), "D100")


# ---------------------------------------------------------------------------
# read_typed_sync
# ---------------------------------------------------------------------------


class TestReadTypedSync(unittest.TestCase):
    def test_unsigned_16(self):
        client = _make_sync_client([0x0042])
        self.assertEqual(read_typed_sync(client, "D100", "U"), 0x0042)

    def test_signed_16_negative(self):
        raw = struct.pack("<h", -1)[0:2]
        word = struct.unpack("<H", raw)[0]
        client = _make_sync_client([word])
        self.assertEqual(read_typed_sync(client, "D100", "S"), -1)

    def test_float32(self):
        raw = struct.pack("<f", 3.14)
        lo, hi = struct.unpack("<HH", raw)
        client = _make_sync_client([lo, hi])
        result = read_typed_sync(client, "D100", "F")
        self.assertAlmostEqual(result, 3.14, places=5)

    def test_unsigned_32(self):
        raw = struct.pack("<I", 100000)
        lo, hi = struct.unpack("<HH", raw)
        client = _make_sync_client([lo, hi])
        self.assertEqual(read_typed_sync(client, "D100", "D"), 100000)

    def test_signed_32_negative(self):
        raw = struct.pack("<i", -50000)
        lo, hi = struct.unpack("<HH", raw)
        client = _make_sync_client([lo, hi])
        self.assertEqual(read_typed_sync(client, "D100", "L"), -50000)

    def test_bit_device(self):
        client = MagicMock()
        client.read_devices.return_value = [True]
        self.assertTrue(read_typed_sync(client, "M100", "BIT"))
        client.read_devices.assert_called_once_with(DeviceRef("M", 100), 1, bit_unit=True)

    def test_long_families_use_helper_backed_reads(self):
        client = MagicMock()
        client.read_long_timer.return_value = [
            LongTimerResult(10, "LTN10", 0x00010002, True, False, 0x0002, [2, 1, 2, 0])
        ]
        client.read_long_retentive_timer.return_value = [
            LongTimerResult(20, "LSTN20", 7, False, True, 0x0001, [7, 0, 1, 0])
        ]
        client.read_devices.return_value = [0x0008, 0x0000, 0x0003, 0x0000]

        self.assertEqual(read_typed_sync(client, "LTN10", "D"), 0x00010002)
        self.assertTrue(read_typed_sync(client, "LTS10", "BIT"))
        self.assertFalse(read_typed_sync(client, "LTC10", "BIT"))
        self.assertEqual(read_typed_sync(client, "LSTN20", "D"), 7)
        self.assertTrue(read_typed_sync(client, "LSTC20", "BIT"))
        self.assertEqual(read_typed_sync(client, "LCN30", "D"), 8)
        self.assertTrue(read_typed_sync(client, "LCS30", "BIT"))
        self.assertTrue(read_typed_sync(client, "LCC30", "BIT"))

        client.read_long_timer.assert_called()
        client.read_long_retentive_timer.assert_called()
        client.read_devices.assert_called_with(DeviceRef("LCN", 30), 4, bit_unit=False)


# ---------------------------------------------------------------------------
# write_typed_sync
# ---------------------------------------------------------------------------


class TestWriteTypedSync(unittest.TestCase):
    def test_write_uint16(self):
        client = MagicMock()
        write_typed_sync(client, "D100", "U", 42)
        client.write_devices.assert_called_once_with("D100", [42], bit_unit=False)

    def test_write_float32(self):
        client = MagicMock()
        write_typed_sync(client, "D100", "F", 1.0)
        raw = struct.pack("<f", 1.0)
        expected = list(struct.unpack("<HH", raw))
        client.write_devices.assert_called_once_with("D100", expected, bit_unit=False)

    def test_write_signed_32(self):
        client = MagicMock()
        write_typed_sync(client, "D100", "L", -1)
        raw = struct.pack("<i", -1)
        expected = list(struct.unpack("<HH", raw))
        client.write_devices.assert_called_once_with("D100", expected, bit_unit=False)

    def test_write_bit(self):
        client = MagicMock()
        write_typed_sync(client, "M100", "BIT", True)
        client.write_devices.assert_called_once_with("M100", [True], bit_unit=True)


# ---------------------------------------------------------------------------
# write_bit_in_word_sync
# ---------------------------------------------------------------------------


class TestWriteBitInWordSync(unittest.TestCase):
    def test_set_bit(self):
        client = _make_sync_client([0x0000])
        write_bit_in_word_sync(client, "D0", 3, True)
        client.write_devices.assert_called_once_with("D0", [0x0008], bit_unit=False)

    def test_clear_bit(self):
        client = _make_sync_client([0x00FF])
        write_bit_in_word_sync(client, "D0", 0, False)
        client.write_devices.assert_called_once_with("D0", [0x00FE], bit_unit=False)

    def test_invalid_bit_index(self):
        client = MagicMock()
        with self.assertRaises(ValueError):
            write_bit_in_word_sync(client, "D0", 16, True)


# ---------------------------------------------------------------------------
# read_named_sync
# ---------------------------------------------------------------------------


class TestReadNamedSync(unittest.TestCase):
    def test_mixed_dtypes(self):
        raw_f = struct.pack("<f", 2.5)
        dword = struct.unpack("<I", raw_f)[0]
        client = MagicMock()
        client.read_random.return_value = RandomReadResult(
            word={"D100": 10, "D0": 0x00FF},
            dword={"D101": dword},
        )
        result = read_named_sync(client, ["D100", "D101:F", "D0.3"])
        self.assertEqual(result["D100"], 10)
        self.assertAlmostEqual(result["D101:F"], 2.5, places=5)
        self.assertEqual(result["D0.3"], bool((0x00FF >> 3) & 1))
        client.read_random.assert_called_once_with(
            word_devices=[DeviceRef("D", 100), DeviceRef("D", 0)],
            dword_devices=[DeviceRef("D", 101)],
        )

    def test_bit_in_word_false(self):
        client = MagicMock()
        client.read_random.return_value = RandomReadResult(word={"D0": 0x0000}, dword={})
        result = read_named_sync(client, ["D0.0"])
        self.assertFalse(result["D0.0"])

    def test_bit_device_falls_back_to_single_read(self):
        client = MagicMock()
        client.read_devices.return_value = [True]
        result = read_named_sync(client, ["M100"])
        self.assertTrue(result["M100"])
        client.read_random.assert_not_called()
        client.read_devices.assert_called_once_with(DeviceRef("M", 100), 1, bit_unit=True)

    def test_bit_device_bit_suffix_raises(self):
        client = MagicMock()
        with self.assertRaisesRegex(ValueError, "only valid for word devices"):
            read_named_sync(client, ["M100.0"])

    def test_long_timer_family_uses_helper_backed_reads(self):
        client = MagicMock()
        client.read_long_timer.side_effect = [
            [LongTimerResult(10, "LTN10", 0x00010002, True, False, 0x0002, [2, 1, 2, 0])],
        ]
        client.read_long_retentive_timer.side_effect = [
            [LongTimerResult(20, "LSTN20", 7, False, True, 0x0001, [7, 0, 1, 0])],
        ]
        client.read_devices.side_effect = [
            [0x0008, 0x0000, 0x0003, 0x0000],
        ]

        result = read_named_sync(
            client,
            ["LTN10", "LTS10", "LTC10", "LSTN20", "LSTS20", "LSTC20", "LCN30", "LCS30", "LCC30"],
        )

        self.assertEqual(result["LTN10"], 0x00010002)
        self.assertTrue(result["LTS10"])
        self.assertFalse(result["LTC10"])
        self.assertEqual(result["LSTN20"], 7)
        self.assertFalse(result["LSTS20"])
        self.assertTrue(result["LSTC20"])
        self.assertEqual(result["LCN30"], 8)
        self.assertTrue(result["LCS30"])
        self.assertTrue(result["LCC30"])
        client.read_random.assert_not_called()
        client.read_long_timer.assert_called_once_with(head_no=10, points=1)
        client.read_long_retentive_timer.assert_called_once_with(head_no=20, points=1)
        client.read_devices.assert_called_once_with(DeviceRef("LCN", 30), 4, bit_unit=False)


# ---------------------------------------------------------------------------
# write_named_sync
# ---------------------------------------------------------------------------


class TestWriteNamedSync(unittest.TestCase):
    def test_write_multiple(self):
        client = MagicMock()
        write_named_sync(client, {"D100": 1, "D200": 2})
        self.assertEqual(client.write_devices.call_count, 2)

    def test_write_float(self):
        client = MagicMock()
        write_named_sync(client, {"D100:F": 1.0})
        raw = struct.pack("<f", 1.0)
        expected = list(struct.unpack("<HH", raw))
        client.write_devices.assert_called_once_with("D100", expected, bit_unit=False)

    def test_write_bit_in_word(self):
        client = _make_sync_client([0x0000])
        write_named_sync(client, {"D0.2": True})
        client.write_devices.assert_called_once_with("D0", [0x0004], bit_unit=False)

    def test_write_direct_bit_device(self):
        client = MagicMock()
        write_named_sync(client, {"M100": True})
        client.write_devices.assert_called_once_with("M100", [True], bit_unit=True)

    def test_write_bit_device_bit_suffix_raises(self):
        client = MagicMock()
        with self.assertRaisesRegex(ValueError, "only valid for word devices"):
            write_named_sync(client, {"M100.0": True})

    def test_write_named_defaults_long_current_values_to_dword(self):
        client = MagicMock()
        write_named_sync(client, {"LTN10": 1, "LSTN20": 2, "LCN30": 3})

        self.assertEqual(
            client.write_random_words.call_args_list,
            [
                unittest.mock.call(dword_values={DeviceRef("LTN", 10): 1}, series=client.plc_series),
                unittest.mock.call(dword_values={DeviceRef("LSTN", 20): 2}, series=client.plc_series),
                unittest.mock.call(dword_values={DeviceRef("LCN", 30): 3}, series=client.plc_series),
            ],
        )

    def test_write_named_routes_long_timer_state_writes_to_native_paths(self):
        client = MagicMock()
        write_named_sync(
            client,
            {
                "LTC10": True,
                "LTS10": False,
                "LSTC20": True,
                "LSTS20": False,
                "LCC30": True,
                "LCS30": False,
            },
        )

        self.assertEqual(
            client.write_random_bits.call_args_list,
            [
                unittest.mock.call({DeviceRef("LTC", 10): True}, series=client.plc_series),
                unittest.mock.call({DeviceRef("LTS", 10): False}, series=client.plc_series),
                unittest.mock.call({DeviceRef("LSTC", 20): True}, series=client.plc_series),
                unittest.mock.call({DeviceRef("LSTS", 20): False}, series=client.plc_series),
                unittest.mock.call({DeviceRef("LCC", 30): True}, series=client.plc_series),
            ],
        )
        client.write_devices.assert_called_once_with(DeviceRef("LCS", 30), [0], bit_unit=False)


# ---------------------------------------------------------------------------
# read_words_sync / read_dwords_sync
# ---------------------------------------------------------------------------


class TestReadWordsSyncChunking(unittest.TestCase):
    def test_read_words_single_request_sync(self):
        client = _make_sync_client(list(range(4)))
        result = read_words_single_request_sync(client, "D0", 4)
        self.assertEqual(result, [0, 1, 2, 3])
        client.read_devices.assert_called_once_with(DeviceRef("D", 0), 4, bit_unit=False)

    def test_no_split_within_limit(self):
        client = _make_sync_client(list(range(10)))
        result = read_words_sync(client, "D0", 10)
        self.assertEqual(result, list(range(10)))

    def test_no_split_exceeds_limit_raises(self):
        client = MagicMock()
        with self.assertRaises(ValueError):
            read_words_sync(client, "D0", 100, max_per_request=10)

    def test_split_two_chunks(self):
        chunk1 = list(range(10))
        chunk2 = list(range(10, 14))
        client = _make_sync_client(chunk1, chunk2)
        result = read_words_sync(client, "D0", 14, max_per_request=10, allow_split=True)
        self.assertEqual(result, list(range(14)))
        self.assertEqual(client.read_devices.call_count, 2)

    def test_read_dwords_sync(self):
        raw = struct.pack("<I", 100000)
        lo, hi = struct.unpack("<HH", raw)
        client = _make_sync_client([lo, hi])
        result = read_dwords_sync(client, "D0", 1)
        self.assertEqual(result, [100000])

    def test_read_dwords_single_request_sync(self):
        raw = struct.pack("<II", 100000, 200000)
        words = list(struct.unpack("<HHHH", raw))
        client = _make_sync_client(words)
        result = read_dwords_single_request_sync(client, "D0", 2)
        self.assertEqual(result, [100000, 200000])

    def test_read_words_chunked_sync(self):
        chunk1 = list(range(8))
        chunk2 = list(range(8, 12))
        client = _make_sync_client(chunk1, chunk2)
        result = read_words_chunked_sync(client, "D0", 12, max_per_request=8)
        self.assertEqual(result, list(range(12)))
        self.assertEqual(client.read_devices.call_count, 2)

    def test_read_dwords_chunked_sync_preserves_dword_boundaries(self):
        raw1 = struct.pack("<II", 1, 2)
        raw2 = struct.pack("<II", 3, 4)
        client = _make_sync_client(list(struct.unpack("<HHHH", raw1)), list(struct.unpack("<HHHH", raw2)))
        result = read_dwords_chunked_sync(client, "D0", 4, max_dwords_per_request=2)
        self.assertEqual(result, [1, 2, 3, 4])


class TestWriteWordsSyncChunking(unittest.TestCase):
    def test_write_words_single_request_sync(self):
        client = MagicMock()
        write_words_single_request_sync(client, "D0", [1, 2, 3])
        client.write_devices.assert_called_once_with("D0", [1, 2, 3], bit_unit=False)

    def test_write_dwords_single_request_sync(self):
        client = MagicMock()
        write_dwords_single_request_sync(client, "D0", [1, 2])
        client.write_devices.assert_called_once_with("D0", [1, 0, 2, 0], bit_unit=False)

    def test_write_words_chunked_sync(self):
        client = MagicMock()
        write_words_chunked_sync(client, "D0", list(range(12)), max_per_request=8)
        self.assertEqual(
            client.write_devices.call_args_list,
            [
                unittest.mock.call(DeviceRef("D", 0), list(range(8)), bit_unit=False),
                unittest.mock.call(DeviceRef("D", 8), list(range(8, 12)), bit_unit=False),
            ],
        )

    def test_write_dwords_chunked_sync(self):
        client = MagicMock()
        write_dwords_chunked_sync(client, "D0", [1, 2, 3], max_dwords_per_request=2)
        self.assertEqual(
            client.write_devices.call_args_list,
            [
                unittest.mock.call(DeviceRef("D", 0), [1, 0, 2, 0], bit_unit=False),
                unittest.mock.call(DeviceRef("D", 4), [3, 0], bit_unit=False),
            ],
        )


class TestBitBlockHelpers(unittest.TestCase):
    def test_read_bits_sync(self):
        client = MagicMock()
        client.read_devices.return_value = [True, False, True]
        self.assertEqual(read_bits_sync(client, "M100", 3), [True, False, True])
        client.read_devices.assert_called_once_with("M100", 3, bit_unit=True)

    def test_write_bits_sync(self):
        client = MagicMock()
        write_bits_sync(client, "M100", [True, False, True])
        client.write_devices.assert_called_once_with("M100", [True, False, True], bit_unit=True)


# ---------------------------------------------------------------------------
# poll_sync
# ---------------------------------------------------------------------------


class TestPollSync(unittest.TestCase):
    def test_yields_snapshots(self):
        client = MagicMock()
        client.read_random.side_effect = [
            RandomReadResult(word={"D0": 1}, dword={}),
            RandomReadResult(word={"D0": 2}, dword={}),
            RandomReadResult(word={"D0": 3}, dword={}),
        ]
        gen = poll_sync(client, ["D0"], interval=0)
        snap1 = next(gen)
        snap2 = next(gen)
        snap3 = next(gen)
        self.assertEqual(snap1["D0"], 1)
        self.assertEqual(snap2["D0"], 2)
        self.assertEqual(snap3["D0"], 3)


class TestReadPlan(unittest.TestCase):
    def test_compile_read_plan_batches_word_and_dword_addresses(self):
        plan = _compile_read_plan(["D100", "D100.3", "D101:F", "M10"])
        self.assertEqual(plan.word_devices, (DeviceRef("D", 100),))
        self.assertEqual(plan.dword_devices, (DeviceRef("D", 101),))
        self.assertEqual([entry.batch_kind for entry in plan.entries], ["WORD", "WORD", "DWORD", None])

    def test_compile_read_plan_marks_long_timer_helper_reads_and_long_currents(self):
        plan = _compile_read_plan(["LTN10", "LTS10", "LTC10", "LSTN20", "LCN30", "LCS30", "LCC30"])

        self.assertEqual(plan.word_devices, ())
        self.assertEqual(plan.dword_devices, ())
        self.assertEqual(
            [(entry.address, entry.dtype, entry.batch_kind) for entry in plan.entries],
            [
                ("LTN10", "D", "LONG_TIMER"),
                ("LTS10", "BIT", "LONG_TIMER"),
                ("LTC10", "BIT", "LONG_TIMER"),
                ("LSTN20", "D", "LONG_TIMER"),
                ("LCN30", "D", "LONG_TIMER"),
                ("LCS30", "BIT", "LONG_TIMER"),
                ("LCC30", "BIT", "LONG_TIMER"),
            ],
        )


class TestQueuedAsyncSlmpClient(unittest.IsolatedAsyncioTestCase):
    async def test_context_manager_connects_and_closes_inner_client(self):
        inner = MagicMock()
        inner.connect = AsyncMock()
        inner.close = AsyncMock()
        queued = QueuedAsyncSlmpClient(inner)

        entered = await queued.__aenter__()
        await queued.__aexit__(None, None, None)

        self.assertIs(entered, queued)
        inner.connect.assert_awaited_once()
        inner.close.assert_awaited_once()

    async def test_open_and_connect_returns_queued_client(self):
        options = SlmpConnectionOptions("127.0.0.1", port=1025)
        with patch("slmp.async_client.AsyncSlmpClient") as client_cls:
            inner = MagicMock()
            inner.connect = AsyncMock()
            client_cls.return_value = inner

            queued = await open_and_connect(options)

        self.assertIsInstance(queued, QueuedAsyncSlmpClient)
        inner.connect.assert_awaited_once()


# ---------------------------------------------------------------------------
# write_named (async)
# ---------------------------------------------------------------------------


class TestWriteNamedAsync(unittest.IsolatedAsyncioTestCase):
    async def test_write_multiple(self):
        client = MagicMock()

        async def _write(*a, **kw):
            pass

        client.write_devices = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        await write_named(client, {"D100": 1, "D200": 2})
        self.assertEqual(client.write_devices.call_count, 2)

    async def test_write_named_defaults_long_current_values_to_dword(self):
        client = MagicMock()
        client.write_devices = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_words = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_bits = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))

        await write_named(client, {"LTN10": 1, "LSTN20": 2, "LCN30": 3})

        self.assertEqual(
            client.write_random_words.call_args_list,
            [
                unittest.mock.call(dword_values={DeviceRef("LTN", 10): 1}, series=client.plc_series),
                unittest.mock.call(dword_values={DeviceRef("LSTN", 20): 2}, series=client.plc_series),
                unittest.mock.call(dword_values={DeviceRef("LCN", 30): 3}, series=client.plc_series),
            ],
        )

    async def test_write_named_routes_long_timer_state_writes_to_native_paths(self):
        client = MagicMock()
        client.write_devices = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_words = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_bits = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))

        await write_named(
            client,
            {"LTC10": True, "LTS10": False, "LSTC20": True, "LSTS20": False, "LCC30": True, "LCS30": False},
        )

        self.assertEqual(
            client.write_random_bits.call_args_list,
            [
                unittest.mock.call({DeviceRef("LTC", 10): True}, series=client.plc_series),
                unittest.mock.call({DeviceRef("LTS", 10): False}, series=client.plc_series),
                unittest.mock.call({DeviceRef("LSTC", 20): True}, series=client.plc_series),
                unittest.mock.call({DeviceRef("LSTS", 20): False}, series=client.plc_series),
                unittest.mock.call({DeviceRef("LCC", 30): True}, series=client.plc_series),
            ],
        )
        client.write_devices.assert_called_once_with(DeviceRef("LCS", 30), [0], bit_unit=False)


if __name__ == "__main__":
    unittest.main()
