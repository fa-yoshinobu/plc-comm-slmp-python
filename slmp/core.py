"""Core codec/types/helpers for SLMP 4E binary."""

from __future__ import annotations

import re
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from .constants import (
    DEVICE_CODES,
    DIRECT_MEMORY_CPU_BUFFER,
    DIRECT_MEMORY_LINK_DIRECT,
    DIRECT_MEMORY_MODULE_ACCESS,
    DIRECT_MEMORY_NORMAL,
    FRAME_3E_REQUEST_SUBHEADER,
    FRAME_3E_RESPONSE_SUBHEADER,
    FRAME_4E_REQUEST_SUBHEADER,
    FRAME_4E_RESPONSE_SUBHEADER,
    SUBCOMMAND_DEVICE_BIT_IQR,
    SUBCOMMAND_DEVICE_BIT_IQR_EXT,
    SUBCOMMAND_DEVICE_BIT_QL,
    SUBCOMMAND_DEVICE_BIT_QL_EXT,
    SUBCOMMAND_DEVICE_WORD_IQR,
    SUBCOMMAND_DEVICE_WORD_IQR_EXT,
    SUBCOMMAND_DEVICE_WORD_QL,
    SUBCOMMAND_DEVICE_WORD_QL_EXT,
    Command,
    FrameType,
    ModuleIONo,
    PLCSeries,
)
from .errors import (
    SlmpBoundaryBehaviorWarning,
    SlmpError,
    SlmpPracticalPathWarning,
    SlmpUnsupportedDeviceError,
)


@dataclass(frozen=True)
class SlmpTarget:
    """SLMP frame destination fields.

    Attributes:
        network: Network number (0x00 for local network).
        station: Station number (0xFF for control CPU).
        module_io: Module I/O number (0x03FF for own station).
        multidrop: Multidrop station number (0x00 for no multidrop).
    """

    network: int = 0x00
    station: int = 0xFF
    module_io: int | ModuleIONo | str = 0x03FF
    multidrop: int = 0x00

    def __post_init__(self) -> None:
        """Resolve module_io from enum name or value."""
        value = self.module_io
        if isinstance(value, str):
            try:
                # Try to resolve from ModuleIONo enum by name (case-insensitive)
                resolved = ModuleIONo[value.upper()].value
            except KeyError:
                raise ValueError(f"unknown ModuleIONo keyword: {value}") from None
            object.__setattr__(self, "module_io", resolved)
        elif isinstance(value, ModuleIONo):
            object.__setattr__(self, "module_io", value.value)


@dataclass(frozen=True)
class DeviceRef:
    """Device reference.

    Attributes:
        code: Device code string (e.g. 'D', 'X').
        number: Device address number.
    """

    code: str
    number: int
    radix_override: int | None = field(default=None, compare=False, repr=False)

    def __str__(self) -> str:
        """Return the string representation of the device (e.g., 'D100', 'X1F')."""
        radix = self.radix_override
        if radix is None and self.code in DEVICE_CODES:
            radix = DEVICE_CODES[self.code].radix
        if radix == 16:
            return f"{self.code}{self.number:X}"
        if radix == 8:
            return f"{self.code}{self.number:o}".upper()
        return f"{self.code}{self.number}"


_IQF_OCTAL_DEVICE_CODES = frozenset({"X", "Y"})
_DEVICE_FAMILIES = frozenset(
    {
        "iq-r",
        "mx-f",
        "mx-r",
        "iq-f",
        "qcpu",
        "lcpu",
        "qnu",
        "qnudv",
    }
)


def _normalize_device_family_hint(family: object | None) -> str | None:
    if family is None:
        return None
    raw = getattr(family, "value", family)
    normalized = str(raw).strip().lower()
    if not normalized:
        return None
    if normalized in _DEVICE_FAMILIES:
        return normalized
    supported = ", ".join(sorted(_DEVICE_FAMILIES))
    raise ValueError(f"Unsupported device_family {family!r}. Supported families: {supported}")


def _resolve_device_radix(code: str, family: object | None = None) -> int:
    normalized_family = _normalize_device_family_hint(family)
    if normalized_family == "iq-f" and code in _IQF_OCTAL_DEVICE_CODES:
        return 8
    return DEVICE_CODES[code].radix


def _apply_device_family_hint(value: DeviceRef, family: object | None = None) -> DeviceRef:
    if family is None:
        return value
    if value.code not in DEVICE_CODES:
        return value
    radix = _resolve_device_radix(value.code, family)
    if value.radix_override == radix:
        return value
    if value.radix_override is None and DEVICE_CODES[value.code].radix == radix:
        return value
    return replace(value, radix_override=radix)


