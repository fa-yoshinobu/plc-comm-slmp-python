"""Regression tests for the approved 2026-08-01 Python contract changes."""

import asyncio
import gc
import warnings
from collections.abc import Callable
from unittest.mock import patch

import pytest

from slmp import _operations
from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.constants import PLCSeries
from slmp.core import SlmpTarget, _ExtensionSpec, _SlmpTraceFrame

_TARGET = SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0)
_WIRE_CASES = (
    (PLCSeries.QL, "melsec:qcpu:qj71e71-100", 0xFFFFFF),
    (PLCSeries.IQR, "melsec:iq-r", 0xFFFFFFFF),
)


def _read_request(device: str, points: int, *, bit_unit: bool, series: PLCSeries, profile: str):
    return _operations.build_read_devices_request(
        device,
        points,
        bit_unit=bit_unit,
        series=None,
        default_series=series,
        address_profile=profile,
    )


def _write_request(
    device: str,
    values: list[int] | list[bool],
    *,
    bit_unit: bool,
    series: PLCSeries,
    profile: str,
):
    return _operations.build_write_devices_request(
        device,
        values,
        bit_unit=bit_unit,
        series=None,
        default_series=series,
        address_profile=profile,
    )


@pytest.mark.parametrize(("series", "profile", "maximum"), _WIRE_CASES)
@pytest.mark.parametrize(("code", "bit_unit", "one_value"), (("D", False, 1), ("M", True, True)))
def test_direct_read_write_span_uses_selected_wire_width(
    series: PLCSeries,
    profile: str,
    maximum: int,
    code: str,
    bit_unit: bool,
    one_value: int | bool,
) -> None:
    address = f"{code}{maximum}"

    read_request = _read_request(address, 1, bit_unit=bit_unit, series=series, profile=profile)
    write_request = _write_request(
        address,
        [one_value],
        bit_unit=bit_unit,
        series=series,
        profile=profile,
    )
    width = 3 if series == PLCSeries.QL else 4
    assert read_request.payload[:width] == maximum.to_bytes(width, "little")
    assert write_request.payload[:width] == maximum.to_bytes(width, "little")

    with pytest.raises(ValueError, match="device span out of range"):
        _read_request(address, 2, bit_unit=bit_unit, series=series, profile=profile)
    with pytest.raises(ValueError, match="device span out of range"):
        _write_request(
            address,
            [one_value, one_value],
            bit_unit=bit_unit,
            series=series,
            profile=profile,
        )


@pytest.mark.parametrize(("series", "profile", "maximum"), _WIRE_CASES)
def test_dword_and_float32_span_consume_two_word_addresses(
    series: PLCSeries,
    profile: str,
    maximum: int,
) -> None:
    valid = f"D{maximum - 1}"
    invalid = f"D{maximum}"

    read_request = _operations.build_read_dwords_request(
        valid,
        1,
        series=None,
        default_series=series,
        address_profile=profile,
    )
    write_request = _operations.build_write_dwords_request(
        valid,
        [0x12345678],
        series=None,
        default_series=series,
        address_profile=profile,
    )
    float_request = _operations.build_write_float32s_request(
        valid,
        [1.25],
        series=None,
        default_series=series,
        address_profile=profile,
    )
    assert read_request.payload[-2:] == b"\x02\x00"
    assert write_request.payload[-4:] == b"\x78\x56\x34\x12"
    assert float_request.payload[-4:] == b"\x00\x00\xa0\x3f"

    for start, count in ((valid, 2), (invalid, 1)):
        with pytest.raises(ValueError, match="device span out of range"):
            _operations.build_read_dwords_request(
                start,
                count,
                series=None,
                default_series=series,
                address_profile=profile,
            )
    for start, values in ((valid, [1, 2]), (invalid, [1])):
        with pytest.raises(ValueError, match="device span out of range"):
            _operations.build_write_dwords_request(
                start,
                values,
                series=None,
                default_series=series,
                address_profile=profile,
            )
        with pytest.raises(ValueError, match="device span out of range"):
            _operations.build_write_float32s_request(
                start,
                [float(value) for value in values],
                series=None,
                default_series=series,
                address_profile=profile,
            )


