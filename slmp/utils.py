"""High-level utility helpers for the SLMP client."""

from __future__ import annotations

import asyncio
import math
import struct
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from .constants import DEVICE_CODES, DeviceUnit, FrameType, PLCSeries
from .core import (
    DeviceRef,
    SlmpTarget,
    _normalize_plc_profile_hint,
    _require_explicit_plc_profile_for_xy,
    _require_write_u16,
    _require_write_u32,
    _resolve_connection_profile,
    _resolve_port,
    _validate_direct_dword_read_device,
    parse_device,
)

if TYPE_CHECKING:
    from .async_client import AsyncSlmpClient
    from .client import SlmpClient


_WORD_DTYPES = frozenset({"U", "S"})
_DWORD_DTYPES = frozenset({"D", "L", "F"})
_UNBATCHED_DEVICE_CODES = frozenset({"G", "HG"})
_PLAIN_BIT_WORD_BATCHABLE_CODES = frozenset({"SM", "X", "Y", "M", "L", "F", "V", "B", "SB"})
_RANDOM_DWORD_SCALAR_DEVICE_CODES = frozenset({"LCN", "LZ"})
_LONG_COUNTER_STATE_DEVICE_CODES = frozenset({"LCS", "LCC"})
_LONG_TIMER_READ_FAMILIES: dict[str, tuple[str, str]] = {
    "LTN": ("LTN", "current"),
    "LTS": ("LTN", "contact"),
    "LTC": ("LTN", "coil"),
    "LSTN": ("LSTN", "current"),
    "LSTS": ("LSTN", "contact"),
    "LSTC": ("LSTN", "coil"),
    "LCN": ("LCN", "current"),
    "LCS": ("LCS", "contact"),
    "LCC": ("LCC", "coil"),
}


@dataclass(frozen=True)
class _ReadPlanEntry:
    address: str
    device: DeviceRef
    dtype: str
    bit_index: int | None
    batch_kind: str | None
    long_timer_read: tuple[str, str] | None


@dataclass(frozen=True)
class _ReadPlan:
    entries: tuple[_ReadPlanEntry, ...]
    word_devices: tuple[DeviceRef, ...]
    dword_devices: tuple[DeviceRef, ...]


@dataclass(frozen=True)
class SlmpConnectionOptions:
    """Stable connection settings for one queued SLMP session.

    The options object is the recommended input for :func:`open_and_connect`
    and :func:`open_and_connect_sync`. It keeps transport-level settings and
    protocol-level defaults together so maintained documentation can point users to
    one explicit connection entry point.

    Attributes:
        host: PLC hostname or IP address.
        plc_profile: Canonical high-level PLC profile. This is the only
            application-level PLC selector for the recommended helper layer.
        port: Required TCP or UDP port used by the SLMP endpoint.
        transport: Transport name such as ``"tcp"`` or ``"udp"``.
        timeout: Socket timeout in seconds.
        default_target: Optional routing target applied to requests.
        monitoring_timer: SLMP monitoring timer encoded into frames.
        raise_on_error: Whether protocol errors raise exceptions immediately.
        plc_series: Derived access profile fixed by ``plc_profile``.
        frame_type: Derived frame type fixed by ``plc_profile``.
        address_profile: Derived address profile used for string device parsing.
        range_profile: Derived range profile used for device-range catalog reads.
    """

    host: str
    plc_profile: object
    port: int
    transport: str
    default_target: SlmpTarget
    timeout: float = 3.0
    monitoring_timer: int = 0x0010
    raise_on_error: bool = True
    plc_series: PLCSeries = field(init=False)
    frame_type: FrameType = field(init=False)
    address_profile: str = field(init=False)
    range_profile: str = field(init=False)

    def __post_init__(self) -> None:
        if self.plc_profile is None:
            raise ValueError("plc_profile is required. Use an explicit canonical PLC profile such as 'melsec:iq-r'.")
        if not isinstance(self.transport, str):
            raise ValueError("transport must be 'tcp' or 'udp'")
        transport = self.transport.strip().lower()
        port = _resolve_port(self.port, transport)
        if not isinstance(self.default_target, SlmpTarget):
            raise ValueError("default_target is required and must be a complete SlmpTarget")
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not math.isfinite(self.timeout)
            or self.timeout <= 0
        ):
            raise ValueError("timeout must be a finite number greater than zero")
        if (
            isinstance(self.monitoring_timer, bool)
            or not isinstance(self.monitoring_timer, int)
            or not 0 <= self.monitoring_timer <= 0xFFFF
        ):
            raise ValueError("monitoring_timer must be an integer in range 0..65535")
        if type(self.raise_on_error) is not bool:
            raise ValueError("raise_on_error must be a boolean")
        (
            normalized_plc_profile,
            plc_series,
            frame_type,
            address_profile,
            range_profile,
        ) = _resolve_connection_profile(
            plc_profile=self.plc_profile,
            plc_series=None,
            frame_type=None,
            address_profile=None,
        )
        object.__setattr__(self, "transport", transport)
        object.__setattr__(self, "port", port)
        object.__setattr__(self, "timeout", float(self.timeout))
        object.__setattr__(self, "plc_profile", normalized_plc_profile)
        object.__setattr__(self, "plc_series", plc_series)
        object.__setattr__(self, "frame_type", frame_type)
        object.__setattr__(self, "address_profile", address_profile)
        object.__setattr__(self, "range_profile", range_profile)


@dataclass(frozen=True)
class SlmpAddress:
    """Parsed public SLMP helper-layer address notation."""

    text: str
    base_device: str
    dtype: str
    bit_index: int | None = None
    explicit_dtype: bool = False


def _client_address_profile(client: object) -> str | None:
    plc_profile = getattr(client, "plc_profile", None)
    if plc_profile is None:
        return None
    if isinstance(plc_profile, str):
        return plc_profile
    value = getattr(plc_profile, "value", None)
    if isinstance(value, str):
        return value
    return None


