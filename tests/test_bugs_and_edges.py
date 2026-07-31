import unittest

from slmp import _operations
from slmp.constants import ModuleIONo
from slmp.core import (
    SlmpError,
    SlmpResponse,
    SlmpTarget,
    unpack_bit_values,
)


class TestBugsAndEdges(unittest.TestCase):
    """Test suite for bugs and edge cases."""

    def test_unpack_bit_values_short(self) -> None:
        """Test unpacking bit values with short data."""
        # Need 3 bits (2 bytes), but got 1 byte
        data = b"\x11"
        with self.assertRaises(SlmpError) as cm:
            unpack_bit_values(data, 3)
        self.assertIn("bit data length mismatch", str(cm.exception))

    def test_unpack_bit_values_rejects_trailing_bytes_and_non_binary_nibbles(self) -> None:
        with self.assertRaisesRegex(SlmpError, "length mismatch"):
            unpack_bit_values(b"\x10\x00", 1)
        with self.assertRaisesRegex(SlmpError, "high nibble"):
            unpack_bit_values(b"\x20", 1)
        with self.assertRaisesRegex(SlmpError, "low nibble"):
            unpack_bit_values(b"\x12", 2)
        self.assertEqual(unpack_bit_values(b"\x1f", 1), [True])

    def test_device_read_decoder_rejects_nonzero_end_code_before_payload_decode(self) -> None:
        response = SlmpResponse(
            serial=0,
            target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            end_code=0xC051,
            data=b"\x00",
            raw=b"",
        )

        with self.assertRaises(SlmpError) as cm:
            _operations.decode_read_devices_response(response, points=1, bit_unit=True)
        self.assertEqual(cm.exception.end_code, 0xC051)

    def test_slmp_target_module_io_keywords(self) -> None:
        """Test SlmpTarget module_io keywords."""
        expected = {
            "CONTROL_SYSTEM_CPU": 0x03D0,
            "STANDBY_SYSTEM_CPU": 0x03D1,
            "SYSTEM_A_CPU": 0x03D2,
            "SYSTEM_B_CPU": 0x03D3,
            "MULTIPLE_CPU_1": 0x03E0,
            "MULTIPLE_CPU_2": 0x03E1,
            "MULTIPLE_CPU_3": 0x03E2,
            "MULTIPLE_CPU_4": 0x03E3,
            "REMOTE_HEAD_1": 0x03E0,
            "REMOTE_HEAD_2": 0x03E1,
            "CONTROL_SYSTEM_REMOTE_HEAD": 0x03D0,
            "STANDBY_SYSTEM_REMOTE_HEAD": 0x03D1,
            "OWN_STATION": 0x03FF,
        }
        for name, value in expected.items():
            self.assertEqual(ModuleIONo.__members__[name].value, value)

        t = SlmpTarget(network=0, station=0xFF, module_io="CONTROL_SYSTEM_CPU", multidrop=0)
        self.assertEqual(t.module_io, 0x03D0)
        t = SlmpTarget(network=0, station=0xFF, module_io=ModuleIONo.MULTIPLE_CPU_2, multidrop=0)
        self.assertEqual(t.module_io, 0x03E1)
        t = SlmpTarget(network=0, station=0xFF, module_io="own_station", multidrop=0)
        self.assertEqual(t.module_io, 0x03FF)
        with self.assertRaises(ValueError):
            SlmpTarget(network=0, station=0xFF, module_io="INVALID_KEYWORD", multidrop=0)


if __name__ == "__main__":
    unittest.main()
