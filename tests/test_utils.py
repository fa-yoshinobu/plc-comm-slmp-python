"""Unit tests for slmp.utils sync and async utility functions."""

import struct
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from slmp.core import DeviceRef, LongTimerResult, RandomReadResult, SlmpTarget
from slmp.utils import (
    SlmpConnectionOptions,
    _compile_read_plan,
    _parse_address,
    format_address,
    normalize_address,
    open_and_connect,
    parse_address,
    poll_sync,
    read_bits_single_request_sync,
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
    write_bits_single_request_sync,
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
    def test_typed_dtype_must_match_device_unit(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"

        with self.assertRaisesRegex(ValueError, "only valid for bit devices"):
            read_typed_sync(client, "D100", "BIT")
        with self.assertRaisesRegex(ValueError, "bit device and requires ':BIT'"):
            read_typed_sync(client, "M100", "U")

        client.read_devices.assert_not_called()
        client.read_random.assert_not_called()

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
    def test_typed_dtype_must_match_device_unit(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"

        with self.assertRaisesRegex(ValueError, "only valid for bit devices"):
            write_typed_sync(client, "D100", "BIT", True)
        with self.assertRaisesRegex(ValueError, "bit device and requires ':BIT'"):
            write_typed_sync(client, "M100", "U", 1)

        client.write_devices.assert_not_called()
        client.write_random_bits.assert_not_called()

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

    def test_write_float32_lz_uses_random_dword_route(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"

        write_typed_sync(client, "LZ0", "F", 1.0)

        expected = struct.unpack("<I", struct.pack("<f", 1.0))[0]
        client.write_random_words.assert_called_once()
        kwargs = client.write_random_words.call_args.kwargs
        self.assertEqual(list(kwargs["dword_values"].values()), [expected])
        client.write_devices.assert_not_called()

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
        client.write_devices.assert_called_once_with(
            DeviceRef("D", 0, "melsec:iq-r"),
            [0x0008],
            bit_unit=False,
        )

    def test_clear_bit(self):
        client = _make_sync_client([0x00FF])
        write_bit_in_word_sync(client, "D0", 0, False)
        client.write_devices.assert_called_once_with(
            DeviceRef("D", 0, "melsec:iq-r"),
            [0x00FE],
            bit_unit=False,
        )

    def test_invalid_bit_index(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaises(ValueError):
            write_bit_in_word_sync(client, "D0", 16, True)

    def test_arguments_are_validated_before_read(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        invalid_calls = (
            lambda: write_bit_in_word_sync(client, "D0", True, True),
            lambda: write_bit_in_word_sync(client, "D0", 0, 1),
            lambda: write_bit_in_word_sync(client, "M0", 0, True),
        )

        for call in invalid_calls:
            with self.assertRaises(ValueError):
                call()
        client.read_devices.assert_not_called()
        client.write_devices.assert_not_called()

    def test_write_named_requires_explicit_bit_index(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaisesRegex(ValueError, "BIT_IN_WORD requires"):
            write_named_sync(client, {"D0:BIT_IN_WORD": True})


# ---------------------------------------------------------------------------
# read_named_sync
# ---------------------------------------------------------------------------


class TestReadNamedSync(unittest.TestCase):
    def test_named_dtype_must_match_device_unit_before_transport(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"

        with self.assertRaisesRegex(ValueError, "only valid for bit devices"):
            read_named_sync(client, ["D100:BIT"])
        with self.assertRaisesRegex(ValueError, "bit device and requires ':BIT'"):
            read_named_sync(client, ["M100:U"])

        client.read_random.assert_not_called()

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

    def test_excluded_bit_device_is_rejected_before_transport(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaisesRegex(ValueError, "one random-read request"):
            read_named_sync(client, ["TS100:BIT"])
        client.read_random.assert_not_called()
        client.read_devices.assert_not_called()

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

    def test_named_read_over_profile_limit_is_rejected_before_transport(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"

        with self.assertRaisesRegex(ValueError, "single-request limit|total access points out of range"):
            read_named_sync(client, [f"D{index}:U" for index in range(97)])

        client.read_random.assert_not_called()

    def test_bit_device_bit_suffix_raises(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaisesRegex(ValueError, "only valid for word devices"):
            read_named_sync(client, ["M100.0"])

    def test_long_timer_helper_routes_are_rejected_before_transport(self):
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

        with self.assertRaisesRegex(ValueError, "hidden Direct long-timer read"):
            read_named_sync(client, ["LTN10:D", "LTS10:BIT", "LCN30:D"])
        client.read_random.assert_not_called()
        client.read_long_timer.assert_not_called()
        client.read_long_retentive_timer.assert_not_called()
        client.read_devices.assert_not_called()

    def test_each_long_timer_direct_family_is_rejected_before_transport(self):
        addresses = (
            "LTN10:D",
            "LSTN10:L",
            "LTS10:BIT",
            "LTC10:BIT",
            "LSTS10:BIT",
            "LSTC10:BIT",
        )
        for address in addresses:
            with self.subTest(address=address):
                client = MagicMock()
                client.plc_profile = "melsec:iq-r"

                with self.assertRaisesRegex(ValueError, "hidden Direct long-timer read"):
                    read_named_sync(client, [address])

                client.read_random.assert_not_called()
                client.read_devices.assert_not_called()
                client.read_long_timer.assert_not_called()
                client.read_long_retentive_timer.assert_not_called()


# ---------------------------------------------------------------------------
# write_named_sync
# ---------------------------------------------------------------------------


class TestWriteNamedSync(unittest.TestCase):
    def test_empty_and_multi_request_named_writes_are_rejected_before_transport(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaisesRegex(ValueError, "updates must not be empty"):
            write_named_sync(client, {})
        with self.assertRaisesRegex(ValueError, "cannot mix bit and word"):
            write_named_sync(client, {"D0:U": 1, "M0:BIT": True})
        client.write_random_words.assert_not_called()
        client.write_random_bits.assert_not_called()

    def test_typed_writes_reject_coercion_and_out_of_range_before_transport(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        cases = [
            ("D0", "U", -1),
            ("D0", "U", 0x10000),
            ("D0", "U", True),
            ("D0", "S", 0x8000),
            ("D0", "D", 0x1_0000_0000),
            ("D0", "L", -0x80000001),
            ("D0", "F", float("inf")),
            ("M0", "BIT", 1),
        ]
        for device, dtype, value in cases:
            with self.subTest(dtype=dtype, value=value):
                with self.assertRaises(ValueError):
                    write_typed_sync(client, device, dtype, value)
        client.write_devices.assert_not_called()
        client.write_random_words.assert_not_called()

    def test_write_multiple(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_named_sync(client, {"D100:U": 1, "D200:U": 2})
        client.write_random_words.assert_called_once_with(
            word_values=[
                (DeviceRef("D", 100, "melsec:iq-r"), 1),
                (DeviceRef("D", 200, "melsec:iq-r"), 2),
            ],
            dword_values=[],
        )

    def test_write_float(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_named_sync(client, {"D100:F": 1.0})
        expected = struct.unpack("<I", struct.pack("<f", 1.0))[0]
        client.write_random_words.assert_called_once_with(
            word_values=[],
            dword_values=[(DeviceRef("D", 100, "melsec:iq-r"), expected)],
        )

    def test_write_bit_in_word(self):
        client = _make_sync_client([0x0000])
        with self.assertRaisesRegex(ValueError, "two-request operation is visible"):
            write_named_sync(client, {"D0.2": True})
        client.write_devices.assert_not_called()

    def test_write_direct_bit_device(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_named_sync(client, {"M100:BIT": True})
        client.write_random_bits.assert_called_once_with([(DeviceRef("M", 100, "melsec:iq-r"), True)])

    def test_write_bit_device_bit_suffix_raises(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaisesRegex(ValueError, "only valid for word devices"):
            write_named_sync(client, {"M100.0": True})

    def test_write_named_requires_explicit_long_current_dtype(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_named_sync(client, {"LTN10:D": 1, "LSTN20:D": 2, "LCN30:D": 3})

        client.write_random_words.assert_called_once_with(
            word_values=[],
            dword_values=[
                (DeviceRef("LTN", 10, "melsec:iq-r"), 1),
                (DeviceRef("LSTN", 20, "melsec:iq-r"), 2),
                (DeviceRef("LCN", 30, "melsec:iq-r"), 3),
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

        client.write_random_bits.assert_called_once_with(
            [
                (DeviceRef("LTC", 10, "melsec:iq-r"), True),
                (DeviceRef("LTS", 10, "melsec:iq-r"), False),
                (DeviceRef("LSTC", 20, "melsec:iq-r"), True),
                (DeviceRef("LSTS", 20, "melsec:iq-r"), False),
                (DeviceRef("LCC", 30, "melsec:iq-r"), True),
                (DeviceRef("LCS", 30, "melsec:iq-r"), False),
            ]
        )
        client.write_devices.assert_not_called()


# ---------------------------------------------------------------------------
# read_words_sync / read_dwords_sync
# ---------------------------------------------------------------------------


class TestReadWordsSyncSingleRequest(unittest.TestCase):
    def test_canonical_word_and_dword_counts_reject_zero_and_negative_before_transport(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        for count in (0, -1):
            with self.assertRaises(ValueError):
                read_words_single_request_sync(client, "D0", count)
            with self.assertRaises(ValueError):
                read_dwords_single_request_sync(client, "D0", count)
        client.read_devices.assert_not_called()

    def test_read_words_single_request_sync(self):
        client = _make_sync_client(list(range(4)))
        result = read_words_single_request_sync(client, "D0", 4)
        self.assertEqual(result, [0, 1, 2, 3])
        client.read_devices.assert_called_once_with(DeviceRef("D", 0, "melsec:iq-r"), 4, bit_unit=False)

    def test_no_split_within_limit(self):
        client = _make_sync_client(list(range(10)))
        with self.assertWarns(DeprecationWarning):
            result = read_words_sync(client, "D0", 10)
        self.assertEqual(result, list(range(10)))

    def test_no_split_exceeds_limit_raises(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertWarns(DeprecationWarning):
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
    def test_canonical_word_and_dword_writes_reject_empty_before_transport(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertRaises(ValueError):
            write_words_single_request_sync(client, "D0", [])
        with self.assertRaises(ValueError):
            write_dwords_single_request_sync(client, "D0", [])
        client.write_devices.assert_not_called()

    def test_write_words_single_request_sync(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_words_single_request_sync(client, "D0", [1, 2, 3])
        client.write_devices.assert_called_once_with(DeviceRef("D", 0, "melsec:iq-r"), [1, 2, 3], bit_unit=False)

    def test_write_dwords_single_request_sync(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        write_dwords_single_request_sync(client, "D0", [1, 2])
        client.write_devices.assert_called_once_with(DeviceRef("D", 0, "melsec:iq-r"), [1, 0, 2, 0], bit_unit=False)


class TestBitBlockHelpers(unittest.TestCase):
    def test_canonical_bit_helpers_issue_one_request(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_devices.return_value = [True, False]
        self.assertEqual(read_bits_single_request_sync(client, "M100", 2), [True, False])
        client.read_devices.assert_called_once_with(DeviceRef("M", 100, "melsec:iq-r"), 2, bit_unit=True)
        write_bits_single_request_sync(client, "M100", [True, False])
        client.write_devices.assert_called_once_with(DeviceRef("M", 100, "melsec:iq-r"), [True, False], bit_unit=True)
        with self.assertRaises(ValueError):
            read_bits_single_request_sync(client, "D0", 1)
        with self.assertRaises(ValueError):
            write_bits_single_request_sync(client, "M100", [False] * 7169)
        client.read_devices.assert_called_once()
        client.write_devices.assert_called_once()

    def test_read_bits_sync(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_devices.return_value = [True, False, True]
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(read_bits_sync(client, "M100", 3), [True, False, True])
        client.read_devices.assert_called_once_with(DeviceRef("M", 100, "melsec:iq-r"), 3, bit_unit=True)

    def test_write_bits_sync(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        with self.assertWarns(DeprecationWarning):
            write_bits_sync(client, "M100", [True, False, True])
        client.write_devices.assert_called_once_with(
            DeviceRef("M", 100, "melsec:iq-r"), [True, False, True], bit_unit=True
        )


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
    def test_empty_read_plan_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "addresses must not be empty"):
            _compile_read_plan([], address_profile="melsec:iq-r")

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

    def test_compile_read_plan_rejects_direct_read_fallback(self):
        with self.assertRaisesRegex(ValueError, "one random-read request"):
            _compile_read_plan(["TS10:BIT", "DX10:BIT"], address_profile="melsec:iq-r")

    def test_compile_read_plan_rejects_long_timer_helper_routes(self):
        with self.assertRaisesRegex(ValueError, "hidden Direct long-timer read"):
            _compile_read_plan(["LTN10:D", "LTS10:BIT", "LCN30:D"], address_profile="melsec:iq-r")


class TestAsyncClientFactory(unittest.IsolatedAsyncioTestCase):
    async def test_open_and_connect_returns_ordinary_client(self):
        options = SlmpConnectionOptions(
            "127.0.0.1", plc_profile="melsec:iq-f", port=1025, transport="tcp", default_target=TEST_TARGET
        )
        with patch("slmp.async_client.AsyncSlmpClient") as client_cls:
            inner = MagicMock()
            inner.connect = AsyncMock()
            client_cls.return_value = inner

            connected = await open_and_connect(options)

        self.assertIs(connected, inner)
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

    def test_connection_options_derive_mxr_unit_profile_with_mxr_address_rules(self):
        options = SlmpConnectionOptions(
            "127.0.0.1",
            plc_profile="melsec:mx-r:rj71en71",
            port=1025,
            transport="tcp",
            default_target=TEST_TARGET,
        )

        self.assertEqual(options.plc_profile, "melsec:mx-r:rj71en71")
        self.assertEqual(options.plc_series.value, "iqr")
        self.assertEqual(options.frame_type.value, "4e")
        self.assertEqual(options.address_profile, "melsec:mx-r")
        self.assertEqual(options.range_profile, "melsec:mx-r:rj71en71")

    def test_connection_options_require_port_and_transport(self):
        with self.assertRaises(TypeError):
            SlmpConnectionOptions("127.0.0.1", plc_profile="melsec:iq-r", transport="tcp", default_target=TEST_TARGET)
        with self.assertRaises(TypeError):
            SlmpConnectionOptions("127.0.0.1", plc_profile="melsec:iq-r", port=1025, default_target=TEST_TARGET)

    def test_connection_options_require_boolean_raise_on_error(self):
        for invalid in (None, 0, 1, "false", "true", "", [], {}):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "raise_on_error must be a boolean"):
                    SlmpConnectionOptions(
                        "127.0.0.1",
                        plc_profile="melsec:iq-r",
                        port=1025,
                        transport="tcp",
                        default_target=TEST_TARGET,
                        raise_on_error=invalid,  # type: ignore[arg-type]
                    )

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
    async def test_named_read_over_profile_limit_is_rejected_before_transport(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.read_random = AsyncMock()

        with self.assertRaisesRegex(ValueError, "single-request limit|total access points out of range"):
            await read_named(client, [f"D{index}:U" for index in range(97)])

        client.read_random.assert_not_awaited()

    async def test_each_long_timer_direct_family_is_rejected_before_transport(self):
        addresses = (
            "LTN10:D",
            "LSTN10:L",
            "LTS10:BIT",
            "LTC10:BIT",
            "LSTS10:BIT",
            "LSTC10:BIT",
        )
        for address in addresses:
            with self.subTest(address=address):
                client = MagicMock()
                client.plc_profile = "melsec:iq-r"
                client.read_random = AsyncMock()
                client.read_devices = AsyncMock()

                with self.assertRaisesRegex(ValueError, "hidden Direct long-timer read"):
                    await read_named(client, [address])

                client.read_random.assert_not_awaited()
                client.read_devices.assert_not_awaited()

    async def test_write_multiple(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.write_random_words = AsyncMock()
        await write_named(client, {"D100:U": 1, "D200:U": 2})
        client.write_random_words.assert_awaited_once_with(
            word_values=[
                (DeviceRef("D", 100, "melsec:iq-r"), 1),
                (DeviceRef("D", 200, "melsec:iq-r"), 2),
            ],
            dword_values=[],
        )

    async def test_write_named_requires_explicit_long_current_dtype(self):
        client = MagicMock()
        client.plc_profile = "melsec:iq-r"
        client.write_devices = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_words = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))
        client.write_random_bits = MagicMock(side_effect=lambda *a, **kw: _make_coro(None))

        await write_named(client, {"LTN10:D": 1, "LSTN20:D": 2, "LCN30:D": 3})

        client.write_random_words.assert_called_once_with(
            word_values=[],
            dword_values=[
                (DeviceRef("LTN", 10, "melsec:iq-r"), 1),
                (DeviceRef("LSTN", 20, "melsec:iq-r"), 2),
                (DeviceRef("LCN", 30, "melsec:iq-r"), 3),
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

        client.write_random_bits.assert_called_once_with(
            [
                (DeviceRef("LTC", 10, "melsec:iq-r"), True),
                (DeviceRef("LTS", 10, "melsec:iq-r"), False),
                (DeviceRef("LSTC", 20, "melsec:iq-r"), True),
                (DeviceRef("LSTS", 20, "melsec:iq-r"), False),
                (DeviceRef("LCC", 30, "melsec:iq-r"), True),
                (DeviceRef("LCS", 30, "melsec:iq-r"), False),
            ]
        )
        client.write_devices.assert_not_called()


if __name__ == "__main__":
    unittest.main()
