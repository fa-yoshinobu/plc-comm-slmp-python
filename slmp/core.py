"""Core codec/types/helpers for SLMP 4E binary."""

from __future__ import annotations

import re
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from .capability_profiles import display_name, is_profile_read_only_device, profile_limit
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
    DeviceUnit,
    FrameType,
    ModuleIONo,
    PLCSeries,
)
from .errors import (
    SlmpBoundaryBehaviorWarning,
    SlmpError,
    SlmpErrorInfo,
    SlmpPracticalPathWarning,
    SlmpUnsupportedDeviceError,
)

_MAX_REQUEST_PAYLOAD_LENGTH = 0xFFFF - 6
_MAX_IPV4_UDP_DATAGRAM_LENGTH = 65_507


def _resolve_port(port: int | None, transport: str) -> int:
    if not isinstance(transport, str) or transport.strip().lower() not in {"tcp", "udp"}:
        raise ValueError("transport must be 'tcp' or 'udp'")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port is required and must be an integer in range 1..65535")
    return port


def _request_payload_limit(transport: str, frame_type: FrameType) -> int:
    if transport != "udp":
        return _MAX_REQUEST_PAYLOAD_LENGTH
    request_header_size = 19 if frame_type == FrameType.FRAME_4E else 15
    return _MAX_IPV4_UDP_DATAGRAM_LENGTH - request_header_size


def _validate_request_payload_length(payload_length: int, maximum: int = _MAX_REQUEST_PAYLOAD_LENGTH) -> None:
    if payload_length < 0 or payload_length > maximum:
        raise ValueError(f"request payload length out of range: actual={payload_length}, maximum={maximum}")


@dataclass(frozen=True)
class SlmpTarget:
    """SLMP frame destination fields.

    Attributes:
        network: Network number (0x00 for local network).
        station: Station number (0xFF for the connected station).
        module_io: Module I/O number (0x03FF for own station).
        multidrop: Multidrop station number (0x00 for no multidrop).
    """

    network: int
    station: int
    module_io: int | ModuleIONo | str
    multidrop: int

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
        for name, item, maximum in (
            ("network", self.network, 0xFF),
            ("station", self.station, 0xFF),
            ("module_io", self.module_io, 0xFFFF),
            ("multidrop", self.multidrop, 0xFF),
        ):
            if isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= maximum:
                raise ValueError(f"{name} must be an integer in range 0..{maximum}")


@dataclass(frozen=True)
class SlmpTrafficStats:
    """Immutable lifetime traffic-counter snapshot for one client."""

    request_count: int
    tx_bytes: int
    rx_bytes: int


@dataclass(frozen=True)
class DeviceRef:
    """Immutable profile-bound semantic device reference.

    Attributes:
        code: Device code string (e.g. 'D', 'X').
        number: Wire-level device address number.
        plc_profile: Canonical PLC profile used to interpret and format the address.
    """

    code: str
    number: int
    plc_profile: str | SlmpPlcProfile

    def __post_init__(self) -> None:
        normalized_profile = _normalize_plc_profile_hint(self.plc_profile)
        if normalized_profile is None:
            raise ValueError("plc_profile is required for DeviceRef")
        if normalized_profile == SlmpPlcProfile.QCpu.value:
            raise ValueError(_QCPU_BASE_PROFILE_MESSAGE)
        code = str(self.code).strip().upper()
        if code not in DEVICE_CODES:
            raise ValueError(f"Unknown SLMP device code: {self.code!r}")
        if isinstance(self.number, bool) or not isinstance(self.number, int) or self.number < 0:
            raise ValueError("device number must be a non-negative integer")
        _ensure_device_supported_for_profile(code, normalized_profile)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "plc_profile", normalized_profile)

    def __str__(self) -> str:
        """Return the string representation of the device (e.g., 'D100', 'X1F')."""
        radix = _resolve_device_radix(self.code, self.plc_profile)
        if radix == 16:
            return f"{self.code}{self.number:X}"
        if radix == 8:
            return f"{self.code}{self.number:o}".upper()
        return f"{self.code}{self.number}"


_IQF_OCTAL_DEVICE_CODES = frozenset({"X", "Y"})
_DEVICE_CODE_CANDIDATES = tuple(sorted(DEVICE_CODES.keys(), key=lambda code: (-len(code), code)))


class SlmpPlcProfile(str, Enum):
    """Canonical PLC profile used by high-level SLMP helpers."""

    IqF = "melsec:iq-f"
    IqR = "melsec:iq-r"
    IqRRj71En71 = "melsec:iq-r:rj71en71"
    IqL = "melsec:iq-l"
    MxF = "melsec:mx-f"
    MxR = "melsec:mx-r"
    MxRRj71En71 = "melsec:mx-r:rj71en71"
    QCpu = "melsec:qcpu"
    QCpuQj71E71100 = "melsec:qcpu:qj71e71-100"
    LCpu = "melsec:lcpu"
    LCpuLj71E71100 = "melsec:lcpu:lj71e71-100"
    QnU = "melsec:qnu"
    QnUQj71E71100 = "melsec:qnu:qj71e71-100"
    QnUDV = "melsec:qnudv"
    QnUDVQj71E71100 = "melsec:qnudv:qj71e71-100"


@dataclass(frozen=True)
class SlmpPlcProfileDescriptor:
    """One canonical PLC profile and its connection-selection metadata."""

    canonical_name: str
    display_name: str
    connectable: bool
    base_profile: str | None


def available_plc_profiles() -> tuple[SlmpPlcProfile, ...]:
    """Return profiles accepted by the standard connection helpers."""

    return tuple(profile for profile in SlmpPlcProfile if profile is not SlmpPlcProfile.QCpu)


_PLC_PROFILES = frozenset(profile.value for profile in SlmpPlcProfile)
_QCPU_BASE_PROFILE_MESSAGE = "melsec:qcpu is a base profile; use melsec:qcpu:qj71e71-100."


@dataclass(frozen=True)
class _PlcProfileDefaults:
    frame_type: FrameType
    plc_series: PLCSeries
    address_profile: str
    range_profile: str


_PLC_PROFILE_DEFAULTS: dict[str, _PlcProfileDefaults] = {
    "melsec:iq-f": _PlcProfileDefaults(FrameType.FRAME_3E, PLCSeries.QL, "melsec:iq-f", "melsec:iq-f"),
    "melsec:iq-r": _PlcProfileDefaults(FrameType.FRAME_4E, PLCSeries.IQR, "melsec:iq-r", "melsec:iq-r"),
    "melsec:iq-r:rj71en71": _PlcProfileDefaults(
        FrameType.FRAME_4E,
        PLCSeries.IQR,
        "melsec:iq-r",
        "melsec:iq-r:rj71en71",
    ),
    "melsec:iq-l": _PlcProfileDefaults(FrameType.FRAME_4E, PLCSeries.IQR, "melsec:iq-l", "melsec:iq-l"),
    "melsec:mx-f": _PlcProfileDefaults(FrameType.FRAME_4E, PLCSeries.IQR, "melsec:mx-f", "melsec:mx-f"),
    "melsec:mx-r": _PlcProfileDefaults(FrameType.FRAME_4E, PLCSeries.IQR, "melsec:mx-r", "melsec:mx-r"),
    "melsec:mx-r:rj71en71": _PlcProfileDefaults(
        FrameType.FRAME_4E, PLCSeries.IQR, "melsec:mx-r", "melsec:mx-r:rj71en71"
    ),
    "melsec:qcpu": _PlcProfileDefaults(FrameType.FRAME_3E, PLCSeries.QL, "melsec:qcpu", "melsec:qcpu"),
    "melsec:qcpu:qj71e71-100": _PlcProfileDefaults(
        FrameType.FRAME_4E,
        PLCSeries.QL,
        "melsec:qcpu",
        "melsec:qcpu:qj71e71-100",
    ),
    "melsec:lcpu": _PlcProfileDefaults(FrameType.FRAME_3E, PLCSeries.QL, "melsec:lcpu", "melsec:lcpu"),
    "melsec:lcpu:lj71e71-100": _PlcProfileDefaults(
        FrameType.FRAME_4E,
        PLCSeries.QL,
        "melsec:lcpu",
        "melsec:lcpu:lj71e71-100",
    ),
    "melsec:qnu": _PlcProfileDefaults(FrameType.FRAME_3E, PLCSeries.QL, "melsec:qnu", "melsec:qnu"),
    "melsec:qnu:qj71e71-100": _PlcProfileDefaults(
        FrameType.FRAME_4E,
        PLCSeries.QL,
        "melsec:qnu",
        "melsec:qnu:qj71e71-100",
    ),
    "melsec:qnudv": _PlcProfileDefaults(FrameType.FRAME_3E, PLCSeries.QL, "melsec:qnudv", "melsec:qnudv"),
    "melsec:qnudv:qj71e71-100": _PlcProfileDefaults(
        FrameType.FRAME_4E,
        PLCSeries.QL,
        "melsec:qnudv",
        "melsec:qnudv:qj71e71-100",
    ),
}