@pytest.mark.parametrize(("series", "profile", "maximum"), _WIRE_CASES)
def test_word_unit_bit_device_routes_consume_sixteen_bits_per_word(
    series: PLCSeries,
    profile: str,
    maximum: int,
) -> None:
    valid_word = f"M{maximum - 15}"
    invalid_word = f"M{maximum - 14}"
    valid_dword = f"M{maximum - 31}"
    invalid_dword = f"M{maximum - 30}"

    _read_request(valid_word, 1, bit_unit=False, series=series, profile=profile)
    _write_request(valid_word, [1], bit_unit=False, series=series, profile=profile)
    _operations.build_read_dwords_request(
        valid_dword,
        1,
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_write_dwords_request(
        valid_dword,
        [1],
        series=None,
        default_series=series,
        address_profile=profile,
    )

    with pytest.raises(ValueError, match="device span out of range"):
        _read_request(invalid_word, 1, bit_unit=False, series=series, profile=profile)
    with pytest.raises(ValueError, match="device span out of range"):
        _write_request(invalid_word, [1], bit_unit=False, series=series, profile=profile)
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_dwords_request(
            invalid_dword,
            1,
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_write_dwords_request(
            invalid_dword,
            [1],
            series=None,
            default_series=series,
            address_profile=profile,
        )


@pytest.mark.parametrize(("series", "profile", "maximum"), _WIRE_CASES)
def test_random_and_monitor_dword_entries_consume_two_word_addresses(
    series: PLCSeries,
    profile: str,
    maximum: int,
) -> None:
    valid = f"D{maximum - 1}"
    invalid = f"D{maximum}"

    _operations.build_read_random_request(
        word_devices=(),
        dword_devices=(valid,),
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_write_random_words_request(
        word_values=(),
        dword_values=((valid, 1),),
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_register_monitor_devices_request(
        word_devices=(),
        dword_devices=(valid,),
        series=None,
        default_series=series,
        address_profile=profile,
    )

    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_random_request(
            word_devices=(),
            dword_devices=(invalid,),
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_write_random_words_request(
            word_values=(),
            dword_values=((invalid, 1),),
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_register_monitor_devices_request(
            word_devices=(),
            dword_devices=(invalid,),
            series=None,
            default_series=series,
            address_profile=profile,
        )


@pytest.mark.parametrize(("series", "profile", "maximum"), _WIRE_CASES)
def test_random_and_monitor_word_unit_bit_entries_use_packed_width(
    series: PLCSeries,
    profile: str,
    maximum: int,
) -> None:
    valid_word = f"M{maximum - 15}"
    invalid_word = f"M{maximum - 14}"
    valid_dword = f"M{maximum - 31}"
    invalid_dword = f"M{maximum - 30}"

    _operations.build_read_random_request(
        word_devices=(valid_word,),
        dword_devices=(valid_dword,),
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_write_random_words_request(
        word_values=((valid_word, 1),),
        dword_values=(),
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_write_random_words_request(
        word_values=(),
        dword_values=((valid_dword, 1),),
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_register_monitor_devices_request(
        word_devices=(valid_word,),
        dword_devices=(valid_dword,),
        series=None,
        default_series=series,
        address_profile=profile,
    )

    invalid_calls = (
        lambda: _operations.build_read_random_request(
            word_devices=(invalid_word,),
            dword_devices=(),
            series=None,
            default_series=series,
            address_profile=profile,
        ),
        lambda: _operations.build_read_random_request(
            word_devices=(),
            dword_devices=(invalid_dword,),
            series=None,
            default_series=series,
            address_profile=profile,
        ),
        lambda: _operations.build_write_random_words_request(
            word_values=((invalid_word, 1),),
            dword_values=(),
            series=None,
            default_series=series,
            address_profile=profile,
        ),
        lambda: _operations.build_write_random_words_request(
            word_values=(),
            dword_values=((invalid_dword, 1),),
            series=None,
            default_series=series,
            address_profile=profile,
        ),
        lambda: _operations.build_register_monitor_devices_request(
            word_devices=(invalid_word,),
            dword_devices=(),
            series=None,
            default_series=series,
            address_profile=profile,
        ),
        lambda: _operations.build_register_monitor_devices_request(
            word_devices=(),
            dword_devices=(invalid_dword,),
            series=None,
            default_series=series,
            address_profile=profile,
        ),
    )
    for call in invalid_calls:
        with pytest.raises(ValueError, match="device span out of range"):
            call()


@pytest.mark.parametrize(("series", "profile", "maximum"), _WIRE_CASES)
def test_block_word_and_bit_spans_use_protocol_consumed_width(
    series: PLCSeries,
    profile: str,
    maximum: int,
) -> None:
    valid_word = f"D{maximum}"
    valid_bit = f"M{maximum - 15}"

    _operations.build_read_block_request(
        word_blocks=((valid_word, 1),),
        bit_blocks=((valid_bit, 1),),
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_write_block_request(
        word_blocks=((valid_word, (1,)),),
        bit_blocks=((valid_bit, (1,)),),
        series=None,
        default_series=series,
        address_profile=profile,
    )

    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_block_request(
            word_blocks=((valid_word, 2),),
            bit_blocks=(),
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_write_block_request(
            word_blocks=((valid_word, (1, 2)),),
            bit_blocks=(),
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_block_request(
            word_blocks=(),
            bit_blocks=((f"M{maximum - 14}", 1),),
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_write_block_request(
            word_blocks=(),
            bit_blocks=((f"M{maximum - 14}", (1,)),),
            series=None,
            default_series=series,
            address_profile=profile,
        )


def test_long_timer_current_word_blocks_consume_one_device_per_four_words() -> None:
    maximum = 0xFFFFFFFF
    profile = "melsec:iq-r"

    _read_request(f"LTN{maximum}", 4, bit_unit=False, series=PLCSeries.IQR, profile=profile)
    _operations.build_read_block_request(
        word_blocks=((f"LSTN{maximum}", 4),),
        bit_blocks=(),
        series=None,
        default_series=PLCSeries.IQR,
        address_profile=profile,
    )

    with pytest.raises(ValueError, match="device span out of range"):
        _read_request(f"LTN{maximum}", 8, bit_unit=False, series=PLCSeries.IQR, profile=profile)
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_block_request(
            word_blocks=((f"LSTN{maximum}", 8),),
            bit_blocks=(),
            series=None,
            default_series=PLCSeries.IQR,
            address_profile=profile,
        )


@pytest.mark.parametrize("code", ("LTN", "LSTN", "LCN", "LZ"))
def test_native_random_dword_routes_consume_one_logical_device(code: str) -> None:
    maximum = 0xFFFFFFFF
    address = f"{code}{maximum}"

    _operations.build_read_random_request(
        word_devices=(),
        dword_devices=(address,),
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )
    _operations.build_write_random_words_request(
        word_values=(),
        dword_values=((address, 1),),
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )
    _operations.build_register_monitor_devices_request(
        word_devices=(),
        dword_devices=(address,),
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )


def test_random_write_overlap_uses_route_specific_consumed_widths() -> None:
    common = {
        "series": None,
        "default_series": PLCSeries.IQR,
        "address_profile": "melsec:iq-r",
    }

    _operations.build_write_random_words_request(
        word_values=(("M0", 1), ("M16", 2)),
        dword_values=(),
        **common,
    )
    _operations.build_write_random_words_request(
        word_values=(),
        dword_values=(("LCN0", 1), ("LCN1", 2)),
        **common,
    )

    with pytest.raises(ValueError, match="overlapping word destinations"):
        _operations.build_write_random_words_request(
            word_values=(("M0", 1), ("M1", 2)),
            dword_values=(),
            **common,
        )
    with pytest.raises(ValueError, match="overlapping word/dword destinations"):
        _operations.build_write_random_words_request(
            word_values=(("M16", 1),),
            dword_values=(("M0", 2),),
            **common,
        )


def test_extended_random_write_overlap_uses_packed_bit_width() -> None:
    common = {
        "series": None,
        "default_series": PLCSeries.IQR,
        "address_profile": "melsec:iq-r",
    }

    _operations.build_write_random_words_ext_request(
        word_values=((r"J2\M0", 1, _ExtensionSpec()), (r"J2\M16", 2, _ExtensionSpec())),
        dword_values=(),
        **common,
    )
    with pytest.raises(ValueError, match="overlapping word destinations"):
        _operations.build_write_random_words_ext_request(
            word_values=((r"J2\M0", 1, _ExtensionSpec()), (r"J2\M1", 2, _ExtensionSpec())),
            dword_values=(),
            **common,
        )
    with pytest.raises(ValueError, match="overlapping word/dword destinations"):
        _operations.build_write_random_words_ext_request(
            word_values=((r"J2\M16", 1, _ExtensionSpec()),),
            dword_values=((r"J2\M0", 2, _ExtensionSpec()),),
            **common,
        )


def test_block_write_overlap_retains_packed_bit_width() -> None:
    common = {
        "series": None,
        "default_series": PLCSeries.IQR,
        "address_profile": "melsec:iq-r",
    }
    _operations.build_write_block_request(
        word_blocks=(),
        bit_blocks=(("M0", (1,)), ("M16", (2,))),
        **common,
    )
    with pytest.raises(ValueError, match="overlapping bit destination range"):
        _operations.build_write_block_request(
            word_blocks=(),
            bit_blocks=(("M0", (1,)), ("M15", (2,))),
            **common,
        )


@pytest.mark.parametrize(
    ("series", "profile", "valid", "invalid"),
    (
        (PLCSeries.QL, "melsec:qcpu:qj71e71-100", r"U1\G16777214", r"U1\G16777215"),
        (PLCSeries.IQR, "melsec:iq-r", r"U1\G4294967294", r"U1\G4294967295"),
        (PLCSeries.IQR, "melsec:iq-r", r"J2\SWFFFFFE", r"J2\SWFFFFFF"),
    ),
)
def test_extended_direct_random_and_monitor_use_each_entry_wire_width(
    series: PLCSeries,
    profile: str,
    valid: str,
    invalid: str,
) -> None:
    _operations.build_read_devices_ext_request(
        valid,
        2,
        extension=_ExtensionSpec(),
        bit_unit=False,
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_write_devices_ext_request(
        valid,
        [1, 2],
        extension=_ExtensionSpec(),
        bit_unit=False,
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_read_random_ext_request(
        word_devices=(),
        dword_devices=((valid, _ExtensionSpec(), valid),),
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_write_random_words_ext_request(
        word_values=(),
        dword_values=((valid, 1, _ExtensionSpec()),),
        series=None,
        default_series=series,
        address_profile=profile,
    )
    _operations.build_register_monitor_devices_ext_request(
        word_devices=(),
        dword_devices=((valid, _ExtensionSpec()),),
        series=None,
        default_series=series,
        address_profile=profile,
    )

    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_devices_ext_request(
            invalid,
            2,
            extension=_ExtensionSpec(),
            bit_unit=False,
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_write_devices_ext_request(
            invalid,
            [1, 2],
            extension=_ExtensionSpec(),
            bit_unit=False,
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_random_ext_request(
            word_devices=(),
            dword_devices=((invalid, _ExtensionSpec(), invalid),),
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_write_random_words_ext_request(
            word_values=(),
            dword_values=((invalid, 1, _ExtensionSpec()),),
            series=None,
            default_series=series,
            address_profile=profile,
        )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_register_monitor_devices_ext_request(
            word_devices=(),
            dword_devices=((invalid, _ExtensionSpec()),),
            series=None,
            default_series=series,
            address_profile=profile,
        )


def test_link_direct_bit_span_uses_24_bit_device_number_width() -> None:
    _operations.build_read_devices_ext_request(
        r"J2\XFFFFFF",
        1,
        extension=_ExtensionSpec(),
        bit_unit=True,
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_devices_ext_request(
            r"J2\XFFFFFF",
            2,
            extension=_ExtensionSpec(),
            bit_unit=True,
            series=None,
            default_series=PLCSeries.IQR,
            address_profile="melsec:iq-r",
        )


def test_link_direct_word_unit_bit_span_uses_packed_width() -> None:
    _operations.build_read_devices_ext_request(
        r"J2\XFFFFF0",
        1,
        extension=_ExtensionSpec(),
        bit_unit=False,
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )
    with pytest.raises(ValueError, match="device span out of range"):
        _operations.build_read_devices_ext_request(
            r"J2\XFFFFF1",
            1,
            extension=_ExtensionSpec(),
            bit_unit=False,
            series=None,
            default_series=PLCSeries.IQR,
            address_profile="melsec:iq-r",
        )


@pytest.mark.parametrize(
    ("dword", "valid", "invalid"),
    (
        (False, r"J2\XFFFFF0", r"J2\XFFFFF1"),
        (True, r"J2\XFFFFE0", r"J2\XFFFFE1"),
    ),
)
def test_link_direct_random_and_monitor_bit_entries_use_packed_width(
    dword: bool,
    valid: str,
    invalid: str,
) -> None:
    word_devices = () if dword else ((valid, _ExtensionSpec(), valid),)
    dword_devices = ((valid, _ExtensionSpec(), valid),) if dword else ()
    word_values = () if dword else ((valid, 1, _ExtensionSpec()),)
    dword_values = ((valid, 1, _ExtensionSpec()),) if dword else ()
    monitor_words = () if dword else ((valid, _ExtensionSpec()),)
    monitor_dwords = ((valid, _ExtensionSpec()),) if dword else ()

    _operations.build_read_random_ext_request(
        word_devices=word_devices,
        dword_devices=dword_devices,
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )
    _operations.build_write_random_words_ext_request(
        word_values=word_values,
        dword_values=dword_values,
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )
    _operations.build_register_monitor_devices_ext_request(
        word_devices=monitor_words,
        dword_devices=monitor_dwords,
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )

    invalid_word_devices = () if dword else ((invalid, _ExtensionSpec(), invalid),)
    invalid_dword_devices = ((invalid, _ExtensionSpec(), invalid),) if dword else ()
    invalid_word_values = () if dword else ((invalid, 1, _ExtensionSpec()),)
    invalid_dword_values = ((invalid, 1, _ExtensionSpec()),) if dword else ()
    invalid_monitor_words = () if dword else ((invalid, _ExtensionSpec()),)
    invalid_monitor_dwords = ((invalid, _ExtensionSpec()),) if dword else ()
    invalid_calls = (
        lambda: _operations.build_read_random_ext_request(
            word_devices=invalid_word_devices,
            dword_devices=invalid_dword_devices,
            series=None,
            default_series=PLCSeries.IQR,
            address_profile="melsec:iq-r",
        ),
        lambda: _operations.build_write_random_words_ext_request(
            word_values=invalid_word_values,
            dword_values=invalid_dword_values,
            series=None,
            default_series=PLCSeries.IQR,
            address_profile="melsec:iq-r",
        ),
        lambda: _operations.build_register_monitor_devices_ext_request(
            word_devices=invalid_monitor_words,
            dword_devices=invalid_monitor_dwords,
            series=None,
            default_series=PLCSeries.IQR,
            address_profile="melsec:iq-r",
        ),
    )
    for call in invalid_calls:
        with pytest.raises(ValueError, match="device span out of range"):
            call()


@pytest.mark.parametrize(("_series", "profile", "maximum"), _WIRE_CASES)
def test_sync_span_rejection_precedes_request_frame_connection_and_counters(
    _series: PLCSeries,
    profile: str,
    maximum: int,
) -> None:
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=_TARGET,
        plc_profile=profile,
    )
    calls: tuple[Callable[[], object], ...] = (
        lambda: client.read_devices(f"D{maximum}", 2, bit_unit=False),
        lambda: client.write_devices(f"M{maximum}", [True, True], bit_unit=True),
        lambda: client.read_dwords(f"D{maximum}", 1),
        lambda: client.write_dwords(f"D{maximum - 1}", [1, 2]),
        lambda: client.read_float32s(f"D{maximum}", 1),
        lambda: client.write_float32s(f"D{maximum - 1}", [1.0, 2.0]),
    )

    initial_serial = client._serial
    initial_stats = client.traffic_stats()
    with patch("slmp.client.encode_request") as encode:
        for call in calls:
            with pytest.raises(ValueError, match="device span out of range"):
                call()
        encode.assert_not_called()
    assert client._serial == initial_serial
    assert client.traffic_stats() == initial_stats
    assert client._sock is None


def test_equivalent_span_rejection_precedes_sync_frame_connection_and_counters() -> None:
    maximum = 0xFFFFFFFF
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=_TARGET,
        plc_profile="melsec:iq-r",
    )
    calls: tuple[Callable[[], object], ...] = (
        lambda: client.read_random(dword_devices=(f"D{maximum}",)),
        lambda: client.write_random_words(dword_values=((f"D{maximum}", 1),)),
        lambda: client.register_monitor_devices(dword_devices=(f"D{maximum}",)),
        lambda: client.read_block(word_blocks=((f"D{maximum}", 2),)),
        lambda: client.write_block(bit_blocks=((f"M{maximum - 14}", (1,)),)),
        lambda: client.read_devices_ext(r"U1\G4294967295", 2, bit_unit=False),
        lambda: client.read_random_ext(dword_devices=(r"U1\G4294967295",)),
        lambda: client.write_random_words_ext(dword_values=((r"U1\G4294967295", 1),)),
        lambda: client.register_monitor_devices_ext(dword_devices=(r"U1\G4294967295",)),
    )

    initial_serial = client._serial
    initial_stats = client.traffic_stats()
    with patch("slmp.client.encode_request") as encode:
        for call in calls:
            with pytest.raises(ValueError, match="device span out of range"):
                call()
        encode.assert_not_called()
    assert client._serial == initial_serial
    assert client.traffic_stats() == initial_stats
    assert client._sock is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("_series", "profile", "maximum"), _WIRE_CASES)
async def test_async_span_rejection_precedes_request_frame_connection_and_counters(
    _series: PLCSeries,
    profile: str,
    maximum: int,
) -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=_TARGET,
        plc_profile=profile,
    )
    calls = (
        lambda: client.read_devices(f"D{maximum}", 2, bit_unit=False),
        lambda: client.write_devices(f"M{maximum}", [True, True], bit_unit=True),
        lambda: client.read_dwords(f"D{maximum}", 1),
        lambda: client.write_dwords(f"D{maximum - 1}", [1, 2]),
        lambda: client.read_float32s(f"D{maximum}", 1),
        lambda: client.write_float32s(f"D{maximum - 1}", [1.0, 2.0]),
    )

    initial_serial = client._serial
    initial_stats = client.traffic_stats()
    with patch("slmp.async_client.encode_request") as encode:
        for call in calls:
            with pytest.raises(ValueError, match="device span out of range"):
                await call()
        encode.assert_not_called()
    assert client._serial == initial_serial
    assert client.traffic_stats() == initial_stats
    assert client._reader is None
    assert client._writer is None


@pytest.mark.parametrize("address", (r"J２\SW10", r"J٢\SW10"))
def test_j_network_requires_ascii_digits_before_request_activity(address: str) -> None:
    client = SlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=_TARGET,
        plc_profile="melsec:iq-r",
    )
    initial_stats = client.traffic_stats()
    with patch("slmp.client._operations.build_read_devices_ext_request") as build:
        with pytest.raises(ValueError):
            client.read_devices_ext(address, 1, bit_unit=False)
        build.assert_not_called()
    assert client.traffic_stats() == initial_stats
    assert client._sock is None


@pytest.mark.asyncio
@pytest.mark.parametrize("address", (r"J２\SW10", r"J٢\SW10"))
async def test_async_j_network_requires_ascii_digits_before_request_activity(address: str) -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=_TARGET,
        plc_profile="melsec:iq-r",
    )
    initial_stats = client.traffic_stats()
    with patch("slmp.async_client._operations.build_read_devices_ext_request") as build:
        with pytest.raises(ValueError):
            await client.read_devices_ext(address, 1, bit_unit=False)
        build.assert_not_called()
    assert client.traffic_stats() == initial_stats
    assert client._reader is None
    assert client._writer is None


def test_j_network_accepts_ascii_decimal_digits() -> None:
    request = _operations.build_read_devices_ext_request(
        r"J2\SW10",
        1,
        extension=_ExtensionSpec(),
        bit_unit=False,
        series=None,
        default_series=PLCSeries.IQR,
        address_profile="melsec:iq-r",
    )
    assert request.payload[8] == 2


def _trace() -> _SlmpTraceFrame:
    return _SlmpTraceFrame(
        serial=1,
        command=0x0401,
        subcommand=0,
        request_data=b"request",
        request_frame=b"frame",
        response_frame=b"response",
        response_end_code=0,
        target=_TARGET,
        monitoring_timer=0x0010,
    )


def _async_client_with_trace(hook: Callable[[_SlmpTraceFrame], object]) -> AsyncSlmpClient:
    return AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=_TARGET,
        plc_profile="melsec:iq-r",
        _maintainer_trace_hook=hook,
    )


@pytest.mark.asyncio
async def test_async_trace_calls_sync_and_async_functions_once() -> None:
    sync_calls: list[_SlmpTraceFrame] = []
    async_calls: list[_SlmpTraceFrame] = []

    def sync_hook(trace: _SlmpTraceFrame) -> None:
        sync_calls.append(trace)

    async def async_hook(trace: _SlmpTraceFrame) -> None:
        await asyncio.sleep(0)
        async_calls.append(trace)

    trace = _trace()
    await _async_client_with_trace(sync_hook)._emit_trace(trace)
    await _async_client_with_trace(async_hook)._emit_trace(trace)
    assert sync_calls == [trace]
    assert async_calls == [trace]


@pytest.mark.asyncio
async def test_async_trace_awaits_async_callable_object_without_runtime_warning() -> None:
    class AsyncCallable:
        def __init__(self) -> None:
            self.calls = 0
            self.completed = False

        def __bool__(self) -> bool:
            return False

        async def __call__(self, _trace: _SlmpTraceFrame) -> None:
            self.calls += 1
            await asyncio.sleep(0)
            self.completed = True

    hook = AsyncCallable()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await _async_client_with_trace(hook)._emit_trace(_trace())
        gc.collect()
        await asyncio.sleep(0)

    assert hook.calls == 1
    assert hook.completed
    assert not [item for item in caught if issubclass(item.category, RuntimeWarning)]


@pytest.mark.asyncio
async def test_async_trace_sync_and_awaited_exceptions_are_diagnostic_only() -> None:
    sync_calls = 0
    async_calls = 0

    def sync_failure(_trace: _SlmpTraceFrame) -> None:
        nonlocal sync_calls
        sync_calls += 1
        raise ValueError("sync trace failure")

    async def async_failure(_trace: _SlmpTraceFrame) -> None:
        nonlocal async_calls
        async_calls += 1
        await asyncio.sleep(0)
        raise ValueError("async trace failure")

    await _async_client_with_trace(sync_failure)._emit_trace(_trace())
    await _async_client_with_trace(async_failure)._emit_trace(_trace())
    assert sync_calls == 1
    assert async_calls == 1