def _parse_device_for_address_profile(
    device: str | DeviceRef,
    address_profile: object,
) -> DeviceRef:
    ref = parse_device(device, plc_profile=address_profile)
    return _require_explicit_plc_profile_for_xy(device, address_profile, ref)


def _parse_device_for_client(
    client: object,
    device: str | DeviceRef,
) -> DeviceRef:
    return _parse_device_for_address_profile(device, _client_address_profile(client))


def _validate_dword_read_target(client: object, device: str | DeviceRef) -> DeviceRef:
    ref = _parse_device_for_client(client, device)
    _validate_direct_dword_read_device(ref)
    return ref


# ---------------------------------------------------------------------------
# Typed single-device read / write  (async)
# ---------------------------------------------------------------------------


async def read_typed(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    dtype: str,
) -> int | float | bool:
    """Read one logical value and convert it to a Python scalar.

    Args:
        client: Connected high-level or raw async SLMP client.
        device: Starting device address as a string such as ``"D100"`` or as
            a parsed :class:`DeviceRef`.
        dtype: Application type code. Supported values are ``"BIT"``,
            ``"U"``, ``"S"``, ``"D"``, ``"L"``, and ``"F"``.

    Returns:
        ``bool`` for ``BIT``, otherwise ``int`` or ``float``.
    """
    ref = _parse_device_for_client(client, device)
    key = _require_dtype(dtype)
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        _validate_long_timer_entry(str(ref), ref, key)
        if ref.code == "LCN" and long_read[1] == "current":
            value = (await client.read_random(dword_devices=[ref])).dword[str(ref)]
            return _decode_dword_value(value, key)
        return await _read_long_family_value(client, ref, key, long_read)
    if key == "BIT":
        values = await client.read_devices(ref, 1, bit_unit=True)
        return bool(values[0])
    if key in ("D", "L", "F"):
        if ref.code in _RANDOM_DWORD_SCALAR_DEVICE_CODES:
            value = (await client.read_random(dword_devices=[ref])).dword[str(ref)]
            return _decode_dword_value(value, key)
        words = await client.read_devices(ref, 2, bit_unit=False)
        return _decode_word_pair_value(words, key)
    else:
        words = await client.read_devices(ref, 1, bit_unit=False)
        if key == "S":
            return cast(int, struct.unpack("<h", struct.pack("<H", words[0]))[0])
        return int(words[0])


async def write_typed(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    dtype: str,
    value: int | float | bool,
) -> None:
    """Write one logical value using the requested application type.

    Args:
        client: Connected high-level or raw async SLMP client.
        device: Starting device address.
        dtype: Type code accepted by :func:`read_typed`.
        value: Application value to encode and write.
    """
    ref = _parse_device_for_client(client, device)
    key = _require_dtype(dtype)
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        _validate_long_timer_entry(str(ref), ref, key)
        await _write_long_family_value(client, ref, key, value, long_read)
        return
    if key == "BIT":
        await client.write_devices(device, [_require_typed_bool(value)], bit_unit=True)
        return
    if key in {"D", "L"} and ref.code in _RANDOM_DWORD_SCALAR_DEVICE_CODES:
        await client.write_random_words(
            dword_values={ref: _encode_typed_dword(value, key)},
        )
        return
    if key not in {"D", "L", "F"}:
        await client.write_devices(device, [_encode_typed_word(value, key)], bit_unit=False)
        return
    await client.write_devices(device, _encode_dword_words(value, key), bit_unit=False)


# ---------------------------------------------------------------------------
# Typed single-device read / write  (sync)
# ---------------------------------------------------------------------------


def read_typed_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    dtype: str,
) -> int | float | bool:
    """Synchronously read one logical value as a Python scalar."""
    ref = _parse_device_for_client(client, device)
    key = _require_dtype(dtype)
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        _validate_long_timer_entry(str(ref), ref, key)
        if ref.code == "LCN" and long_read[1] == "current":
            value = client.read_random(dword_devices=[ref]).dword[str(ref)]
            return _decode_dword_value(value, key)
        return _read_long_family_value_sync(client, ref, key, long_read)
    if key == "BIT":
        values = client.read_devices(ref, 1, bit_unit=True)
        return bool(values[0])
    if key in ("D", "L", "F"):
        if ref.code in _RANDOM_DWORD_SCALAR_DEVICE_CODES:
            value = client.read_random(dword_devices=[ref]).dword[str(ref)]
            return _decode_dword_value(value, key)
        words = client.read_devices(ref, 2, bit_unit=False)
        return _decode_word_pair_value(words, key)
    else:
        words = client.read_devices(ref, 1, bit_unit=False)
        if key == "S":
            return cast(int, struct.unpack("<h", struct.pack("<H", words[0]))[0])
        return int(words[0])


def write_typed_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    dtype: str,
    value: int | float | bool,
) -> None:
    """Synchronously write one logical value using the requested type."""
    ref = _parse_device_for_client(client, device)
    key = _require_dtype(dtype)
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        _validate_long_timer_entry(str(ref), ref, key)
        _write_long_family_value_sync(client, ref, key, value, long_read)
        return
    if key == "BIT":
        client.write_devices(device, [_require_typed_bool(value)], bit_unit=True)
        return
    if key in {"D", "L"} and ref.code in _RANDOM_DWORD_SCALAR_DEVICE_CODES:
        client.write_random_words(
            dword_values={ref: _encode_typed_dword(value, key)},
        )
        return
    if key not in {"D", "L", "F"}:
        client.write_devices(device, [_encode_typed_word(value, key)], bit_unit=False)
        return
    client.write_devices(device, _encode_dword_words(value, key), bit_unit=False)


# ---------------------------------------------------------------------------
# Bit-in-word  (async + sync)
# ---------------------------------------------------------------------------


async def write_bit_in_word(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    bit_index: int,
    value: bool,
) -> None:
    """Set or clear one bit inside one word device.

    This helper is only for word devices such as ``D50``. Direct bit devices
    such as ``M1000`` should be written with :func:`write_typed` using
    ``"BIT"``.
    """
    words = await client.read_devices(device, 1, bit_unit=False)
    await client.write_devices(device, [_update_bit_in_word_value(int(words[0]), bit_index, value)], bit_unit=False)


