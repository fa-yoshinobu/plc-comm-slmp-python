import unittest

from slmp.constants import ModuleIONo
from slmp.core import (
    SlmpError,
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
        self.assertIn("bit data too short", str(cm.exception))

    def test_slmp_target_module_io_keywords(self) -> None:
        """Test SlmpTarget module_io keywords."""
        expected = {
            "CONTROL_CPU": 0x03D0,
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
            "DEFAULT": 0x03FF,
            "CONNECTED_CPU": 0x03FF,
        }
        for name, value in expected.items():
            self.assertEqual(ModuleIONo.__members__[name].value, value)

        t = SlmpTarget(module_io="CONTROL_CPU")
        self.assertEqual(t.module_io, 0x03D0)
        t = SlmpTarget(module_io=ModuleIONo.MULTIPLE_CPU_2)
        self.assertEqual(t.module_io, 0x03E1)
        t = SlmpTarget(module_io="own_station")
        self.assertEqual(t.module_io, 0x03FF)
        with self.assertRaises(ValueError):
            SlmpTarget(module_io="INVALID_KEYWORD")


if __name__ == "__main__":
    unittest.main()
