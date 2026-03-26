import socket
import unittest

from slmp.client import SlmpClient
from slmp.constants import DEVICE_CODES, DeviceUnit, FrameType, PLCSeries
from slmp.core import SlmpError


class TestLiveSimMixedFrames(unittest.TestCase):
    """Write using 3E and read using 4E across all device families."""

    HOST = "127.0.0.1"
    PORT = 5511
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
        # 3E Writer
        self.writer = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES, frame_type=FrameType.FRAME_3E)
        # 4E Reader
        self.reader = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES, frame_type=FrameType.FRAME_4E)

    def test_mixed_frame_all_devices(self) -> None:
        """Write 3E -> Read 4E for all supported device codes."""
        results = []
        # Target addresses for R/W (lower to avoid range errors)
        base_addr = 100

        # Use a single client and switch frame_type dynamically
        client = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES)

        for code, spec in DEVICE_CODES.items():
            # Skip read-only, model-specific, or special-handling devices
            if code in ["SM", "SD", "G", "HG", "DX", "DY"]:
                continue
            if code in ["LTS", "LTC", "LSTS", "LSTC", "TS", "TC", "CS", "CC", "LCS", "LCC"]:
                continue

            addr = f"{code}{base_addr}"
            is_bit = spec.unit == DeviceUnit.BIT
            test_val: list[bool] = [True] if is_bit else [0x55AA]  # type: ignore[list-item]

            try:
                # 1. Write via 3E
                client.frame_type = FrameType.FRAME_3E
                client.write_devices(addr, test_val, bit_unit=is_bit)

                # 2. Read via 4E
                client.frame_type = FrameType.FRAME_4E
                read_val = client.read_devices(addr, 1, bit_unit=is_bit)

                if read_val == test_val:
                    results.append(f"{code}: OK (Mixed-Frame Match)")
                else:
                    results.append(f"{code}: MISMATCH (3E={test_val}, 4E={read_val})")
            except SlmpError as e:
                results.append(f"{code}: SLMP_ERR (0x{e.end_code:04X})")
            except Exception as e:
                results.append(f"{code}: EXCEPTION ({e})")

        client.close()

        print("\n--- Mixed Frame Connectivity Report (3E Write -> 4E Read) ---")
        print("\n".join(results))
        self.assertIn("D: OK (Mixed-Frame Match)", results)
        self.assertIn("M: OK (Mixed-Frame Match)", results)


if __name__ == "__main__":
    unittest.main()