_PLC_PROFILE_BASES: dict[str, str | None] = {
    "melsec:iq-f": None,
    "melsec:iq-r": None,
    "melsec:iq-r:rj71en71": "melsec:iq-r",
    "melsec:iq-l": None,
    "melsec:mx-f": "melsec:iq-r",
    "melsec:mx-r": "melsec:iq-r",
    "melsec:mx-r:rj71en71": "melsec:mx-r",
    "melsec:qcpu": "melsec:qnu",
    "melsec:qcpu:qj71e71-100": "melsec:qcpu",
    "melsec:lcpu": None,
    "melsec:lcpu:lj71e71-100": "melsec:lcpu",
    "melsec:qnu": None,
    "melsec:qnu:qj71e71-100": "melsec:qnu",
    "melsec:qnudv": None,
    "melsec:qnudv:qj71e71-100": "melsec:qnudv",
}


def plc_profile_descriptors() -> tuple[SlmpPlcProfileDescriptor, ...]:
    """Return all canonical profiles with display, connection, and base metadata.

    The abstract ``melsec:qcpu`` entry is included with ``connectable=False``
    so selectors can explain why it cannot be opened directly.
    """

    return tuple(
        SlmpPlcProfileDescriptor(
            canonical_name=profile.value,
            display_name=display_name(profile),
            connectable=profile is not SlmpPlcProfile.QCpu,
            base_profile=_PLC_PROFILE_BASES[profile.value],
        )
        for profile in SlmpPlcProfile
    )


def _normalize_plc_profile_hint(plc_profile: object | None) -> str | None:
    if plc_profile is None:
        return None
    raw = getattr(plc_profile, "value", plc_profile)
    normalized = str(raw).strip()
    if not normalized:
        return None
    if normalized in _PLC_PROFILES:
        return normalized
    supported = ", ".join(sorted(_PLC_PROFILES))
    raise ValueError(f"Unsupported plc_profile {plc_profile!r}. Supported profiles: {supported}")


def _resolve_plc_profile_defaults(plc_profile: object | None) -> _PlcProfileDefaults | None:
    normalized = _normalize_plc_profile_hint(plc_profile)
    if normalized is None:
        return None
    return _PLC_PROFILE_DEFAULTS[normalized]


def _profile_address_profile(plc_profile: object | None) -> str | None:
    defaults = _resolve_plc_profile_defaults(plc_profile)
    if defaults is None:
        return None
    return defaults.address_profile


def _resolve_connection_profile(
    *,
    plc_profile: object | None,
    plc_series: PLCSeries | str | None,
    frame_type: FrameType | str | None,
    address_profile: object | None,
) -> tuple[str | None, PLCSeries, FrameType, str | None, str | None]:
    defaults = _resolve_plc_profile_defaults(plc_profile)
    if defaults is not None:
        if plc_series is not None or frame_type is not None or address_profile is not None:
            raise ValueError(
                "plc_profile already determines frame_type, access_profile, and address/range handling. "
                "Do not also pass plc_series, frame_type, or address_profile."
            )
        normalized_plc_profile = _normalize_plc_profile_hint(plc_profile)
        if normalized_plc_profile == "melsec:qcpu":
            raise ValueError(_QCPU_BASE_PROFILE_MESSAGE)
        return (
            normalized_plc_profile,
            defaults.plc_series,
            defaults.frame_type,
            defaults.address_profile,
            defaults.range_profile,
        )
    return (
        None,
        PLCSeries(plc_series) if plc_series is not None else PLCSeries.QL,
        FrameType(frame_type) if frame_type is not None else FrameType.FRAME_4E,
        _normalize_plc_profile_hint(address_profile),
        None,
    )


def _resolve_device_radix(code: str, plc_profile: object | None = None) -> int:
    normalized_profile = _profile_address_profile(plc_profile)
    if normalized_profile == "melsec:iq-f" and code in _IQF_OCTAL_DEVICE_CODES:
        return 8
    return DEVICE_CODES[code].radix


def _ensure_device_supported_for_profile(code: str, plc_profile: object | None = None) -> None:
    normalized_profile = _profile_address_profile(plc_profile)
    unsupported = _PROFILE_UNSUPPORTED_DEVICE_CODES.get(normalized_profile or "")
    if unsupported is not None and code in unsupported:
        raise SlmpUnsupportedDeviceError(
            f"SLMP device code '{code}' is not supported for plc_profile '{normalized_profile}'."
        )


def _require_explicit_plc_profile_for_xy(
    value: str | DeviceRef,
    plc_profile: object | None,
    ref: DeviceRef,
) -> DeviceRef:
    normalized_profile = _normalize_plc_profile_hint(plc_profile)
    if normalized_profile is None:
        raise ValueError("plc_profile is required for semantic device addresses")
    if ref.plc_profile != normalized_profile:
        raise ValueError(
            f"DeviceRef plc_profile {ref.plc_profile!r} does not match requested plc_profile {normalized_profile!r}."
        )
    return ref


def _split_device_text(value: str, text: str) -> tuple[str, str]:
    valid_codes = ", ".join(sorted(DEVICE_CODES.keys()))
    if not re.fullmatch(r"[A-Z]+[0-9A-F]+", text):
        raise ValueError(
            f"Invalid SLMP device string {value!r}. "
            f"Expected format: <DeviceCode><Number> (e.g. 'D100', 'X1F'). "
            f"Valid device codes: {valid_codes}"
        )

    for code in _DEVICE_CODE_CANDIDATES:
        if text.startswith(code):
            return code, text[len(code) :]

    match = re.fullmatch(r"([A-Z]+)([0-9A-F]+)", text)
    unknown_code = match.group(1) if match else text
    raise ValueError(f"Unknown SLMP device code '{unknown_code}' in {value!r}. Valid codes: {valid_codes}")


@dataclass(frozen=True)
class SlmpResponse:
    """Decoded SLMP response frame.

    Attributes:
        serial: Serial number matching the request.
        target: Source station routing information.
        end_code: Response end code (0x0000 for success).
        data: Command-specific response payload.
        raw: Full raw binary response frame.
        error_info: Structured PLC error information when end_code is non-zero and present.
    """

    serial: int
    target: SlmpTarget
    end_code: int
    data: bytes
    raw: bytes
    error_info: SlmpErrorInfo | None = None

    @property
    def is_success(self) -> bool:
        """Return True if the response end_code is 0."""
        return self.end_code == 0


