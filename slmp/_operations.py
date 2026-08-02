"""Private shared operation builders for sync and async clients."""

from __future__ import annotations

import math
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from .constants import DIRECT_MEMORY_LINK_DIRECT, Command, DeviceUnit, PLCSeries
from .core import (
    BlockReadResult,
    DeviceBlockResult,
    DeviceRef,
    LabelArrayReadPoint,
    LabelArrayReadResult,
    LabelArrayWritePoint,
    LabelRandomReadResult,
    LabelRandomWritePoint,
    MonitorResult,
    RandomReadResult,
    TypeNameInfo,
    _check_block_request_limits,
    _check_direct_device_points,
    _check_label_unit_specification,
    _check_points_u16,
    _check_random_bit_write_count,
    _check_random_read_like_counts,
    _check_random_write_word_counts,
    _check_temporarily_unsupported_device,
    _check_temporarily_unsupported_devices,
    _check_u16,
    _check_u32,
    _device_unit,
    _encode_label_name,
    _encode_remote_password_payload,
    _encode_resolved_extended_device_spec,
    _encode_resolved_extended_device_spec_into,
    _ExtensionSpec,
    _label_array_data_bytes,
    _label_array_wire_data_bytes,
    _normalize_items,
    _random_device_span_points,
    _require_explicit_plc_profile_for_xy,
    _require_write_bit,
    _require_write_u16,
    _require_write_u32,
    _resolve_extended_device_and_extension,
    _resolved_extended_device_spec_size,
    _SlmpDecodedResponse,
    _validate_block_read_devices,
    _validate_block_write_devices,
    _validate_block_write_ranges,
    _validate_device_span,
    _validate_direct_dword_read_device,
    _validate_direct_read_device,
    _validate_direct_write_device,
    _validate_monitor_register_devices,
    _validate_random_read_devices,
    _validate_random_write_bit_devices,
    _validate_random_write_word_devices,
    _validate_request_payload_length,
    _warn_boundary_behavior,
    _warn_practical_device_path,
    decode_device_dwords,
    decode_device_words,
    encode_device_spec,
    pack_bit_values,
    parse_device,
    resolve_device_subcommand,
    unpack_bit_values,
)
from .errors import SlmpError


@dataclass(frozen=True)
class OperationRequest:
    """Encoded SLMP operation request ready for transport."""

    command: Command
    subcommand: int
    payload: bytes | memoryview


def _freeze_owned_payload(payload: bytearray) -> memoryview:
    """Expose one privately owned final buffer as a read-only zero-copy view."""
    return memoryview(payload).toreadonly()


@dataclass(frozen=True)
class RandomReadOperation:
    """Random-read request plus the refs needed to decode the response."""

    request: OperationRequest
    word_refs: tuple[DeviceRef, ...]
    dword_refs: tuple[DeviceRef, ...]
    word_keys: tuple[str, ...]
    dword_keys: tuple[str, ...]


@dataclass(frozen=True)
class BlockReadOperation:
    """Block-read request plus block metadata needed to decode the response."""

    request: OperationRequest
    word_blocks: tuple[tuple[DeviceRef, int], ...]
    bit_blocks: tuple[tuple[DeviceRef, int], ...]


def _effective_series(series: PLCSeries | str | None, default_series: PLCSeries) -> PLCSeries:
    return PLCSeries(series) if series is not None else default_series


def _extended_subcommand_series(
    effective_series: PLCSeries,
    *,
    has_link_direct: bool,
    has_other_layout: bool,
    operation: str,
) -> PLCSeries:
    if effective_series == PLCSeries.IQR and has_link_direct and has_other_layout:
        raise ValueError(
            f"{operation} cannot mix J link-direct Q/L entries with 13-byte iQ-R extended entries in one request"
        )
    return PLCSeries.QL if has_link_direct else effective_series


def _extended_wire_series(effective_series: PLCSeries, extension: _ExtensionSpec) -> PLCSeries:
    """Return the device-number width used by one Extended Device entry."""
    if extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        return PLCSeries.QL
    return effective_series


def _word_unit_device_span_points(
    ref: DeviceRef,
    word_points: int,
    *,
    long_current_block: bool = False,
) -> int:
    """Convert transferred word points to addresses consumed by the device family."""
    if long_current_block and ref.code in {"LTN", "LSTN"}:
        return (word_points + 3) // 4
    if _device_unit(ref) == DeviceUnit.BIT:
        return word_points * 16
    return word_points


def _direct_device_span_points(ref: DeviceRef, points: int, *, bit_unit: bool) -> int:
    return points if bit_unit else _word_unit_device_span_points(ref, points, long_current_block=True)


def _validate_random_result_keys(word_keys: Sequence[str], dword_keys: Sequence[str]) -> None:
    """Reject collisions before a dict-shaped random-read result can lose values."""
    if len(set(word_keys)) != len(word_keys):
        raise ValueError("word_devices must not contain duplicate wire targets")
    if len(set(dword_keys)) != len(dword_keys):
        raise ValueError("dword_devices must not contain duplicate wire targets")
    overlap = set(word_keys).intersection(dword_keys)
    if overlap:
        raise ValueError(f"word_devices and dword_devices must not overlap: {sorted(overlap)!r}")


def _require_bit_unit(bit_unit: object, operation: str) -> bool:
    if type(bit_unit) is not bool:
        raise ValueError(f"{operation} bit_unit is required and must be a boolean")
    return bit_unit


def _validate_long_timer_range(head_no: object, points: object, plc_profile: object) -> tuple[int, int]:
    if type(head_no) is not int:
        raise TypeError("head_no is required and must be an integer")
    _check_u32(head_no, "head_no")
    if type(points) is not int:
        raise TypeError("points is required and must be an integer")
    word_points = points * 4
    _check_direct_device_points(
        word_points,
        bit_unit=False,
        name="long timer",
        plc_profile=plc_profile,
    )
    return head_no, word_points


def _parse_device_for_address_profile(device: str | DeviceRef, address_profile: object | None) -> DeviceRef:
    ref = parse_device(device, plc_profile=address_profile)
    return _require_explicit_plc_profile_for_xy(device, address_profile, ref)


def _resolve_extended_device_for_family(
    device: str | DeviceRef,
    extension: _ExtensionSpec,
    address_profile: object | None,
) -> tuple[DeviceRef, _ExtensionSpec]:
    ref, effective_extension = _resolve_extended_device_and_extension(device, extension, plc_profile=address_profile)
    return _require_explicit_plc_profile_for_xy(device, address_profile, ref), effective_extension