def _require_explicit_device_family_for_xy(
    value: str | DeviceRef,
    family: object | None,
    ref: DeviceRef,
) -> DeviceRef:
    if not isinstance(value, str):
        return ref
    if _normalize_device_family_hint(family) is not None:
        return ref
    if ref.code not in _IQF_OCTAL_DEVICE_CODES:
        return ref
    raise ValueError(
        "X/Y string addresses require explicit device_family. "
        "Use device_family='iq-f' for FX/iQ-F targets, choose an explicit non-iQ-F family, "
        "or pass a numeric DeviceRef."
    )


@dataclass(frozen=True)
class SlmpResponse:
    """Decoded SLMP response frame.

    Attributes:
        serial: Serial number matching the request.
        target: Source station routing information.
        end_code: Response end code (0x0000 for success).
        data: Command-specific response payload.
        raw: Full raw binary response frame.
    """

    serial: int
    target: SlmpTarget
    end_code: int
    data: bytes
    raw: bytes

    @property
    def is_success(self) -> bool:
        """Return True if the response end_code is 0."""
        return self.end_code == 0


@dataclass(frozen=True)
class LabelArrayReadPoint:
    """Request point for array label read."""

    label: str
    unit_specification: int
    array_data_length: int


@dataclass(frozen=True)
class LabelArrayWritePoint:
    """Request point for array label write."""

    label: str
    unit_specification: int
    array_data_length: int
    data: bytes


@dataclass(frozen=True)
class LabelRandomWritePoint:
    """Request point for random label write."""

    label: str
    data: bytes


@dataclass(frozen=True)
class RandomReadResult:
    """Result of random device read."""

    word: dict[str, int]
    dword: dict[str, int]


@dataclass(frozen=True)
class MonitorResult:
    """Result of registered monitor device read."""

    word: list[int]
    dword: list[int]


@dataclass(frozen=True)
class DeviceBlockResult:
    """Result of a single device block in block access."""

    device: str
    values: list[int]


@dataclass(frozen=True)
class BlockReadResult:
    """Result of block device read."""

    word_blocks: list[DeviceBlockResult]
    bit_blocks: list[DeviceBlockResult]


@dataclass(frozen=True)
class LongTimerResult:
    """Result of long timer read."""

    index: int
    device: str
    current_value: int
    contact: bool
    coil: bool
    status_word: int
    raw_words: list[int]


@dataclass(frozen=True)
class LabelArrayReadResult:
    """Result of array label read."""

    data_type_id: int
    unit_specification: int
    array_data_length: int
    data: bytes


@dataclass(frozen=True)
class LabelRandomReadResult:
    """Result of random label read."""

    data_type_id: int
    spare: int
    read_data_length: int
    data: bytes


@dataclass(frozen=True)
class TypeNameInfo:
    """Result of READ_TYPE_NAME command."""

    raw: bytes
    model: str
    model_code: int | None


class CpuOperationStatus(str, Enum):
    """Decoded CPU operation state from the lower 4 bits of SD203."""

    Unknown = "Unknown"
    Run = "Run"
    Stop = "Stop"
    Pause = "Pause"


@dataclass(frozen=True)
class CpuOperationState:
    """Decoded CPU operation state read from SD203."""

    status: CpuOperationStatus
    raw_status_word: int
    raw_code: int


def decode_cpu_operation_state(status_word: int) -> CpuOperationState:
    """Decode the CPU operation state from SD203 lower 4 bits."""
    raw_status_word = int(status_word) & 0xFFFF
    raw_code = raw_status_word & 0x000F
    if raw_code == 0x00:
        status = CpuOperationStatus.Run
    elif raw_code == 0x02:
        status = CpuOperationStatus.Stop
    elif raw_code == 0x03:
        status = CpuOperationStatus.Pause
    else:
        status = CpuOperationStatus.Unknown
    return CpuOperationState(status=status, raw_status_word=raw_status_word, raw_code=raw_code)


@dataclass(frozen=True)
class SlmpTraceFrame:
    """A single SLMP transaction captured by a trace hook."""

    serial: int
    command: int
    subcommand: int
    request_data: bytes
    request_frame: bytes
    response_frame: bytes
    response_end_code: int | None
    target: SlmpTarget
    monitoring_timer: int


@dataclass(frozen=True)
class ExtensionSpec:
    """Extended Device extension fields (binary, 0080..0083)."""

    extension_specification: int = 0x0000
    extension_specification_modification: int = 0x00
    device_modification_index: int = 0x00
    device_modification_flags: int = 0x00
    direct_memory_specification: int = DIRECT_MEMORY_NORMAL


@dataclass(frozen=True)
class ExtendedDevice:
    """Extended Device text plus optional qualified extension-specification override."""

    ref: DeviceRef
    extension_specification: int | None = None
    direct_memory_specification: int | None = None


