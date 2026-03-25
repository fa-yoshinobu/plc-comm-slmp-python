#!/usr/bin/env python
"""Q-series full command test script."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries


def test_all_commands(host: str = "192.168.250.101", port: int = 1025) -> None:
    """Run full command validation on Q06UDV."""

    print(f"Full Command Validation on Q06UDV ({host}:{port})")
    print("Settings: 3E Frame + Legacy (QL) Mode\n")
    print("| Code | Command Name | Result | Detail/EndCode |")
    print("|:---:|:---|:---:|:---|")

    with SlmpClient(host, port, frame_type=FrameType.FRAME_3E, plc_series=PLCSeries.QL, timeout=2.0) as client:
        # 1. 0101 Read Type Name
        try:
            client.read_type_name()
            print("| 0101 | Read Type Name | PASS | - |")
        except Exception as e:
            print(f"| 0101 | Read Type Name | FAIL | {e} |")

        # 2. 0401 Read Device (Word)
        try:
            client.read_devices("D130", 1)
            print("| 0401 | Read Device (Word) | PASS | - |")
        except Exception as e:
            print(f"| 0401 | Read Device (Word) | FAIL | {e} |")

        # 3. 0401 Read Device (Bit)
        try:
            client.read_devices("M120", 1, bit_unit=True)
            print("| 0401 | Read Device (Bit) | PASS | - |")
        except Exception as e:
            print(f"| 0401 | Read Device (Bit) | FAIL | {e} |")

        # 4. 1401 Write Device (Word)
        try:
            client.write_devices("D130", [0])
            print("| 1401 | Write Device (Word) | PASS | - |")
        except Exception as e:
            print(f"| 1401 | Write Device (Word) | FAIL | {e} |")

        # 5. 1401 Write Device (Bit)
        try:
            client.write_devices("M120", [False], bit_unit=True)
            print("| 1401 | Write Device (Bit) | PASS | - |")
        except Exception as e:
            print(f"| 1401 | Write Device (Bit) | FAIL | {e} |")

        # 6. 0403 Read Random
        try:
            client.read_random(word_devices=["D130", "D131"])
            print("| 0403 | Read Random (Word) | PASS | - |")
        except Exception as e:
            print(f"| 0403 | Read Random (Word) | FAIL | {e} |")

        # 7. 1402 Write Random (Word)
        try:
            client.write_random_words(word_values=[("D135", 0)])
            print("| 1402 | Write Random (Word) | PASS | - |")
        except Exception as e:
            print(f"| 1402 | Write Random (Word) | FAIL | {e} |")

        # 8. 1402 Write Random (Bit)
        try:
            client.write_random_bits(bit_values=[("M125", False)])
            print("| 1402 | Write Random (Bit) | PASS | - |")
        except Exception as e:
            print(f"| 1402 | Write Random (Bit) | FAIL | {e} |")

        # 9. 0406 Read Block
        try:
            client.read_block(word_blocks=[("D140", 1)])
            print("| 0406 | Read Block | PASS | - |")
        except Exception as e:
            print(f"| 0406 | Read Block | FAIL | {e} |")

        # 10. 1406 Write Block
        try:
            client.write_block(word_blocks=[("D140", [0])])
            print("| 1406 | Write Block | PASS | - |")
        except Exception as e:
            print(f"| 1406 | Write Block | FAIL | {e} |")

        # 11. 0619 Self Test
        try:
            # Send 4 bytes of dummy data
            client.request(0x0619, 0x0000, b"\x04\x00\x11\x22\x33\x44")
            print("| 0619 | Self Test | PASS | - |")
        except Exception as e:
            print(f"| 0619 | Self Test | FAIL | {e} |")

        # 12. 0613 Buffer Read
        try:
            client.memory_read_words(0, 1)
            print("| 0613 | Buffer Memory Read | PASS | - |")
        except Exception as e:
            print(f"| 0613 | Buffer Memory Read | FAIL | {e} |")

        # 13. 1613 Buffer Write
        try:
            client.memory_write_words(0, [0])
            print("| 1613 | Buffer Memory Write | PASS | - |")
        except Exception as e:
            print(f"| 1613 | Buffer Memory Write | FAIL | {e} |")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.250.101")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()
    test_all_commands(host=args.host, port=args.port)
