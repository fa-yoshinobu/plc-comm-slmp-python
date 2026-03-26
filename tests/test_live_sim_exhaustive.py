import socket
import time
import unittest

from slmp.client import SlmpClient
from slmp.constants import DEVICE_CODES, DeviceUnit, PLCSeries
from slmp.core import SlmpError


class TestLiveSimExhaustive(unittest.TestCase):
    """Exhaustive live tests against GX Simulator 3."""

    HOST = "127.0.0.1"
    PORT = 5511
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
                raise unittest.SkipTest(f"Simulator not reachable at {cls.HOST}:{cls.PORT}") from None

        # Force RUN state to ensure SD520 ticks
        client = SlmpClient(cls.HOST, cls.PORT, plc_series=cls.SERIES)
        try:
            client.remote_run(force=True)
            time.sleep(0.5)  # Wait for transition
        except Exception:
            pass

    def setUp(self) -> None:
        """Set up the SLMP client for testing."""
        self.client = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES)

    def test_01_all_device_connectivity(self) -> None:
        """Try to read 1 point from EVERY defined device code to check compatibility."""
        results = []
        for code, spec in DEVICE_CODES.items():
            # Skip some codes that might be model-specific or need special handling
            if code in ["G", "HG"]:
                continue  # G/HG direct typed access is blocked in core

            try:
                # Read 1 point
                is_bit = spec.unit == DeviceUnit.BIT
                res = self.client.read_devices(f"{code}0", 1, bit_unit=is_bit)
                results.append(f"{code}: OK (val={res[0]})")
            except SlmpError as e:
                results.append(f"{code}: ERR (0x{e.end_code:04X})")
            except Exception as e:
                results.append(f"{code}: EXCEPTION ({e})")

        print("\n--- Device Connectivity Report ---")
        print("\n".join(results))

    def test_02_bit_order_consistency(self) -> None:
        """Verify that our [1st=Upper, 2nd=Lower] nibble rule is consistent across M and Y."""
        # Test M-relays (internal)
        test_bits = [True, False, True, True, False, True]  # 10 11 10 in nibbles
        # If 1st is upper:
        # Byte0: (1<<4)|0 = 0x10
        # Byte1: (1<<4)|1 = 0x11
        # Byte2: (1<<4)|0 = 0x10
        self.client.write_devices("M2000", test_bits, bit_unit=True)
        read_bits = self.client.read_devices("M2000", 6, bit_unit=True)
        self.assertEqual(read_bits, test_bits, "Bit order inconsistency on M-relays")

        # Test Y-outputs (external)
        self.client.write_devices("Y100", [True, False], bit_unit=True)
        read_y = self.client.read_devices("Y100", 2, bit_unit=True)
        self.assertEqual(read_y, [True, False], "Bit order inconsistency on Y-outputs")

    def test_03_random_access_exhaustive(self) -> None:
        """Test scattered read/write across different families."""
        # 1. Random Write
        write_map: dict[str, int] = {
            "D2000": 0xAAAA,
            "W100": 0xBBBB,
            "R500": 0xCCCC,
        }
        self.client.write_random_words(word_values=write_map)

        # 2. Random Read (Words and DWords)
        res = self.client.read_random(word_devices=["D2000", "W100", "R500"], dword_devices=["ZR1000"])
        self.assertEqual(res.word["D2000"], 0xAAAA)
        self.assertEqual(res.word["W100"], 0xBBBB)
        self.assertEqual(res.word["R500"], 0xCCCC)

    def test_04_timer_counter_details(self) -> None:
        """Test reading Timer/Counter current values and contacts."""
        # GX Sim usually initializes these to 0
        # Read Timer current value (TN0)
        tn0 = self.client.read_devices("TN0", 1)[0]
        # Read Timer contact (TS0)
        ts0 = self.client.read_devices("TS0", 1, bit_unit=True)[0]
        print(f"Timer 0: Current={tn0}, Contact={ts0}")

        # Long Counter (LCN0) - 32 bit
        lcn0 = self.client.read_devices("LCN0", 1)[0]  # Read as word (low)
        print(f"Long Counter 0 (low): {lcn0}")

    def test_05_large_block_transfer(self) -> None:
        """Test pushing boundaries with a larger block (e.g. 500 words)."""
        data = [i % 65535 for i in range(500)]
        self.client.write_devices("D5000", data)
        readback = self.client.read_devices("D5000", 500)
        self.assertEqual(readback, data)

    def test_06_system_device_dynamics(self) -> None:
        """Verify system values (Scan count SD520) change over time."""
        v1 = self.client.read_devices("SD520", 1)[0]
        time.sleep(0.1)
        v2 = self.client.read_devices("SD520", 1)[0]
        print(f"SD520 (Scan Count) changed from {v1} to {v2}")
        self.assertNotEqual(v1, v2, "Scan count should increase")


if __name__ == "__main__":
    unittest.main()