def parse_device(
    value: str | DeviceRef,
    *,
    family: object | None = None,
) -> DeviceRef:
    """Parse a device string into a `DeviceRef`.

    Args:
        value: Device string (e.g. 'D100', 'X1F') or `DeviceRef` object.

    Returns:
        A `DeviceRef` object containing the device code and numeric address.

    Raises:
        ValueError: If the device format is invalid or the code is unknown.
    """
    if isinstance(value, DeviceRef):
        return _apply_device_family_hint(value, family)

    text = value.strip().upper()
    match = re.fullmatch(r"([A-Z]+)([0-9A-F]+)", text)
    if not match:
        valid_codes = ", ".join(sorted(DEVICE_CODES.keys()))
        raise ValueError(
            f"Invalid SLMP device string {value!r}. "
            f"Expected format: <DeviceCode><Number> (e.g. 'D100', 'X1F'). "
            f"Valid device codes: {valid_codes}"
        )

    code, num_txt = match.groups()
    if code not in DEVICE_CODES:
        valid_codes = ", ".join(sorted(DEVICE_CODES.keys()))
        raise ValueError(f"Unknown SLMP device code '{code}' in {value!r}. Valid codes: {valid_codes}")

    base = _resolve_device_radix(code, family)
    number = int(num_txt, base)
    return _apply_device_family_hint(DeviceRef(code=code, number=number), family)


def parse_extended_device(
    value: str | DeviceRef,
    *,
    family: object | None = None,
) -> ExtendedDevice:
    r"""Parse an Extended Device string (e.g., 'U01\G10', 'J2\SW10') or return ExtendedDevice as-is."""
    if isinstance(value, DeviceRef):
        return ExtendedDevice(ref=parse_device(value, family=family))

    text = value.strip().upper()

    # J-format: link direct device (e.g. 'J2\SW10')
    j_qualified = re.fullmatch(r"J(\d+)[\\/](.+)", text)
    if j_qualified:
        j_net_txt, device_txt = j_qualified.groups()
        j_network = int(j_net_txt)
        _check_u8(j_network, "extended_device j_network")
        return ExtendedDevice(
            ref=parse_device(device_txt, family=family),
            extension_specification=j_network,
            direct_memory_specification=DIRECT_MEMORY_LINK_DIRECT,
        )

    qualified = re.fullmatch(r"U([0-9A-F]+)[\\/](.+)", text)
    if qualified:
        extension_txt, device_txt = qualified.groups()
        extension_specification = int(extension_txt, 16)
        _check_u16(extension_specification, "extended_device extension_specification")
        dev_ref = parse_device(device_txt, family=family)
        # G/HG buffer memory devices have a fixed DM by device code (matches GOT pcap-verified format)
        dm: int | None = None
        if dev_ref.code == "G":
            dm = DIRECT_MEMORY_MODULE_ACCESS  # 0xF8
        elif dev_ref.code == "HG":
            dm = DIRECT_MEMORY_CPU_BUFFER  # 0xFA
        return ExtendedDevice(
            ref=dev_ref,
            extension_specification=extension_specification,
            direct_memory_specification=dm,
        )

    return ExtendedDevice(ref=parse_device(value, family=family))


def resolve_extended_device_and_extension(
    device: str | DeviceRef,
    extension: ExtensionSpec,
    *,
    family: object | None = None,
) -> tuple[DeviceRef, ExtensionSpec]:
    """Resolve device and extension specification, prioritizing explicit qualification in the device string."""
    qualified = parse_extended_device(device, family=family)
    overrides: dict[str, Any] = {}
    if (
        qualified.extension_specification is not None
        and qualified.extension_specification != extension.extension_specification
    ):
        overrides["extension_specification"] = qualified.extension_specification
    if (
        qualified.direct_memory_specification is not None
        and extension.direct_memory_specification == DIRECT_MEMORY_NORMAL
    ):
        overrides["direct_memory_specification"] = qualified.direct_memory_specification
    if not overrides:
        return qualified.ref, extension
    return qualified.ref, replace(extension, **overrides)


def encode_4e_request(
    *,
    serial: int,
    target: SlmpTarget,
    monitoring_timer: int,
    command: int,
    subcommand: int,
    data: bytes = b"",
) -> bytes:
    """Encode a full 4E request frame."""
    _check_u16(serial, "serial")
    _check_u16(monitoring_timer, "monitoring_timer")
    _check_u16(command, "command")
    _check_u16(subcommand, "subcommand")
    _check_u8(target.network, "target.network")
    _check_u8(target.station, "target.station")
    module_io = int(target.module_io)
    _check_u16(module_io, "target.module_io")
    _check_u8(target.multidrop, "target.multidrop")

    body = bytearray()
    body += target.network.to_bytes(1, "little")
    body += target.station.to_bytes(1, "little")
    body += module_io.to_bytes(2, "little")
    body += target.multidrop.to_bytes(1, "little")

    req_len = 2 + 2 + 2 + len(data)  # timer + command + subcommand + payload
    _check_u16(req_len, "request_data_length")
    body += req_len.to_bytes(2, "little")
    body += monitoring_timer.to_bytes(2, "little")
    body += command.to_bytes(2, "little")
    body += subcommand.to_bytes(2, "little")
    body += data

    frame = bytearray()
    frame += FRAME_4E_REQUEST_SUBHEADER
    frame += serial.to_bytes(2, "little")
    frame += b"\x00\x00"
    frame += body
    return bytes(frame)