def write_bit_in_word_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    bit_index: int,
    value: bool,
) -> None:
    """Synchronously set or clear one bit inside one word device."""
    words = client.read_devices(device, 1, bit_unit=False)
    client.write_devices(device, [_update_bit_in_word_value(int(words[0]), bit_index, value)], bit_unit=False)


async def read_bits(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[bool]:
    """Read a contiguous bit-device range as booleans."""
    return _bool_values(await client.read_devices(device, count, bit_unit=True))


def read_bits_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[bool]:
    """Synchronously read a contiguous bit-device range as booleans."""
    return _bool_values(client.read_devices(device, count, bit_unit=True))


async def write_bits(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    values: list[bool],
) -> None:
    """Write a contiguous bit-device range from booleans."""
    await client.write_devices(device, _bool_values(values), bit_unit=True)


def write_bits_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    values: list[bool],
) -> None:
    """Synchronously write a contiguous bit-device range from booleans."""
    client.write_devices(device, _bool_values(values), bit_unit=True)


# ---------------------------------------------------------------------------
# Named-device read  (async + sync)
# ---------------------------------------------------------------------------


async def read_named(
    client: AsyncSlmpClient,
    addresses: list[str],
) -> dict[str, int | float | bool]:
    """Read a mixed logical snapshot by address string.

    Args:
        client: Connected async SLMP client.
        addresses: Address list such as ``"D100"``, ``"D200:F"``,
            ``"D300:L"``, ``"D50.3"``, or direct bit devices like ``"M1000"``.

    Returns:
        A dictionary keyed by the original address strings.

    Notes:
        The address list is compiled once, then grouped into random reads where
        possible. Use ``.bit`` notation only with word devices.
    """
    plan = _compile_read_plan(addresses, address_profile=_client_address_profile(client))
    return await _read_named_with_plan(client, plan)


def read_named_sync(
    client: SlmpClient,
    addresses: list[str],
) -> dict[str, int | float | bool]:
    """Synchronously read a mixed logical snapshot by address string."""
    plan = _compile_read_plan(addresses, address_profile=_client_address_profile(client))
    return _read_named_with_plan_sync(client, plan)


# ---------------------------------------------------------------------------
# Named-device write  (async + sync)
# ---------------------------------------------------------------------------


async def write_named(
    client: AsyncSlmpClient,
    updates: dict[str, int | float | bool],
) -> None:
    """Write a mixed logical snapshot by address string.

    ``D50.3`` updates one bit inside one word. Direct bit devices such as
    ``M1000`` are normalized to ``"BIT"`` writes.
    """
    word_values, dword_values, bit_values = _compile_named_write(updates, _client_address_profile(client))
    if bit_values:
        await client.write_random_bits(bit_values)
    else:
        await client.write_random_words(word_values=word_values, dword_values=dword_values)


def write_named_sync(
    client: SlmpClient,
    updates: dict[str, int | float | bool],
) -> None:
    """Synchronously write a mixed logical snapshot by address string."""
    word_values, dword_values, bit_values = _compile_named_write(updates, _client_address_profile(client))
    if bit_values:
        client.write_random_bits(bit_values)
    else:
        client.write_random_words(word_values=word_values, dword_values=dword_values)


def _compile_named_write(
    updates: dict[str, int | float | bool],
    address_profile: object,
) -> tuple[list[tuple[DeviceRef, int]], list[tuple[DeviceRef, int]], list[tuple[DeviceRef, bool]]]:
    """Compile one named write into exactly one protocol command family."""
    if not updates:
        raise ValueError("updates must not be empty")
    word_values: list[tuple[DeviceRef, int]] = []
    dword_values: list[tuple[DeviceRef, int]] = []
    bit_values: list[tuple[DeviceRef, bool]] = []
    for address, value in updates.items():
        base, dtype, bit_idx = _parse_address(address)
        device = _parse_device_for_address_profile(base, address_profile)
        if dtype == "BIT_IN_WORD":
            _validate_bit_in_word_target(address, device)
            raise ValueError(
                f"Address '{address}' requires read-modify-write and is not supported by write_named; "
                "call write_bit_in_word explicitly so the two-request operation is visible"
            )
        resolved_dtype = _resolve_dtype_for_address(address, device, dtype, bit_idx)
        _validate_device_dtype(address, device, resolved_dtype)
        _validate_long_timer_entry(address, device, resolved_dtype)
        if resolved_dtype == "BIT":
            bit_values.append((device, _require_typed_bool(value)))
        elif resolved_dtype in _WORD_DTYPES:
            word_values.append((device, _encode_typed_word(value, resolved_dtype)))
        elif resolved_dtype == "F":
            dword_values.append((device, _encode_typed_float32(value)))
        else:
            dword_values.append((device, _encode_typed_dword(value, resolved_dtype)))
    if bit_values and (word_values or dword_values):
        raise ValueError(
            "write_named cannot mix bit and word/dword destinations because that requires multiple protocol requests"
        )
    return word_values, dword_values, bit_values


# ---------------------------------------------------------------------------
# Address parser (shared)
# ---------------------------------------------------------------------------


def _parse_address(address: str) -> tuple[str, str, int | None]:
    """Parse extended address notation.

    Returns (base_device, dtype, bit_index).
    """
    address = address.strip()
    if ":" in address:
        base, dtype = address.split(":", 1)
        return base.strip(), _require_dtype(dtype), None
    if "." in address:
        base, bit_str = address.split(".", 1)
        bit_text = bit_str.strip()
        if len(bit_text) == 1 and bit_text.upper() in "0123456789ABCDEF":
            return base.strip(), "BIT_IN_WORD", int(bit_text, 16)
        raise ValueError(f"Invalid bit-in-word index {bit_str!r}; use one hex digit 0-F or ':' for dtype.")
    raise ValueError(f"Address {address!r} requires an explicit dtype such as ':U', ':D', or ':BIT'.")


