"""Sync/async request-frame parity tests."""

from __future__ import annotations

import struct
import unittest
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.constants import (
    DIRECT_MEMORY_LINK_DIRECT,
    Command,
    FrameType,
    PLCSeries,
)
from slmp.core import (
    ExtensionSpec,
    LabelArrayReadPoint,
    LabelArrayWritePoint,
    LabelRandomWritePoint,
    SlmpTarget,
    encode_request,
    pack_bit_values,
)


def _words(*values: int) -> bytes:
    return b"".join(int(value).to_bytes(2, "little") for value in values)


def _dwords(*values: int) -> bytes:
    return b"".join(int(value).to_bytes(4, "little") for value in values)


def _float32s(*values: float) -> bytes:
    return b"".join(struct.pack("<f", value) for value in values)


def _build_response(frame: bytes, *, frame_type: FrameType, response_data: bytes = b"", end_code: int = 0) -> bytes:
    payload = end_code.to_bytes(2, "little") + response_data
    if frame_type == FrameType.FRAME_3E:
        header = bytearray()
        header += b"\xd0\x00"
        header += frame[2:7]
        header += len(payload).to_bytes(2, "little")
        return bytes(header + payload)

    header = bytearray()
    header += b"\xd4\x00"
    header += frame[2:4]
    header += b"\x00\x00"
    header += frame[6:11]
    header += len(payload).to_bytes(2, "little")
    return bytes(header + payload)


class _SyncCaptureClient(SlmpClient):
    def __init__(self, responses: Sequence[bytes], **kwargs: Any) -> None:
        super().__init__("127.0.0.1", **kwargs)
        self.frames: list[bytes] = []
        self._responses = list(responses)

    def _send_and_receive(self, frame: bytes) -> bytes:
        self.frames.append(frame)
        if not self._responses:
            raise AssertionError("test response queue exhausted")
        return _build_response(frame, frame_type=self.frame_type, response_data=self._responses.pop(0))

    def _send_no_response(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
    ) -> None:
        serial_no = self._next_serial() if serial is None else serial
        target_info = target or self.default_target
        monitor = self.monitoring_timer if monitoring_timer is None else monitoring_timer
        self.frames.append(
            encode_request(
                frame_type=self.frame_type,
                serial=serial_no,
                target=target_info,
                monitoring_timer=monitor,
                command=int(command),
                subcommand=subcommand,
                data=data,
            )
        )


class _AsyncCaptureClient(AsyncSlmpClient):
    def __init__(self, responses: Sequence[bytes], **kwargs: Any) -> None:
        super().__init__("127.0.0.1", **kwargs)
        self.frames: list[bytes] = []
        self._responses = list(responses)

    async def _send_and_receive(self, frame: bytes) -> bytes:
        self.frames.append(frame)
        if not self._responses:
            raise AssertionError("test response queue exhausted")
        return _build_response(frame, frame_type=self.frame_type, response_data=self._responses.pop(0))

    async def _send_no_response(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
    ) -> None:
        serial_no = self._next_serial() if serial is None else serial
        target_info = target or self.default_target
        monitor = self.monitoring_timer if monitoring_timer is None else monitoring_timer
        self.frames.append(
            encode_request(
                frame_type=self.frame_type,
                serial=serial_no,
                target=target_info,
                monitoring_timer=monitor,
                command=int(command),
                subcommand=subcommand,
                data=data,
            )
        )


SyncCall = Callable[[_SyncCaptureClient], object]
AsyncCall = Callable[[_AsyncCaptureClient], Awaitable[object]]


@dataclass(frozen=True)
class _ParityCase:
    name: str
    sync_call: SyncCall
    async_call: AsyncCall
    responses: Sequence[bytes]


def _extension_for(client: SlmpClient | AsyncSlmpClient) -> ExtensionSpec:
    return client.make_extension_spec(
        extension_specification=0x03E0,
        direct_memory_specification=DIRECT_MEMORY_LINK_DIRECT,
        series=client.plc_series,
    )


def _label_array_read_response() -> bytes:
    return b"\x01\x00" + b"\x02\x01" + (4).to_bytes(2, "little") + b"DATA"


def _label_random_read_response() -> bytes:
    return b"\x01\x00" + b"\x02\x00" + (2).to_bytes(2, "little") + b"\x34\x12"


