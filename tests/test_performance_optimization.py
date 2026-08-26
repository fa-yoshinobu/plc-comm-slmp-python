from __future__ import annotations

import builtins
from unittest.mock import MagicMock, patch

import pytest

from slmp import _operations
from slmp.client import SlmpClient
from slmp.constants import FrameType, PLCSeries
from slmp.core import (
    SlmpResponse,
    SlmpTarget,
    _decode_response_view,
    _ExtensionSpec,
    decode_response,
    encode_request,
    parse_device,
)
from slmp.utils import poll_sync


def _response_3e(payload: bytes, *, end_code: int = 0) -> bytes:
    target = bytes([0x00, 0xFF, 0xFF, 0x03, 0x00])
    return b"\xd0\x00" + target + (len(payload) + 2).to_bytes(2, "little") + end_code.to_bytes(2, "little") + payload


def test_private_response_decode_views_payload_but_public_decode_owns_bytes() -> None:
    raw = _response_3e(b"\x34\x12")

    private = _decode_response_view(raw, frame_type=FrameType.FRAME_3E)
    public = decode_response(raw, frame_type=FrameType.FRAME_3E)

    assert isinstance(private.data, memoryview)
    assert private.data.obj is raw
    assert isinstance(public.data, bytes)
    assert public.data == b"\x34\x12"
    assert public.raw is raw

    private_error = _decode_response_view(
        _response_3e(b"", end_code=0xC051),
        frame_type=FrameType.FRAME_3E,
    )
    assert isinstance(private_error, SlmpResponse)
    assert isinstance(private_error.data, bytes)


def test_poll_prepares_payload_once_and_reuses_compact_decode_indexes() -> None:
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    client._request_decoded = MagicMock(side_effect=[([1], []), ([2], [])])  # type: ignore[method-assign]
    original = _operations.build_read_random_request

    with patch.object(_operations, "build_read_random_request", wraps=original) as build:
        snapshots = poll_sync(client, ["D100:U"], interval=0)
        assert next(snapshots) == {"D100:U": 1}
        assert next(snapshots) == {"D100:U": 2}

    assert build.call_count == 1
    first_payload = client._request_decoded.call_args_list[0].args[2]
    second_payload = client._request_decoded.call_args_list[1].args[2]
    assert first_payload is second_payload


@pytest.mark.parametrize("builder_name", ["read", "monitor", "write_words", "write_bits"])
def test_extended_random_and_monitor_builders_use_one_exact_final_buffer(builder_name: str) -> None:
    word = parse_device("D100", plc_profile="melsec:iq-r")
    bit = parse_device("M100", plc_profile="melsec:iq-r")
    extension = _ExtensionSpec()
    allocations: list[int] = []

    def allocate(size: int = 0) -> bytearray:
        allocations.append(size)
        return builtins.bytearray(size)

    with (
        patch.object(
            _operations,
            "_encode_resolved_extended_device_spec",
            side_effect=AssertionError("owned per-device spec must not be used"),
        ),
        patch.object(
            _operations,
            "_encode_resolved_extended_device_spec_into",
            wraps=_operations._encode_resolved_extended_device_spec_into,
        ) as encode_into,
        patch.object(_operations, "bytearray", side_effect=allocate, create=True),
    ):
        if builder_name == "read":
            request = _operations.build_read_random_ext_request(
                word_devices=[(word, extension, "D100")],
                dword_devices=[],
                series=None,
                default_series=PLCSeries.IQR,
                address_profile="melsec:iq-r",
            ).request
        elif builder_name == "monitor":
            request = _operations.build_register_monitor_devices_ext_request(
                word_devices=[(word, extension)],
                dword_devices=[],
                series=None,
                default_series=PLCSeries.IQR,
                address_profile="melsec:iq-r",
            )
        elif builder_name == "write_words":
            request = _operations.build_write_random_words_ext_request(
                word_values=[(word, 0x1234, extension)],
                dword_values=[],
                series=None,
                default_series=PLCSeries.IQR,
                address_profile="melsec:iq-r",
            )
        else:
            request = _operations.build_write_random_bits_ext_request(
                [(bit, True, extension)],
                series=None,
                default_series=PLCSeries.IQR,
                address_profile="melsec:iq-r",
            )

    assert len(allocations) == 1
    assert allocations[0] == len(request.payload)
    assert encode_into.call_count == 1
    assert isinstance(request.payload, memoryview)
    assert request.payload.readonly
    with pytest.raises(TypeError):
        request.payload[0] = 0
    frame = encode_request(
        frame_type=FrameType.FRAME_3E,
        serial=0,
        target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        monitoring_timer=16,
        command=request.command,
        subcommand=request.subcommand,
        data=request.payload,
    )
    assert frame.endswith(bytes(request.payload))


def test_extended_builder_does_not_allocate_final_buffer_before_validation_passes() -> None:
    word = parse_device("D100", plc_profile="melsec:iq-r")
    with (
        patch.object(_operations, "bytearray", wraps=builtins.bytearray, create=True) as allocate,
        patch.object(
            _operations,
            "_encode_resolved_extended_device_spec_into",
            wraps=_operations._encode_resolved_extended_device_spec_into,
        ) as encode_into,
        pytest.raises(ValueError, match=r"word_values\[0\]"),
    ):
        _operations.build_write_random_words_ext_request(
            word_values=[(word, 0x1_0000, _ExtensionSpec())],
            dword_values=[],
            series=None,
            default_series=PLCSeries.IQR,
            address_profile="melsec:iq-r",
        )

    allocate.assert_not_called()
    encode_into.assert_not_called()