def build_read_devices_request(
    device: str | DeviceRef,
    points: int,
    *,
    bit_unit: bool,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a direct device read request."""

    bit_unit = _require_bit_unit(bit_unit, "read_devices")
    _check_direct_device_points(
        points,
        bit_unit=bit_unit,
        name="read_devices",
        plc_profile=address_profile,
    )
    effective_series = _effective_series(series, default_series)
    ref = _parse_device_for_address_profile(device, address_profile)
    _validate_direct_read_device(ref, points=points, bit_unit=bit_unit)
    _validate_device_span(
        ref,
        points=_direct_device_span_points(ref, points, bit_unit=bit_unit),
        series=effective_series,
        operation="read_devices",
    )
    _check_temporarily_unsupported_device(ref)
    _warn_practical_device_path(ref, series=effective_series, access_kind="direct")
    _warn_boundary_behavior(
        ref,
        series=effective_series,
        points=points,
        write=False,
        bit_unit=bit_unit,
        access_kind="direct",
    )
    subcommand = resolve_device_subcommand(bit_unit=bit_unit, series=effective_series, extension=False)
    payload = encode_device_spec(ref, series=effective_series) + points.to_bytes(2, "little")
    return OperationRequest(Command.DEVICE_READ, subcommand, payload)


def decode_read_devices_response(
    response: _SlmpDecodedResponse,
    *,
    points: int,
    bit_unit: bool,
) -> list[int] | list[bool]:
    """Decode a direct device read response into word or bit values."""

    if response.end_code != 0:
        raise SlmpError(
            f"device read failed with end_code=0x{response.end_code:04X}",
            end_code=response.end_code,
            data=bytes(response.data),
            error_info=response.error_info,
        )
    if bit_unit:
        return unpack_bit_values(response.data, points)
    words = decode_device_words(response.data)
    if len(words) != points:
        raise SlmpError(f"word count mismatch: expected={points}, actual={len(words)}")
    return words


def build_write_devices_request(
    device: str | DeviceRef,
    values: Sequence[int | bool],
    *,
    bit_unit: bool,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a direct device write request."""

    bit_unit = _require_bit_unit(bit_unit, "write_devices")
    if not values:
        raise ValueError("values must not be empty")
    _check_direct_device_points(
        len(values),
        bit_unit=bit_unit,
        name="write_devices",
        write=True,
        plc_profile=address_profile,
    )
    effective_series = _effective_series(series, default_series)
    ref = _parse_device_for_address_profile(device, address_profile)
    _validate_direct_write_device(ref, bit_unit=bit_unit, plc_profile=address_profile)
    _validate_device_span(
        ref,
        points=_direct_device_span_points(ref, len(values), bit_unit=bit_unit),
        series=effective_series,
        operation="write_devices",
    )
    _check_temporarily_unsupported_device(ref)
    _warn_practical_device_path(ref, series=effective_series, access_kind="direct")
    _warn_boundary_behavior(
        ref,
        series=effective_series,
        points=len(values),
        write=True,
        bit_unit=bit_unit,
        access_kind="direct",
    )
    subcommand = resolve_device_subcommand(bit_unit=bit_unit, series=effective_series, extension=False)
    payload = bytearray()
    payload += encode_device_spec(ref, series=effective_series)
    payload += len(values).to_bytes(2, "little")
    if bit_unit:
        # pack_bit_values performs the exact-bool runtime check; this cast only
        # narrows the shared word/bit builder's static type after bit_unit chose
        # the Boolean branch.
        payload += pack_bit_values(cast(Sequence[bool], values))
    else:
        for index, value in enumerate(values):
            payload += _require_write_u16(value, f"values[{index}]").to_bytes(2, "little", signed=False)
    return OperationRequest(Command.DEVICE_WRITE, subcommand, bytes(payload))


def build_read_dwords_request(
    device: str | DeviceRef,
    count: int,
    *,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a direct dword read request using word-unit transfer."""

    if count < 1:
        raise ValueError("count must be >= 1")
    ref = _parse_device_for_address_profile(device, address_profile)
    _validate_direct_dword_read_device(ref)
    return build_read_devices_request(
        ref,
        count * 2,
        bit_unit=False,
        series=series,
        default_series=default_series,
        address_profile=address_profile,
    )


def decode_read_dwords_response(response: _SlmpDecodedResponse, *, count: int) -> list[int]:
    """Decode a direct dword read response into unsigned 32-bit values."""

    words = [int(value) for value in decode_read_devices_response(response, points=count * 2, bit_unit=False)]
    values: list[int] = []
    for offset in range(0, len(words), 2):
        values.append(words[offset] | (words[offset + 1] << 16))
    return values


def build_write_dwords_request(
    device: str | DeviceRef,
    values: Sequence[int],
    *,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a direct dword write request using word-unit transfer."""

    if not values:
        raise ValueError("values must not be empty")
    words: list[int] = []
    for index, value in enumerate(values):
        bits = _require_write_u32(value, f"values[{index}]")
        words.append(bits & 0xFFFF)
        words.append((bits >> 16) & 0xFFFF)
    return build_write_devices_request(
        device,
        words,
        bit_unit=False,
        series=series,
        default_series=default_series,
        address_profile=address_profile,
    )


def decode_read_float32s_response(response: _SlmpDecodedResponse, *, count: int) -> list[float]:
    """Decode a dword read response as little-endian float32 values."""

    values: list[float] = []
    for bits in decode_read_dwords_response(response, count=count):
        values.append(struct.unpack("<f", struct.pack("<I", bits))[0])
    return values


def build_write_float32s_request(
    device: str | DeviceRef,
    values: Sequence[float],
    *,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a direct float32 write request using dword transfer."""

    dwords: list[int] = []
    for index, value in enumerate(values):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"values[{index}] must be a finite int or float: {value!r}")
        try:
            dwords.append(struct.unpack("<I", struct.pack("<f", value))[0])
        except (OverflowError, struct.error) as error:
            raise ValueError(f"values[{index}] is outside the finite float32 range: {value!r}") from error
    return build_write_dwords_request(
        device,
        dwords,
        series=series,
        default_series=default_series,
        address_profile=address_profile,
    )


def build_read_devices_ext_request(
    device: str | DeviceRef,
    points: int,
    *,
    extension: _ExtensionSpec,
    bit_unit: bool,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
    enforce_semantic_unit: bool = True,
) -> OperationRequest:
    """Build an extended-device direct read request."""

    bit_unit = _require_bit_unit(bit_unit, "read_devices_ext")
    _check_direct_device_points(
        points,
        bit_unit=bit_unit,
        name="read_devices_ext",
        plc_profile=address_profile,
    )
    effective_series = _effective_series(series, default_series)
    ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
    _validate_direct_read_device(
        ref,
        points=points,
        bit_unit=bit_unit,
        enforce_semantic_unit=enforce_semantic_unit,
    )
    _check_temporarily_unsupported_device(ref, access_kind="extended_device")
    if effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        effective_series = PLCSeries.QL
    _validate_device_span(
        ref,
        points=_direct_device_span_points(ref, points, bit_unit=bit_unit),
        series=effective_series,
        operation="read_devices_ext",
    )
    _warn_practical_device_path(ref, series=effective_series, access_kind="extended_device")
    subcommand = resolve_device_subcommand(bit_unit=bit_unit, series=effective_series, extension=True)
    payload = bytearray()
    payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
    payload += points.to_bytes(2, "little")
    return OperationRequest(Command.DEVICE_READ, subcommand, bytes(payload))


def build_write_devices_ext_request(
    device: str | DeviceRef,
    values: Sequence[int | bool],
    *,
    extension: _ExtensionSpec,
    bit_unit: bool,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
    enforce_semantic_unit: bool = True,
) -> OperationRequest:
    """Build an extended-device direct write request."""

    bit_unit = _require_bit_unit(bit_unit, "write_devices_ext")
    if not values:
        raise ValueError("values must not be empty")
    _check_direct_device_points(
        len(values),
        bit_unit=bit_unit,
        name="write_devices_ext",
        write=True,
        plc_profile=address_profile,
    )
    effective_series = _effective_series(series, default_series)
    ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
    _validate_direct_write_device(
        ref,
        bit_unit=bit_unit,
        plc_profile=address_profile,
        enforce_semantic_unit=enforce_semantic_unit,
    )
    _check_temporarily_unsupported_device(ref, access_kind="extended_device")
    if effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        effective_series = PLCSeries.QL
    _validate_device_span(
        ref,
        points=_direct_device_span_points(ref, len(values), bit_unit=bit_unit),
        series=effective_series,
        operation="write_devices_ext",
    )
    _warn_practical_device_path(ref, series=effective_series, access_kind="extended_device")
    subcommand = resolve_device_subcommand(bit_unit=bit_unit, series=effective_series, extension=True)
    payload = bytearray()
    payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
    payload += len(values).to_bytes(2, "little")
    if bit_unit:
        payload += pack_bit_values(cast(Sequence[bool], values))
    else:
        for index, value in enumerate(values):
            payload += _require_write_u16(value, f"values[{index}]").to_bytes(2, "little", signed=False)
    return OperationRequest(Command.DEVICE_WRITE, subcommand, bytes(payload))


def build_register_monitor_devices_request(
    *,
    word_devices: Sequence[str | DeviceRef],
    dword_devices: Sequence[str | DeviceRef],
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a monitor registration request for direct devices."""

    if not word_devices and not dword_devices:
        raise ValueError("word_devices and dword_devices must not both be empty")
    if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
        raise ValueError("word_devices and dword_devices must be <= 255 each")
    effective_series = _effective_series(series, default_series)
    _check_random_read_like_counts(
        len(word_devices),
        len(dword_devices),
        series=effective_series,
        name="register_monitor_devices",
        plc_profile=address_profile,
        limit_key="monitor_register_word",
    )
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=False)

    payload = bytearray([len(word_devices), len(dword_devices)])
    word_refs: list[DeviceRef] = []
    dword_refs: list[DeviceRef] = []
    for dev in word_devices:
        ref = _parse_device_for_address_profile(dev, address_profile)
        _check_temporarily_unsupported_device(ref)
        _validate_monitor_register_devices([ref], [])
        _validate_device_span(
            ref,
            points=_random_device_span_points(ref, dword=False),
            series=effective_series,
            operation="register_monitor_devices",
        )
        payload += encode_device_spec(ref, series=effective_series)
        word_refs.append(ref)
    for dev in dword_devices:
        ref = _parse_device_for_address_profile(dev, address_profile)
        _check_temporarily_unsupported_device(ref)
        _validate_monitor_register_devices([], [ref])
        _validate_device_span(
            ref,
            points=_random_device_span_points(ref, dword=True),
            series=effective_series,
            operation="register_monitor_devices",
        )
        payload += encode_device_spec(ref, series=effective_series)
        dword_refs.append(ref)
    _validate_monitor_register_devices(word_refs, dword_refs)
    return OperationRequest(Command.DEVICE_ENTRY_MONITOR, subcommand, bytes(payload))


def build_register_monitor_devices_ext_request(
    *,
    word_devices: Sequence[tuple[str | DeviceRef, _ExtensionSpec]],
    dword_devices: Sequence[tuple[str | DeviceRef, _ExtensionSpec]],
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a monitor registration request for extended devices."""

    if not word_devices and not dword_devices:
        raise ValueError("word_devices and dword_devices must not both be empty")
    if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
        raise ValueError("word_devices and dword_devices must be <= 255 each")
    effective_series = _effective_series(series, default_series)
    _check_random_read_like_counts(
        len(word_devices),
        len(dword_devices),
        series=effective_series,
        name="register_monitor_devices_ext",
        extension=True,
        plc_profile=address_profile,
        limit_key="monitor_register_word",
    )
    word_refs: list[DeviceRef] = []
    dword_refs: list[DeviceRef] = []
    word_extensions: list[_ExtensionSpec] = []
    dword_extensions: list[_ExtensionSpec] = []
    link_direct = False
    other_layout = False
    payload_length = 2
    for dev, ext in word_devices:
        ref, effective_extension = _resolve_extended_device_for_family(dev, ext, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _validate_monitor_register_devices([ref], [])
        word_refs.append(ref)
        word_extensions.append(effective_extension)
        is_link_direct = effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT
        link_direct = link_direct or is_link_direct
        other_layout = other_layout or not is_link_direct
        _validate_device_span(
            ref,
            points=_random_device_span_points(ref, dword=False),
            series=_extended_wire_series(effective_series, effective_extension),
            operation="register_monitor_devices_ext",
        )
        payload_length += _resolved_extended_device_spec_size(
            series=effective_series,
            extension=effective_extension,
        )
    for dev, ext in dword_devices:
        ref, effective_extension = _resolve_extended_device_for_family(dev, ext, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _validate_monitor_register_devices([], [ref])
        dword_refs.append(ref)
        dword_extensions.append(effective_extension)
        is_link_direct = effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT
        link_direct = link_direct or is_link_direct
        other_layout = other_layout or not is_link_direct
        _validate_device_span(
            ref,
            points=_random_device_span_points(ref, dword=True),
            series=_extended_wire_series(effective_series, effective_extension),
            operation="register_monitor_devices_ext",
        )
        payload_length += _resolved_extended_device_spec_size(
            series=effective_series,
            extension=effective_extension,
        )
    _validate_monitor_register_devices(word_refs, dword_refs)
    subcommand = resolve_device_subcommand(
        bit_unit=False,
        series=_extended_subcommand_series(
            effective_series,
            has_link_direct=link_direct,
            has_other_layout=other_layout,
            operation="register_monitor_devices_ext",
        ),
        extension=True,
    )
    payload = bytearray(payload_length)
    payload[0] = len(word_devices)
    payload[1] = len(dword_devices)
    offset = 2
    for ref, extension in zip(word_refs, word_extensions, strict=True):
        offset += _encode_resolved_extended_device_spec_into(
            ref,
            series=effective_series,
            extension=extension,
            output=payload,
            offset=offset,
        )
    for ref, extension in zip(dword_refs, dword_extensions, strict=True):
        offset += _encode_resolved_extended_device_spec_into(
            ref,
            series=effective_series,
            extension=extension,
            output=payload,
            offset=offset,
        )
    assert offset == len(payload)
    return OperationRequest(Command.DEVICE_ENTRY_MONITOR, subcommand, _freeze_owned_payload(payload))


def build_run_monitor_cycle_request(
    *,
    word_points: int,
    dword_points: int,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a monitor execution request for registered monitor points."""

    if type(word_points) is not int or type(dword_points) is not int:
        raise ValueError("word_points and dword_points must be integers")
    _check_random_read_like_counts(
        word_points,
        dword_points,
        series=default_series,
        name="run_monitor_cycle",
        plc_profile=address_profile,
        limit_key="monitor_register_word",
    )
    return OperationRequest(Command.DEVICE_EXECUTE_MONITOR, 0x0000, b"")


def decode_run_monitor_cycle_response(
    response: _SlmpDecodedResponse,
    *,
    word_points: int,
    dword_points: int,
) -> MonitorResult:
    """Decode monitor execution data into word and dword result lists."""

    expected = word_points * 2 + dword_points * 4
    if len(response.data) != expected:
        raise SlmpError(f"monitor response size mismatch: expected={expected}, actual={len(response.data)}")
    offset = 0
    words = decode_device_words(response.data[offset : offset + word_points * 2])
    offset += word_points * 2
    dwords = decode_device_dwords(response.data[offset:])
    return MonitorResult(word=words, dword=dwords)


def build_read_type_name_request() -> OperationRequest:
    """Build a PLC type-name read request."""

    return OperationRequest(Command.READ_TYPE_NAME, 0x0000, b"")


def decode_read_type_name_response(response: _SlmpDecodedResponse) -> TypeNameInfo:
    """Decode a type-name response into model text and model code metadata."""

    data = response.data
    model = ""
    model_code = None
    if len(data) >= 16:
        model = bytes(data[:16]).split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
    if len(data) >= 18:
        model_code = int.from_bytes(data[16:18], "little")
    return TypeNameInfo(raw=bytes(data), model=model, model_code=model_code)


def build_remote_run_request(*, force: bool, clear_mode: int) -> OperationRequest:
    """Build a remote RUN request."""

    if clear_mode not in {0, 1, 2}:
        raise ValueError(f"clear_mode must be one of 0,1,2: {clear_mode}")
    mode = 0x0003 if force else 0x0001
    payload = mode.to_bytes(2, "little") + clear_mode.to_bytes(2, "little")
    return OperationRequest(Command.REMOTE_RUN, 0x0000, payload)


def build_remote_stop_request() -> OperationRequest:
    """Build a remote STOP request."""

    return OperationRequest(Command.REMOTE_STOP, 0x0000, b"\x01\x00")


def build_remote_pause_request(*, force: bool) -> OperationRequest:
    """Build a remote PAUSE request."""

    mode = 0x0003 if force else 0x0001
    return OperationRequest(Command.REMOTE_PAUSE, 0x0000, mode.to_bytes(2, "little"))


def build_remote_latch_clear_request() -> OperationRequest:
    """Build a remote latch-clear request."""

    return OperationRequest(Command.REMOTE_LATCH_CLEAR, 0x0000, b"\x01\x00")


def build_clear_error_request() -> OperationRequest:
    """Build the fixed Clear Error request."""

    return OperationRequest(Command.CLEAR_ERROR, 0x0000, b"")


def build_remote_reset_request(*, subcommand: int) -> OperationRequest:
    """Build a remote RESET request."""

    if subcommand != 0x0000:
        raise ValueError(f"remote reset subcommand must be 0x0000: 0x{subcommand:04X}")
    return OperationRequest(Command.REMOTE_RESET, subcommand, b"\x01\x00")


def build_remote_password_lock_request(
    password: str,
    *,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
) -> OperationRequest:
    """Build a remote-password lock request."""

    effective_series = _effective_series(series, default_series)
    payload = _encode_remote_password_payload(password, series=effective_series)
    return OperationRequest(Command.REMOTE_PASSWORD_LOCK, 0x0000, payload)


def build_remote_password_unlock_request(
    password: str,
    *,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
) -> OperationRequest:
    """Build a remote-password unlock request."""

    effective_series = _effective_series(series, default_series)
    payload = _encode_remote_password_payload(password, series=effective_series)
    return OperationRequest(Command.REMOTE_PASSWORD_UNLOCK, 0x0000, payload)


def build_read_random_request(
    *,
    word_devices: Sequence[str | DeviceRef],
    dword_devices: Sequence[str | DeviceRef],
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> RandomReadOperation:
    """Build a random word/dword read request for direct devices."""

    if not word_devices and not dword_devices:
        raise ValueError("word_devices and dword_devices must not both be empty")
    if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
        raise ValueError("word_devices and dword_devices must be <= 255 each")
    effective_series = _effective_series(series, default_series)
    _check_random_read_like_counts(
        len(word_devices),
        len(dword_devices),
        series=effective_series,
        name="read_random",
        plc_profile=address_profile,
    )
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=False)

    words = [_parse_device_for_address_profile(device, address_profile) for device in word_devices]
    dwords = [_parse_device_for_address_profile(device, address_profile) for device in dword_devices]
    _validate_random_read_devices(words, dwords)
    word_keys = tuple(str(device) for device in words)
    dword_keys = tuple(str(device) for device in dwords)
    _validate_random_result_keys(word_keys, dword_keys)
    _check_temporarily_unsupported_devices(words)
    _check_temporarily_unsupported_devices(dwords)
    for device in words:
        _validate_device_span(
            device,
            points=_random_device_span_points(device, dword=False),
            series=effective_series,
            operation="read_random",
        )
    for device in dwords:
        _validate_device_span(
            device,
            points=_random_device_span_points(device, dword=True),
            series=effective_series,
            operation="read_random",
        )

    payload = bytearray([len(words), len(dwords)])
    for device in words:
        payload += encode_device_spec(device, series=effective_series)
    for device in dwords:
        payload += encode_device_spec(device, series=effective_series)
    return RandomReadOperation(
        request=OperationRequest(Command.DEVICE_READ_RANDOM, subcommand, bytes(payload)),
        word_refs=tuple(words),
        dword_refs=tuple(dwords),
        word_keys=word_keys,
        dword_keys=dword_keys,
    )


def build_read_random_ext_request(
    *,
    word_devices: Sequence[tuple[str | DeviceRef, _ExtensionSpec, str]],
    dword_devices: Sequence[tuple[str | DeviceRef, _ExtensionSpec, str]],
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> RandomReadOperation:
    """Build a random word/dword read request for extended devices."""

    if not word_devices and not dword_devices:
        raise ValueError("word_devices and dword_devices must not both be empty")
    if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
        raise ValueError("word_devices and dword_devices must be <= 255 each")
    effective_series = _effective_series(series, default_series)
    _check_random_read_like_counts(
        len(word_devices),
        len(dword_devices),
        series=effective_series,
        name="read_random_ext",
        extension=True,
        plc_profile=address_profile,
    )
    words: list[DeviceRef] = []
    dwords: list[DeviceRef] = []
    word_extensions: list[_ExtensionSpec] = []
    dword_extensions: list[_ExtensionSpec] = []
    word_keys: list[str] = []
    dword_keys: list[str] = []
    link_direct = False
    other_layout = False
    payload_length = 2
    for device, extension, result_key in word_devices:
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _validate_random_read_devices([ref], [])
        words.append(ref)
        word_extensions.append(effective_extension)
        word_keys.append(result_key)
        is_link_direct = effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT
        link_direct = link_direct or is_link_direct
        other_layout = other_layout or not is_link_direct
        _validate_device_span(
            ref,
            points=_random_device_span_points(ref, dword=False),
            series=_extended_wire_series(effective_series, effective_extension),
            operation="read_random_ext",
        )
        payload_length += _resolved_extended_device_spec_size(
            series=effective_series,
            extension=effective_extension,
        )
    for device, extension, result_key in dword_devices:
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _validate_random_read_devices([], [ref])
        dwords.append(ref)
        dword_extensions.append(effective_extension)
        dword_keys.append(result_key)
        is_link_direct = effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT
        link_direct = link_direct or is_link_direct
        other_layout = other_layout or not is_link_direct
        _validate_device_span(
            ref,
            points=_random_device_span_points(ref, dword=True),
            series=_extended_wire_series(effective_series, effective_extension),
            operation="read_random_ext",
        )
        payload_length += _resolved_extended_device_spec_size(
            series=effective_series,
            extension=effective_extension,
        )
    _validate_random_read_devices(words, dwords)
    _validate_random_result_keys(word_keys, dword_keys)
    subcommand = resolve_device_subcommand(
        bit_unit=False,
        series=_extended_subcommand_series(
            effective_series,
            has_link_direct=link_direct,
            has_other_layout=other_layout,
            operation="read_random_ext",
        ),
        extension=True,
    )
    payload = bytearray(payload_length)
    payload[0] = len(word_devices)
    payload[1] = len(dword_devices)
    offset = 2
    for ref, extension in zip(words, word_extensions, strict=True):
        offset += _encode_resolved_extended_device_spec_into(
            ref,
            series=effective_series,
            extension=extension,
            output=payload,
            offset=offset,
        )
    for ref, extension in zip(dwords, dword_extensions, strict=True):
        offset += _encode_resolved_extended_device_spec_into(
            ref,
            series=effective_series,
            extension=extension,
            output=payload,
            offset=offset,
        )
    assert offset == len(payload)
    return RandomReadOperation(
        request=OperationRequest(Command.DEVICE_READ_RANDOM, subcommand, _freeze_owned_payload(payload)),
        word_refs=tuple(words),
        dword_refs=tuple(dwords),
        word_keys=tuple(word_keys),
        dword_keys=tuple(dword_keys),
    )


def decode_read_random_response(response: _SlmpDecodedResponse, operation: RandomReadOperation) -> RandomReadResult:
    """Decode a random read response using its original operation metadata."""

    expected = len(operation.word_refs) * 2 + len(operation.dword_refs) * 4
    if len(response.data) != expected:
        raise SlmpError(f"random read response size mismatch: expected={expected}, actual={len(response.data)}")

    offset = 0
    word_values = decode_device_words(response.data[offset : offset + (len(operation.word_refs) * 2)])
    offset += len(operation.word_refs) * 2
    dword_values = decode_device_dwords(response.data[offset:])
    return RandomReadResult(
        word={key: value for key, value in zip(operation.word_keys, word_values, strict=True)},
        dword={key: value for key, value in zip(operation.dword_keys, dword_values, strict=True)},
    )


def decode_prepared_random_read_values(
    response: _SlmpDecodedResponse,
    operation: RandomReadOperation,
) -> tuple[list[int], list[int]]:
    """Decode private prepared random-read values without per-cycle key maps."""
    expected = len(operation.word_refs) * 2 + len(operation.dword_refs) * 4
    if len(response.data) != expected:
        raise SlmpError(f"random read response size mismatch: expected={expected}, actual={len(response.data)}")
    word_bytes = len(operation.word_refs) * 2
    return (
        decode_device_words(response.data[:word_bytes]),
        decode_device_dwords(response.data[word_bytes:]),
    )


def build_write_random_words_request(
    *,
    word_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]],
    dword_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]],
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a random word/dword write request for direct devices."""

    word_items = _normalize_items(word_values, plc_profile=address_profile)
    dword_items = _normalize_items(dword_values, plc_profile=address_profile)
    if not word_items and not dword_items:
        raise ValueError("word_values and dword_values must not both be empty")
    if len(word_items) > 0xFF or len(dword_items) > 0xFF:
        raise ValueError("word_values and dword_values must be <= 255 each")

    effective_series = _effective_series(series, default_series)
    _check_random_write_word_counts(
        len(word_items),
        len(dword_items),
        series=effective_series,
        name="write_random_words",
        plc_profile=address_profile,
    )
    _validate_random_write_word_devices(
        [device for device, _ in word_items],
        [device for device, _ in dword_items],
        plc_profile=address_profile,
    )
    for device, _ in word_items:
        _validate_device_span(
            device,
            points=_random_device_span_points(device, dword=False),
            series=effective_series,
            operation="write_random_words",
        )
    for device, _ in dword_items:
        _validate_device_span(
            device,
            points=_random_device_span_points(device, dword=True),
            series=effective_series,
            operation="write_random_words",
        )
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=False)
    payload = bytearray([len(word_items), len(dword_items)])
    for index, (device, value) in enumerate(word_items):
        _check_temporarily_unsupported_device(device)
        payload += encode_device_spec(device, series=effective_series)
        payload += _require_write_u16(value, f"word_values[{index}]").to_bytes(2, "little", signed=False)
    for index, (device, value) in enumerate(dword_items):
        _check_temporarily_unsupported_device(device)
        payload += encode_device_spec(device, series=effective_series)
        payload += _require_write_u32(value, f"dword_values[{index}]").to_bytes(4, "little", signed=False)
    return OperationRequest(Command.DEVICE_WRITE_RANDOM, subcommand, bytes(payload))


def build_write_random_words_ext_request(
    *,
    word_values: Sequence[tuple[str | DeviceRef, int, _ExtensionSpec]],
    dword_values: Sequence[tuple[str | DeviceRef, int, _ExtensionSpec]],
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a random word/dword write request for extended devices."""

    if not word_values and not dword_values:
        raise ValueError("word_values and dword_values must not both be empty")
    if len(word_values) > 0xFF or len(dword_values) > 0xFF:
        raise ValueError("word_values and dword_values must be <= 255 each")
    effective_series = _effective_series(series, default_series)
    _check_random_write_word_counts(
        len(word_values),
        len(dword_values),
        series=effective_series,
        name="write_random_words_ext",
        extension=True,
        plc_profile=address_profile,
    )
    word_refs: list[DeviceRef] = []
    dword_refs: list[DeviceRef] = []
    word_extensions: list[_ExtensionSpec] = []
    dword_extensions: list[_ExtensionSpec] = []
    encoded_word_values: list[int] = []
    encoded_dword_values: list[int] = []
    link_direct = False
    other_layout = False
    payload_length = 2
    for index, (device, value, extension) in enumerate(word_values):
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _validate_random_write_word_devices(
            [ref],
            [],
            plc_profile=address_profile,
            word_namespaces=[effective_extension],
        )
        word_refs.append(ref)
        word_extensions.append(effective_extension)
        is_link_direct = effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT
        link_direct = link_direct or is_link_direct
        other_layout = other_layout or not is_link_direct
        _validate_device_span(
            ref,
            points=_random_device_span_points(ref, dword=False),
            series=_extended_wire_series(effective_series, effective_extension),
            operation="write_random_words_ext",
        )
        encoded_word_values.append(_require_write_u16(value, f"word_values[{index}]"))
        payload_length += _resolved_extended_device_spec_size(
            series=effective_series,
            extension=effective_extension,
        ) + 2
    for index, (device, value, extension) in enumerate(dword_values):
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _validate_random_write_word_devices(
            [],
            [ref],
            plc_profile=address_profile,
            dword_namespaces=[effective_extension],
        )
        dword_refs.append(ref)
        dword_extensions.append(effective_extension)
        is_link_direct = effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT
        link_direct = link_direct or is_link_direct
        other_layout = other_layout or not is_link_direct
        _validate_device_span(
            ref,
            points=_random_device_span_points(ref, dword=True),
            series=_extended_wire_series(effective_series, effective_extension),
            operation="write_random_words_ext",
        )
        encoded_dword_values.append(_require_write_u32(value, f"dword_values[{index}]"))
        payload_length += _resolved_extended_device_spec_size(
            series=effective_series,
            extension=effective_extension,
        ) + 4
    _validate_random_write_word_devices(
        word_refs,
        dword_refs,
        plc_profile=address_profile,
        word_namespaces=word_extensions,
        dword_namespaces=dword_extensions,
    )
    subcommand = resolve_device_subcommand(
        bit_unit=False,
        series=_extended_subcommand_series(
            effective_series,
            has_link_direct=link_direct,
            has_other_layout=other_layout,
            operation="write_random_words_ext",
        ),
        extension=True,
    )
    payload = bytearray(payload_length)
    payload[0] = len(word_values)
    payload[1] = len(dword_values)
    offset = 2
    for ref, extension, value in zip(word_refs, word_extensions, encoded_word_values, strict=True):
        offset += _encode_resolved_extended_device_spec_into(
            ref,
            series=effective_series,
            extension=extension,
            output=payload,
            offset=offset,
        )
        payload[offset] = value & 0xFF
        payload[offset + 1] = (value >> 8) & 0xFF
        offset += 2
    for ref, extension, value in zip(dword_refs, dword_extensions, encoded_dword_values, strict=True):
        offset += _encode_resolved_extended_device_spec_into(
            ref,
            series=effective_series,
            extension=extension,
            output=payload,
            offset=offset,
        )
        payload[offset] = value & 0xFF
        payload[offset + 1] = (value >> 8) & 0xFF
        payload[offset + 2] = (value >> 16) & 0xFF
        payload[offset + 3] = (value >> 24) & 0xFF
        offset += 4
    assert offset == len(payload)
    return OperationRequest(Command.DEVICE_WRITE_RANDOM, subcommand, _freeze_owned_payload(payload))


def build_write_random_bits_request(
    bit_values: Mapping[str | DeviceRef, bool] | Sequence[tuple[str | DeviceRef, bool]],
    *,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a random bit write request for direct devices."""

    items = _normalize_items(bit_values, plc_profile=address_profile)
    if not items:
        raise ValueError("bit_values must not be empty")
    if len(items) > 0xFF:
        raise ValueError("bit_values must be <= 255")
    effective_series = _effective_series(series, default_series)
    _check_random_bit_write_count(
        len(items),
        series=effective_series,
        name="write_random_bits",
        plc_profile=address_profile,
    )
    _validate_random_write_bit_devices([device for device, _ in items], plc_profile=address_profile)
    subcommand = resolve_device_subcommand(bit_unit=True, series=effective_series, extension=False)
    payload = bytearray([len(items)])
    for index, (device, state) in enumerate(items):
        _check_temporarily_unsupported_device(device)
        payload += encode_device_spec(device, series=effective_series)
        encoded_state = _require_write_bit(state, f"bit_values[{index}]")
        if effective_series == PLCSeries.IQR:
            payload += b"\x01\x00" if encoded_state else b"\x00\x00"
        else:
            payload += b"\x01" if encoded_state else b"\x00"
    return OperationRequest(Command.DEVICE_WRITE_RANDOM, subcommand, bytes(payload))


def build_write_random_bits_ext_request(
    bit_values: Sequence[tuple[str | DeviceRef, bool, _ExtensionSpec]],
    *,
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a random bit write request for extended devices."""

    if not bit_values:
        raise ValueError("bit_values must not be empty")
    if len(bit_values) > 0xFF:
        raise ValueError("bit_values must be <= 255")
    effective_series = _effective_series(series, default_series)
    _check_random_bit_write_count(
        len(bit_values),
        series=effective_series,
        name="write_random_bits_ext",
        extension=True,
        plc_profile=address_profile,
    )
    refs: list[DeviceRef] = []
    extensions: list[_ExtensionSpec] = []
    encoded_states: list[int] = []
    link_direct = False
    other_layout = False
    payload_length = 1
    for index, (device, state, extension) in enumerate(bit_values):
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        refs.append(ref)
        extensions.append(effective_extension)
        is_link_direct = effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT
        link_direct = link_direct or is_link_direct
        other_layout = other_layout or not is_link_direct
        encoded_state = _require_write_bit(state, f"bit_values[{index}]")
        encoded_states.append(encoded_state)
        payload_length += _resolved_extended_device_spec_size(
            series=effective_series,
            extension=effective_extension,
        ) + (2 if effective_series == PLCSeries.IQR and not is_link_direct else 1)
    _validate_random_write_bit_devices(refs, plc_profile=address_profile, namespaces=extensions)
    subcommand = resolve_device_subcommand(
        bit_unit=True,
        series=_extended_subcommand_series(
            effective_series,
            has_link_direct=link_direct,
            has_other_layout=other_layout,
            operation="write_random_bits_ext",
        ),
        extension=True,
    )
    payload = bytearray(payload_length)
    payload[0] = len(bit_values)
    offset = 1
    for ref, extension, encoded_state_value in zip(refs, extensions, encoded_states, strict=True):
        offset += _encode_resolved_extended_device_spec_into(
            ref,
            series=effective_series,
            extension=extension,
            output=payload,
            offset=offset,
        )
        payload[offset] = encoded_state_value
        offset += 1
        if effective_series == PLCSeries.IQR and extension.direct_memory_specification != DIRECT_MEMORY_LINK_DIRECT:
            payload[offset] = 0
            offset += 1
    assert offset == len(payload)
    return OperationRequest(Command.DEVICE_WRITE_RANDOM, subcommand, _freeze_owned_payload(payload))


def build_read_block_request(
    *,
    word_blocks: Sequence[tuple[str | DeviceRef, int]],
    bit_blocks: Sequence[tuple[str | DeviceRef, int]],
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> BlockReadOperation:
    """Build a block read request for word and bit block groups."""

    if not word_blocks and not bit_blocks:
        raise ValueError("word_blocks and bit_blocks must not both be empty")
    if len(word_blocks) > 0xFF or len(bit_blocks) > 0xFF:
        raise ValueError("word_blocks and bit_blocks must be <= 255 each")
    effective_series = _effective_series(series, default_series)
    _check_block_request_limits(
        word_blocks,
        bit_blocks,
        series=effective_series,
        name="read_block",
        plc_profile=address_profile,
    )
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=False)

    payload = bytearray([len(word_blocks), len(bit_blocks)])
    normalized_word: list[tuple[DeviceRef, int]] = []
    normalized_bit: list[tuple[DeviceRef, int]] = []
    for device, points in word_blocks:
        _check_points_u16(points, "word_block points")
        ref = _parse_device_for_address_profile(device, address_profile)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=effective_series, access_kind="direct")
        _validate_block_read_devices([(ref, points)], [])
        _validate_device_span(
            ref,
            points=_word_unit_device_span_points(ref, points, long_current_block=True),
            series=effective_series,
            operation="read_block",
        )
        normalized_word.append((ref, points))
        payload += encode_device_spec(ref, series=effective_series)
        payload += points.to_bytes(2, "little")
    for device, points in bit_blocks:
        _check_points_u16(points, "bit_block points")
        ref = _parse_device_for_address_profile(device, address_profile)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=effective_series, access_kind="direct")
        _validate_block_read_devices([], [(ref, points)])
        _validate_device_span(ref, points=points * 16, series=effective_series, operation="read_block")
        normalized_bit.append((ref, points))
        payload += encode_device_spec(ref, series=effective_series)
        payload += points.to_bytes(2, "little")
    _validate_block_read_devices(normalized_word, normalized_bit)
    return BlockReadOperation(
        request=OperationRequest(Command.DEVICE_READ_BLOCK, subcommand, bytes(payload)),
        word_blocks=tuple(normalized_word),
        bit_blocks=tuple(normalized_bit),
    )