def _require_dtype(dtype: str) -> str:
    key = str(dtype).strip().upper()
    if not key:
        raise ValueError("dtype is required; specify BIT/U/S/D/L/F explicitly.")
    if key == "BIT_IN_WORD":
        raise ValueError("BIT_IN_WORD requires '.bit' notation such as 'D50.A'.")
    if key not in {"BIT", "U", "S", "D", "L", "F"}:
        raise ValueError(f"Unsupported dtype {key!r}; expected BIT/U/S/D/L/F")
    return key


def _require_bit_in_word_index(address: str, bit_index: int | None) -> int:
    if bit_index is None:
        raise ValueError(f"bit-in-word address requires explicit bit index 0-F: {address!r}")
    if not 0 <= bit_index <= 15:
        raise ValueError(f"bit-in-word index must be 0-F: {address!r}")
    return bit_index


def _effective_address_profile(
    *,
    plc_profile: object | None = None,
) -> object | None:
    if plc_profile is not None:
        return _normalize_plc_profile_hint(plc_profile)
    return None


def parse_address(
    address: str | DeviceRef,
    *,
    plc_profile: object,
) -> SlmpAddress:
    """Parse public SLMP helper-layer address notation.

    Supported forms match :func:`read_named`: ``"D100:U"``, ``"D200:F"``,
    ``"D50.A"``, and direct bit devices such as ``"M100:BIT"``.
    """

    if not isinstance(address, str):
        text = str(address)
        raise ValueError(f"Address {text!r} requires an explicit dtype; pass a string such as '{text}:U'.")

    effective_address_profile = _effective_address_profile(plc_profile=plc_profile)
    raw_text = address.strip()
    base, dtype, bit_index = _parse_address(raw_text)
    device = _parse_device_for_address_profile(base, effective_address_profile)
    canonical_base = str(device)

    if bit_index is not None:
        if not 0 <= bit_index <= 15:
            raise ValueError(f"bit-in-word index must be 0-F: {address!r}")
        _validate_bit_in_word_target(raw_text, device)
        return SlmpAddress(
            text=f"{canonical_base}.{bit_index:X}",
            base_device=canonical_base,
            dtype="BIT_IN_WORD",
            bit_index=bit_index,
            explicit_dtype=False,
        )

    resolved_dtype = _resolve_dtype_for_address(raw_text, device, dtype, bit_index)
    _validate_device_dtype(raw_text, device, resolved_dtype)
    explicit_dtype = True
    return SlmpAddress(
        text=f"{canonical_base}:{resolved_dtype}",
        base_device=canonical_base,
        dtype=resolved_dtype,
        bit_index=None,
        explicit_dtype=explicit_dtype,
    )


def try_parse_address(
    address: str | DeviceRef,
    *,
    plc_profile: object,
) -> SlmpAddress | None:
    """Return parsed address information, or ``None`` when parsing fails."""

    try:
        return parse_address(address, plc_profile=plc_profile)
    except Exception:
        return None


def format_address(
    address: SlmpAddress | str | DeviceRef,
    *,
    plc_profile: object,
) -> str:
    """Return canonical public SLMP address text."""

    if not isinstance(address, SlmpAddress):
        return parse_address(address, plc_profile=plc_profile).text

    effective_address_profile = _effective_address_profile(plc_profile=plc_profile)
    canonical_base = str(parse_device(address.base_device, plc_profile=effective_address_profile))
    if address.dtype == "BIT_IN_WORD":
        if address.bit_index is None or not 0 <= address.bit_index <= 15:
            raise ValueError("bit-in-word address requires bit_index 0-F")
        return f"{canonical_base}.{address.bit_index:X}"
    dtype = _require_dtype(address.dtype)
    return f"{canonical_base}:{dtype}"


def normalize_address(
    address: str | DeviceRef,
    *,
    plc_profile: object,
) -> str:
    """Return the canonical helper-layer form of one SLMP device address.

    The helper accepts free-form user text such as ``" d200:f "`` or an
    already parsed :class:`DeviceRef`. The result is suitable for logs,
    configuration files, and cache keys.
    """

    if not isinstance(address, str):
        return str(address)

    effective_address_profile = _effective_address_profile(plc_profile=plc_profile)

    text = address.strip()
    if ":" not in text and "." not in text:
        raise ValueError(f"Address {text!r} requires an explicit dtype such as ':U', ':D', or ':BIT'.")

    base, dtype, bit_index = _parse_address(text)
    canonical_base = str(parse_device(base, plc_profile=effective_address_profile))
    if bit_index is not None:
        return f"{canonical_base}.{bit_index:X}"
    device = parse_device(base, plc_profile=effective_address_profile)
    _validate_device_dtype(text, device, dtype)
    return f"{canonical_base}:{dtype}"


def _is_batchable_word_device(device: DeviceRef) -> bool:
    code = DEVICE_CODES.get(device.code)
    return code is not None and code.unit == DeviceUnit.WORD and device.code not in _UNBATCHED_DEVICE_CODES


def _plain_bit_word_read(device: DeviceRef) -> tuple[DeviceRef, int] | None:
    if device.code not in _PLAIN_BIT_WORD_BATCHABLE_CODES:
        return None
    bit_index = device.number % 16
    word_device = DeviceRef(device.code, device.number - bit_index, device.plc_profile)
    return word_device, bit_index


def _normalize_dtype_for_device(device: DeviceRef, dtype: str) -> str:
    return _require_dtype(dtype)


def _resolve_dtype_for_address(address: str, device: DeviceRef, dtype: str, bit_index: int | None) -> str:
    if bit_index is not None:
        return "BIT_IN_WORD"
    return _normalize_dtype_for_device(device, dtype)


def _validate_device_dtype(address: str, device: DeviceRef, dtype: str) -> None:
    if dtype == "BIT_IN_WORD":
        return
    code = DEVICE_CODES.get(device.code)
    is_bit_device = code is not None and code.unit == DeviceUnit.BIT
    if is_bit_device and dtype != "BIT":
        raise ValueError(f"Address '{address}' is a bit device and requires ':BIT'.")
    if not is_bit_device and dtype == "BIT":
        raise ValueError(
            f"Address '{address}' uses ':BIT', which is only valid for bit devices. "
            "Use '.bit' notation for a bit inside a word device."
        )