def encode_3e_request(
    *,
    target: SlmpTarget,
    monitoring_timer: int,
    command: int,
    subcommand: int,
    data: bytes = b"",
) -> bytes:
    """Encode a full 3E request frame."""
    _check_u16(monitoring_timer, "monitoring_timer")
    _check_u16(command, "command")
    _check_u16(subcommand, "subcommand")
    _check_u8(target.network, "target.network")
    _check_u8(target.station, "target.station")
    module_io = int(target.module_io)
    _check_u16(module_io, "target.module_io")
    _check_u8(target.multidrop, "target.multidrop")

    body = bytearray()
    body += target.network.to_bytes(1, "little")
    body += target.station.to_bytes(1, "little")
    body += module_io.to_bytes(2, "little")
    body += target.multidrop.to_bytes(1, "little")

    req_len = 2 + 2 + 2 + len(data)  # timer + command + subcommand + payload
    _check_u16(req_len, "request_data_length")
    body += req_len.to_bytes(2, "little")
    body += monitoring_timer.to_bytes(2, "little")
    body += command.to_bytes(2, "little")
    body += subcommand.to_bytes(2, "little")
    body += data

    frame = bytearray()
    frame += FRAME_3E_REQUEST_SUBHEADER
    frame += body
    return bytes(frame)


def encode_request(
    *,
    frame_type: FrameType,
    serial: int,
    target: SlmpTarget,
    monitoring_timer: int,
    command: int,
    subcommand: int,
    data: bytes = b"",
) -> bytes:
    """Encode an SLMP request frame based on frame_type.

    Args:
        frame_type: SLMP frame format (3E or 4E).
        serial: Serial number for 4E frames (ignored for 3E).
        target: Target station routing information.
        monitoring_timer: Timeout value in multiples of 250ms.
        command: SLMP command code.
        subcommand: SLMP subcommand code.
        data: Command-specific binary payload.

    Returns:
        The full binary request frame.
    """
    if frame_type == FrameType.FRAME_3E:
        return encode_3e_request(
            target=target,
            monitoring_timer=monitoring_timer,
            command=command,
            subcommand=subcommand,
            data=data,
        )
    return encode_4e_request(
        serial=serial,
        target=target,
        monitoring_timer=monitoring_timer,
        command=command,
        subcommand=subcommand,
        data=data,
    )


def decode_3e_response(frame: bytes) -> SlmpResponse:
    """Decode a 3E response frame."""
    if len(frame) < 11:
        raise SlmpError(f"response too short: {len(frame)} bytes")
    if frame[:2] != FRAME_3E_RESPONSE_SUBHEADER:
        got = frame[:2].hex(" ").upper()
        raise SlmpError(f"unexpected 3E response subheader: {got}")

    target = SlmpTarget(
        network=frame[2],
        station=frame[3],
        module_io=int.from_bytes(frame[4:6], "little"),
        multidrop=frame[6],
    )

    response_data_length = int.from_bytes(frame[7:9], "little")
    if len(frame) != 9 + response_data_length:
        raise SlmpError(
            "response size mismatch: "
            f"actual={len(frame)}, expected={9 + response_data_length}, "
            f"response_data_length={response_data_length}"
        )
    if response_data_length < 2:
        raise SlmpError(f"invalid response_data_length: {response_data_length}")

    end_code = int.from_bytes(frame[9:11], "little")
    data = frame[11:]
    return SlmpResponse(serial=0, target=target, end_code=end_code, data=data, raw=frame)


def decode_response(frame: bytes, *, frame_type: FrameType) -> SlmpResponse:
    """Decode an SLMP response frame based on frame_type.

    Args:
        frame: Full raw binary response frame.
        frame_type: Expected frame format (3E or 4E).

    Returns:
        A decoded `SlmpResponse` object.

    Raises:
        SlmpError: If the frame is malformed or the subheader does not match.
    """
    if frame_type == FrameType.FRAME_3E:
        return decode_3e_response(frame)
    return decode_4e_response(frame)


def decode_4e_response(frame: bytes) -> SlmpResponse:
    """Decode a 4E response frame."""
    if len(frame) < 15:
        raise SlmpError(f"response too short: {len(frame)} bytes")
    if frame[:2] != FRAME_4E_RESPONSE_SUBHEADER:
        got = frame[:2].hex(" ").upper()
        raise SlmpError(f"unexpected 4E response subheader: {got}")

    serial = int.from_bytes(frame[2:4], "little")
    target = SlmpTarget(
        network=frame[6],
        station=frame[7],
        module_io=int.from_bytes(frame[8:10], "little"),
        multidrop=frame[10],
    )

    response_data_length = int.from_bytes(frame[11:13], "little")
    if len(frame) != 13 + response_data_length:
        raise SlmpError(
            "response size mismatch: "
            f"actual={len(frame)}, expected={13 + response_data_length}, "
            f"response_data_length={response_data_length}"
        )
    if response_data_length < 2:
        raise SlmpError(f"invalid response_data_length: {response_data_length}")

    end_code = int.from_bytes(frame[13:15], "little")
    data = frame[15:]
    return SlmpResponse(serial=serial, target=target, end_code=end_code, data=data, raw=frame)