def decode_read_block_response(response: _SlmpDecodedResponse, operation: BlockReadOperation) -> BlockReadResult:
    """Decode a block read response using its original operation metadata."""

    offset = 0
    word_result: list[DeviceBlockResult] = []
    for ref, points in operation.word_blocks:
        size = points * 2
        words = decode_device_words(response.data[offset : offset + size])
        if len(words) != points:
            raise SlmpError(f"word block response mismatch for {ref}")
        word_result.append(DeviceBlockResult(device=str(ref), values=words))
        offset += size

    bit_result: list[DeviceBlockResult] = []
    for ref, points in operation.bit_blocks:
        size = points * 2
        words = decode_device_words(response.data[offset : offset + size])
        if len(words) != points:
            raise SlmpError(f"bit block response mismatch for {ref}")
        bit_result.append(DeviceBlockResult(device=str(ref), values=words))
        offset += size

    if offset != len(response.data):
        raise SlmpError(f"read block response trailing data: {len(response.data) - offset} bytes")
    return BlockReadResult(word_blocks=word_result, bit_blocks=bit_result)


def build_write_block_request(
    *,
    word_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]],
    bit_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]],
    series: PLCSeries | str | None,
    default_series: PLCSeries,
    address_profile: object | None,
) -> OperationRequest:
    """Build a block write request for word and bit block groups."""

    if not word_blocks and not bit_blocks:
        raise ValueError("word_blocks and bit_blocks must not both be empty")
    if len(word_blocks) > 0xFF or len(bit_blocks) > 0xFF:
        raise ValueError("word_blocks and bit_blocks must be <= 255 each")
    effective_series = _effective_series(series, default_series)
    _check_block_request_limits(
        word_blocks,
        bit_blocks,
        series=effective_series,
        name="write_block",
        write=True,
        plc_profile=address_profile,
    )
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=False)

    word_refs: list[DeviceRef] = []
    bit_refs: list[DeviceRef] = []
    for device, values in word_blocks:
        ref = _parse_device_for_address_profile(device, address_profile)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=effective_series, access_kind="direct")
        _check_points_u16(len(values), "word block size")
        _validate_block_write_devices([ref], [], plc_profile=address_profile)
        _validate_device_span(
            ref,
            points=_word_unit_device_span_points(ref, len(values)),
            series=effective_series,
            operation="write_block",
        )
        word_refs.append(ref)
    for device, values in bit_blocks:
        ref = _parse_device_for_address_profile(device, address_profile)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=effective_series, access_kind="direct")
        _check_points_u16(len(values), "bit block size")
        _validate_block_write_devices([], [ref], plc_profile=address_profile)
        _validate_device_span(ref, points=len(values) * 16, series=effective_series, operation="write_block")
        bit_refs.append(ref)
    _validate_block_write_devices(word_refs, bit_refs, plc_profile=address_profile)
    _validate_block_write_ranges(
        [(ref, values) for ref, (_, values) in zip(word_refs, word_blocks, strict=True)],
        [(ref, values) for ref, (_, values) in zip(bit_refs, bit_blocks, strict=True)],
    )

    # Each block's write data follows that block's own spec (SLMP reference
    # manual Write Block request format); data must not be batched after the
    # block specs, or multi-block/mixed requests misparse on the PLC.
    payload = bytearray([len(word_blocks), len(bit_blocks)])
    for ref, (_, values) in zip(word_refs, word_blocks, strict=True):
        payload += encode_device_spec(ref, series=effective_series)
        payload += len(values).to_bytes(2, "little")
        for index, value in enumerate(values):
            payload += _require_write_u16(value, f"word block value[{index}]").to_bytes(2, "little", signed=False)
    for ref, (_, values) in zip(bit_refs, bit_blocks, strict=True):
        payload += encode_device_spec(ref, series=effective_series)
        payload += len(values).to_bytes(2, "little")
        for index, value in enumerate(values):
            payload += _require_write_u16(value, f"bit block value[{index}]").to_bytes(2, "little", signed=False)
    return OperationRequest(Command.DEVICE_WRITE_BLOCK, subcommand, bytes(payload))