def _get_long_timer_read(device: DeviceRef) -> tuple[str, str] | None:
    return _LONG_TIMER_READ_FAMILIES.get(device.code)


def _validate_long_timer_entry(address: str, device: DeviceRef, dtype: str) -> None:
    long_read = _get_long_timer_read(device)
    if long_read is None:
        return
    _, role = long_read
    if role == "current":
        if dtype not in {"D", "L"}:
            raise ValueError(f"Address '{address}' uses a 32-bit long current value. Specify ':D' or ':L'.")
        return
    if dtype != "BIT":
        raise ValueError(f"Address '{address}' is a long timer state device. Specify ':BIT'.")


async def _write_long_family_value(
    client: AsyncSlmpClient,
    device: DeviceRef,
    dtype: str,
    value: int | float,
    long_read: tuple[str, str],
) -> None:
    _, role = long_read
    if role == "current":
        await client.write_random_words(
            dword_values={device: _encode_typed_dword(value, dtype)},
        )
        return
    await client.write_random_bits({device: _require_typed_bool(value)})


def _write_long_family_value_sync(
    client: SlmpClient,
    device: DeviceRef,
    dtype: str,
    value: int | float,
    long_read: tuple[str, str],
) -> None:
    _, role = long_read
    if role == "current":
        client.write_random_words(
            dword_values={device: _encode_typed_dword(value, dtype)},
        )
        return
    client.write_random_bits({device: _require_typed_bool(value)})


