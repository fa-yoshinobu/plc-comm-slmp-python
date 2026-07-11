"""Unit tests for slmp.utils sync and async utility functions."""

import struct
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from slmp.core import DeviceRef, LongTimerResult, RandomReadResult, SlmpTarget
from slmp.utils import (
    QueuedAsyncSlmpClient,
    SlmpConnectionOptions,
    _compile_read_plan,
    _parse_address,
    format_address,
    normalize_address,
    open_and_connect,
    parse_address,
    poll_sync,
    read_bits_sync,
    read_dwords_single_request_sync,
    read_dwords_sync,
    read_named,
    read_named_sync,
    read_typed_sync,
    read_words_single_request_sync,
    read_words_sync,
    try_parse_address,
    write_bit_in_word_sync,
    write_bits_sync,
    write_dwords_single_request_sync,
    write_named,
    write_named_sync,
    write_typed_sync,
    write_words_single_request_sync,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_TARGET = SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0)


def _make_sync_client(*word_sequences: list[int]) -> MagicMock:
    """Return a mock SlmpClient whose read_devices returns each sequence in turn."""
    client = MagicMock()
    client.plc_profile = "melsec:iq-r"
    client.read_devices.side_effect = list(word_sequences)
    return client


def _make_async_client(*word_sequences: list[int]) -> MagicMock:
    """Return a mock AsyncSlmpClient whose read_devices coroutine returns sequences."""
    client = MagicMock()
    client.plc_profile = "melsec:iq-r"

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
        with self.assertRaisesRegex(ValueError, "requires an explicit dtype"):
            _parse_address("D100")
        self.assertIsNone(try_parse_address("D100", plc_profile="melsec:iq-r"))

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
        _, _, idx = _parse_address("D0.D")
        self.assertEqual(idx, 13)

    def test_invalid_bit_in_word_suffix(self):
        with self.assertRaises(ValueError):
            _parse_address("D0.10")
        self.assertIsNone(try_parse_address("D0.10", plc_profile="melsec:iq-r"))

    def test_bit_in_word_dtype_requires_explicit_bit_index(self):
        with self.assertRaisesRegex(ValueError, "BIT_IN_WORD requires"):
            _compile_read_plan(["D0:BIT_IN_WORD"], address_profile="melsec:iq-r")

    def test_normalize_address(self):
        self.assertEqual(normalize_address("d100:u", plc_profile="melsec:iq-r"), "D100:U")
        self.assertEqual(normalize_address("y220:bit", plc_profile="melsec:iq-f"), "Y220:BIT")
        self.assertEqual(normalize_address("y220:bit", plc_profile="melsec:iq-f"), "Y220:BIT")

    def test_public_parse_try_format_address(self):
        typed = parse_address("d200:f", plc_profile="melsec:iq-r")
        bit = parse_address("d50.a", plc_profile="melsec:iq-r")
        direct_bit = parse_address("m100:bit", plc_profile="melsec:iq-r")

        self.assertEqual(typed.text, "D200:F")
        self.assertEqual(typed.base_device, "D200")
        self.assertEqual(typed.dtype, "F")
        self.assertTrue(typed.explicit_dtype)
        self.assertEqual(format_address(typed, plc_profile="melsec:iq-r"), "D200:F")
        self.assertEqual(bit.text, "D50.A")
        self.assertEqual(bit.dtype, "BIT_IN_WORD")
        self.assertEqual(bit.bit_index, 10)
        self.assertEqual(format_address(bit, plc_profile="melsec:iq-r"), "D50.A")
        self.assertEqual(direct_bit.text, "M100:BIT")
        self.assertEqual(direct_bit.dtype, "BIT")
        self.assertEqual(format_address("d100:s", plc_profile="melsec:iq-r"), "D100:S")

    def test_public_parse_address_uses_plc_profile(self):
        parsed = parse_address("x100:bit", plc_profile="melsec:iq-f")

        self.assertEqual(parsed.text, "X100:BIT")
        self.assertEqual(parsed.base_device, "X100")
        self.assertEqual(parsed.dtype, "BIT")
        self.assertIsNone(try_parse_address("x100", plc_profile="melsec:iq-f"))
        self.assertIsNone(try_parse_address("m100.0", plc_profile="melsec:iq-r"))

    def test_public_parse_address_rejects_short_plc_profile(self):
        with self.assertRaisesRegex(ValueError, "Unsupported plc_profile"):
            parse_address("x100:bit", plc_profile="iq-f")

    def test_public_parse_address_rejects_noncanonical_profile_case(self):
        with self.assertRaisesRegex(ValueError, "Unsupported plc_profile"):
            parse_address("x100:bit", plc_profile="MELSEC:IQ-F")

    def test_read_named_sync_rejects_xy_without_address_profile(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.plc_profile = None
        with self.assertRaisesRegex(ValueError, "plc_profile"):
            read_named_sync(client, ["X40:BIT"])


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
        client.plc_profile = "melsec:iq-r"
        client.read_devices.return_value = [True]
        self.assertTrue(read_typed_sync(client, "M100", "BIT"))
        client.read_devices.assert_called_once_with(DeviceRef("M", 100, "melsec:iq-r"), 1, bit_unit=True)

    def test_long_families_use_helper_backed_reads(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_long_timer.return_value = [
            LongTimerResult(10, "LTN10", 0x00010002, True, False, 0x0002, [2, 1, 2, 0])
        ]
        client.read_long_retentive_timer.return_value = [
            LongTimerResult(20, "LSTN20", 7, False, True, 0x0001, [7, 0, 1, 0])
        ]
        client.read_random.return_value = RandomReadResult(word={}, dword={"LCN30": 8})
        client.read_devices.side_effect = [
            [True],
            [True],
        ]

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
        client.read_random.assert_called_once_with(dword_devices=[DeviceRef("LCN", 30, "melsec:iq-r")])
        self.assertEqual(
            client.read_devices.call_args_list,
            [
                unittest.mock.call(DeviceRef("LCS", 30, "melsec:iq-r"), 1, bit_unit=True),
                unittest.mock.call(DeviceRef("LCC", 30, "melsec:iq-r"), 1, bit_unit=True),
            ],
        )


# ---------------------------------------------------------------------------
# write_typed_sync
# ---------------------------------------------------------------------------


class TestWriteTypedSync(unittest.TestCase):
    def test_write_uint16(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_typed_sync(client, "D100", "U", 42)
        client.write_devices.assert_called_once_with("D100", [42], bit_unit=False)

    def test_write_float32(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_typed_sync(client, "D100", "F", 1.0)
        raw = struct.pack("<f", 1.0)
        expected = list(struct.unpack("<HH", raw))
        client.write_devices.assert_called_once_with("D100", expected, bit_unit=False)

    def test_write_signed_32(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_typed_sync(client, "D100", "L", -1)
        raw = struct.pack("<i", -1)
        expected = list(struct.unpack("<HH", raw))
        client.write_devices.assert_called_once_with("D100", expected, bit_unit=False)

    def test_write_bit(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
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
        client.plc_profile = "melsec:iq-r"
        with self.assertRaises(ValueError):
            write_bit_in_word_sync(client, "D0", 16, True)

    def test_write_named_requires_explicit_bit_index(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaisesRegex(ValueError, "BIT_IN_WORD requires"):
            write_named_sync(client, {"D0:BIT_IN_WORD": True})


# ---------------------------------------------------------------------------
# read_named_sync
# ---------------------------------------------------------------------------


class TestReadNamedSync(unittest.TestCase):
    def test_mixed_dtypes(self):
        raw_f = struct.pack("<f", 2.5)
        dword = struct.unpack("<I", raw_f)[0]
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_random.return_value = RandomReadResult(
            word={"D100": 10, "D0": 0x00FF},
            dword={"D101": dword},
        )
        result = read_named_sync(client, ["D100:U", "D101:F", "D0.3"])
        self.assertEqual(result["D100:U"], 10)
        self.assertAlmostEqual(result["D101:F"], 2.5, places=5)
        self.assertEqual(result["D0.3"], bool((0x00FF >> 3) & 1))
        client.read_random.assert_called_once_with(
            word_devices=[DeviceRef("D", 100, "melsec:iq-r"), DeviceRef("D", 0, "melsec:iq-r")],
            dword_devices=[DeviceRef("D", 101, "melsec:iq-r")],
        )

    def test_bit_in_word_false(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_random.return_value = RandomReadResult(word={"D0": 0x0000}, dword={})
        result = read_named_sync(client, ["D0.0"])
        self.assertFalse(result["D0.0"])

    def test_excluded_bit_device_falls_back_to_single_read(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_devices.return_value = [True]
        result = read_named_sync(client, ["TS100:BIT"])
        self.assertTrue(result["TS100:BIT"])
        client.read_random.assert_not_called()
        client.read_devices.assert_called_once_with(DeviceRef("TS", 100, "melsec:iq-r"), 1, bit_unit=True)

    def test_plain_bit_devices_batch_as_random_word_reads(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_random.return_value = RandomReadResult(
            word={"M96": 0x0010, "SM16": 0x0002, "SB10": 0x8000},
            dword={},
        )

        result = read_named_sync(client, ["M100:BIT", "SM17:BIT", "SB1F:BIT"])

        self.assertTrue(result["M100:BIT"])
        self.assertTrue(result["SM17:BIT"])
        self.assertTrue(result["SB1F:BIT"])
        client.read_random.assert_called_once_with(
            word_devices=[
                DeviceRef("M", 96, "melsec:iq-r"),
                DeviceRef("SM", 16, "melsec:iq-r"),
                DeviceRef("SB", 0x10, "melsec:iq-r"),
            ],
            dword_devices=[],
        )
        client.read_devices.assert_not_called()

    def test_more_than_255_word_devices_is_rejected_without_splitting(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"

        with self.assertRaisesRegex(ValueError, "at most 255 word devices"):
            read_named_sync(client, [f"D{index}:U" for index in range(256)])

        client.read_random.assert_not_called()

    def test_bit_device_bit_suffix_raises(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaisesRegex(ValueError, "only valid for word devices"):
            read_named_sync(client, ["M100.0"])

    def test_long_timer_family_uses_helper_backed_reads(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_long_timer.side_effect = [
            [LongTimerResult(10, "LTN10", 0x00010002, True, False, 0x0002, [2, 1, 2, 0])],
        ]
        client.read_long_retentive_timer.side_effect = [
            [LongTimerResult(20, "LSTN20", 7, False, True, 0x0001, [7, 0, 1, 0])],
        ]
        client.read_random.return_value = RandomReadResult(word={}, dword={"LCN30": 8})
        client.read_devices.side_effect = [
            [True],
            [True],
        ]

        result = read_named_sync(
            client,
            [
                "LTN10:D",
                "LTS10:BIT",
                "LTC10:BIT",
                "LSTN20:D",
                "LSTS20:BIT",
                "LSTC20:BIT",
                "LCN30:D",
                "LCS30:BIT",
                "LCC30:BIT",
            ],
        )

        self.assertEqual(result["LTN10:D"], 0x00010002)
        self.assertTrue(result["LTS10:BIT"])
        self.assertFalse(result["LTC10:BIT"])
        self.assertEqual(result["LSTN20:D"], 7)
        self.assertFalse(result["LSTS20:BIT"])
        self.assertTrue(result["LSTC20:BIT"])
        self.assertEqual(result["LCN30:D"], 8)
        self.assertTrue(result["LCS30:BIT"])
        self.assertTrue(result["LCC30:BIT"])
        client.read_random.assert_called_once_with(word_devices=[], dword_devices=[DeviceRef("LCN", 30, "melsec:iq-r")])
        client.read_long_timer.assert_called_once_with(head_no=10, points=1)
        client.read_long_retentive_timer.assert_called_once_with(head_no=20, points=1)
        self.assertEqual(
            client.read_devices.call_args_list,
            [
                unittest.mock.call(DeviceRef("LCS", 30, "melsec:iq-r"), 1, bit_unit=True),
                unittest.mock.call(DeviceRef("LCC", 30, "melsec:iq-r"), 1, bit_unit=True),
            ],
        )


# ---------------------------------------------------------------------------
# write_named_sync
# ---------------------------------------------------------------------------


class TestWriteNamedSync(unittest.TestCase):
    def test_write_multiple(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_named_sync(client, {"D100:U": 1, "D200:U": 2})
        self.assertEqual(client.write_devices.call_count, 2)

    def test_write_float(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
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
        client.plc_profile = "melsec:iq-r"
        write_named_sync(client, {"M100:BIT": True})
        client.write_devices.assert_called_once_with("M100", [True], bit_unit=True)

    def test_write_bit_device_bit_suffix_raises(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaisesRegex(ValueError, "only valid for word devices"):
            write_named_sync(client, {"M100.0": True})

    def test_write_named_requires_explicit_long_current_dtype(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_named_sync(client, {"LTN10:D": 1, "LSTN20:D": 2, "LCN30:D": 3})

        self.assertEqual(
            client.write_random_words.call_args_list,
            [
                unittest.mock.call(dword_values={DeviceRef("LTN", 10, "melsec:iq-r"): 1}),
                unittest.mock.call(dword_values={DeviceRef("LSTN", 20, "melsec:iq-r"): 2}),
                unittest.mock.call(dword_values={DeviceRef("LCN", 30, "melsec:iq-r"): 3}),
            ],
        )

    def test_write_named_routes_long_timer_state_writes_to_native_paths(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_named_sync(
            client,
            {
                "LTC10:BIT": True,
                "LTS10:BIT": False,
                "LSTC20:BIT": True,
                "LSTS20:BIT": False,
                "LCC30:BIT": True,
                "LCS30:BIT": False,
            },
        )

        self.assertEqual(
            client.write_random_bits.call_args_list,
            [
                unittest.mock.call({DeviceRef("LTC", 10, "melsec:iq-r"): True}),
                unittest.mock.call({DeviceRef("LTS", 10, "melsec:iq-r"): False}),
                unittest.mock.call({DeviceRef("LSTC", 20, "melsec:iq-r"): True}),
                unittest.mock.call({DeviceRef("LSTS", 20, "melsec:iq-r"): False}),
                unittest.mock.call({DeviceRef("LCC", 30, "melsec:iq-r"): True}),
                unittest.mock.call({DeviceRef("LCS", 30, "melsec:iq-r"): False}),
            ],
        )
        client.write_devices.assert_not_called()


# ---------------------------------------------------------------------------
# read_words_sync / read_dwords_sync
# ---------------------------------------------------------------------------


class TestReadWordsSyncSingleRequest(unittest.TestCase):
    def test_read_words_single_request_sync(self):
        client = _make_sync_client(list(range(4)))
        result = read_words_single_request_sync(client, "D0", 4)
        self.assertEqual(result, [0, 1, 2, 3])
        client.read_devices.assert_called_once_with(DeviceRef("D", 0, "melsec:iq-r"), 4, bit_unit=False)

    def test_no_split_within_limit(self):
        client = _make_sync_client(list(range(10)))
        result = read_words_sync(client, "D0", 10)
        self.assertEqual(result, list(range(10)))

    def test_no_split_exceeds_limit_raises(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaises(ValueError):
            read_words_sync(client, "D0", 961)
        client.read_devices.assert_not_called()

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


class TestWriteWordsSyncSingleRequest(unittest.TestCase):
    def test_write_words_single_request_sync(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_words_single_request_sync(client, "D0", [1, 2, 3])
        client.write_devices.assert_called_once_with("D0", [1, 2, 3], bit_unit=False)

    def test_write_dwords_single_request_sync(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_dwords_single_request_sync(client, "D0", [1, 2])
        client.write_devices.assert_called_once_with("D0", [1, 0, 2, 0], bit_unit=False)


class TestBitBlockHelpers(unittest.TestCase):
    def test_read_bits_sync(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_devices.return_value = [True, False, True]
        self.assertEqual(read_bits_sync(client, "M100", 3), [True, False, True])
        client.read_devices.assert_called_once_with("M100", 3, bit_unit=True)

    def test_write_bits_sync(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_bits_sync(client, "M100", [True, False, True])
        client.write_devices.assert_called_once_with("M100", [True, False, True], bit_unit=True)


# ---------------------------------------------------------------------------
# poll_sync
# ---------------------------------------------------------------------------


class TestPollSync(unittest.TestCase):
    def test_yields_snapshots(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_random.side_effect = [
            RandomReadResult(word={"D0": 1}, dword={}),
            RandomReadResult(word={"D0": 2}, dword={}),
            RandomReadResult(word={"D0": 3}, dword={}),
        ]
        gen = poll_sync(client, ["D0:U"], interval=0)
        snap1 = next(gen)
        snap2 = next(gen)
        snap3 = next(gen)
        self.assertEqual(snap1["D0:U"], 1)
        self.assertEqual(snap2["D0:U"], 2)
        self.assertEqual(snap3["D0:U"], 3)


class TestReadPlan(unittest.TestCase):
    def test_compile_read_plan_batches_word_and_dword_addresses(self):
        plan = _compile_read_plan(
            ["D100:U", "D100.3", "D101:F", "M10:BIT"],
            address_profile="melsec:iq-r",
        )
        self.assertEqual(plan.word_devices, (DeviceRef("D", 100, "melsec:iq-r"), DeviceRef("M", 0, "melsec:iq-r")))
        self.assertEqual(plan.dword_devices, (DeviceRef("D", 101, "melsec:iq-r"),))
        self.assertEqual([entry.batch_kind for entry in plan.entries], ["WORD", "WORD", "DWORD", "WORD"])
        self.assertEqual(plan.entries[3].device, DeviceRef("M", 0, "melsec:iq-r"))
        self.assertEqual(plan.entries[3].dtype, "BIT_IN_WORD")
        self.assertEqual(plan.entries[3].bit_index, 10)

    def test_compile_read_plan_keeps_risky_bit_families_on_direct_read(self):
        plan = _compile_read_plan(
            ["TS10:BIT", "TC10:BIT", "STS10:BIT", "STC10:BIT", "CS10:BIT", "CC10:BIT", "DX10:BIT", "DY10:BIT"],
            address_profile="melsec:iq-r",
        )
        self.assertEqual(plan.word_devices, ())
        self.assertEqual(plan.dword_devices, ())
        self.assertTrue(all(entry.batch_kind is None for entry in plan.entries))
        self.assertTrue(all(entry.dtype == "BIT" for entry in plan.entries))

    def test_compile_read_plan_marks_long_timer_helper_reads_and_long_currents(self):
        plan = _compile_read_plan(
            ["LTN10:D", "LTS10:BIT", "LTC10:BIT", "LSTN20:D", "LCN30:D", "LCS30:BIT", "LCC30:BIT"],
            address_profile="melsec:iq-r",
        )

        self.assertEqual(plan.word_devices, ())
        self.assertEqual(plan.dword_devices, (DeviceRef("LCN", 30, "melsec:iq-r"),))
        self.assertEqual(
            [(entry.address, entry.dtype, entry.batch_kind) for entry in plan.entries],
            [
                ("LTN10:D", "D", "LONG_TIMER"),
                ("LTS10:BIT", "BIT", "LONG_TIMER"),
                ("LTC10:BIT", "BIT", "LONG_TIMER"),
                ("LSTN20:D", "D", "LONG_TIMER"),
                ("LCN30:D", "D", "DWORD"),
                ("LCS30:BIT", "BIT", "LONG_TIMER"),
                ("LCC30:BIT", "BIT", "LONG_TIMER"),
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
        options = SlmpConnectionOptions(
            "127.0.0.1", plc_profile="melsec:iq-f", port=1025, transport="tcp", default_target=TEST_TARGET
        )
        with patch("slmp.async_client.AsyncSlmpClient") as client_cls:
            inner = MagicMock()
            inner.connect = AsyncMock()
            client_cls.return_value = inner

            queued = await open_and_connect(options)

        self.assertIsInstance(queued, QueuedAsyncSlmpClient)
        inner.connect.assert_awaited_once()
        client_cls.assert_called_once()
        self.assertEqual(client_cls.call_args.kwargs["plc_profile"], "melsec:iq-f")

    def test_connection_options_derive_fixed_profile_from_plc_profile(self):
        options = SlmpConnectionOptions(
            "127.0.0.1", plc_profile="melsec:iq-l", port=1025, transport="tcp", default_target=TEST_TARGET
        )

        self.assertEqual(options.plc_profile, "melsec:iq-l")
        self.assertEqual(options.plc_series.value, "iqr")
        self.assertEqual(options.frame_type.value, "4e")
        self.assertEqual(options.address_profile, "melsec:iq-l")
        self.assertEqual(options.range_profile, "melsec:iq-l")

    def test_connection_options_derive_unit_profile_with_independent_frame_and_series(self):
        options = SlmpConnectionOptions(
            "127.0.0.1", plc_profile="melsec:qcpu:qj71e71-100", port=1025, transport="tcp", default_target=TEST_TARGET
        )

        self.assertEqual(options.plc_profile, "melsec:qcpu:qj71e71-100")
        self.assertEqual(options.plc_series.value, "ql")
        self.assertEqual(options.frame_type.value, "4e")
        self.assertEqual(options.address_profile, "melsec:qcpu")
        self.assertEqual(options.range_profile, "melsec:qcpu:qj71e71-100")

    def test_connection_options_derive_iqr_unit_profile_with_iqr_address_rules(self):
        options = SlmpConnectionOptions(
            "127.0.0.1", plc_profile="melsec:iq-r:rj71en71", port=1025, transport="tcp", default_target=TEST_TARGET
        )

        self.assertEqual(options.plc_profile, "melsec:iq-r:rj71en71")
        self.assertEqual(options.plc_series.value, "iqr")
        self.assertEqual(options.frame_type.value, "4e")
        self.assertEqual(options.address_profile, "melsec:iq-r")
        self.assertEqual(options.range_profile, "melsec:iq-r:rj71en71")

    def test_connection_options_require_port_and_transport(self):
        with self.assertRaises(TypeError):
            SlmpConnectionOptions("127.0.0.1", plc_profile="melsec:iq-r", transport="tcp", default_target=TEST_TARGET)
        with self.assertRaises(TypeError):
            SlmpConnectionOptions("127.0.0.1", plc_profile="melsec:iq-r", port=1025, default_target=TEST_TARGET)

    def test_connection_options_reject_short_plc_profile_alias(self):
        with self.assertRaisesRegex(ValueError, "Unsupported plc_profile"):
            SlmpConnectionOptions(
                "127.0.0.1", plc_profile="iq-l", port=1025, transport="tcp", default_target=TEST_TARGET
            )

    def test_connection_options_require_explicit_plc_profile(self):
        with self.assertRaisesRegex(ValueError, "plc_profile is required"):
            SlmpConnectionOptions("127.0.0.1", plc_profile=None, port=1025, transport="tcp", default_target=TEST_TARGET)

    def test_connection_options_reject_noncanonical_profile_case(self):
        with self.assertRaisesRegex(ValueError, "Unsupported plc_profile"):
            SlmpConnectionOptions(
                "127.0.0.1", plc_profile="MELSEC:IQ-L", port=1025, transport="tcp", default_target=TEST_TARGET
            )

    def test_connection_options_reject_base_qcpu_profile(self):
        with self.assertRaisesRegex(ValueError, "melsec:qcpu is a base profile.*melsec:qcpu:qj71e71-100"):
            SlmpConnectionOptions(
                "127.0.0.1", plc_profile="melsec:qcpu", port=1025, transport="tcp", default_target=TEST_TARGET
            )


# ---------------------------------------------------------------------------
# write_named (async)
# ---------------------------------------------------------------------------


class TestWriteNamedAsync(unittest.IsolatedAsyncioTestCase):
    async def test_read_named_more_than_255_word_devices_is_rejected_without_splitting(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_random = AsyncMock()

        with self.assertRaisesRegex(ValueError, "at most 255 word devices"):
            await read_named(client, [f"D{index}:U" for index in range(256)])

        client.read_random.assert_not_awaited()

    async def test_write_multiple(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"

        async def _write(*a, **kw):
            pass

        client.write_devices = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        await write_named(client, {"D100:U": 1, "D200:U": 2})
        self.assertEqual(client.write_devices.call_count, 2)

    async def test_write_named_requires_explicit_long_current_dtype(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.write_devices = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_words = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_bits = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))

        await write_named(client, {"LTN10:D": 1, "LSTN20:D": 2, "LCN30:D": 3})

        self.assertEqual(
            client.write_random_words.call_args_list,
            [
                unittest.mock.call(dword_values={DeviceRef("LTN", 10, "melsec:iq-r"): 1}),
                unittest.mock.call(dword_values={DeviceRef("LSTN", 20, "melsec:iq-r"): 2}),
                unittest.mock.call(dword_values={DeviceRef("LCN", 30, "melsec:iq-r"): 3}),
            ],
        )

    async def test_write_named_routes_long_timer_state_writes_to_native_paths(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.write_devices = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_words = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_bits = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))

        await write_named(
            client,
            {
                "LTC10:BIT": True,
                "LTS10:BIT": False,
                "LSTC20:BIT": True,
                "LSTS20:BIT": False,
                "LCC30:BIT": True,
                "LCS30:BIT": False,
            },
        )

        self.assertEqual(
            client.write_random_bits.call_args_list,
            [
                unittest.mock.call({DeviceRef("LTC", 10, "melsec:iq-r"): True}),
                unittest.mock.call({DeviceRef("LTS", 10, "melsec:iq-r"): False}),
                unittest.mock.call({DeviceRef("LSTC", 20, "melsec:iq-r"): True}),
                unittest.mock.call({DeviceRef("LSTS", 20, "melsec:iq-r"): False}),
                unittest.mock.call({DeviceRef("LCC", 30, "melsec:iq-r"): True}),
                unittest.mock.call({DeviceRef("LCS", 30, "melsec:iq-r"): False}),
            ],
        )
        client.write_devices.assert_not_called()


if __name__ == "__main__":
    unittest.main()