def resolve_device_subcommand(
    *,
    bit_unit: bool,
    series: PLCSeries,
    extension: bool = False,
) -> int:
    """Resolve the SLMP subcommand for device read/write operations."""
    if extension:
        if series == PLCSeries.QL:
            return SUBCOMMAND_DEVICE_BIT_QL_EXT if bit_unit else SUBCOMMAND_DEVICE_WORD_QL_EXT
        return SUBCOMMAND_DEVICE_BIT_IQR_EXT if bit_unit else SUBCOMMAND_DEVICE_WORD_IQR_EXT
    if series == PLCSeries.QL:
        return SUBCOMMAND_DEVICE_BIT_QL if bit_unit else SUBCOMMAND_DEVICE_WORD_QL
    return SUBCOMMAND_DEVICE_BIT_IQR if bit_unit else SUBCOMMAND_DEVICE_WORD_IQR


def encode_device_spec(
    device: str | DeviceRef,
    *,
    series: PLCSeries,
    family: object | None = None,
) -> bytes:
    """Encode a device specification into bytes based on the PLC series."""
    ref = parse_device(device, family=family)
    if ref.code == "R" and ref.number > 32767:
        raise ValueError(f"R device number out of supported range (0..32767): {ref.number}")
    dev = DEVICE_CODES[ref.code]

    if series == PLCSeries.QL:
        if ref.number < 0 or ref.number > 0xFFFFFF:
            raise ValueError(f"device number out of range for Q/L format: {ref.number}")
        return ref.number.to_bytes(3, "little") + (dev.code & 0xFF).to_bytes(1, "little")

    _check_u32(ref.number, "device.number")
    return ref.number.to_bytes(4, "little") + dev.code.to_bytes(2, "little")


def encode_extension_spec(spec: ExtensionSpec) -> bytes:
    """Encode an Extended Device extension specification into bytes."""
    _validate_extension_spec(spec)
    return (
        spec.extension_specification.to_bytes(2, "little")
        + spec.extension_specification_modification.to_bytes(1, "little")
        + spec.device_modification_index.to_bytes(1, "little")
        + spec.device_modification_flags.to_bytes(1, "little")
    )


def _validate_extension_spec(spec: ExtensionSpec) -> None:
    _check_u16(spec.extension_specification, "extension_specification")
    _check_u8(spec.extension_specification_modification, "extension_specification_modification")
    _check_u8(spec.device_modification_index, "device_modification_index")
    _check_u8(spec.device_modification_flags, "device_modification_flags")
    _check_u8(spec.direct_memory_specification, "direct_memory_specification")


def _uses_capture_aligned_g_hg_layout(ref: DeviceRef, *, extension: ExtensionSpec) -> bool:
    return ref.code in _G_HG_CODES and extension.direct_memory_specification in {0xF8, 0xFA}


def _encode_capture_aligned_g_hg_extension_spec(
    ref: DeviceRef,
    *,
    series: PLCSeries,
    extension: ExtensionSpec,
    include_direct_memory_at_end: bool,
) -> bytes:
    _validate_extension_spec(extension)
    payload = bytearray()
    payload += extension.extension_specification_modification.to_bytes(1, "little")
    payload += extension.device_modification_index.to_bytes(1, "little")
    payload += encode_device_spec(ref, series=series)
    payload += extension.device_modification_flags.to_bytes(1, "little")
    # Real U3E0\G10, U3E0\HG20, and U01\G22 captures include one zero byte here.
    payload += b"\x00"
    payload += extension.extension_specification.to_bytes(2, "little")
    if include_direct_memory_at_end:
        payload += extension.direct_memory_specification.to_bytes(1, "little")
    return bytes(payload)


def _encode_link_direct_device_spec(
    ref: DeviceRef,
    *,
    extension: ExtensionSpec,
    include_direct_memory_at_end: bool,
) -> bytes:
    """Encode a link direct device spec (J\\device) verified by GOT pcap.

    Format: reserved(2) + dev_no(3) + dev_code(1) + reserved(2) + j_net(1) + reserved(1) + 0xF9(1)
    Always uses QL (3-byte device number) format.
    """
    j_net = extension.extension_specification & 0xFF
    dev = DEVICE_CODES[ref.code]
    payload = bytearray()
    payload += b"\x00\x00"
    payload += ref.number.to_bytes(3, "little")
    payload += (dev.code & 0xFF).to_bytes(1, "little")
    payload += b"\x00\x00"
    payload += bytes([j_net])
    payload += b"\x00"
    if include_direct_memory_at_end:
        payload += bytes([DIRECT_MEMORY_LINK_DIRECT])
    return bytes(payload)