@dataclass(frozen=True)
class _SlmpResponseView:
    """Private successful response whose payload borrows its owned raw frame."""

    serial: int
    target: SlmpTarget
    end_code: int
    data: memoryview
    raw: bytes
    error_info: None = None


_SlmpDecodedResponse = SlmpResponse | _SlmpResponseView


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
class _SlmpTraceFrame:
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
class _ExtensionSpec:
    """Extended Device extension fields (binary, 0080..0083)."""

    extension_specification: int = 0x0000
    extension_specification_modification: int = 0x00
    device_modification_index: int = 0x00
    device_modification_flags: int = 0x00
    direct_memory_specification: int = DIRECT_MEMORY_NORMAL


@dataclass(frozen=True)
class SlmpIndexZ:
    """Typed Z index-register modification for one Extended Device operand."""

    index: int

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise ValueError("SlmpIndexZ.index must be an integer in range 0..255")
        _check_u8(self.index, "SlmpIndexZ.index")


@dataclass(frozen=True)
class SlmpIndexLz:
    """Typed LZ long-index-register modification for one Extended Device operand."""

    index: int

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise ValueError("SlmpIndexLz.index must be an integer in range 0..1")
        if not 0 <= self.index <= 1:
            raise ValueError(f"SlmpIndexLz.index out of range (0..1): {self.index}")


@dataclass(frozen=True)
class SlmpIndirect:
    """Typed word-device indirect modification for one Extended Device operand."""


SlmpDeviceModification = SlmpIndexZ | SlmpIndexLz | SlmpIndirect


@dataclass(frozen=True)
class SlmpExtendedDevice:
    """Qualified Extended Device text plus an optional typed modification."""

    address: str
    modification: SlmpDeviceModification | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.address, str) or not self.address.strip():
            raise ValueError("SlmpExtendedDevice.address must be a non-empty qualified device string")
        object.__setattr__(self, "address", self.address.strip())
        if self.modification is not None and not isinstance(
            self.modification,
            (SlmpIndexZ, SlmpIndexLz, SlmpIndirect),
        ):
            raise ValueError("SlmpExtendedDevice.modification must be SlmpIndexZ, SlmpIndexLz, SlmpIndirect, or None")


def _format_semantic_extended_device_key(
    device: str | SlmpExtendedDevice,
    *,
    plc_profile: object,
) -> str:
    """Return a canonical result key that preserves the complete Extended Device route."""
    address = device.address if isinstance(device, SlmpExtendedDevice) else device
    parsed = _parse_extended_device(address, plc_profile=plc_profile)
    if parsed.qualifier == "J":
        assert parsed.extension_specification is not None
        key = f"J{parsed.extension_specification}\\{parsed.ref}"
    elif parsed.qualifier == "U":
        assert parsed.extension_specification is not None
        key = f"U{parsed.extension_specification:X}\\{parsed.ref}"
    else:
        key = str(parsed.ref)

    modification = device.modification if isinstance(device, SlmpExtendedDevice) else None
    if isinstance(modification, SlmpIndexZ):
        return f"{key}+Z{modification.index}"
    if isinstance(modification, SlmpIndexLz):
        return f"{key}+LZ{modification.index}"
    if isinstance(modification, SlmpIndirect):
        return f"{key}+INDIRECT"
    return key


@dataclass(frozen=True)
class _ExtendedDevice:
    """Extended Device text plus optional qualified extension-specification override."""

    ref: DeviceRef
    extension_specification: int | None = None
    direct_memory_specification: int | None = None
    qualifier: str | None = None


def parse_device(
    value: str | DeviceRef,
    *,
    plc_profile: object,
) -> DeviceRef:
    """Parse a device string into a `DeviceRef`.

    Args:
        value: Device string (e.g. 'D100', 'X1F') or `DeviceRef` object.
        plc_profile: Exact canonical PLC profile that defines the device grammar.

    Returns:
        A `DeviceRef` object containing the device code and numeric address.

    Raises:
        ValueError: If the profile is missing or ambiguous, the device format is
            invalid, the code is unsupported, or a bound `DeviceRef` belongs to
            another profile.
    """
    normalized_profile = _normalize_plc_profile_hint(plc_profile)
    if normalized_profile is None:
        raise ValueError("plc_profile is required for semantic device addresses")
    if normalized_profile == SlmpPlcProfile.QCpu.value:
        raise ValueError(_QCPU_BASE_PROFILE_MESSAGE)
    if isinstance(value, DeviceRef):
        if value.plc_profile != normalized_profile:
            raise ValueError(
                f"DeviceRef plc_profile {value.plc_profile!r} does not match requested "
                f"plc_profile {normalized_profile!r}."
            )
        return value

    text = value.strip().upper()
    code, num_txt = _split_device_text(value, text)
    _ensure_device_supported_for_profile(code, normalized_profile)

    base = _resolve_device_radix(code, normalized_profile)
    try:
        number = int(num_txt, base)
    except ValueError:
        raise ValueError(f"Invalid SLMP device number {num_txt!r} for device code '{code}' in {value!r}.") from None
    return DeviceRef(code=code, number=number, plc_profile=normalized_profile)


def _parse_extended_device(
    value: str | DeviceRef,
    *,
    plc_profile: object,
) -> _ExtendedDevice:
    r"""Parse an Extended Device string (e.g., 'U01\G10', 'J2\SW10') or return _ExtendedDevice as-is."""
    if isinstance(value, DeviceRef):
        return _ExtendedDevice(ref=parse_device(value, plc_profile=plc_profile))

    text = value.strip().upper()

    # J-format: link direct device (e.g. 'J2\SW10')
    j_qualified = re.fullmatch(r"J([0-9]+)[\\/](.+)", text)
    if j_qualified:
        j_net_txt, device_txt = j_qualified.groups()
        j_network = int(j_net_txt)
        _check_u8(j_network, "extended_device j_network")
        return _ExtendedDevice(
            ref=parse_device(device_txt, plc_profile=plc_profile),
            extension_specification=j_network,
            direct_memory_specification=DIRECT_MEMORY_LINK_DIRECT,
            qualifier="J",
        )

    qualified = re.fullmatch(r"U([0-9A-F]+)[\\/](.+)", text)
    if qualified:
        extension_txt, device_txt = qualified.groups()
        extension_specification = int(extension_txt, 16)
        _check_u16(extension_specification, "extended_device extension_specification")
        dev_ref = parse_device(device_txt, plc_profile=plc_profile)
        # G/HG buffer memory devices have a fixed DM by device code (matches GOT pcap-verified format)
        dm: int | None = None
        if dev_ref.code == "G":
            dm = DIRECT_MEMORY_MODULE_ACCESS  # 0xF8
        elif dev_ref.code == "HG":
            _validate_hg_extension_specification(extension_specification)
            dm = DIRECT_MEMORY_CPU_BUFFER  # 0xFA
        return _ExtendedDevice(
            ref=dev_ref,
            extension_specification=extension_specification,
            direct_memory_specification=dm,
            qualifier="U",
        )

    return _ExtendedDevice(ref=parse_device(value, plc_profile=plc_profile))


