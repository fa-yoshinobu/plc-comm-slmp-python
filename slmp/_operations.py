"""Private shared operation builders for sync and async clients."""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .constants import DIRECT_MEMORY_LINK_DIRECT, Command, PLCSeries
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
    SlmpResponse,
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
    _encode_label_name,
    _encode_remote_password_payload,
    _encode_resolved_extended_device_spec,
    _ExtensionSpec,
    _label_array_data_bytes,
    _normalize_items,
    _require_explicit_plc_profile_for_xy,
    _resolve_extended_device_and_extension,
    _validate_block_read_devices,
    _validate_block_write_devices,
    _validate_direct_dword_read_device,
    _validate_direct_read_device,
    _validate_direct_write_device,
    _validate_monitor_register_devices,
    _validate_random_read_devices,
    _validate_random_write_bit_devices,
    _validate_random_write_word_devices,
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
    payload: bytes


@dataclass(frozen=True)
class RandomReadOperation:
    """Random-read request plus the refs needed to decode the response."""

    request: OperationRequest
    word_refs: tuple[DeviceRef, ...]
    dword_refs: tuple[DeviceRef, ...]


@dataclass(frozen=True)
class BlockReadOperation:
    """Block-read request plus block metadata needed to decode the response."""

    request: OperationRequest
    word_blocks: tuple[tuple[DeviceRef, int], ...]
    bit_blocks: tuple[tuple[DeviceRef, int], ...]


def _effective_series(series: PLCSeries | str | None, default_series: PLCSeries) -> PLCSeries:
    return PLCSeries(series) if series is not None else default_series


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

    _check_direct_device_points(
        points,
        bit_unit=bit_unit,
        name="read_devices",
        plc_profile=address_profile,
    )
    effective_series = _effective_series(series, default_series)
    ref = _parse_device_for_address_profile(device, address_profile)
    _validate_direct_read_device(ref, points=points, bit_unit=bit_unit)
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
    response: SlmpResponse,
    *,
    points: int,
    bit_unit: bool,
) -> list[int] | list[bool]:
    """Decode a direct device read response into word or bit values."""

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
        payload += pack_bit_values(values)
    else:
        for value in values:
            payload += int(value).to_bytes(2, "little", signed=False)
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


def decode_read_dwords_response(response: SlmpResponse, *, count: int) -> list[int]:
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
    for value in values:
        bits = int(value) & 0xFFFFFFFF
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


