"""Shared cross-implementation parity tests for the Python SLMP library."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from slmp.client import SlmpClient
from slmp.core import SlmpTarget, encode_request
from slmp.utils import _parse_address, normalize_address

_SHARED_SPEC_DIR = Path(__file__).resolve().parent / "shared-spec"


def _load_json(name: str) -> dict[str, Any]:
    return json.loads((_SHARED_SPEC_DIR / name).read_text(encoding="utf-8"))


def _build_4e_response(request: bytes, response_data: bytes, end_code: int = 0) -> bytes:
    payload = end_code.to_bytes(2, "little") + response_data
    header = bytearray()
    header += b"\xd4\x00"
    header += request[2:4]
    header += b"\x00\x00"
    header += request[6:11]
    header += len(payload).to_bytes(2, "little")
    return bytes(header + payload)


class CaptureClient(SlmpClient):
    """Capture outgoing frames without using a real socket."""

    def __init__(self, response_data: bytes, plc_profile: str = "melsec:iq-r") -> None:
        super().__init__(
            "127.0.0.1",
            1025,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile=plc_profile,
            monitoring_timer=0x0010,
            raise_on_error=True,
        )
        self.captured_frame: bytes | None = None
        self._response_data = response_data

    def _send_and_receive(self, frame: bytes) -> bytes:
        self.captured_frame = frame
        return _build_4e_response(frame, self._response_data)

    def _send_no_response(self, command, subcommand, data, **kwargs) -> None:  # type: ignore[no-untyped-def]
        del kwargs
        self.captured_frame = encode_request(
            frame_type=self.frame_type,
            serial=self._next_serial(),
            target=self.default_target,
            monitoring_timer=self.monitoring_timer,
            command=int(command),
            subcommand=subcommand,
            data=data,
        )


class TestSharedAddressVectors(unittest.TestCase):
    def test_normalize_vectors(self) -> None:
        data = _load_json("high_level_address_normalize_vectors.json")
        for case in data["cases"]:
            if "python" not in case.get("implementations", []):
                continue
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    normalize_address(case["input"], plc_profile="melsec:iq-r"),
                    case["expected"],
                )

    def test_parse_vectors(self) -> None:
        data = _load_json("high_level_address_parse_vectors.json")
        for case in data["cases"]:
            if "python" not in case.get("implementations", []):
                continue
            with self.subTest(case=case["id"]):
                base, dtype, bit_index = _parse_address(case["input"])
                self.assertEqual(
                    {"base": base, "dtype": dtype, "bit_index": bit_index},
                    case["expected"],
                )


class TestSharedFrameVectors(unittest.TestCase):
    def test_request_frames_match_shared_vectors(self) -> None:
        data = _load_json("frame_golden_vectors.json")
        for case in data["cases"]:
            if "python" not in case.get("implementations", []):
                continue
            with self.subTest(case=case["id"]):
                response_data = bytes.fromhex(case.get("response_data_hex", ""))
                client = CaptureClient(response_data, case.get("plc_profile", "melsec:iq-r"))
                self._dispatch_case(client, case)
                self.assertIsNotNone(client.captured_frame)
                self.assertEqual(client.captured_frame.hex().upper(), case["request_hex"])

    def _dispatch_case(self, client: CaptureClient, case: dict[str, Any]) -> None:
        operation = case["operation"]
        args = case.get("args", {})

        if operation == "read_type_name":
            info = client.read_type_name()
            self.assertEqual(info.model, "Q03UDVCPU")
            return

        if operation == "read_words":
            values = client.read_devices(args["device"], args["points"], bit_unit=False)
            self.assertEqual(values, [0x1234, 0x5678])
            return

        if operation == "write_bits":
            client.write_devices(args["device"], args["values"], bit_unit=True)
            return

        if operation == "read_random":
            result = client.read_random(
                word_devices=args["word_devices"],
                dword_devices=args["dword_devices"],
            )
            self.assertEqual(result.word["D100"], 0x1111)
            self.assertEqual(result.word["D101"], 0x2222)
            self.assertEqual(result.dword["D200"], 0x12345678)
            return

        if operation == "write_random_bits":
            bit_values = {item["device"]: item["value"] for item in args["bit_values"]}
            client.write_random_bits(bit_values)
            return

        if operation == "read_block":
            result = client.read_block(
                word_blocks=[(item["device"], item["points"]) for item in args["word_blocks"]],
                bit_blocks=[(item["device"], item["points"]) for item in args["bit_blocks"]],
            )
            self.assertEqual(result.word_blocks[0].values, [0x1234, 0x5678])
            self.assertEqual(result.bit_blocks[0].values, [0x0005])
            return

        if operation == "remote_password_unlock":
            client.remote_password_unlock(args["password"])
            return

        if operation == "remote_reset":
            client.remote_reset()
            return

        raise AssertionError(f"Unsupported shared frame operation: {operation}")