def _resolve_extended_device_and_extension(
    device: str | DeviceRef,
    extension: _ExtensionSpec,
    *,
    plc_profile: object,
) -> tuple[DeviceRef, _ExtensionSpec]:
    """Resolve device and extension specification, prioritizing explicit qualification in the device string."""
    qualified = _parse_extended_device(device, plc_profile=plc_profile)
    _validate_g_hg_extended_device_qualification(qualified)
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
    elif (
        qualified.direct_memory_specification is not None
        and extension.direct_memory_specification != qualified.direct_memory_specification
    ):
        raise ValueError(
            f"{qualified.ref.code} Extended Device access requires "
            f"direct_memory_specification=0x{qualified.direct_memory_specification:02X}; "
            f"got 0x{extension.direct_memory_specification:02X}"
        )
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
    data: bytes | memoryview = b"",
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
    data: bytes | memoryview = b"",
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
    data: bytes | memoryview = b"",
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


def _decode_3e_response(frame: bytes, *, view_data: bool) -> _SlmpDecodedResponse:
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
    if view_data and end_code == 0:
        return _SlmpResponseView(
            serial=0,
            target=target,
            end_code=end_code,
            data=memoryview(frame)[11:],
            raw=frame,
        )
    data = frame[11:]
    error_info = SlmpErrorInfo.parse(data) if end_code != 0 else None
    return SlmpResponse(serial=0, target=target, end_code=end_code, data=data, raw=frame, error_info=error_info)


def decode_3e_response(frame: bytes) -> SlmpResponse:
    """Decode a 3E response frame with independently owned public payload data."""
    response = _decode_3e_response(frame, view_data=False)
    if not isinstance(response, SlmpResponse):
        raise AssertionError("public 3E decoding must return owned response data")
    return response


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


def _decode_response_view(frame: bytes, *, frame_type: FrameType) -> _SlmpDecodedResponse:
    """Decode a private typed response with a payload view over its owned frame."""
    if frame_type == FrameType.FRAME_3E:
        return _decode_3e_response(frame, view_data=True)
    return _decode_4e_response(frame, view_data=True)


def _decode_4e_response(frame: bytes, *, view_data: bool) -> _SlmpDecodedResponse:
    if len(frame) < 15:
        raise SlmpError(f"response too short: {len(frame)} bytes")
    if frame[:2] != FRAME_4E_RESPONSE_SUBHEADER:
        got = frame[:2].hex(" ").upper()
        raise SlmpError(f"unexpected 4E response subheader: {got}")
    if frame[4:6] != b"\x00\x00":
        got = frame[4:6].hex(" ").upper()
        raise SlmpError(f"unexpected 4E response reserved field: {got}")

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
    if view_data and end_code == 0:
        return _SlmpResponseView(
            serial=serial,
            target=target,
            end_code=end_code,
            data=memoryview(frame)[15:],
            raw=frame,
        )
    data = frame[15:]
    error_info = SlmpErrorInfo.parse(data) if end_code != 0 else None
    return SlmpResponse(serial=serial, target=target, end_code=end_code, data=data, raw=frame, error_info=error_info)


def decode_4e_response(frame: bytes) -> SlmpResponse:
    """Decode a 4E response frame with independently owned public payload data."""
    response = _decode_4e_response(frame, view_data=False)
    if not isinstance(response, SlmpResponse):
        raise AssertionError("public 4E decoding must return owned response data")
    return response


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
    plc_profile: object | None = None,
) -> bytes:
    """Encode a device specification into bytes based on the PLC series."""
    if isinstance(device, DeviceRef) and plc_profile is None:
        ref = device
    else:
        ref = parse_device(device, plc_profile=plc_profile)
    # PROFILE_RANGE_NOT_A_TRANSPORT_GUARD: PLC profile device ranges are
    # application-layer metadata. Validate syntax, device support, and only
    # the selected wire representation width in the communication library.
    dev = DEVICE_CODES[ref.code]

    if series == PLCSeries.QL:
        if ref.number < 0 or ref.number > 0xFFFFFF:
            raise ValueError(f"device number out of range for Q/L format: {ref.number}")
        return ref.number.to_bytes(3, "little") + (dev.code & 0xFF).to_bytes(1, "little")

    _check_u32(ref.number, "device.number")
    return ref.number.to_bytes(4, "little") + dev.code.to_bytes(2, "little")


def _validate_device_span(
    ref: DeviceRef,
    *,
    points: int,
    series: PLCSeries,
    operation: str,
) -> None:
    """Validate a contiguous request against the selected wire address width."""
    maximum = 0xFFFFFF if series == PLCSeries.QL else 0xFFFFFFFF
    end = ref.number + points - 1
    if ref.number < 0 or end > maximum:
        raise ValueError(
            f"{operation} device span out of range for {series.value} format: "
            f"start={ref.number}, points={points}, end={end}, maximum={maximum}"
        )


def _encode_extension_spec(spec: _ExtensionSpec) -> bytes:
    """Encode an Extended Device extension specification into bytes."""
    _validate_extension_spec(spec)
    return (
        spec.extension_specification.to_bytes(2, "little")
        + spec.extension_specification_modification.to_bytes(1, "little")
        + spec.device_modification_index.to_bytes(1, "little")
        + spec.device_modification_flags.to_bytes(1, "little")
    )


def _validate_extension_spec(spec: _ExtensionSpec) -> None:
    _check_u16(spec.extension_specification, "extension_specification")
    _check_u8(spec.extension_specification_modification, "extension_specification_modification")
    _check_u8(spec.device_modification_index, "device_modification_index")
    _check_u8(spec.device_modification_flags, "device_modification_flags")
    _check_u8(spec.direct_memory_specification, "direct_memory_specification")


def _validate_hg_extension_specification(extension_specification: int) -> None:
    if extension_specification not in _HG_VALID_EXTENSION_SPECIFICATIONS:
        raise ValueError("HG Extended Device access is valid only for U3E0\\HG through U3E3\\HG.")


def _validate_g_hg_extended_device_qualification(device: _ExtendedDevice) -> None:
    if device.ref.code == "G":
        if device.qualifier != "U":
            raise ValueError("G Extended Device access requires U-qualified module access such as U1\\G0.")
        return
    if device.ref.code != "HG":
        return
    if device.qualifier != "U":
        raise ValueError("HG Extended Device access requires U-qualified CPU-buffer access U3E0\\HG through U3E3\\HG.")
    assert device.extension_specification is not None
    _validate_hg_extension_specification(device.extension_specification)


def _encode_manual_extended_device_spec(
    ref: DeviceRef,
    *,
    series: PLCSeries,
    extension: _ExtensionSpec,
    include_direct_memory_at_end: bool,
) -> bytes:
    _validate_extension_spec(extension)
    payload = bytearray()
    payload += extension.device_modification_index.to_bytes(1, "little")
    payload += extension.device_modification_flags.to_bytes(1, "little")
    payload += encode_device_spec(ref, series=series)
    payload += extension.extension_specification_modification.to_bytes(1, "little")
    payload += b"\x00"
    payload += extension.extension_specification.to_bytes(2, "little")
    if include_direct_memory_at_end:
        payload += extension.direct_memory_specification.to_bytes(1, "little")
    return bytes(payload)


def _encode_link_direct_device_spec(
    ref: DeviceRef,
    *,
    extension: _ExtensionSpec,
    include_direct_memory_at_end: bool,
) -> bytes:
    """Encode a link direct device spec (J\\device) verified by GOT pcap.

    Format: reserved(2) + dev_no(3) + dev_code(1) + reserved(2) + j_net(1) + reserved(1) + 0xF9(1)
    Always uses QL (3-byte device number) format.
    """
    if ref.number < 0 or ref.number > 0xFFFFFF:
        raise ValueError(f"link-direct device number out of range for Q/L format: {ref.number}")
    if extension.extension_specification > 0xFF:
        raise ValueError(
            f"link-direct network number must fit the 8-bit wire field: {extension.extension_specification}"
        )
    j_net = extension.extension_specification
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


