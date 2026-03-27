import unittest

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
        t = SlmpTarget(module_io="CONTROL_CPU")
        self.assertEqual(t.module_io, 0x03FF)
        t = SlmpTarget(module_io="own_station")
        self.assertEqual(t.module_io, 0x03FF)
        with self.assertRaises(ValueError):
            SlmpTarget(module_io="INVALID_KEYWORD")


if __name__ == "__main__":
    unittest.main()