def build_self_test_loopback_request(data: bytes | str) -> OperationRequest:
    """Build a self-test loopback request."""

    loopback = data.encode("ascii") if isinstance(data, str) else bytes(data)
    if len(loopback) < 1 or len(loopback) > 960:
        raise ValueError(f"loopback data size out of range (1..960): {len(loopback)}")
    if any(ch not in b"0123456789ABCDEF" for ch in loopback):
        raise ValueError("loopback data must contain only ASCII 0-9/A-F bytes")
    payload = len(loopback).to_bytes(2, "little") + loopback
    return OperationRequest(Command.SELF_TEST, 0x0000, payload)


def decode_self_test_loopback_response(response: _SlmpDecodedResponse, *, expected: bytes) -> bytes:
    """Decode a self-test loopback response body."""

    data = response.data
    if len(data) < 2:
        raise SlmpError(f"self test response too short: {len(data)}")
    size = int.from_bytes(data[:2], "little")
    body = data[2:]
    if size != len(body):
        raise SlmpError(f"self test response size mismatch: size={size}, actual={len(body)}")
    if size != len(expected):
        raise SlmpError(f"self test response length mismatch: expected={len(expected)}, actual={size}")
    if body != expected:
        raise SlmpError("self test response payload mismatch")
    return bytes(body)