def decode_read_float32s_response(response: SlmpResponse, *, count: int) -> list[float]:
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
    for value in values:
        dwords.append(struct.unpack("<I", struct.pack("<f", float(value)))[0])
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
) -> OperationRequest:
    """Build an extended-device direct read request."""

    _check_direct_device_points(
        points,
        bit_unit=bit_unit,
        name="read_devices_ext",
        plc_profile=address_profile,
    )
    effective_series = _effective_series(series, default_series)
    ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
    _validate_direct_read_device(ref, points=points, bit_unit=bit_unit)
    _check_temporarily_unsupported_device(ref, access_kind="extended_device")
    _warn_practical_device_path(ref, series=effective_series, access_kind="extended_device")
    if effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        effective_series = PLCSeries.QL
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
) -> OperationRequest:
    """Build an extended-device direct write request."""

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
    _validate_direct_write_device(ref, bit_unit=bit_unit, plc_profile=address_profile)
    _check_temporarily_unsupported_device(ref, access_kind="extended_device")
    _warn_practical_device_path(ref, series=effective_series, access_kind="extended_device")
    if effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        effective_series = PLCSeries.QL
    subcommand = resolve_device_subcommand(bit_unit=bit_unit, series=effective_series, extension=True)
    payload = bytearray()
    payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
    payload += len(values).to_bytes(2, "little")
    if bit_unit:
        payload += pack_bit_values(values)
    else:
        for value in values:
            payload += int(value).to_bytes(2, "little", signed=False)
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
        payload += encode_device_spec(ref, series=effective_series)
        word_refs.append(ref)
    for dev in dword_devices:
        ref = _parse_device_for_address_profile(dev, address_profile)
        _check_temporarily_unsupported_device(ref)
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
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=True)
    payload = bytearray([len(word_devices), len(dword_devices)])
    word_refs: list[DeviceRef] = []
    dword_refs: list[DeviceRef] = []
    for dev, ext in word_devices:
        ref, effective_extension = _resolve_extended_device_for_family(dev, ext, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        word_refs.append(ref)
        payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
    for dev, ext in dword_devices:
        ref, effective_extension = _resolve_extended_device_for_family(dev, ext, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        dword_refs.append(ref)
        payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
    _validate_monitor_register_devices(word_refs, dword_refs)
    return OperationRequest(Command.DEVICE_ENTRY_MONITOR, subcommand, bytes(payload))


def build_run_monitor_cycle_request(*, word_points: int, dword_points: int) -> OperationRequest:
    """Build a monitor execution request for registered monitor points."""

    if word_points < 0 or dword_points < 0:
        raise ValueError("word_points and dword_points must be >= 0")
    return OperationRequest(Command.DEVICE_EXECUTE_MONITOR, 0x0000, b"")


def decode_run_monitor_cycle_response(
    response: SlmpResponse,
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


def decode_read_type_name_response(response: SlmpResponse) -> TypeNameInfo:
    """Decode a type-name response into model text and model code metadata."""

    data = response.data
    model = ""
    model_code = None
    if len(data) >= 16:
        model = data[:16].split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
    if len(data) >= 18:
        model_code = int.from_bytes(data[16:18], "little")
    return TypeNameInfo(raw=data, model=model, model_code=model_code)


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
    _check_temporarily_unsupported_devices(words)
    _check_temporarily_unsupported_devices(dwords)

    payload = bytearray([len(words), len(dwords)])
    for device in words:
        payload += encode_device_spec(device, series=effective_series)
    for device in dwords:
        payload += encode_device_spec(device, series=effective_series)
    return RandomReadOperation(
        request=OperationRequest(Command.DEVICE_READ_RANDOM, subcommand, bytes(payload)),
        word_refs=tuple(words),
        dword_refs=tuple(dwords),
    )


def build_read_random_ext_request(
    *,
    word_devices: Sequence[tuple[str | DeviceRef, _ExtensionSpec]],
    dword_devices: Sequence[tuple[str | DeviceRef, _ExtensionSpec]],
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
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=True)

    payload = bytearray([len(word_devices), len(dword_devices)])
    words: list[DeviceRef] = []
    dwords: list[DeviceRef] = []
    for device, extension in word_devices:
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        words.append(ref)
        payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
    for device, extension in dword_devices:
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        dwords.append(ref)
        payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
    _validate_random_read_devices(words, dwords)
    return RandomReadOperation(
        request=OperationRequest(Command.DEVICE_READ_RANDOM, subcommand, bytes(payload)),
        word_refs=tuple(words),
        dword_refs=tuple(dwords),
    )


def decode_read_random_response(response: SlmpResponse, operation: RandomReadOperation) -> RandomReadResult:
    """Decode a random read response using its original operation metadata."""

    expected = len(operation.word_refs) * 2 + len(operation.dword_refs) * 4
    if len(response.data) != expected:
        raise SlmpError(f"random read response size mismatch: expected={expected}, actual={len(response.data)}")

    offset = 0
    word_values = decode_device_words(response.data[offset : offset + (len(operation.word_refs) * 2)])
    offset += len(operation.word_refs) * 2
    dword_values = decode_device_dwords(response.data[offset:])
    return RandomReadResult(
        word={str(device): value for device, value in zip(operation.word_refs, word_values, strict=True)},
        dword={str(device): value for device, value in zip(operation.dword_refs, dword_values, strict=True)},
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
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=False)
    payload = bytearray([len(word_items), len(dword_items)])
    for device, value in word_items:
        _check_temporarily_unsupported_device(device)
        payload += encode_device_spec(device, series=effective_series)
        payload += int(value).to_bytes(2, "little", signed=False)
    for device, value in dword_items:
        _check_temporarily_unsupported_device(device)
        payload += encode_device_spec(device, series=effective_series)
        payload += int(value).to_bytes(4, "little", signed=False)
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
    subcommand = resolve_device_subcommand(bit_unit=False, series=effective_series, extension=True)
    payload = bytearray([len(word_values), len(dword_values)])
    word_refs: list[DeviceRef] = []
    dword_refs: list[DeviceRef] = []
    for device, value, extension in word_values:
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        word_refs.append(ref)
        payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
        payload += int(value).to_bytes(2, "little", signed=False)
    for device, value, extension in dword_values:
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        dword_refs.append(ref)
        payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
        payload += int(value).to_bytes(4, "little", signed=False)
    _validate_random_write_word_devices(word_refs, dword_refs, plc_profile=address_profile)
    return OperationRequest(Command.DEVICE_WRITE_RANDOM, subcommand, bytes(payload))


def build_write_random_bits_request(
    bit_values: Mapping[str | DeviceRef, bool | int] | Sequence[tuple[str | DeviceRef, bool | int]],
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
    for device, state in items:
        _check_temporarily_unsupported_device(device)
        payload += encode_device_spec(device, series=effective_series)
        if effective_series == PLCSeries.IQR:
            payload += b"\x01\x00" if bool(state) else b"\x00\x00"
        else:
            payload += b"\x01" if bool(state) else b"\x00"
    return OperationRequest(Command.DEVICE_WRITE_RANDOM, subcommand, bytes(payload))


def build_write_random_bits_ext_request(
    bit_values: Sequence[tuple[str | DeviceRef, bool | int, _ExtensionSpec]],
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
    subcommand = resolve_device_subcommand(bit_unit=True, series=effective_series, extension=True)
    payload = bytearray([len(bit_values)])
    refs: list[DeviceRef] = []
    for device, state, extension in bit_values:
        ref, effective_extension = _resolve_extended_device_for_family(device, extension, address_profile)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        refs.append(ref)
        payload += _encode_resolved_extended_device_spec(ref, series=effective_series, extension=effective_extension)
        if effective_series == PLCSeries.IQR:
            payload += b"\x01\x00" if bool(state) else b"\x00\x00"
        else:
            payload += b"\x01" if bool(state) else b"\x00"
    _validate_random_write_bit_devices(refs, plc_profile=address_profile)
    return OperationRequest(Command.DEVICE_WRITE_RANDOM, subcommand, bytes(payload))


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
        normalized_word.append((ref, points))
        payload += encode_device_spec(ref, series=effective_series)
        payload += points.to_bytes(2, "little")
    for device, points in bit_blocks:
        _check_points_u16(points, "bit_block points")
        ref = _parse_device_for_address_profile(device, address_profile)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=effective_series, access_kind="direct")
        normalized_bit.append((ref, points))
        payload += encode_device_spec(ref, series=effective_series)
        payload += points.to_bytes(2, "little")
    _validate_block_read_devices(normalized_word, normalized_bit)
    return BlockReadOperation(
        request=OperationRequest(Command.DEVICE_READ_BLOCK, subcommand, bytes(payload)),
        word_blocks=tuple(normalized_word),
        bit_blocks=tuple(normalized_bit),
    )


def decode_read_block_response(response: SlmpResponse, operation: BlockReadOperation) -> BlockReadResult:
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
        word_refs.append(ref)
    for device, values in bit_blocks:
        ref = _parse_device_for_address_profile(device, address_profile)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=effective_series, access_kind="direct")
        _check_points_u16(len(values), "bit block size")
        bit_refs.append(ref)
    _validate_block_write_devices(word_refs, bit_refs, plc_profile=address_profile)

    # Each block's write data follows that block's own spec (SLMP reference
    # manual Write Block request format); data must not be batched after the
    # block specs, or multi-block/mixed requests misparse on the PLC.
    payload = bytearray([len(word_blocks), len(bit_blocks)])
    for ref, (_, values) in zip(word_refs, word_blocks, strict=True):
        payload += encode_device_spec(ref, series=effective_series)
        payload += len(values).to_bytes(2, "little")
        for value in values:
            payload += int(value).to_bytes(2, "little", signed=False)
    for ref, (_, values) in zip(bit_refs, bit_blocks, strict=True):
        payload += encode_device_spec(ref, series=effective_series)
        payload += len(values).to_bytes(2, "little")
        for value in values:
            payload += int(value).to_bytes(2, "little", signed=False)
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


def decode_self_test_loopback_response(response: SlmpResponse) -> bytes:
    """Decode a self-test loopback response body."""

    data = response.data
    if len(data) < 2:
        raise SlmpError(f"self test response too short: {len(data)}")
    size = int.from_bytes(data[:2], "little")
    body = data[2:]
    if size != len(body):
        raise SlmpError(f"self test response size mismatch: size={size}, actual={len(body)}")
    return body


def build_memory_read_words_request(head_address: int, word_length: int) -> OperationRequest:
    """Build a direct memory read request for words."""

    _check_u32(head_address, "head_address")
    if word_length < 1 or word_length > 0x01E0:
        raise ValueError(f"word_length out of range (1..480): {word_length}")
    payload = head_address.to_bytes(4, "little") + word_length.to_bytes(2, "little")
    return OperationRequest(Command.MEMORY_READ, 0x0000, payload)


def decode_memory_read_words_response(response: SlmpResponse, *, word_length: int) -> list[int]:
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
    for value in values:
        payload += int(value).to_bytes(2, "little", signed=False)
    return OperationRequest(Command.MEMORY_WRITE, 0x0000, bytes(payload))


def build_extend_unit_read_bytes_request(head_address: int, byte_length: int, module_no: int) -> OperationRequest:
    """Build an extension-unit byte-read request."""

    _check_u32(head_address, "head_address")
    _check_u16(module_no, "module_no")
    if byte_length < 2 or byte_length > 0x0780:
        raise ValueError(f"byte_length out of range (2..1920): {byte_length}")
    payload = head_address.to_bytes(4, "little") + byte_length.to_bytes(2, "little") + module_no.to_bytes(2, "little")
    return OperationRequest(Command.EXTEND_UNIT_READ, 0x0000, payload)


def decode_extend_unit_read_bytes_response(response: SlmpResponse, *, byte_length: int) -> bytes:
    """Decode an extension-unit byte-read response."""

    if len(response.data) != byte_length:
        raise SlmpError(f"extend unit read size mismatch: expected={byte_length}, actual={len(response.data)}")
    return response.data


def build_extend_unit_read_words_request(head_address: int, word_length: int, module_no: int) -> OperationRequest:
    """Build an extension-unit word-read request."""

    _check_u32(head_address, "head_address")
    if word_length < 1 or word_length > 0x03C0:
        raise ValueError(f"word_length out of range (1..960): {word_length}")
    return build_extend_unit_read_bytes_request(head_address, word_length * 2, module_no)


def decode_extend_unit_read_words_response(response: SlmpResponse, *, word_length: int) -> list[int]:
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
    for value in values:
        payload += int(value).to_bytes(2, "little", signed=False)
    return build_extend_unit_write_bytes_request(head_address, module_no, bytes(payload))


def build_extend_unit_write_word_request(head_address: int, module_no: int, value: int) -> OperationRequest:
    """Build an extension-unit single-word write request."""

    _check_u16(value, "value")
    return build_extend_unit_write_words_request(head_address, module_no, [value])


def build_extend_unit_write_dword_request(head_address: int, module_no: int, value: int) -> OperationRequest:
    """Build an extension-unit single-dword write request."""

    _check_u32(value, "value")
    return build_extend_unit_write_bytes_request(
        head_address,
        module_no,
        int(value).to_bytes(4, "little", signed=False),
    )


def build_array_label_read_payload(
    points: Sequence[LabelArrayReadPoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> bytes:
    """Build payload bytes for array label read operations."""

    if not points:
        raise ValueError("points must not be empty")
    _check_u16(len(points), "number of array points")
    _check_u16(len(abbreviation_labels), "number of abbreviation points")
    payload = bytearray()
    payload += len(points).to_bytes(2, "little")
    payload += len(abbreviation_labels).to_bytes(2, "little")
    for name in abbreviation_labels:
        payload += _encode_label_name(name)
    for point in points:
        _check_label_unit_specification(point.unit_specification, "unit_specification")
        _check_u16(point.array_data_length, "array_data_length")
        payload += _encode_label_name(point.label)
        payload += point.unit_specification.to_bytes(1, "little")
        payload += b"\x00"
        payload += point.array_data_length.to_bytes(2, "little")
    return bytes(payload)


def build_array_label_write_payload(
    points: Sequence[LabelArrayWritePoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> bytes:
    """Build payload bytes for array label write operations."""

    if not points:
        raise ValueError("points must not be empty")
    _check_u16(len(points), "number of array points")
    _check_u16(len(abbreviation_labels), "number of abbreviation points")
    payload = bytearray()
    payload += len(points).to_bytes(2, "little")
    payload += len(abbreviation_labels).to_bytes(2, "little")
    for name in abbreviation_labels:
        payload += _encode_label_name(name)
    for point in points:
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
        payload += _encode_label_name(point.label)
        payload += point.unit_specification.to_bytes(1, "little")
        payload += b"\x00"
        payload += point.array_data_length.to_bytes(2, "little")
        payload += raw
    return bytes(payload)


def build_label_read_random_payload(
    labels: Sequence[str],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> bytes:
    """Build payload bytes for random label read operations."""

    if not labels:
        raise ValueError("labels must not be empty")
    _check_u16(len(labels), "number of read data points")
    _check_u16(len(abbreviation_labels), "number of abbreviation points")
    payload = bytearray()
    payload += len(labels).to_bytes(2, "little")
    payload += len(abbreviation_labels).to_bytes(2, "little")
    for name in abbreviation_labels:
        payload += _encode_label_name(name)
    for label in labels:
        payload += _encode_label_name(label)
    return bytes(payload)


def build_label_write_random_payload(
    points: Sequence[LabelRandomWritePoint],
    *,
    abbreviation_labels: Sequence[str] = (),
) -> bytes:
    """Build payload bytes for random label write operations."""

    if not points:
        raise ValueError("points must not be empty")
    _check_u16(len(points), "number of write data points")
    _check_u16(len(abbreviation_labels), "number of abbreviation points")
    payload = bytearray()
    payload += len(points).to_bytes(2, "little")
    payload += len(abbreviation_labels).to_bytes(2, "little")
    for name in abbreviation_labels:
        payload += _encode_label_name(name)
    for point in points:
        raw = bytes(point.data)
        _check_u16(len(raw), "write data length")
        payload += _encode_label_name(point.label)
        payload += len(raw).to_bytes(2, "little")
        payload += raw
    return bytes(payload)


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
    expected_points: int | None = None,
) -> list[LabelArrayReadResult]:
    """Parse an array label read response payload."""

    if len(data) < 2:
        raise SlmpError(f"array label read response too short: {len(data)}")
    points = int.from_bytes(data[:2], "little")
    if expected_points is not None and points != expected_points:
        raise SlmpError(f"array label read point count mismatch: expected={expected_points}, actual={points}")
    offset = 2
    out: list[LabelArrayReadResult] = []
    for _ in range(points):
        if offset + 4 > len(data):
            raise SlmpError("array label read response truncated before metadata")
        data_type_id = data[offset]
        unit_specification = data[offset + 1]
        _check_label_unit_specification(unit_specification, "response unit_specification")
        array_data_length = int.from_bytes(data[offset + 2 : offset + 4], "little")
        offset += 4
        data_size = _label_array_data_bytes(unit_specification, array_data_length)
        if offset + data_size > len(data):
            raise SlmpError(
                "array label read response truncated in data payload: "
                f"needed={data_size}, remaining={len(data) - offset}"
            )
        raw = data[offset : offset + data_size]
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
    expected_points: int | None = None,
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
        if offset + read_data_length > len(data):
            raise SlmpError(
                "label random read response truncated in data payload: "
                f"needed={read_data_length}, remaining={len(data) - offset}"
            )
        raw = data[offset : offset + read_data_length]
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
