"""Unit tests for slmp.utils — sync and async utility functions."""

import struct
import unittest
from unittest.mock import MagicMock

from slmp.utils import (
    _parse_address,
    poll_sync,
    read_dwords_sync,
    read_named_sync,
    read_typed_sync,
    read_words_sync,
    write_bit_in_word_sync,
    write_named,
    write_named_sync,
    write_typed_sync,
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
        lo, hi = struct.unpack("<HH", raw_f)
        client = _make_sync_client([10], [lo, hi], [0x00FF])
        result = read_named_sync(client, ["D100", "D101:F", "D0.3"])
        self.assertEqual(result["D100"], 10)
        self.assertAlmostEqual(result["D101:F"], 2.5, places=5)
        self.assertEqual(result["D0.3"], bool((0x00FF >> 3) & 1))

    def test_bit_in_word_false(self):
        client = _make_sync_client([0x0000])
        result = read_named_sync(client, ["D0.0"])
        self.assertFalse(result["D0.0"])


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


# ---------------------------------------------------------------------------
# read_words_sync / read_dwords_sync
# ---------------------------------------------------------------------------


class TestReadWordsSyncChunking(unittest.TestCase):
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


# ---------------------------------------------------------------------------
# poll_sync
# ---------------------------------------------------------------------------


class TestPollSync(unittest.TestCase):
    def test_yields_snapshots(self):
        client = _make_sync_client([1], [2], [3])
        gen = poll_sync(client, ["D0"], interval=0)
        snap1 = next(gen)
        snap2 = next(gen)
        snap3 = next(gen)
        self.assertEqual(snap1["D0"], 1)
        self.assertEqual(snap2["D0"], 2)
        self.assertEqual(snap3["D0"], 3)


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


if __name__ == "__main__":
    unittest.main()