def build_memory_read_words_request(head_address: int, word_length: int) -> OperationRequest:
    """Build a direct memory read request for words."""

    _check_u32(head_address, "head_address")
    if word_length < 1 or word_length > 0x01E0:
        raise ValueError(f"word_length out of range (1..480): {word_length}")
    payload = head_address.to_bytes(4, "little") + word_length.to_bytes(2, "little")
    return OperationRequest(Command.MEMORY_READ, 0x0000, payload)


def decode_memory_read_words_response(response: _SlmpDecodedResponse, *, word_length: int) -> list[int]:
    """Decode a direct memory word-read response."""

    words = decode_device_words(response.data)
    if len(words) != word_length:
        raise SlmpError(f"memory read size mismatch: expected={word_length}, actual={len(words)}")
    return words


def build_memory_write_words_request(head_address: int, values: Sequence[int]) -> OperationRequest:
    """Build a direct memory write request for words."""

    _check_u32(head_address, "head_address")
    if not values:
        raise ValueError("values must not be empty")
    if len(values) > 0x01E0:
        raise ValueError(f"word length out of range (1..480): {len(values)}")
    payload = bytearray()
    payload += head_address.to_bytes(4, "little")
    payload += len(values).to_bytes(2, "little")
    for index, value in enumerate(values):
        payload += _require_write_u16(value, f"values[{index}]").to_bytes(2, "little", signed=False)
    return OperationRequest(Command.MEMORY_WRITE, 0x0000, bytes(payload))