def encode_extended_device_spec(
    device: str | DeviceRef,
    *,
    series: PLCSeries,
    extension: ExtensionSpec,
    include_direct_memory_at_end: bool = True,
    family: object | None = None,
) -> bytes:
    """Encode an Extended Device extended device specification into bytes."""
    ref, effective_extension = resolve_extended_device_and_extension(device, extension, family=family)
    if effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        return _encode_link_direct_device_spec(
            ref,
            extension=effective_extension,
            include_direct_memory_at_end=include_direct_memory_at_end,
        )
    if _uses_capture_aligned_g_hg_layout(ref, extension=effective_extension):
        return _encode_capture_aligned_g_hg_extension_spec(
            ref,
            series=series,
            extension=effective_extension,
            include_direct_memory_at_end=include_direct_memory_at_end,
        )
    payload = bytearray()
    payload += encode_extension_spec(effective_extension)
    payload += encode_device_spec(ref, series=series)
    if include_direct_memory_at_end:
        payload += effective_extension.direct_memory_specification.to_bytes(1, "little")
    return bytes(payload)


def build_device_modification_flags(
    *,
    series: PLCSeries,
    use_indirect_specification: bool = False,
    register_mode: str = "none",
) -> int:
    """Build device_modification_flags from Extended Device semantics.

    register_mode:
      - "none"
      - "z"
      - "lz" (iQ-R/iQ-L only)
    """
    mode = register_mode.lower()
    if mode not in {"none", "z", "lz"}:
        raise ValueError(f"register_mode must be one of none,z,lz: {register_mode}")
    if series == PLCSeries.QL and mode == "lz":
        raise ValueError("LZ register mode is not available for Q/L extension subcommands")

    high = 0x0
    if mode == "z":
        high = 0x4
    elif mode == "lz":
        high = 0x8
    low = 0x8 if use_indirect_specification else 0x0
    return ((high & 0xF) << 4) | (low & 0xF)


def decode_device_words(data: bytes) -> list[int]:
    """Decode a byte array into a list of 16-bit word values."""
    if len(data) % 2 != 0:
        raise SlmpError(f"word data length must be even: {len(data)}")
    return [int.from_bytes(data[i : i + 2], "little") for i in range(0, len(data), 2)]


def decode_device_dwords(data: bytes) -> list[int]:
    """Decode a byte array into a list of 32-bit double-word values."""
    if len(data) % 4 != 0:
        raise SlmpError(f"dword data length must be multiple of 4: {len(data)}")
    return [int.from_bytes(data[i : i + 4], "little") for i in range(0, len(data), 4)]


def pack_bit_values(values: Iterable[bool | int]) -> bytes:
    """Pack a sequence of bit values into binary format.

    In SLMP binary bit-unit access, each byte contains two points.
    The high nibble stores the first point, and the low nibble stores the second.

    Args:
        values: An iterable of boolean or integer (0/1) values.

    Returns:
        Packed binary data.
    """
    bits = [1 if bool(v) else 0 for v in values]
    out = bytearray()
    for i in range(0, len(bits), 2):
        hi = bits[i] & 0x1
        lo = bits[i + 1] & 0x1 if i + 1 < len(bits) else 0
        out.append((hi << 4) | lo)
    return bytes(out)


def unpack_bit_values(data: bytes, count: int) -> list[bool]:
    """Unpack binary bit data into a list of booleans.

    Args:
        data: Binary data received from the PLC.
        count: The number of bit points to extract.

    Returns:
        A list of boolean values.

    Raises:
        SlmpError: If the data length is insufficient for the requested count.
    """
    result: list[bool] = []
    for byte in data:
        result.append(bool((byte >> 4) & 0x1))  # Upper 4 bits = first device
        if len(result) >= count:
            return result
        result.append(bool(byte & 0x1))  # Lower 4 bits = second device
        if len(result) >= count:
            return result
    if len(result) != count:
        raise SlmpError(f"bit data too short: needed {count}, got {len(result)}")
    return result


def _check_u8(value: int, name: str) -> None:
    if value < 0 or value > 0xFF:
        raise ValueError(f"{name} out of range (0..255): {value}")


def _check_u16(value: int, name: str) -> None:
    if value < 0 or value > 0xFFFF:
        raise ValueError(f"{name} out of range (0..65535): {value}")


def _check_u32(value: int, name: str) -> None:
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError(f"{name} out of range (0..4294967295): {value}")


def _check_points_u16(points: int, name: str) -> None:
    if points < 0 or points > 0xFFFF:
        raise ValueError(f"{name} out of range (0..65535): {points}")