def _require_typed_bool(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError(f"BIT value must be bool: {value!r}")
    return value


def _require_typed_int(value: object, *, minimum: int, maximum: int, dtype: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{dtype} value must be an integer in range {minimum}..{maximum}: {value!r}")
    return value


def _encode_typed_word(value: object, dtype: str) -> int:
    if dtype == "S":
        signed = _require_typed_int(value, minimum=-0x8000, maximum=0x7FFF, dtype=dtype)
        return cast(int, struct.unpack("<H", struct.pack("<h", signed))[0])
    return _require_write_u16(value, f"{dtype} value")


def _encode_typed_dword(value: object, dtype: str) -> int:
    if dtype == "L":
        signed = _require_typed_int(value, minimum=-0x80000000, maximum=0x7FFFFFFF, dtype=dtype)
        return cast(int, struct.unpack("<I", struct.pack("<i", signed))[0])
    if dtype == "D":
        return _require_write_u32(value, "D value")
    raise ValueError(f"{dtype} is not an integer dword dtype")


def _encode_typed_float32(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"F value must be a finite int or float: {value!r}")
    try:
        return cast(int, struct.unpack("<I", struct.pack("<f", value))[0])
    except (OverflowError, struct.error) as error:
        raise ValueError(f"F value is outside the finite float32 range: {value!r}") from error


def _validate_bit_in_word_target(address: str, device: DeviceRef) -> None:
    code = DEVICE_CODES.get(device.code)
    if code is None or code.unit != DeviceUnit.WORD:
        raise ValueError(
            f"Address '{address}' uses '.bit' notation, which is only valid for word devices. "
            "Address bit devices directly, for example 'M1000' instead of 'M1000.0'."
        )


def _coerce_long_current_value(current_value: int, dtype: str) -> int:
    if dtype == "L":
        return cast(int, struct.unpack("<i", struct.pack("<I", int(current_value) & 0xFFFFFFFF))[0])
    return int(current_value)


def _decode_long_family_words(words: list[int]) -> tuple[int, bool, bool]:
    current_value = int(words[0]) | (int(words[1]) << 16)
    status_word = int(words[2]) & 0xFFFF
    return current_value, bool(status_word & 0x0002), bool(status_word & 0x0001)


async def _read_long_family_point(
    client: AsyncSlmpClient,
    prefix: str,
    head_no: int,
) -> tuple[int, bool, bool]:
    if prefix == "LTN":
        timer = (await client.read_long_timer(head_no=head_no, points=1))[0]
        return int(timer.current_value), bool(timer.contact), bool(timer.coil)
    if prefix == "LSTN":
        timer = (await client.read_long_retentive_timer(head_no=head_no, points=1))[0]
        return int(timer.current_value), bool(timer.contact), bool(timer.coil)
    raise ValueError("LCN current values use random dword read; LCS/LCC state reads use direct bit read.")


def _read_long_family_point_sync(
    client: SlmpClient,
    prefix: str,
    head_no: int,
) -> tuple[int, bool, bool]:
    if prefix == "LTN":
        timer = client.read_long_timer(head_no=head_no, points=1)[0]
        return int(timer.current_value), bool(timer.contact), bool(timer.coil)
    if prefix == "LSTN":
        timer = client.read_long_retentive_timer(head_no=head_no, points=1)[0]
        return int(timer.current_value), bool(timer.contact), bool(timer.coil)
    raise ValueError("LCN current values use random dword read; LCS/LCC state reads use direct bit read.")


async def _read_long_family_value(
    client: AsyncSlmpClient,
    device: DeviceRef,
    dtype: str,
    long_read: tuple[str, str],
) -> int | bool:
    prefix, role = long_read
    if device.code in _LONG_COUNTER_STATE_DEVICE_CODES:
        values = await client.read_devices(device, 1, bit_unit=True)
        return bool(values[0])
    current_value, contact, coil = await _read_long_family_point(client, prefix, device.number)
    if role == "current":
        return _coerce_long_current_value(current_value, dtype)
    if role == "contact":
        return contact
    return coil


def _read_long_family_value_sync(
    client: SlmpClient,
    device: DeviceRef,
    dtype: str,
    long_read: tuple[str, str],
) -> int | bool:
    prefix, role = long_read
    if device.code in _LONG_COUNTER_STATE_DEVICE_CODES:
        values = client.read_devices(device, 1, bit_unit=True)
        return bool(values[0])
    current_value, contact, coil = _read_long_family_point_sync(client, prefix, device.number)
    if role == "current":
        return _coerce_long_current_value(current_value, dtype)
    if role == "contact":
        return contact
    return coil


def _compile_read_plan(
    addresses: list[str],
    *,
    address_profile: object,
) -> _ReadPlan:
    if not addresses:
        raise ValueError("addresses must not be empty")
    entries: list[_ReadPlanEntry] = []
    word_devices: list[DeviceRef] = []
    dword_devices: list[DeviceRef] = []
    seen_words: set[DeviceRef] = set()
    seen_dwords: set[DeviceRef] = set()

    for address in addresses:
        base, dtype, bit_index = _parse_address(address)
        device = _parse_device_for_address_profile(base, address_profile)
        batch_kind: str | None = None
        long_timer_read = _get_long_timer_read(device)

        if dtype == "BIT_IN_WORD":
            dtype = _resolve_dtype_for_address(address, device, dtype, bit_index)
            bit_index = _require_bit_in_word_index(address, bit_index)
            _validate_bit_in_word_target(address, device)
            if _is_batchable_word_device(device):
                batch_kind = "WORD"
                if device not in seen_words:
                    word_devices.append(device)
                    seen_words.add(device)
        else:
            dtype = _resolve_dtype_for_address(address, device, dtype, bit_index)
            _validate_device_dtype(address, device, dtype)
            _validate_long_timer_entry(address, device, dtype)

        if long_timer_read is not None and not (device.code == "LCN" and long_timer_read[1] == "current"):
            batch_kind = "LONG_TIMER"
        elif long_timer_read is not None:
            batch_kind = "DWORD"
            if device not in seen_dwords:
                dword_devices.append(device)
                seen_dwords.add(device)
        elif dtype == "BIT":
            bit_word = _plain_bit_word_read(device)
            if bit_word is not None:
                device, bit_index = bit_word
                dtype = "BIT_IN_WORD"
                batch_kind = "WORD"
                if device not in seen_words:
                    word_devices.append(device)
                    seen_words.add(device)
        elif dtype in _WORD_DTYPES:
            if _is_batchable_word_device(device):
                batch_kind = "WORD"
                if device not in seen_words:
                    word_devices.append(device)
                    seen_words.add(device)
        elif dtype in _DWORD_DTYPES:
            if _is_batchable_word_device(device):
                batch_kind = "DWORD"
                if device not in seen_dwords:
                    dword_devices.append(device)
                    seen_dwords.add(device)

        entries.append(_ReadPlanEntry(address, device, dtype, bit_index, batch_kind, long_timer_read))

    unsupported = [entry.address for entry in entries if entry.batch_kind not in {"WORD", "DWORD"}]
    if unsupported:
        raise ValueError(
            "read_named accepts only addresses that fit one random-read request; "
            f"use explicit read calls for {unsupported}"
        )

    return _ReadPlan(tuple(entries), tuple(word_devices), tuple(dword_devices))


def _decode_word_value(value: int, dtype: str) -> int:
    if dtype == "S":
        return cast(int, struct.unpack("<h", struct.pack("<H", value & 0xFFFF))[0])
    return int(value)


def _decode_dword_value(value: int, dtype: str) -> int | float:
    raw = struct.pack("<I", value & 0xFFFFFFFF)
    if dtype == "F":
        return cast(float, struct.unpack("<f", raw)[0])
    if dtype == "L":
        return cast(int, struct.unpack("<i", raw)[0])
    return int(value)


def _decode_word_pair_value(words: list[int] | list[bool], dtype: str) -> int | float:
    raw = struct.pack("<HH", int(words[0]), int(words[1]))
    if dtype == "F":
        return cast(float, struct.unpack("<f", raw)[0])
    if dtype == "L":
        return cast(int, struct.unpack("<i", raw)[0])
    return cast(int, struct.unpack("<I", raw)[0])


def _encode_dword_words(value: int | float, dtype: str) -> list[int]:
    if dtype == "F":
        raw = struct.pack("<I", _encode_typed_float32(value))
    else:
        raw = struct.pack("<I", _encode_typed_dword(value, dtype))
    return list(struct.unpack("<HH", raw))


def _update_bit_in_word_value(current: int, bit_index: int, value: bool) -> int:
    if not 0 <= bit_index <= 15:
        raise ValueError(f"bit_index must be 0-15, got {bit_index}")
    if value:
        current |= 1 << bit_index
    else:
        current &= ~(1 << bit_index)
    return current & 0xFFFF


def _bool_values(values: list[int] | list[bool]) -> list[bool]:
    return [bool(value) for value in values]


def _pack_dword_words(values: list[int]) -> list[int]:
    words: list[int] = []
    for index, value in enumerate(values):
        words.extend(struct.unpack("<HH", struct.pack("<I", _require_write_u32(value, f"values[{index}]"))))
    return words


def _unpack_dword_words(words: list[int], count: int) -> list[int]:
    return [struct.unpack("<I", struct.pack("<HH", words[i], words[i + 1]))[0] for i in range(0, count * 2, 2)]


def _validate_unsplit_word_count(count: int, max_per_request: int) -> int:
    if max_per_request <= 0:
        raise ValueError("max_per_request must be at least 1")
    if count > max_per_request:
        raise ValueError(
            f"count {count} exceeds the single-request limit {max_per_request}; "
            "issue multiple explicit requests with application-level consistency handling"
        )
    return max_per_request


def _validate_unsplit_dword_count(count: int, max_dwords_per_request: int) -> int:
    if max_dwords_per_request <= 0:
        raise ValueError("max_dwords_per_request must be at least 1")
    if count > max_dwords_per_request:
        raise ValueError(
            f"count {count} exceeds the single-request dword limit {max_dwords_per_request}; "
            "issue multiple explicit requests with application-level consistency handling"
        )
    return max_dwords_per_request


async def _read_random_maps(
    client: AsyncSlmpClient,
    plan: _ReadPlan,
) -> tuple[dict[str, int], dict[str, int]]:
    word_values: dict[str, int] = {}
    dword_values: dict[str, int] = {}
    word_devices = list(plan.word_devices)
    dword_devices = list(plan.dword_devices)
    if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
        raise ValueError("read_named supports at most 255 word devices and 255 dword devices in one request")
    if word_devices or dword_devices:
        result = await client.read_random(word_devices=word_devices, dword_devices=dword_devices)
        word_values.update(result.word)
        dword_values.update(result.dword)

    return word_values, dword_values


def _read_random_maps_sync(
    client: SlmpClient,
    plan: _ReadPlan,
) -> tuple[dict[str, int], dict[str, int]]:
    word_values: dict[str, int] = {}
    dword_values: dict[str, int] = {}
    word_devices = list(plan.word_devices)
    dword_devices = list(plan.dword_devices)
    if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
        raise ValueError("read_named supports at most 255 word devices and 255 dword devices in one request")
    if word_devices or dword_devices:
        result = client.read_random(word_devices=word_devices, dword_devices=dword_devices)
        word_values.update(result.word)
        dword_values.update(result.dword)

    return word_values, dword_values


async def _read_named_with_plan(
    client: AsyncSlmpClient,
    plan: _ReadPlan,
) -> dict[str, int | float | bool]:
    result: dict[str, int | float | bool] = {}
    word_values, dword_values = await _read_random_maps(client, plan)
    long_timer_cache: dict[tuple[str, int], Any] = {}

    for entry in plan.entries:
        if entry.batch_kind == "LONG_TIMER":
            assert entry.long_timer_read is not None
            if entry.device.code in _LONG_COUNTER_STATE_DEVICE_CODES:
                values = await client.read_devices(entry.device, 1, bit_unit=True)
                result[entry.address] = bool(values[0])
                continue
            prefix, role = entry.long_timer_read
            cache_key = (prefix, entry.device.number)
            if cache_key not in long_timer_cache:
                long_timer_cache[cache_key] = await _read_long_family_point(client, prefix, entry.device.number)
            current_value, contact, coil = long_timer_cache[cache_key]
            if role == "current":
                result[entry.address] = _coerce_long_current_value(current_value, entry.dtype)
            elif role == "contact":
                result[entry.address] = bool(contact)
            else:
                result[entry.address] = bool(coil)
            continue
        if entry.batch_kind == "WORD":
            word = word_values[str(entry.device)]
            if entry.dtype == "BIT_IN_WORD":
                bit_index = _require_bit_in_word_index(entry.address, entry.bit_index)
                result[entry.address] = bool((word >> bit_index) & 1)
            else:
                result[entry.address] = _decode_word_value(word, entry.dtype)
            continue
        if entry.batch_kind == "DWORD":
            result[entry.address] = _decode_dword_value(dword_values[str(entry.device)], entry.dtype)
            continue
        if entry.dtype == "BIT_IN_WORD":
            words = await client.read_devices(entry.device, 1, bit_unit=False)
            bit_index = _require_bit_in_word_index(entry.address, entry.bit_index)
            result[entry.address] = bool((words[0] >> bit_index) & 1)
        else:
            result[entry.address] = await read_typed(client, entry.device, entry.dtype)

    return result


def _read_named_with_plan_sync(
    client: SlmpClient,
    plan: _ReadPlan,
) -> dict[str, int | float | bool]:
    result: dict[str, int | float | bool] = {}
    word_values, dword_values = _read_random_maps_sync(client, plan)
    long_timer_cache: dict[tuple[str, int], Any] = {}

    for entry in plan.entries:
        if entry.batch_kind == "LONG_TIMER":
            assert entry.long_timer_read is not None
            if entry.device.code in _LONG_COUNTER_STATE_DEVICE_CODES:
                values = client.read_devices(entry.device, 1, bit_unit=True)
                result[entry.address] = bool(values[0])
                continue
            prefix, role = entry.long_timer_read
            cache_key = (prefix, entry.device.number)
            if cache_key not in long_timer_cache:
                long_timer_cache[cache_key] = _read_long_family_point_sync(client, prefix, entry.device.number)
            current_value, contact, coil = long_timer_cache[cache_key]
            if role == "current":
                result[entry.address] = _coerce_long_current_value(current_value, entry.dtype)
            elif role == "contact":
                result[entry.address] = bool(contact)
            else:
                result[entry.address] = bool(coil)
            continue
        if entry.batch_kind == "WORD":
            word = word_values[str(entry.device)]
            if entry.dtype == "BIT_IN_WORD":
                bit_index = _require_bit_in_word_index(entry.address, entry.bit_index)
                result[entry.address] = bool((word >> bit_index) & 1)
            else:
                result[entry.address] = _decode_word_value(word, entry.dtype)
            continue
        if entry.batch_kind == "DWORD":
            result[entry.address] = _decode_dword_value(dword_values[str(entry.device)], entry.dtype)
            continue
        if entry.dtype == "BIT_IN_WORD":
            words = client.read_devices(entry.device, 1, bit_unit=False)
            bit_index = _require_bit_in_word_index(entry.address, entry.bit_index)
            result[entry.address] = bool((words[0] >> bit_index) & 1)
        else:
            result[entry.address] = read_typed_sync(client, entry.device, entry.dtype)

    return result


# ---------------------------------------------------------------------------
# Polling  (async + sync)
# ---------------------------------------------------------------------------


async def poll(
    client: AsyncSlmpClient,
    addresses: list[str],
    interval: float,
) -> AsyncIterator[dict[str, int | float | bool]]:
    """Continuously yield mixed snapshots at a fixed interval.

    The address list is compiled once and reused for every cycle.
    """
    plan = _compile_read_plan(addresses, address_profile=_client_address_profile(client))
    while True:
        yield await _read_named_with_plan(client, plan)
        await asyncio.sleep(interval)


def poll_sync(
    client: SlmpClient,
    addresses: list[str],
    interval: float,
) -> Iterator[dict[str, int | float | bool]]:
    """Synchronously yield mixed snapshots at a fixed interval."""
    plan = _compile_read_plan(addresses, address_profile=_client_address_profile(client))
    while True:
        yield _read_named_with_plan_sync(client, plan)
        time.sleep(interval)


# ---------------------------------------------------------------------------
# Contiguous reads and writes  (async)
# ---------------------------------------------------------------------------


async def read_words_single_request(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[int]:
    """Read contiguous 16-bit values using one protocol request.

    Counts above the profile's one-request limit must be split explicitly by
    the application together with its required consistency checks.
    """

    ref = _parse_device_for_client(client, device)
    return list(await client.read_devices(ref, count, bit_unit=False))


async def read_dwords_single_request(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[int]:
    """Read contiguous unsigned 32-bit values using one protocol request.

    Adjacent word pairs are combined in little-endian order and never split
    across requests by this helper.
    """

    ref = _validate_dword_read_target(client, device)
    words = await read_words_single_request(client, ref, count * 2)
    return _unpack_dword_words(words, count)


async def write_words_single_request(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    values: list[int],
) -> None:
    """Write contiguous 16-bit values using one protocol request.

    Use this helper for logical ranges that should stay within one protocol
    write operation.
    """

    await client.write_devices(
        device,
        [_require_write_u16(value, f"values[{index}]") for index, value in enumerate(values)],
        bit_unit=False,
    )


async def write_dwords_single_request(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    values: list[int],
) -> None:
    """Write contiguous unsigned 32-bit values using one protocol request.

    Each Python ``int`` is encoded as two PLC words in little-endian order.
    """

    await write_words_single_request(client, device, _pack_dword_words(values))


async def read_words(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[int]:
    """Read a contiguous word-device range using exactly one request."""
    _validate_unsplit_word_count(count, 960)
    return await read_words_single_request(client, device, count)


async def read_dwords(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[int]:
    """Read a contiguous DWord range using exactly one request."""
    _validate_unsplit_dword_count(count, 480)
    return await read_dwords_single_request(client, device, count)


# ---------------------------------------------------------------------------
# Contiguous reads and writes  (sync)
# ---------------------------------------------------------------------------


def read_words_single_request_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[int]:
    """Synchronously read contiguous 16-bit values using one protocol request."""

    ref = _parse_device_for_client(client, device)
    return list(client.read_devices(ref, count, bit_unit=False))


def read_dwords_single_request_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[int]:
    """Synchronously read contiguous unsigned 32-bit values using one protocol request."""

    ref = _validate_dword_read_target(client, device)
    words = read_words_single_request_sync(client, ref, count * 2)
    return _unpack_dword_words(words, count)


def write_words_single_request_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    values: list[int],
) -> None:
    """Synchronously write contiguous 16-bit values using one protocol request."""

    client.write_devices(
        device,
        [_require_write_u16(value, f"values[{index}]") for index, value in enumerate(values)],
        bit_unit=False,
    )


def write_dwords_single_request_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    values: list[int],
) -> None:
    """Synchronously write contiguous unsigned 32-bit values using one protocol request."""

    write_words_single_request_sync(client, device, _pack_dword_words(values))


def read_words_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[int]:
    """Synchronously read a contiguous word-device range using one request."""
    _validate_unsplit_word_count(count, 960)
    return read_words_single_request_sync(client, device, count)


def read_dwords_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[int]:
    """Synchronously read a contiguous DWord range using one request."""
    _validate_unsplit_dword_count(count, 480)
    return read_dwords_single_request_sync(client, device, count)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


async def open_and_connect(
    options: SlmpConnectionOptions,
) -> QueuedAsyncSlmpClient:
    """Create, connect, and wrap one queued async SLMP client.

    This is the recommended async entry point for applications that share one
    connection across polling, named reads, and writes.

    Args:
        options: Stable connection settings for the session.

    Returns:
        A connected :class:`QueuedAsyncSlmpClient`.
    """

    from .async_client import AsyncSlmpClient

    inner = AsyncSlmpClient(
        options.host,
        options.port,
        transport=options.transport,
        timeout=options.timeout,
        plc_profile=options.plc_profile,
        default_target=options.default_target,
        monitoring_timer=options.monitoring_timer,
        raise_on_error=options.raise_on_error,
    )
    await inner.connect()
    return QueuedAsyncSlmpClient(inner)


def open_and_connect_sync(
    options: SlmpConnectionOptions,
) -> SlmpClient:
    """Create and connect one synchronous SLMP client.

    Args:
        options: Stable connection settings for the session.

    Returns:
        A connected synchronous :class:`SlmpClient`.
    """

    from .client import SlmpClient

    client = SlmpClient(
        options.host,
        options.port,
        transport=options.transport,
        timeout=options.timeout,
        plc_profile=options.plc_profile,
        default_target=options.default_target,
        monitoring_timer=options.monitoring_timer,
        raise_on_error=options.raise_on_error,
    )
    client.connect()
    return client


# ---------------------------------------------------------------------------
# Queued client
# ---------------------------------------------------------------------------


class QueuedAsyncSlmpClient:
    """Serialize all async calls on one shared SLMP connection.

    The wrapper exposes the same methods as :class:`AsyncSlmpClient`, but every
    coroutine call is executed under one lock. Use it when one connection is
    shared by polling, snapshot, and write tasks.

    The wrapper does not change protocol semantics. It only prevents multiple
    helper-layer coroutines from interleaving frames on the same socket.
    """

    def __init__(self, inner: AsyncSlmpClient) -> None:
        self._inner = inner
        self._lock = asyncio.Lock()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if asyncio.iscoroutinefunction(attr):

            async def _locked(*args: Any, **kwargs: Any) -> Any:
                async with self._lock:
                    return await attr(*args, **kwargs)

            return _locked
        return attr

    async def __aenter__(self) -> QueuedAsyncSlmpClient:
        async with self._lock:
            await self._inner.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        async with self._lock:
            await self._inner.close()