def build_extend_unit_read_bytes_request(head_address: int, byte_length: int, module_no: int) -> OperationRequest:
    """Build an extension-unit byte-read request."""

    _check_u32(head_address, "head_address")
    _check_u16(module_no, "module_no")
    if byte_length < 2 or byte_length > 0x0780:
        raise ValueError(f"byte_length out of range (2..1920): {byte_length}")
    payload = head_address.to_bytes(4, "little") + byte_length.to_bytes(2, "little") + module_no.to_bytes(2, "little")
    return OperationRequest(Command.EXTEND_UNIT_READ, 0x0000, payload)


def decode_extend_unit_read_bytes_response(response: _SlmpDecodedResponse, *, byte_length: int) -> bytes:
    """Decode an extension-unit byte-read response."""

    if len(response.data) != byte_length:
        raise SlmpError(f"extend unit read size mismatch: expected={byte_length}, actual={len(response.data)}")
    return bytes(response.data)


def build_extend_unit_read_words_request(head_address: int, word_length: int, module_no: int) -> OperationRequest:
    """Build an extension-unit word-read request."""

    _check_u32(head_address, "head_address")
    if word_length < 1 or word_length > 0x03C0:
        raise ValueError(f"word_length out of range (1..960): {word_length}")
    return build_extend_unit_read_bytes_request(head_address, word_length * 2, module_no)