def _check_random_read_like_counts(word_points: int, dword_points: int, *, series: PLCSeries, name: str) -> None:
    total = word_points + dword_points
    limit = 96 if series == PLCSeries.IQR else 192
    if total < 1 or total > limit:
        raise ValueError(
            f"{name} total access points out of range (1..{limit}) for {series.value}: "
            f"word={word_points}, dword={dword_points}"
        )


def _check_random_bit_write_count(points: int, *, series: PLCSeries, name: str) -> None:
    limit = 94 if series == PLCSeries.IQR else 188
    if points < 1 or points > limit:
        raise ValueError(f"{name} bit access points out of range (1..{limit}) for {series.value}: {points}")


def _check_block_request_limits(
    word_blocks: Sequence[tuple[str | DeviceRef, int | Sequence[object]]],
    bit_blocks: Sequence[tuple[str | DeviceRef, int | Sequence[object]]],
    *,
    series: PLCSeries,
    name: str,
) -> None:
    total_blocks = len(word_blocks) + len(bit_blocks)
    block_limit = 60 if series == PLCSeries.IQR else 120
    if total_blocks < 1 or total_blocks > block_limit:
        raise ValueError(f"{name} total block count out of range (1..{block_limit}) for {series.value}: {total_blocks}")

    total_points = 0
    for _, points in word_blocks:
        total_points += int(points) if isinstance(points, int) else len(points)
    for _, points in bit_blocks:
        total_points += int(points) if isinstance(points, int) else len(points)
    if total_points > 960:
        raise ValueError(f"{name} total device points out of range (<=960): {total_points}")


def _normalize_items(
    values: Mapping[str | DeviceRef, Any] | Sequence[tuple[str | DeviceRef, Any]],
) -> list[tuple[DeviceRef, Any]]:
    if isinstance(values, Mapping):
        items = list(values.items())
    else:
        items = list(values)
    return [(parse_device(device), value) for device, value in items]


def _raise_response_error(response: SlmpResponse, *, command: int | Command, subcommand: int) -> None:
    if response.end_code == 0:
        return
    raise SlmpError(
        f"SLMP error end_code=0x{response.end_code:04X} command=0x{int(command):04X} subcommand=0x{subcommand:04X}",
        end_code=response.end_code,
        data=response.data,
    )


def _check_temporarily_unsupported_device(ref: DeviceRef, *, access_kind: str = "direct") -> None:
    if access_kind not in {"direct", "extended_device"}:
        raise ValueError(f"unsupported access_kind: {access_kind}")
    if ref.code not in _TEMPORARILY_UNSUPPORTED_TYPED_CODES:
        return
    if ref.code in _G_HG_CODES and access_kind == "extended_device":
        return
    if ref.code in _G_HG_CODES:
        raise SlmpUnsupportedDeviceError(
            f"{ref.code} is temporarily unsupported in direct typed device APIs on this project; "
            "use the Extended Device _ext APIs or the verified cpu_buffer_*/extend_unit_* helpers instead"
        )
    raise SlmpUnsupportedDeviceError(
        f"{ref.code} is temporarily unsupported in typed device APIs on this project; "
        "the access path should be revisited when the cause is known"
    )


def _check_temporarily_unsupported_devices(refs: Sequence[DeviceRef], *, access_kind: str = "direct") -> None:
    for ref in refs:
        _check_temporarily_unsupported_device(ref, access_kind=access_kind)


def _validate_direct_read_device(ref: DeviceRef, *, points: int, bit_unit: bool) -> None:
    if bit_unit and ref.code in _LT_LST_DIRECT_CODES:
        raise ValueError(
            f"Direct bit read is not supported for {ref.code}. "
            "Use read_ltc_states/read_lts_states/read_lstc_states/read_lsts_states "
            "or read_long_timer/read_long_retentive_timer."
        )
    if not bit_unit and ref.code in _LT_LST_CURRENT_CODES and points % 4 != 0:
        raise ValueError(
            f"Direct read of {ref.code} requires 4-word blocks. "
            f"Requested points={points}; use a multiple of 4 or the long timer helpers."
        )


def _validate_random_read_devices(word_refs: Sequence[DeviceRef], dword_refs: Sequence[DeviceRef]) -> None:
    if any(ref.code in _LC_CONTACT_CODES for ref in (*word_refs, *dword_refs)):
        raise ValueError(
            "Read Random (0x0403) does not support LCS/LCC. "
            "Use read_typed/read_named or read_devices('LCN..', 4, bit_unit=False)."
        )


def _validate_block_read_devices(word_refs: Sequence[DeviceRef], bit_refs: Sequence[DeviceRef]) -> None:
    if any(ref.code in _LC_CONTACT_CODES for ref in (*word_refs, *bit_refs)):
        raise ValueError(
            "Read Block (0x0406) does not support LCS/LCC. "
            "Use read_typed/read_named or read_devices('LCN..', 4, bit_unit=False)."
        )