def _encode_extended_device_spec(
    device: str | DeviceRef,
    *,
    series: PLCSeries,
    extension: _ExtensionSpec,
    include_direct_memory_at_end: bool = True,
    plc_profile: object | None = None,
) -> bytes:
    """Encode an Extended Device extended device specification into bytes."""
    ref, effective_extension = _resolve_extended_device_and_extension(device, extension, plc_profile=plc_profile)
    return _encode_resolved_extended_device_spec(
        ref,
        series=series,
        extension=effective_extension,
        include_direct_memory_at_end=include_direct_memory_at_end,
    )


def _encode_resolved_extended_device_spec(
    ref: DeviceRef,
    *,
    series: PLCSeries,
    extension: _ExtensionSpec,
    include_direct_memory_at_end: bool = True,
) -> bytes:
    """Encode an already validated Extended Device spec."""
    if extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        return _encode_link_direct_device_spec(
            ref,
            extension=extension,
            include_direct_memory_at_end=include_direct_memory_at_end,
        )
    return _encode_manual_extended_device_spec(
        ref,
        series=series,
        extension=extension,
        include_direct_memory_at_end=include_direct_memory_at_end,
    )


def _resolved_extended_device_spec_size(
    *,
    series: PLCSeries,
    extension: _ExtensionSpec,
    include_direct_memory_at_end: bool = True,
) -> int:
    """Return the exact encoded size for an already validated extension."""
    if extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        return 11 if include_direct_memory_at_end else 10
    device_size = 4 if series == PLCSeries.QL else 6
    return 2 + device_size + 4 + int(include_direct_memory_at_end)


def _encode_resolved_extended_device_spec_into(
    ref: DeviceRef,
    *,
    series: PLCSeries,
    extension: _ExtensionSpec,
    output: bytearray,
    offset: int,
    include_direct_memory_at_end: bool = True,
) -> int:
    """Directly encode an already validated extension into a final buffer."""
    start = offset
    dev_code = DEVICE_CODES[ref.code].code
    if extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        output[offset] = 0
        output[offset + 1] = 0
        output[offset + 2] = ref.number & 0xFF
        output[offset + 3] = (ref.number >> 8) & 0xFF
        output[offset + 4] = (ref.number >> 16) & 0xFF
        output[offset + 5] = dev_code & 0xFF
        output[offset + 6] = 0
        output[offset + 7] = 0
        output[offset + 8] = extension.extension_specification & 0xFF
        output[offset + 9] = 0
        offset += 10
        if include_direct_memory_at_end:
            output[offset] = DIRECT_MEMORY_LINK_DIRECT
            offset += 1
        return offset - start

    output[offset] = extension.device_modification_index
    output[offset + 1] = extension.device_modification_flags
    offset += 2
    output[offset] = ref.number & 0xFF
    output[offset + 1] = (ref.number >> 8) & 0xFF
    output[offset + 2] = (ref.number >> 16) & 0xFF
    if series == PLCSeries.QL:
        output[offset + 3] = dev_code & 0xFF
        offset += 4
    else:
        output[offset + 3] = (ref.number >> 24) & 0xFF
        output[offset + 4] = dev_code & 0xFF
        output[offset + 5] = (dev_code >> 8) & 0xFF
        offset += 6
    output[offset] = extension.extension_specification_modification
    output[offset + 1] = 0
    output[offset + 2] = extension.extension_specification & 0xFF
    output[offset + 3] = (extension.extension_specification >> 8) & 0xFF
    offset += 4
    if include_direct_memory_at_end:
        output[offset] = extension.direct_memory_specification
        offset += 1
    return offset - start


def _build_device_modification_flags(
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


def _apply_semantic_device_modification(
    extension: _ExtensionSpec,
    modification: SlmpDeviceModification | None,
    *,
    series: PLCSeries,
) -> _ExtensionSpec:
    if modification is None:
        return extension
    if extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
        raise ValueError("J-qualified link-direct devices do not support Z, LZ, or indirect modification")
    if isinstance(modification, SlmpIndexZ):
        return replace(
            extension,
            device_modification_index=modification.index,
            device_modification_flags=_build_device_modification_flags(series=series, register_mode="z"),
        )
    if isinstance(modification, SlmpIndexLz):
        return replace(
            extension,
            device_modification_index=modification.index,
            device_modification_flags=_build_device_modification_flags(series=series, register_mode="lz"),
        )
    return replace(
        extension,
        device_modification_index=0,
        device_modification_flags=_build_device_modification_flags(
            series=series,
            use_indirect_specification=True,
        ),
    )


def decode_device_words(data: bytes | memoryview) -> list[int]:
    """Decode a byte array into a list of 16-bit word values."""
    if len(data) % 2 != 0:
        raise SlmpError(f"word data length must be even: {len(data)}")
    return [int.from_bytes(data[i : i + 2], "little") for i in range(0, len(data), 2)]


def decode_device_dwords(data: bytes | memoryview) -> list[int]:
    """Decode a byte array into a list of 32-bit double-word values."""
    if len(data) % 4 != 0:
        raise SlmpError(f"dword data length must be multiple of 4: {len(data)}")
    return [int.from_bytes(data[i : i + 4], "little") for i in range(0, len(data), 4)]


def pack_bit_values(values: Iterable[bool]) -> bytes:
    """Pack a sequence of bit values into binary format.

    In SLMP binary bit-unit access, each byte contains two points.
    The high nibble stores the first point, and the low nibble stores the second.

    Args:
        values: An iterable of Boolean values. Integers, including 0 and 1,
            are rejected.

    Returns:
        Packed binary data.
    """
    bits = [_require_write_bit(value, "bit value") for value in values]
    out = bytearray()
    for i in range(0, len(bits), 2):
        hi = bits[i] & 0x1
        lo = bits[i + 1] & 0x1 if i + 1 < len(bits) else 0
        out.append((hi << 4) | lo)
    return bytes(out)


def unpack_bit_values(data: bytes | memoryview, count: int) -> list[bool]:
    """Unpack binary bit data into a list of booleans.

    Args:
        data: Binary data received from the PLC.
        count: The number of bit points to extract.

    Returns:
        A list of boolean values.

    Raises:
        SlmpError: If the data length or any used bit nibble is invalid.
    """
    expected_bytes = (count + 1) // 2
    if len(data) != expected_bytes:
        raise SlmpError(f"bit data length mismatch: expected={expected_bytes}, actual={len(data)}")

    result: list[bool] = []
    for byte in data:
        high = (byte >> 4) & 0x0F
        if high not in (0, 1):
            raise SlmpError(f"bit data contains non-binary high nibble: 0x{high:X}")
        result.append(high == 1)
        if len(result) < count:
            low = byte & 0x0F
            if low not in (0, 1):
                raise SlmpError(f"bit data contains non-binary low nibble: 0x{low:X}")
            result.append(low == 1)
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


def _require_write_u16(value: object, name: str = "value") -> int:
    """Return one exact unsigned word value or reject before frame creation."""
    if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise ValueError(f"{name} must be an integer in range 0..65535: {value!r}")
    return value


def _require_write_u32(value: object, name: str = "value") -> int:
    """Return one exact unsigned double-word value or reject before frame creation."""
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"{name} must be an integer in range 0..4294967295: {value!r}")
    return value


