"""Sample script to verify 3E and 4E frame switching.

This script demonstrates how to switch between 3E and 4E frames and
inspects the raw packets using a trace hook.
"""

import os
import sys

# Add project root to path to import slmp
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries
from slmp.core import SlmpTraceFrame


def hex_print(data: bytes) -> str:
    """Return a space-separated hex representation of the bytes."""
    return data.hex(" ").upper()


def trace_packet(info: SlmpTraceFrame) -> None:
    """Print request and response frames in hex."""
    print("\n--- Trace Info ---")
    print(f"Command: 0x{info.command:04X}, Subcommand: 0x{info.subcommand:04X}")
    print(f"Request  ({len(info.request_frame)} bytes): {hex_print(info.request_frame)}")
    if info.response_frame:
        print(f"Response ({len(info.response_frame)} bytes): {hex_print(info.response_frame)}")
    else:
        print("Response: (no response received)")
    print("------------------\n")


def run_test(ip: str, port: int, frame_type: FrameType) -> None:
    """Run a connection test with the specified frame type."""
    print(f"=== Testing with {frame_type.value.upper()} Frame ===")

    # Switching between 3E/4E is done using the frame_type argument
    client = SlmpClient(
        host=ip,
        port=port,
        frame_type=frame_type,
        plc_series=PLCSeries.QL,  # 3E is common for Q/L series
        timeout=2.0,
        trace_hook=trace_packet,  # Hook to inspect the generated packets
    )

    try:
        client.connect()
        print(f"Reading D100 using {frame_type.value.upper()}...")

        # Read 1 point from D100
        data = client.read_devices("D100", 1)
        print(f"Read Result: {data}")

    except Exception as e:
        print(f"Error during {frame_type.value.upper()} test: {e}")
        print("Note: If no real PLC is connected, check the 'Request' packet trace above.")
    finally:
        client.close()


if __name__ == "__main__":
    # Specify the target IP address and port
    PLC_IP = "192.168.250.100"
    PLC_PORT = 5000

    if len(sys.argv) > 1:
        PLC_IP = sys.argv[1]
    if len(sys.argv) > 2:
        PLC_PORT = int(sys.argv[2])

    print(f"Target: {PLC_IP}:{PLC_PORT}\n")

    # Test 4E frame (default)
    run_test(PLC_IP, PLC_PORT, FrameType.FRAME_4E)

    # Test 3E frame
    run_test(PLC_IP, PLC_PORT, FrameType.FRAME_3E)