def _validate_block_write_devices(word_refs: Sequence[DeviceRef], bit_refs: Sequence[DeviceRef]) -> None:
    if any(ref.code in _LC_CONTACT_CODES for ref in (*word_refs, *bit_refs)):
        raise ValueError(
            "Write Block (0x1406) does not support LCS/LCC. "
            "Use write_devices/write_random_bits or helper-backed writes instead."
        )


def _validate_monitor_register_devices(word_refs: Sequence[DeviceRef], dword_refs: Sequence[DeviceRef]) -> None:
    if any(ref.code in _LC_CONTACT_CODES for ref in (*word_refs, *dword_refs)):
        raise ValueError(
            "Entry Monitor Device (0x0801) does not support LCS/LCC. "
            "Use read_typed/read_named or monitor the LCN 4-word status block instead."
        )


def _warn_practical_device_path(ref: DeviceRef, *, series: PLCSeries, access_kind: str) -> None:
    if series != PLCSeries.IQR:
        return
    if access_kind == "direct" and ref.code in _LT_LST_DIRECT_CODES:
        warnings.warn(
            (
                f"direct access to {ref.code} is known to fail on the validated iQ-R target; "
                "use read_ltc_states/read_lts_states/read_lstc_states/read_lsts_states "
                "or read_long_timer/read_long_retentive_timer instead"
            ),
            SlmpPracticalPathWarning,
            stacklevel=3,
        )
        return
    if ref.code in _G_HG_CODES:
        if access_kind == "direct":
            warnings.warn(
                (
                    f"direct access to {ref.code} is known to fail on the validated iQ-R target; "
                    "use cpu_buffer_* or extend_unit_* helpers instead"
                ),
                SlmpPracticalPathWarning,
                stacklevel=3,
            )
        elif access_kind == "extended_device":
            warnings.warn(
                (
                    f"Extended Device access to {ref.code} uses a capture-aligned builder; "
                    "revalidate it on the actual PLC and keep cpu_buffer_* or extend_unit_* helpers as the fallback"
                ),
                SlmpPracticalPathWarning,
                stacklevel=3,
            )


def _warn_boundary_behavior(
    ref: DeviceRef,
    *,
    series: PLCSeries,
    points: int,
    write: bool,
    bit_unit: bool,
    access_kind: str,
) -> None:
    if series != PLCSeries.IQR or access_kind != "direct" or points <= 0 or bit_unit:
        return
    if ref.code in _BOUNDARY_START_ACCEPTANCE_CODES and points > 1:
        warnings.warn(
            (
                f"multi-point direct access to {ref.code} may not be rejected at the configured upper bound "
                "on the validated iQ-R target; acceptance appeared to depend mainly on the start address. "
                "Validate live boundary behavior if exact range enforcement matters."
            ),
            SlmpBoundaryBehaviorWarning,
            stacklevel=3,
        )
    if write and ref.code == "LZ" and points % 2 != 0:
        warnings.warn(
            (
                "direct LZ write with an odd word count may be rejected with 0xC051 on the validated iQ-R target; "
                "two-word units were required in live verification."
            ),
            SlmpBoundaryBehaviorWarning,
            stacklevel=3,
        )


_LT_LST_DIRECT_CODES = frozenset({"LTC", "LTS", "LSTC", "LSTS"})
_LT_LST_CURRENT_CODES = frozenset({"LTN", "LSTN"})
_LC_CONTACT_CODES = frozenset({"LCS", "LCC"})
_G_HG_CODES = frozenset({"G", "HG"})
_TEMPORARILY_UNSUPPORTED_TYPED_CODES = frozenset({"G", "HG"})
_BOUNDARY_START_ACCEPTANCE_CODES = frozenset({"R", "ZR"})
_MIXED_BLOCK_RETRY_END_CODES = frozenset({0xC056, 0xC05B, 0xC061})


def _encode_label_name(label: str) -> bytes:
    if not label:
        raise ValueError("label must not be empty")
    raw = label.encode("utf-16-le")
    if len(raw) % 2 != 0:
        raise ValueError("label utf-16 length must be even")
    chars = len(raw) // 2
    _check_u16(chars, "label name length")
    return chars.to_bytes(2, "little") + raw


def _check_label_unit_specification(value: int, name: str) -> None:
    if value not in {0, 1}:
        raise ValueError(f"{name} must be 0(bit) or 1(byte): {value}")


def _label_array_data_bytes(unit_specification: int, array_data_length: int) -> int:
    _check_label_unit_specification(unit_specification, "unit_specification")
    _check_u16(array_data_length, "array_data_length")
    if unit_specification == 0:
        return array_data_length * 2
    return array_data_length


def _encode_remote_password_payload(password: str, *, series: PLCSeries) -> bytes:
    raw = password.encode("ascii")
    if series == PLCSeries.IQR:
        if len(raw) > 32:
            raise ValueError("iQ-R password text must be <= 32 bytes")
        return len(raw).to_bytes(2, "little") + raw
    if len(raw) > 8:
        raise ValueError("Q/L password text must be <= 8 bytes")
    return raw.ljust(8, b"\x00")