def _require_write_bit(value: object, name: str = "value") -> int:
    """Return 0/1 for an explicit native Boolean bit value."""
    if type(value) is bool:
        return 1 if value else 0
    raise ValueError(f"{name} must be bool: {value!r}")


def _check_points_u16(points: int, name: str) -> None:
    if points < 0 or points > 0xFFFF:
        raise ValueError(f"{name} out of range (0..65535): {points}")


def _uses_iqf_direct_bit_limit(plc_profile: object | None) -> bool:
    if plc_profile is None:
        return False
    try:
        return SlmpPlcProfile(plc_profile) is SlmpPlcProfile.IqF
    except ValueError:
        return False


def _check_direct_device_points(
    points: int,
    *,
    bit_unit: bool,
    name: str,
    write: bool = False,
    plc_profile: object | None = None,
) -> None:
    if bit_unit:
        fallback = 3584 if _uses_iqf_direct_bit_limit(plc_profile) else 7168
        limit_info = profile_limit(plc_profile, "direct_bit_write" if write else "direct_bit_read")
    else:
        fallback = 960
        limit_info = profile_limit(plc_profile, "direct_word_write" if write else "direct_word_read")
    limit = limit_info.max if limit_info is not None else fallback
    unit = "bit" if bit_unit else "word"
    if points < 1 or points > limit:
        raise ValueError(f"{name} {unit} access points out of range (1..{limit}): {points}")


def _check_random_read_like_counts(
    word_points: int,
    dword_points: int,
    *,
    series: PLCSeries,
    name: str,
    extension: bool = False,
    plc_profile: object | None = None,
    limit_key: str = "random_read_word",
) -> None:
    if word_points < 0 or dword_points < 0:
        raise ValueError(
            f"{name} word_points and dword_points must be non-negative: word={word_points}, dword={dword_points}"
        )
    total = word_points + dword_points
    effective_limit_key = f"{limit_key}_ext" if extension else limit_key
    limit_info = profile_limit(plc_profile, effective_limit_key)
    fallback_limit = 96 if extension or series == PLCSeries.IQR else 192
    limit = limit_info.max if limit_info is not None else fallback_limit
    if total < 1 or total > limit:
        raise ValueError(
            f"{name} total access points out of range (1..{limit}) for {series.value}: "
            f"word={word_points}, dword={dword_points}"
        )


def _check_random_bit_write_count(
    points: int,
    *,
    series: PLCSeries,
    name: str,
    extension: bool = False,
    plc_profile: object | None = None,
) -> None:
    limit_info = profile_limit(plc_profile, "random_write_bit_ext" if extension else "random_write_bit")
    fallback_limit = 94 if extension or series == PLCSeries.IQR else 188
    limit = limit_info.max if limit_info is not None else fallback_limit
    if points < 1 or points > limit:
        raise ValueError(f"{name} bit access points out of range (1..{limit}) for {series.value}: {points}")


def _check_random_write_word_counts(
    word_points: int,
    dword_points: int,
    *,
    series: PLCSeries,
    name: str,
    extension: bool = False,
    plc_profile: object | None = None,
) -> None:
    total = word_points + dword_points
    if total < 1:
        raise ValueError(f"{name} word/dword access points out of range: word={word_points}, dword={dword_points}")
    weighted = word_points * 12 + dword_points * 14
    limit_info = profile_limit(plc_profile, "random_write_word_ext" if extension else "random_write_word")
    if limit_info is not None:
        count_limit = limit_info.max
        if total > count_limit:
            raise ValueError(
                f"{name} word/dword access points out of range (1..{count_limit}): "
                f"word={word_points}, dword={dword_points}"
            )
        weighted_limit = limit_info.weighted_max
        if weighted_limit is not None and weighted > weighted_limit:
            raise ValueError(
                f"{name} word/dword access points out of range for {series.value}: "
                f"word={word_points}, dword={dword_points}, weighted={weighted}, "
                f"limit={weighted_limit}"
            )
        return
    limit = 960 if extension or series == PLCSeries.IQR else 1920
    if weighted > limit:
        raise ValueError(
            f"{name} word/dword access points out of range for {series.value}: "
            f"word={word_points}, dword={dword_points}, weighted={weighted}, limit={limit}"
        )


def _block_points(points: int | Sequence[object], name: str) -> int:
    count = int(points) if isinstance(points, int) else len(points)
    if count < 1 or count > 0xFFFF:
        raise ValueError(f"{name} block points out of range (1..65535): {count}")
    return count


def _check_block_request_limits(
    word_blocks: Sequence[tuple[str | DeviceRef, int | Sequence[object]]],
    bit_blocks: Sequence[tuple[str | DeviceRef, int | Sequence[object]]],
    *,
    series: PLCSeries,
    name: str,
    write: bool = False,
    plc_profile: object | None = None,
) -> None:
    total_blocks = len(word_blocks) + len(bit_blocks)
    block_limit = 60 if series == PLCSeries.IQR else 120
    if total_blocks < 1 or total_blocks > block_limit:
        raise ValueError(f"{name} total block count out of range (1..{block_limit}) for {series.value}: {total_blocks}")

    total_points = 0
    for _, points in word_blocks:
        total_points += _block_points(points, f"{name} word")
    for _, points in bit_blocks:
        total_points += _block_points(points, f"{name} bit")
    limit_value = total_points
    if write:
        per_block_overhead = 9 if series == PLCSeries.IQR else 4
        limit_value += total_blocks * per_block_overhead
    limit_key = "direct_word_write" if write else "direct_word_read"
    limit_info = profile_limit(plc_profile, limit_key)
    limit = limit_info.max if limit_info is not None else 960
    if limit_value > limit:
        detail = f"weighted={limit_value}, total_points={total_points}" if write else f"total_points={total_points}"
        raise ValueError(f"{name} total device points out of range (<={limit}): {detail}")


def _normalize_items(
    values: Mapping[str | DeviceRef, Any] | Sequence[tuple[str | DeviceRef, Any]],
    *,
    plc_profile: object,
) -> list[tuple[DeviceRef, Any]]:
    if isinstance(values, Mapping):
        items = list(values.items())
    else:
        items = list(values)
    return [(parse_device(device, plc_profile=plc_profile), value) for device, value in items]


def _raise_response_error(response: SlmpResponse, *, command: int | Command, subcommand: int) -> None:
    if response.end_code == 0:
        return
    raise SlmpError(
        f"SLMP error end_code=0x{response.end_code:04X} command=0x{int(command):04X} subcommand=0x{subcommand:04X}",
        end_code=response.end_code,
        data=response.data,
        error_info=response.error_info,
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
            "use the explicitly qualified Extended Device route supported by the selected profile"
        )
    raise SlmpUnsupportedDeviceError(
        f"{ref.code} is temporarily unsupported in typed device APIs on this project; "
        "the access path should be revisited when the cause is known"
    )


def _check_temporarily_unsupported_devices(refs: Sequence[DeviceRef], *, access_kind: str = "direct") -> None:
    for ref in refs:
        _check_temporarily_unsupported_device(ref, access_kind=access_kind)


def _device_unit(ref: DeviceRef) -> DeviceUnit:
    """Return the canonical semantic unit for a parsed device."""
    return DEVICE_CODES[ref.code].unit


def _require_bit_device(ref: DeviceRef, *, operation: str) -> None:
    if _device_unit(ref) != DeviceUnit.BIT:
        raise ValueError(
            f"{operation} requires a bit device; {ref.code} is a word device. "
            "Use an explicit word-unit API for packed access or '.bit' notation for one bit inside a word device."
        )


