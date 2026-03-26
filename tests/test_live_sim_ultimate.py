import asyncio
import socket
import unittest

from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.constants import DEVICE_CODES, DeviceUnit, FrameType, PLCSeries
from slmp.core import SlmpError


class TestLiveSimUltimate(unittest.TestCase):
    """Ultimate cross-validation: Sync vs Async, 3E vs 4E, All Devices."""

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

    def test_01_reverse_frame_all_devices(self) -> None:
        """Write 4E -> Read 3E across all supported device codes."""
        print("\n--- Test 01: Reverse Frame (Write 4E -> Read 3E) ---")
        client = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES)
        base_addr = 200

        for code, spec in DEVICE_CODES.items():
            if code in ["SM", "SD", "G", "HG", "DX", "DY"]:
                continue
            if code in ["LTS", "LTC", "LSTS", "LSTC", "TS", "TC", "CS", "CC", "LCS", "LCC"]:
                continue

            addr = f"{code}{base_addr}"
            is_bit = spec.unit == DeviceUnit.BIT
            test_val: list[bool] = [True] if is_bit else [0xABCD]  # type: ignore[list-item]

            try:
                # 1. Write via 4E
                client.frame_type = FrameType.FRAME_4E
                client.write_devices(addr, test_val, bit_unit=is_bit)

                # 2. Read via 3E
                client.frame_type = FrameType.FRAME_3E
                read_val = client.read_devices(addr, 1, bit_unit=is_bit)

                self.assertEqual(read_val, test_val, f"Mismatch on {code}")
                print(f"{code}: OK")
            except SlmpError as e:
                if e.end_code in [0x4031, 0xC051]:
                    continue  # Skip range/points errors
                raise e
        client.close()

    def test_02_sync_write_async_read(self) -> None:
        """Write via Sync -> Read via Async."""
        print("\n--- Test 02: Sync Write -> Async Read ---")
        # 1. Sync Write
        sync_cli = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES)
        sync_cli.write_devices("D500", [0x1111])
        sync_cli.close()

        # 2. Async Read
        async def run_async_part() -> None:
            """Async part of the test."""
            async with AsyncSlmpClient(self.HOST, self.PORT, plc_series=self.SERIES) as async_cli:
                val = await async_cli.read_devices("D500", 1)
                self.assertEqual(val, [0x1111])

                # Bit Test (Ensure SM400/401 logic is identical)
                res = await async_cli.read_devices("SM400", 2, bit_unit=True)
                self.assertEqual(res, [True, False], "Async bit order mismatch")
                print("Sync Write -> Async Read: OK")

        asyncio.run(run_async_part())

    def test_03_async_write_sync_read(self) -> None:
        """Write via Async -> Read via Sync."""
        print("\n--- Test 03: Async Write -> Sync Read ---")

        # 1. Async Write
        async def run_async_part() -> None:
            """Async part of the test."""
            async with AsyncSlmpClient(self.HOST, self.PORT, plc_series=self.SERIES) as async_cli:
                await async_cli.write_devices("D501", [0x2222])
                await async_cli.write_devices("M500", [True, False, True], bit_unit=True)

        asyncio.run(run_async_part())

        # 2. Sync Read
        sync_cli = SlmpClient(self.HOST, self.PORT, plc_series=self.SERIES)
        val = sync_cli.read_devices("D501", 1)
        self.assertEqual(val, [0x2222])
        res = sync_cli.read_devices("M500", 3, bit_unit=True)
        self.assertEqual(res, [True, False, True])
        sync_cli.close()
        print("Async Write -> Sync Read: OK")

    def test_04_async_concurrency_stress(self) -> None:
        """Perform many concurrent reads/writes via Async client."""
        print("\n--- Test 04: Async Concurrency Stress ---")

        async def stress() -> None:
            """Async stress test."""
            async with AsyncSlmpClient(self.HOST, self.PORT, plc_series=self.SERIES) as cli:
                # Launch 20 concurrent tasks
                async def task(i: int) -> bool:
                    """Single task for stress test."""
                    addr = f"D{600 + i}"
                    val = [i * 100]
                    await cli.write_devices(addr, val)
                    res = await cli.read_devices(addr, 1)
                    return res == val

                results = await asyncio.gather(*(task(i) for i in range(20)))
                self.assertTrue(all(results))
                print("Async Concurrency (20 tasks): OK")

        asyncio.run(stress())


if __name__ == "__main__":
    unittest.main()