def _parity_cases() -> list[_ParityCase]:
    return [
        _ParityCase(
            "raw_command",
            lambda c: c.raw_command(Command.CLEAR_ERROR, payload=b"\x01\x02"),
            lambda c: c.raw_command(Command.CLEAR_ERROR, payload=b"\x01\x02"),
            [b""],
        ),
        _ParityCase(
            "read_devices_word",
            lambda c: c.read_devices("D100", 2),
            lambda c: c.read_devices("D100", 2),
            [_words(0x1111, 0x2222)],
        ),
        _ParityCase(
            "read_devices_bit",
            lambda c: c.read_devices("M10", 3, bit_unit=True),
            lambda c: c.read_devices("M10", 3, bit_unit=True),
            [pack_bit_values([True, False, True])],
        ),
        _ParityCase(
            "write_devices_word",
            lambda c: c.write_devices("D120", [0x1234, 0x5678]),
            lambda c: c.write_devices("D120", [0x1234, 0x5678]),
            [b""],
        ),
        _ParityCase(
            "write_devices_bit",
            lambda c: c.write_devices("M20", [True, False, True], bit_unit=True),
            lambda c: c.write_devices("M20", [True, False, True], bit_unit=True),
            [b""],
        ),
        _ParityCase(
            "read_dwords",
            lambda c: c.read_dwords("D200", 2),
            lambda c: c.read_dwords("D200", 2),
            [_dwords(0x12345678, 0x90ABCDEF)],
        ),
        _ParityCase(
            "write_dwords",
            lambda c: c.write_dwords("D210", [0x12345678, 0x90ABCDEF]),
            lambda c: c.write_dwords("D210", [0x12345678, 0x90ABCDEF]),
            [b""],
        ),
        _ParityCase(
            "read_float32s",
            lambda c: c.read_float32s("D220", 2),
            lambda c: c.read_float32s("D220", 2),
            [_float32s(1.25, -2.5)],
        ),
        _ParityCase(
            "write_float32s",
            lambda c: c.write_float32s("D230", [1.25, -2.5]),
            lambda c: c.write_float32s("D230", [1.25, -2.5]),
            [b""],
        ),
        _ParityCase(
            "read_devices_ext",
            lambda c: c.read_devices_ext("D300", 2, extension=_extension_for(c)),
            lambda c: c.read_devices_ext("D300", 2, extension=_extension_for(c)),
            [_words(0x1111, 0x2222)],
        ),
        _ParityCase(
            "write_devices_ext",
            lambda c: c.write_devices_ext("D310", [0x1111, 0x2222], extension=_extension_for(c)),
            lambda c: c.write_devices_ext("D310", [0x1111, 0x2222], extension=_extension_for(c)),
            [b""],
        ),
        _ParityCase(
            "read_random",
            lambda c: c.read_random(word_devices=["D400"], dword_devices=["D500"]),
            lambda c: c.read_random(word_devices=["D400"], dword_devices=["D500"]),
            [_words(0x1111) + _dwords(0x12345678)],
        ),
        _ParityCase(
            "read_random_ext",
            lambda c: c.read_random_ext(
                word_devices=[("D410", _extension_for(c))],
                dword_devices=[("D510", _extension_for(c))],
            ),
            lambda c: c.read_random_ext(
                word_devices=[("D410", _extension_for(c))],
                dword_devices=[("D510", _extension_for(c))],
            ),
            [_words(0x1111) + _dwords(0x12345678)],
        ),
        _ParityCase(
            "write_random_words",
            lambda c: c.write_random_words(word_values=[("D420", 0x1111)], dword_values=[("D520", 0x12345678)]),
            lambda c: c.write_random_words(word_values=[("D420", 0x1111)], dword_values=[("D520", 0x12345678)]),
            [b""],
        ),
        _ParityCase(
            "write_random_words_ext",
            lambda c: c.write_random_words_ext(
                word_values=[("D430", 0x1111, _extension_for(c))],
                dword_values=[("D530", 0x12345678, _extension_for(c))],
            ),
            lambda c: c.write_random_words_ext(
                word_values=[("D430", 0x1111, _extension_for(c))],
                dword_values=[("D530", 0x12345678, _extension_for(c))],
            ),
            [b""],
        ),
        _ParityCase(
            "write_random_bits",
            lambda c: c.write_random_bits([("M100", True), ("M101", False)]),
            lambda c: c.write_random_bits([("M100", True), ("M101", False)]),
            [b""],
        ),
        _ParityCase(
            "write_random_bits_ext",
            lambda c: c.write_random_bits_ext([("M110", True, _extension_for(c)), ("M111", False, _extension_for(c))]),
            lambda c: c.write_random_bits_ext([("M110", True, _extension_for(c)), ("M111", False, _extension_for(c))]),
            [b""],
        ),
        _ParityCase(
            "register_monitor_devices",
            lambda c: c.register_monitor_devices(word_devices=["D600"], dword_devices=["D700"]),
            lambda c: c.register_monitor_devices(word_devices=["D600"], dword_devices=["D700"]),
            [b""],
        ),
        _ParityCase(
            "register_monitor_devices_ext",
            lambda c: c.register_monitor_devices_ext(
                word_devices=[("D610", _extension_for(c))],
                dword_devices=[("D710", _extension_for(c))],
            ),
            lambda c: c.register_monitor_devices_ext(
                word_devices=[("D610", _extension_for(c))],
                dword_devices=[("D710", _extension_for(c))],
            ),
            [b""],
        ),
        _ParityCase(
            "run_monitor_cycle",
            lambda c: c.run_monitor_cycle(word_points=1, dword_points=1),
            lambda c: c.run_monitor_cycle(word_points=1, dword_points=1),
            [_words(0x1111) + _dwords(0x12345678)],
        ),
        _ParityCase(
            "read_block",
            lambda c: c.read_block(word_blocks=[("D800", 2)], bit_blocks=[("M200", 1)]),
            lambda c: c.read_block(word_blocks=[("D800", 2)], bit_blocks=[("M200", 1)]),
            [_words(0x1111, 0x2222, 0x0001)],
        ),
        _ParityCase(
            "write_block",
            lambda c: c.write_block(word_blocks=[("D810", [0x1111, 0x2222])], bit_blocks=[("M210", [0x0001])]),
            lambda c: c.write_block(word_blocks=[("D810", [0x1111, 0x2222])], bit_blocks=[("M210", [0x0001])]),
            [b""],
        ),
        _ParityCase(
            "remote_run",
            lambda c: c.remote_run(force=True, clear_mode=1),
            lambda c: c.remote_run(force=True, clear_mode=1),
            [b""],
        ),
        _ParityCase(
            "remote_stop",
            lambda c: c.remote_stop(force=True),
            lambda c: c.remote_stop(force=True),
            [b""],
        ),
        _ParityCase(
            "remote_pause",
            lambda c: c.remote_pause(force=True),
            lambda c: c.remote_pause(force=True),
            [b""],
        ),
        _ParityCase(
            "remote_latch_clear",
            lambda c: c.remote_latch_clear(),
            lambda c: c.remote_latch_clear(),
            [b""],
        ),
        _ParityCase(
            "remote_reset_with_response",
            lambda c: c.remote_reset(subcommand=0x0001, expect_response=True),
            lambda c: c.remote_reset(subcommand=0x0001, expect_response=True),
            [b""],
        ),
        _ParityCase(
            "remote_reset_no_response",
            lambda c: c.remote_reset(expect_response=False),
            lambda c: c.remote_reset(expect_response=False),
            [],
        ),
        _ParityCase(
            "remote_password_lock",
            lambda c: c.remote_password_lock("ABC"),
            lambda c: c.remote_password_lock("ABC"),
            [b""],
        ),
        _ParityCase(
            "remote_password_unlock",
            lambda c: c.remote_password_unlock("ABC"),
            lambda c: c.remote_password_unlock("ABC"),
            [b""],
        ),
        _ParityCase(
            "self_test_loopback",
            lambda c: c.self_test_loopback(b"ABC"),
            lambda c: c.self_test_loopback(b"ABC"),
            [b"\x03\x00ABC"],
        ),
        _ParityCase(
            "read_type_name",
            lambda c: c.read_type_name(),
            lambda c: c.read_type_name(),
            [b"Q03UDVCPU".ljust(16, b"\x00") + (0x1234).to_bytes(2, "little")],
        ),
        _ParityCase(
            "read_cpu_operation_state",
            lambda c: c.read_cpu_operation_state(),
            lambda c: c.read_cpu_operation_state(),
            [_words(0x0001)],
        ),
        _ParityCase(
            "memory_read_words",
            lambda c: c.memory_read_words(0x1000, 2),
            lambda c: c.memory_read_words(0x1000, 2),
            [_words(0x1111, 0x2222)],
        ),
        _ParityCase(
            "memory_write_words",
            lambda c: c.memory_write_words(0x1000, [0x1111, 0x2222]),
            lambda c: c.memory_write_words(0x1000, [0x1111, 0x2222]),
            [b""],
        ),
        _ParityCase(
            "extend_unit_read_bytes",
            lambda c: c.extend_unit_read_bytes(0x2000, 4, 0x03E0),
            lambda c: c.extend_unit_read_bytes(0x2000, 4, 0x03E0),
            [b"\x01\x02\x03\x04"],
        ),
        _ParityCase(
            "extend_unit_write_bytes",
            lambda c: c.extend_unit_write_bytes(0x2000, 0x03E0, b"\x01\x02\x03\x04"),
            lambda c: c.extend_unit_write_bytes(0x2000, 0x03E0, b"\x01\x02\x03\x04"),
            [b""],
        ),
        _ParityCase(
            "cpu_buffer_read_bytes",
            lambda c: c.cpu_buffer_read_bytes(0x3000, 4),
            lambda c: c.cpu_buffer_read_bytes(0x3000, 4),
            [b"\x05\x06\x07\x08"],
        ),
        _ParityCase(
            "cpu_buffer_write_bytes",
            lambda c: c.cpu_buffer_write_bytes(0x3000, b"\x05\x06\x07\x08"),
            lambda c: c.cpu_buffer_write_bytes(0x3000, b"\x05\x06\x07\x08"),
            [b""],
        ),
        _ParityCase(
            "read_array_labels",
            lambda c: c.read_array_labels([LabelArrayReadPoint("LabelW", 1, 4)], abbreviation_labels=["Base"]),
            lambda c: c.read_array_labels([LabelArrayReadPoint("LabelW", 1, 4)], abbreviation_labels=["Base"]),
            [_label_array_read_response()],
        ),
        _ParityCase(
            "write_array_labels",
            lambda c: c.write_array_labels(
                [LabelArrayWritePoint("LabelW", 1, 4, b"DATA")],
                abbreviation_labels=["Base"],
            ),
            lambda c: c.write_array_labels(
                [LabelArrayWritePoint("LabelW", 1, 4, b"DATA")],
                abbreviation_labels=["Base"],
            ),
            [b""],
        ),
        _ParityCase(
            "read_random_labels",
            lambda c: c.read_random_labels(["LabelW"], abbreviation_labels=["Base"]),
            lambda c: c.read_random_labels(["LabelW"], abbreviation_labels=["Base"]),
            [_label_random_read_response()],
        ),
        _ParityCase(
            "write_random_labels",
            lambda c: c.write_random_labels(
                [LabelRandomWritePoint("LabelW", b"\x34\x12")],
                abbreviation_labels=["Base"],
            ),
            lambda c: c.write_random_labels(
                [LabelRandomWritePoint("LabelW", b"\x34\x12")],
                abbreviation_labels=["Base"],
            ),
            [b""],
        ),
    ]


class TestSyncAsyncRequestFrameParity(unittest.IsolatedAsyncioTestCase):
    async def test_sync_async_request_frames_match_for_representative_commands(self) -> None:
        profiles: Sequence[tuple[str, dict[str, object]]] = (
            ("iqr_4e", {"plc_family": "iq-r"}),
            (
                "ql_3e",
                {
                    "_allow_manual_profile": True,
                    "plc_series": PLCSeries.QL,
                    "frame_type": FrameType.FRAME_3E,
                },
            ),
        )
        for profile_name, profile_kwargs in profiles:
            for case in _parity_cases():
                with self.subTest(profile=profile_name, command=case.name):
                    sync_client = _SyncCaptureClient(case.responses, **profile_kwargs)
                    async_client = _AsyncCaptureClient(case.responses, **profile_kwargs)

                    case.sync_call(sync_client)
                    await case.async_call(async_client)

                    self.assertEqual(
                        [frame.hex(" ").upper() for frame in sync_client.frames],
                        [frame.hex(" ").upper() for frame in async_client.frames],
                    )