def _require_word_device(ref: DeviceRef, *, operation: str) -> None:
    if _device_unit(ref) != DeviceUnit.WORD:
        raise ValueError(
            f"{operation} requires a word device; {ref.code} is a bit device. "
            "Use an explicit word-unit direct API only when packed bit-device access is intended."
        )


def _validate_direct_read_device(
    ref: DeviceRef,
    *,
    points: int,
    bit_unit: bool,
    enforce_semantic_unit: bool = True,
) -> None:
    if bit_unit and enforce_semantic_unit:
        _require_bit_device(ref, operation="Direct bit read")
    if bit_unit and ref.code in _LT_LST_DIRECT_CODES:
        raise ValueError(
            f"Direct bit read is not supported for {ref.code}. "
            "Use read_ltc_states/read_lts_states/read_lstc_states/read_lsts_states "
            "or read_long_timer/read_long_retentive_timer."
        )
    if not bit_unit and ref.code in _LT_LST_CURRENT_BLOCK_CODES and points % 4 != 0:
        raise ValueError(
            f"Direct read of {ref.code} requires 4-word blocks. "
            f"Requested points={points}; use a multiple of 4 or the long timer helpers."
        )
    if not bit_unit and ref.code in _RANDOM_DWORD_ONLY_DIRECT_CODES:
        raise ValueError(
            f"Direct word read is not supported for {ref.code}. Use read_typed/read_named for 32-bit access."
        )


def _is_read_only_device(ref: DeviceRef, plc_profile: object | None = None) -> bool:
    return is_profile_read_only_device(plc_profile, ref.code)


def _validate_direct_write_device(
    ref: DeviceRef,
    *,
    bit_unit: bool,
    plc_profile: object | None = None,
    enforce_semantic_unit: bool = True,
) -> None:
    if bit_unit and enforce_semantic_unit:
        _require_bit_device(ref, operation="Direct bit write")
    if _is_read_only_device(ref, plc_profile):
        raise ValueError(f"{ref.code} is read-only for the selected PLC profile and cannot be written.")
    if bit_unit and ref.code in _LONG_FAMILY_STATE_WRITE_DIRECT_CODES:
        raise ValueError(
            f"Direct bit write is not supported for {ref.code}. "
            "Use write_typed/write_named so random bit write (0x1402) is selected."
        )
    if not bit_unit and (ref.code in _LT_LST_CURRENT_CODES or ref.code in _DWORD_ONLY_DIRECT_CODES):
        raise ValueError(
            f"Direct word write is not supported for {ref.code}. Use write_typed/write_named for 32-bit access."
        )


def _validate_direct_dword_read_device(ref: DeviceRef) -> None:
    if ref.code in _LT_LST_CURRENT_CODES or ref.code in _DWORD_ONLY_DIRECT_CODES:
        raise ValueError(
            f"Direct dword read is not supported for {ref.code}. "
            "Use read_typed so the supported 32-bit route is selected; "
            "read_named is available only for random-readable LCN/LZ entries."
        )


def _validate_random_read_devices(word_refs: Sequence[DeviceRef], dword_refs: Sequence[DeviceRef]) -> None:
    if any(ref.code in _LT_LST_DIRECT_CODES for ref in (*word_refs, *dword_refs)):
        raise ValueError(
            "Read Random (0x0403) does not support LTS/LTC/LSTS/LSTC. "
            "Use read_typed or the explicit long-timer status helpers instead."
        )
    if any(ref.code in _LC_CONTACT_CODES for ref in (*word_refs, *dword_refs)):
        raise ValueError(
            "Read Random (0x0403) does not support LCS/LCC. Use read_typed or the explicit long-counter state helpers."
        )
    if any(ref.code in _LT_LST_CURRENT_CODES or ref.code in _DWORD_ONLY_DIRECT_CODES for ref in word_refs):
        raise ValueError(
            "Read Random (0x0403) does not support LTN/LSTN/LCN/LZ as word entries. "
            "Use explicit dword entries or read_typed; read_named ':D' or ':L' is available only for LCN/LZ."
        )


def _random_device_span_points(ref: DeviceRef, *, dword: bool) -> int:
    """Return logical device numbers consumed by one Random/Monitor entry."""
    if dword and (ref.code in _LT_LST_CURRENT_CODES or ref.code in _DWORD_ONLY_DIRECT_CODES):
        return 1
    word_points = 2 if dword else 1
    return word_points * 16 if _device_unit(ref) == DeviceUnit.BIT else word_points


def _validate_random_write_word_devices(
    word_refs: Sequence[DeviceRef],
    dword_refs: Sequence[DeviceRef] = (),
    *,
    plc_profile: object | None = None,
    word_namespaces: Sequence[object] | None = None,
    dword_namespaces: Sequence[object] | None = None,
) -> None:
    read_only = next((ref for ref in (*word_refs, *dword_refs) if _is_read_only_device(ref, plc_profile)), None)
    if read_only is not None:
        raise ValueError(
            f"Write Random (0x1402) does not support read-only device {read_only.code} for the selected PLC profile."
        )
    if any(ref.code in _LT_LST_CURRENT_CODES or ref.code in _DWORD_ONLY_DIRECT_CODES for ref in word_refs):
        raise ValueError(
            "Write Random (0x1402) does not support LTN/LSTN/LCN/LZ as word entries. "
            "Use dword entries or write_typed/write_named with ':D' or ':L' instead."
        )
    word_scopes = tuple(word_namespaces) if word_namespaces is not None else (None,) * len(word_refs)
    dword_scopes = tuple(dword_namespaces) if dword_namespaces is not None else (None,) * len(dword_refs)
    if len(word_scopes) != len(word_refs) or len(dword_scopes) != len(dword_refs):
        raise ValueError("random write destination namespace count mismatch")
    occupied: set[tuple[object, str, int]] = set()
    starts: set[tuple[object, str, int]] = set()
    for ref, scope in zip(word_refs, word_scopes, strict=True):
        start = (scope, ref.code, ref.number)
        if start in starts:
            raise ValueError(f"Write Random (0x1402) has a duplicate destination: {ref}")
        slots = {
            (scope, ref.code, ref.number + offset) for offset in range(_random_device_span_points(ref, dword=False))
        }
        if occupied.intersection(slots):
            raise ValueError(f"Write Random (0x1402) has overlapping word destinations: {ref}")
        occupied.update(slots)
        starts.add(start)
    for ref, scope in zip(dword_refs, dword_scopes, strict=True):
        start = (scope, ref.code, ref.number)
        if start in starts:
            raise ValueError(f"Write Random (0x1402) has a duplicate destination: {ref}")
        slots = {
            (scope, ref.code, ref.number + offset) for offset in range(_random_device_span_points(ref, dword=True))
        }
        if occupied.intersection(slots):
            raise ValueError(f"Write Random (0x1402) has overlapping word/dword destinations: {ref}")
        occupied.update(slots)
        starts.add(start)


def _validate_random_write_bit_devices(
    bit_refs: Sequence[DeviceRef],
    *,
    plc_profile: object | None = None,
    namespaces: Sequence[object] | None = None,
) -> None:
    for ref in bit_refs:
        _require_bit_device(ref, operation="Random bit write")
    read_only = next((ref for ref in bit_refs if _is_read_only_device(ref, plc_profile)), None)
    if read_only is not None:
        raise ValueError(
            f"Write Random (0x1402) does not support read-only device {read_only.code} for the selected PLC profile."
        )
    if any(ref.code in _G_HG_CODES for ref in bit_refs):
        raise ValueError("Write Random (0x1402) does not support G/HG bit entries. Use U-qualified word access.")
    scopes = tuple(namespaces) if namespaces is not None else (None,) * len(bit_refs)
    if len(scopes) != len(bit_refs):
        raise ValueError("random bit write destination namespace count mismatch")
    seen: set[tuple[object, str, int]] = set()
    for ref, scope in zip(bit_refs, scopes, strict=True):
        key = (scope, ref.code, ref.number)
        if key in seen:
            raise ValueError(f"Write Random (0x1402) has a duplicate bit destination: {ref}")
        seen.add(key)