def decode_extend_unit_read_words_response(response: _SlmpDecodedResponse, *, word_length: int) -> list[int]:
    """Decode an extension-unit word-read response."""

    data = decode_extend_unit_read_bytes_response(response, byte_length=word_length * 2)
    words = decode_device_words(data)
    if len(words) != word_length:
        raise SlmpError(f"extend unit read word size mismatch: expected={word_length}, actual={len(words)}")
    return words


def build_extend_unit_write_bytes_request(head_address: int, module_no: int, data: bytes) -> OperationRequest:
    """Build an extension-unit byte-write request."""

    _check_u32(head_address, "head_address")
    _check_u16(module_no, "module_no")
    if len(data) < 2 or len(data) > 0x0780:
        raise ValueError(f"data length out of range (2..1920): {len(data)}")
    payload = head_address.to_bytes(4, "little")
    payload += len(data).to_bytes(2, "little")
    payload += module_no.to_bytes(2, "little")
    payload += data
    return OperationRequest(Command.EXTEND_UNIT_WRITE, 0x0000, payload)


def build_extend_unit_write_words_request(
    head_address: int,
    module_no: int,
    values: Sequence[int],
) -> OperationRequest:
    """Build an extension-unit word-write request."""

    _check_u32(head_address, "head_address")
    if not values:
        raise ValueError("values must not be empty")
    if len(values) > 0x03C0:
        raise ValueError(f"word_length out of range (1..960): {len(values)}")
    payload = bytearray()
    for index, value in enumerate(values):
        payload += _require_write_u16(value, f"values[{index}]").to_bytes(2, "little", signed=False)
    return build_extend_unit_write_bytes_request(head_address, module_no, bytes(payload))


def build_extend_unit_write_word_request(head_address: int, module_no: int, value: int) -> OperationRequest:
    """Build an extension-unit single-word write request."""

    _require_write_u16(value, "value")
    return build_extend_unit_write_words_request(head_address, module_no, [value])


def build_extend_unit_write_dword_request(head_address: int, module_no: int, value: int) -> OperationRequest:
    """Build an extension-unit single-dword write request."""

    _require_write_u32(value, "value")
    return build_extend_unit_write_bytes_request(
        head_address,
        module_no,
        int(value).to_bytes(4, "little", signed=False),
    )


def _normalize_abbreviation_labels(labels: Sequence[str]) -> tuple[str, ...]:
    if isinstance(labels, (str, bytes, bytearray)) or not isinstance(labels, Sequence):
        raise TypeError("abbreviation_labels must be a sequence of strings")
    _check_u16(len(labels), "number of abbreviation points")
    normalized: list[str] = []
    for label in labels:
        if not isinstance(label, str):
            raise TypeError("abbreviation label must be a string")
        _encode_label_name(label)
        normalized.append(label)
    return tuple(normalized)


def _validate_abbreviation_references(label: str, abbreviation_count: int) -> None:
    _encode_label_name(label)
    index = 0
    while index < len(label):
        if label[index] != "%":
            index += 1
            continue
        digit_start = index + 1
        digit_end = digit_start
        while digit_end < len(label) and "0" <= label[digit_end] <= "9":
            digit_end += 1
        if digit_end == digit_start:
            raise ValueError(f"label contains an invalid abbreviation reference; use %1 through %{abbreviation_count}")
        reference = int(label[digit_start:digit_end])
        if reference < 1 or reference > abbreviation_count:
            raise ValueError(f"label contains an invalid abbreviation reference; use %1 through %{abbreviation_count}")
        index = digit_end


def _append_label_payload_part(parts: list[bytes], payload_length: int, part: bytes) -> int:
    next_length = payload_length + len(part)
    _validate_request_payload_length(next_length)
    parts.append(part)
    return next_length


