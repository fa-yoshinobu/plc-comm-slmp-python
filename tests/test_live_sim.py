import socket
import time
import unittest

from slmp.client import SlmpClient
from slmp.constants import PLCSeries


class TestLiveSim(unittest.TestCase):
    """Automated tests against a running GX Simulator 3."""

    HOST = "127.0.0.1"
    PORT = 5511  # System 1, PLC 1 default for GX Sim 3
    SERIES = PLCSeries.IQR

    @classmethod
    def setUpClass(cls) -> None:
        """Quick connectivity check."""
        # Quick connectivity check
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            try:
                s.connect((cls.HOST, cls.PORT))
            except Exception:
                print(f"\nWARNING: Could not connect to Sim at {cls.HOST}:{cls.PORT}")
                print("Make sure GX Simulator 3 is running and 'Start Simulation' is active.")
                raise unittest.SkipTest("Simulator not reachable") from None

    def setUp(self) -> None:
        """Set up the SLMP client for testing."""
        self.client = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES)

    def test_01_read_type_name(self) -> None:
        """Verify we can talk to the SIM and get a model name."""
        info = self.client.read_type_name()
        print(f"\nConnected to SIM Model: {info.model} (Code: 0x{info.model_code:04X})")
        self.assertIsNotNone(info.model)

    def test_02_special_relays_sm400_sm401(self) -> None:
        """Verify the bit order of SM400 (Always ON) and SM401 (Always OFF)."""
        # Read SM400 and SM401 together (2 points)
        # Expected: [True, False] if 1st point is upper nibble (as corrected)
        results = self.client.read_devices("SM400", 2, bit_unit=True)
        print(f"SM400/401 Read: {results}")
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0], "SM400 should be ON")
        self.assertFalse(results[1], "SM401 should be OFF")

    def test_03_word_device_rw(self) -> None:
        """Verify D-register read/write."""
        test_val = int(time.time()) & 0xFFFF
        self.client.write_devices("D1000", [test_val])
        read_val = self.client.read_devices("D1000", 1)[0]
        self.assertEqual(read_val, test_val)

    def test_04_bit_device_rw(self) -> None:
        """Verify M-relay read/write."""
        test_bits = [True, False, True, True, False]
        self.client.write_devices("M1000", test_bits, bit_unit=True)
        read_bits = self.client.read_devices("M1000", 5, bit_unit=True)
        self.assertEqual(read_bits, test_bits)

    def test_05_block_read_mixed(self) -> None:
        """Verify mixed block read works against SIM."""
        self.client.write_devices("D1100", [0x1234, 0x5678])
        self.client.write_devices("M1100", [True, False, True], bit_unit=True)

        res = self.client.read_block(word_blocks=[("D1100", 2)], bit_blocks=[("M1100", 3)])
        self.assertEqual(res.word_blocks[0].values, [0x1234, 0x5678])
        # Note: bit_blocks in read_block return words (packed bits)
        # 101 binary = 0x0005
        self.assertEqual(res.bit_blocks[0].values[0], 0x0005)


if __name__ == "__main__":
    unittest.main()