def _validate_block_write_ranges(
    word_blocks: Sequence[tuple[DeviceRef, Sequence[object]]],
    bit_blocks: Sequence[tuple[DeviceRef, Sequence[object]]],
) -> None:
    """Reject duplicate or overlapping block destinations before encoding."""
    occupied: set[tuple[str, int]] = set()
    for kind, blocks in (("word", word_blocks), ("bit", bit_blocks)):
        for ref, values in blocks:
            span = len(values) * (16 if kind == "bit" else 1)
            slots = {(ref.code, ref.number + offset) for offset in range(span)}
            if occupied.intersection(slots):
                raise ValueError(f"Write Block (0x1406) has overlapping {kind} destination range at {ref}")
            occupied.update(slots)


def _validate_block_read_devices(
    word_blocks: Sequence[tuple[DeviceRef, int]],
    bit_blocks: Sequence[tuple[DeviceRef, int]],
) -> None:
    for ref, _ in word_blocks:
        _require_word_device(ref, operation="Read Block word entry")
    for ref, _ in bit_blocks:
        _require_bit_device(ref, operation="Read Block bit entry")
    all_refs = tuple(ref for ref, _ in (*word_blocks, *bit_blocks))
    invalid_long_block = next(
        ((ref, points) for ref, points in word_blocks if ref.code in _LT_LST_CURRENT_BLOCK_CODES and points % 4 != 0),
        None,
    )
    if invalid_long_block is not None:
        ref, points = invalid_long_block
        raise ValueError(
            f"Read Block (0x0406) direct read of {ref.code} requires 4-word blocks. "
            f"Requested points={points}; use read_typed or an explicit long-timer helper for current values."
        )
    if any(ref.code in _RANDOM_DWORD_ONLY_DIRECT_CODES for ref in all_refs):
        raise ValueError(
            "Read Block (0x0406) does not support LCN/LZ as word or bit blocks. "
            "Use read_typed/read_named so random dword read is selected."
        )
    if any(ref.code in _LC_CONTACT_CODES for ref in all_refs):
        raise ValueError(
            "Read Block (0x0406) does not support LCS/LCC. Use read_typed or the explicit long-counter state helpers."
        )


def _validate_block_write_devices(
    word_refs: Sequence[DeviceRef],
    bit_refs: Sequence[DeviceRef],
    *,
    plc_profile: object | None = None,
) -> None:
    for ref in word_refs:
        _require_word_device(ref, operation="Write Block word entry")
    for ref in bit_refs:
        _require_bit_device(ref, operation="Write Block bit entry")
    read_only = next((ref for ref in (*word_refs, *bit_refs) if _is_read_only_device(ref, plc_profile)), None)
    if read_only is not None:
        raise ValueError(
            f"Write Block (0x1406) does not support read-only device {read_only.code} for the selected PLC profile."
        )
    if any(
        ref.code in _LT_LST_CURRENT_CODES or ref.code in _DWORD_ONLY_DIRECT_CODES for ref in (*word_refs, *bit_refs)
    ):
        raise ValueError(
            "Write Block (0x1406) does not support LTN/LSTN/LCN/LZ as word or bit blocks. "
            "Use write_typed/write_named with ':D' or ':L' instead."
        )
    if any(ref.code in _LC_CONTACT_CODES for ref in (*word_refs, *bit_refs)):
        raise ValueError(
            "Write Block (0x1406) does not support LCS/LCC. "
            "Use write_typed/write_named so random bit write (0x1402) is selected."
        )


def _validate_monitor_register_devices(word_refs: Sequence[DeviceRef], dword_refs: Sequence[DeviceRef]) -> None:
    if any(ref.code in _LC_CONTACT_CODES for ref in (*word_refs, *dword_refs)):
        raise ValueError(
            "Entry Monitor Device (0x0801) does not support LCS/LCC. "
            "Use read_typed or the explicit long-counter state helpers."
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
                    f"standalone direct access to {ref.code} is not a valid route; "
                    "use the explicitly qualified Extended Device route supported by the selected profile"
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


_LT_LST_DIRECT_CODES = frozenset({"LTC", "LTS", "LSTC", "LSTS"})
_LT_LST_CURRENT_BLOCK_CODES = frozenset({"LTN", "LSTN"})
_LT_LST_CURRENT_CODES = frozenset({"LTN", "LSTN", "LCN"})
_LC_CONTACT_CODES = frozenset({"LCS", "LCC"})
_LONG_FAMILY_STATE_WRITE_DIRECT_CODES = _LT_LST_DIRECT_CODES | _LC_CONTACT_CODES
_DWORD_ONLY_DIRECT_CODES = frozenset({"LZ"})
_RANDOM_DWORD_ONLY_DIRECT_CODES = frozenset({"LCN", "LZ"})
_G_HG_CODES = frozenset({"G", "HG"})
_HG_VALID_EXTENSION_SPECIFICATIONS = frozenset({0x03E0, 0x03E1, 0x03E2, 0x03E3})
_TEMPORARILY_UNSUPPORTED_TYPED_CODES = frozenset({"G", "HG"})
_BOUNDARY_START_ACCEPTANCE_CODES = frozenset({"R", "ZR"})
_PROFILE_UNSUPPORTED_DEVICE_CODES: dict[str, frozenset[str]] = {
    "melsec:iq-f": frozenset({"DX", "DY", "V", "LTS", "LTC", "LTN", "LSTS", "LSTC", "LSTN", "ZR", "RD"}),
    "melsec:qcpu": frozenset({"LTS", "LTC", "LTN", "LSTS", "LSTC", "LSTN", "LCS", "LCC", "LCN", "LZ", "RD"}),
    "melsec:lcpu": frozenset({"LTS", "LTC", "LTN", "LSTS", "LSTC", "LSTN", "LCS", "LCC", "LCN", "LZ", "RD"}),
    "melsec:qnu": frozenset({"LTS", "LTC", "LTN", "LSTS", "LSTC", "LSTN", "LCS", "LCC", "LCN", "LZ", "RD"}),
    "melsec:qnudv": frozenset({"LTS", "LTC", "LTN", "LSTS", "LSTC", "LSTN", "LCS", "LCC", "LCN", "LZ", "RD"}),
}


def _encode_label_name(label: str) -> bytes:
    if not isinstance(label, str):
        raise TypeError("label must be a string")
    if not label or not label.strip():
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
    if array_data_length == 0:
        raise ValueError("array_data_length must be in range 1..65535")
    return _label_array_wire_data_bytes(unit_specification, array_data_length)


def _label_array_wire_data_bytes(unit_specification: int, array_data_length: int) -> int:
    if unit_specification == 0:
        return ((array_data_length + 15) // 16) * 2
    return ((array_data_length + 1) // 2) * 2


def _encode_remote_password_payload(password: str, *, series: PLCSeries) -> bytes:
    raw = password.encode("ascii")
    if series == PLCSeries.IQR:
        if len(raw) < 6 or len(raw) > 32:
            raise ValueError("iQ-R password text must be 6..32 bytes")
        return len(raw).to_bytes(2, "little") + raw
    if len(raw) != 4:
        raise ValueError("Q/L password text must be exactly 4 bytes")
    return len(raw).to_bytes(2, "little") + raw