def build_array_label_read_payload(
    points: Sequence[LabelArrayReadPoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> bytes:
    """Build payload bytes for array label read operations."""

    if not points:
        raise ValueError("points must not be empty")
    _check_u16(len(points), "number of array points")
    abbreviations = _normalize_abbreviation_labels(abbreviation_labels)
    parts = [len(points).to_bytes(2, "little"), len(abbreviations).to_bytes(2, "little")]
    payload_length = 4
    for name in abbreviations:
        payload_length = _append_label_payload_part(parts, payload_length, _encode_label_name(name))
    for point in points:
        _validate_abbreviation_references(point.label, len(abbreviations))
        _label_array_data_bytes(point.unit_specification, point.array_data_length)
        payload_length = _append_label_payload_part(parts, payload_length, _encode_label_name(point.label))
        metadata = (
            point.unit_specification.to_bytes(1, "little") + b"\x00" + point.array_data_length.to_bytes(2, "little")
        )
        payload_length = _append_label_payload_part(parts, payload_length, metadata)
    return b"".join(parts)


def build_array_label_write_payload(
    points: Sequence[LabelArrayWritePoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> bytes:
    """Build payload bytes for array label write operations."""

    if not points:
        raise ValueError("points must not be empty")
    _check_u16(len(points), "number of array points")
    abbreviations = _normalize_abbreviation_labels(abbreviation_labels)
    parts = [len(points).to_bytes(2, "little"), len(abbreviations).to_bytes(2, "little")]
    payload_length = 4
    for name in abbreviations:
        payload_length = _append_label_payload_part(parts, payload_length, _encode_label_name(name))
    for point in points:
        _validate_abbreviation_references(point.label, len(abbreviations))
        _check_label_unit_specification(point.unit_specification, "unit_specification")
        _check_u16(point.array_data_length, "array_data_length")
        raw = bytes(point.data)
        expected = _label_array_data_bytes(point.unit_specification, point.array_data_length)
        if len(raw) != expected:
            raise ValueError(
                "array label write data size mismatch: "
                f"expected={expected}, actual={len(raw)}, unit_specification={point.unit_specification}, "
                f"array_data_length={point.array_data_length}"
            )
        payload_length = _append_label_payload_part(parts, payload_length, _encode_label_name(point.label))
        metadata_and_data = (
            point.unit_specification.to_bytes(1, "little")
            + b"\x00"
            + point.array_data_length.to_bytes(2, "little")
            + raw
        )
        payload_length = _append_label_payload_part(parts, payload_length, metadata_and_data)
    return b"".join(parts)


def build_label_read_random_payload(
    labels: Sequence[str],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> bytes:
    """Build payload bytes for random label read operations."""

    if not labels:
        raise ValueError("labels must not be empty")
    _check_u16(len(labels), "number of read data points")
    abbreviations = _normalize_abbreviation_labels(abbreviation_labels)
    parts = [len(labels).to_bytes(2, "little"), len(abbreviations).to_bytes(2, "little")]
    payload_length = 4
    for name in abbreviations:
        payload_length = _append_label_payload_part(parts, payload_length, _encode_label_name(name))
    for label in labels:
        _validate_abbreviation_references(label, len(abbreviations))
        payload_length = _append_label_payload_part(parts, payload_length, _encode_label_name(label))
    return b"".join(parts)


def build_label_write_random_payload(
    points: Sequence[LabelRandomWritePoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> bytes:
    """Build payload bytes for random label write operations."""

    if not points:
        raise ValueError("points must not be empty")
    _check_u16(len(points), "number of write data points")
    abbreviations = _normalize_abbreviation_labels(abbreviation_labels)
    parts = [len(points).to_bytes(2, "little"), len(abbreviations).to_bytes(2, "little")]
    payload_length = 4
    for name in abbreviations:
        payload_length = _append_label_payload_part(parts, payload_length, _encode_label_name(name))
    for point in points:
        _validate_abbreviation_references(point.label, len(abbreviations))
        raw = bytes(point.data)
        _check_u16(len(raw), "write data length")
        if len(raw) == 0 or len(raw) % 2 != 0:
            raise ValueError(f"write data length must be positive and even: {len(raw)}")
        payload_length = _append_label_payload_part(parts, payload_length, _encode_label_name(point.label))
        payload_length = _append_label_payload_part(parts, payload_length, len(raw).to_bytes(2, "little") + raw)
    return b"".join(parts)


def build_read_array_labels_request(
    points: Sequence[LabelArrayReadPoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> OperationRequest:
    """Build an array label read request."""

    payload = build_array_label_read_payload(points, abbreviation_labels=abbreviation_labels)
    return OperationRequest(Command.LABEL_ARRAY_READ, 0x0000, payload)


def build_write_array_labels_request(
    points: Sequence[LabelArrayWritePoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> OperationRequest:
    """Build an array label write request."""

    payload = build_array_label_write_payload(points, abbreviation_labels=abbreviation_labels)
    return OperationRequest(Command.LABEL_ARRAY_WRITE, 0x0000, payload)


def build_read_random_labels_request(
    labels: Sequence[str],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> OperationRequest:
    """Build a random label read request."""

    payload = build_label_read_random_payload(labels, abbreviation_labels=abbreviation_labels)
    return OperationRequest(Command.LABEL_READ_RANDOM, 0x0000, payload)


def build_write_random_labels_request(
    points: Sequence[LabelRandomWritePoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> OperationRequest:
    """Build a random label write request."""

    payload = build_label_write_random_payload(points, abbreviation_labels=abbreviation_labels)
    return OperationRequest(Command.LABEL_WRITE_RANDOM, 0x0000, payload)


def parse_array_label_read_response(
    data: bytes,
    *,
    requested_points: Sequence[LabelArrayReadPoint],
) -> list[LabelArrayReadResult]:
    """Parse an array label read response payload."""

    if len(data) < 2:
        raise SlmpError(f"array label read response too short: {len(data)}")
    points = int.from_bytes(data[:2], "little")
    if points != len(requested_points):
        raise SlmpError(f"array label read point count mismatch: expected={len(requested_points)}, actual={points}")
    offset = 2
    out: list[LabelArrayReadResult] = []
    for index in range(points):
        if offset + 4 > len(data):
            raise SlmpError("array label read response truncated before metadata")
        data_type_id = data[offset]
        unit_specification = data[offset + 1]
        array_data_length = int.from_bytes(data[offset + 2 : offset + 4], "little")
        offset += 4
        if unit_specification not in {0, 1}:
            raise SlmpError(f"array label read response has invalid unit_specification: {unit_specification}")
        if array_data_length == 0:
            raise SlmpError("array label read response has zero array_data_length")
        requested = requested_points[index]
        if unit_specification != requested.unit_specification or array_data_length != requested.array_data_length:
            raise SlmpError(
                f"array label read metadata mismatch at index {index}: "
                f"expected unit={requested.unit_specification}, length={requested.array_data_length}; "
                f"actual unit={unit_specification}, length={array_data_length}"
            )
        data_size = _label_array_wire_data_bytes(unit_specification, array_data_length)
        if offset + data_size > len(data):
            raise SlmpError(
                "array label read response truncated in data payload: "
                f"needed={data_size}, remaining={len(data) - offset}"
            )
        raw = bytes(data[offset : offset + data_size])
        offset += data_size
        out.append(
            LabelArrayReadResult(
                data_type_id=data_type_id,
                unit_specification=unit_specification,
                array_data_length=array_data_length,
                data=raw,
            )
        )
    if offset != len(data):
        raise SlmpError(f"array label read response has trailing bytes: {len(data) - offset}")
    return out


def parse_label_read_random_response(
    data: bytes,
    *,
    expected_points: int,
) -> list[LabelRandomReadResult]:
    """Parse a random label read response payload."""

    if len(data) < 2:
        raise SlmpError(f"label random read response too short: {len(data)}")
    points = int.from_bytes(data[:2], "little")
    if expected_points is not None and points != expected_points:
        raise SlmpError(f"label random read point count mismatch: expected={expected_points}, actual={points}")
    offset = 2
    out: list[LabelRandomReadResult] = []
    for _ in range(points):
        if offset + 4 > len(data):
            raise SlmpError("label random read response truncated before metadata")
        data_type_id = data[offset]
        spare = data[offset + 1]
        read_data_length = int.from_bytes(data[offset + 2 : offset + 4], "little")
        offset += 4
        if read_data_length == 0 or read_data_length % 2 != 0:
            raise SlmpError(f"label random read response data length must be positive and even: {read_data_length}")
        if offset + read_data_length > len(data):
            raise SlmpError(
                "label random read response truncated in data payload: "
                f"needed={read_data_length}, remaining={len(data) - offset}"
            )
        raw = bytes(data[offset : offset + read_data_length])
        offset += read_data_length
        out.append(
            LabelRandomReadResult(
                data_type_id=data_type_id,
                spare=spare,
                read_data_length=read_data_length,
                data=raw,
            )
        )
    if offset != len(data):
        raise SlmpError(f"label random read response has trailing bytes: {len(data) - offset}")
    return out
