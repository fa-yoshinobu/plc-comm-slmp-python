import socket
import unittest

from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries


class TestLiveSim3E(unittest.TestCase):
    """Test SLMP 3E binary frames against GX Simulator 3."""

    HOST = "127.0.0.1"
    PORT = 5511  # System 1, PLC 1
    SERIES = PLCSeries.IQR

    @classmethod
    def setUpClass(cls) -> None:
        """Quick connectivity check."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            try:
                s.connect((cls.HOST, cls.PORT))
            except Exception:
                raise unittest.SkipTest("Simulator not reachable") from None

    def setUp(self) -> None:
        """Set up the SLMP client for testing."""
        # Explicitly use FRAME_3E
        self.client = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES, frame_type=FrameType.FRAME_3E)

    def test_01_3e_read_type_name(self) -> None:
        """Read type name using 3E frame."""
        info = self.client.read_type_name()
        print(f"\n[3E] Connected to SIM Model: {info.model}")
        self.assertIsNotNone(info.model)

    def test_02_3e_bit_order(self) -> None:
        """Verify SM400/401 bit order using 3E frame."""
        results = self.client.read_devices("SM400", 2, bit_unit=True)
        print(f"[3E] SM400/401 Read: {results}")
        self.assertTrue(results[0], "SM400 should be ON")
        self.assertFalse(results[1], "SM401 should be OFF")

    def test_03_3e_word_rw(self) -> None:
        """Verify D-register R/W using 3E frame."""
        self.client.write_devices("D3000", [0x1234, 0x5678])
        res = self.client.read_devices("D3000", 2)
        self.assertEqual(res, [0x1234, 0x5678])

    def test_04_3e_bit_rw(self) -> None:
        """Verify M-relay R/W using 3E frame."""
        test_bits = [True, False, True, True]
        self.client.write_devices("M3000", test_bits, bit_unit=True)
        res = self.client.read_devices("M3000", 4, bit_unit=True)
        self.assertEqual(res, test_bits)


if __name__ == "__main__":
    unittest.main()
