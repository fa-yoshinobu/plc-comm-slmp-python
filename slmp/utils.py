"""High-level utility helpers for the SLMP client."""

from __future__ import annotations

import asyncio
import struct
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, cast

from .constants import DEVICE_CODES, DeviceUnit, FrameType, PLCSeries
from .core import (
    DeviceRef,
    SlmpTarget,
    _normalize_device_family_hint,
    _require_explicit_device_family_for_xy,
    _resolve_connection_profile,
    _resolve_plc_family_defaults,
    parse_device,
)

if TYPE_CHECKING:
    from .async_client import AsyncSlmpClient
    from .client import SlmpClient


_WORD_DTYPES = frozenset({"U", "S"})
_DWORD_DTYPES = frozenset({"D", "L", "F"})
_UNBATCHED_DEVICE_CODES = frozenset({"G", "HG"})
_DEFAULT_DWORD_DEVICE_CODES = frozenset({"LTN", "LSTN", "LCN"})
_LONG_TIMER_READ_FAMILIES: dict[str, tuple[str, str]] = {
    "LTN": ("LTN", "current"),
    "LTS": ("LTN", "contact"),
    "LTC": ("LTN", "coil"),
    "LSTN": ("LSTN", "current"),
    "LSTS": ("LSTN", "contact"),
    "LSTC": ("LSTN", "coil"),
    "LCN": ("LCN", "current"),
    "LCS": ("LCN", "contact"),
    "LCC": ("LCN", "coil"),
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
    protocol-level defaults together so generated API docs can point users to
    one explicit connection entry point.

    Attributes:
        host: PLC hostname or IP address.
        plc_family: Canonical high-level PLC family. This is the only
            application-level PLC selector for the recommended helper layer.
        port: TCP or UDP port used by the SLMP endpoint.
        transport: Transport name such as ``"tcp"`` or ``"udp"``.
        timeout: Socket timeout in seconds.
        default_target: Optional routing target applied to requests.
        monitoring_timer: SLMP monitoring timer encoded into frames.
        raise_on_error: Whether protocol errors raise exceptions immediately.
        trace_hook: Optional callback for transport tracing.
        plc_series: Derived access profile fixed by ``plc_family``.
        frame_type: Derived frame type fixed by ``plc_family``.
        device_family: Derived address family used for string device parsing.
        device_range_family: Derived family used for device-range catalog reads.
    """

    host: str
    plc_family: object
    port: int = 5000
    transport: str = "tcp"
    timeout: float = 3.0
    default_target: SlmpTarget | None = None
    monitoring_timer: int = 0x0010
    raise_on_error: bool = True
    trace_hook: Any | None = None
    plc_series: PLCSeries = field(init=False)
    frame_type: FrameType = field(init=False)
    device_family: str = field(init=False)
    device_range_family: str = field(init=False)

    def __post_init__(self) -> None:
        (
            normalized_plc_family,
            plc_series,
            frame_type,
            device_family,
            device_range_family,
        ) = _resolve_connection_profile(
            plc_family=self.plc_family,
            plc_series=None,
            frame_type=None,
            device_family=None,
        )
        object.__setattr__(self, "plc_family", normalized_plc_family)
        object.__setattr__(self, "plc_series", plc_series)
        object.__setattr__(self, "frame_type", frame_type)
        object.__setattr__(self, "device_family", device_family)
        object.__setattr__(self, "device_range_family", device_range_family)


def _client_device_family(client: object) -> str | None:
    family = getattr(client, "device_family", None)
    if family is None:
        return None
    if isinstance(family, str):
        return family
    value = getattr(family, "value", None)
    if isinstance(value, str):
        return value
    return None


def _parse_device_for_family(
    device: str | DeviceRef,
    family: object | None = None,
) -> DeviceRef:
    ref = parse_device(device, family=family)
    return _require_explicit_device_family_for_xy(device, family, ref)


def _parse_device_for_client(
    client: object,
    device: str | DeviceRef,
) -> DeviceRef:
    return _parse_device_for_family(device, _client_device_family(client))


# ---------------------------------------------------------------------------
# Typed single-device read / write  (async)
# ---------------------------------------------------------------------------


async def read_typed(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    dtype: str,
) -> int | float:
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
    key = dtype.upper()
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        return await _read_long_family_value(client, ref, key, long_read)
    if key == "BIT":
        values = await client.read_devices(ref, 1, bit_unit=True)
        return bool(values[0])
    if key in ("D", "L", "F"):
        words = await client.read_devices(ref, 2, bit_unit=False)
        raw = struct.pack("<HH", words[0], words[1])
        if key == "F":
            return cast(float, struct.unpack("<f", raw)[0])
        elif key == "L":
            return cast(int, struct.unpack("<i", raw)[0])
        else:
            return cast(int, struct.unpack("<I", raw)[0])
    else:
        words = await client.read_devices(ref, 1, bit_unit=False)
        if key == "S":
            return cast(int, struct.unpack("<h", struct.pack("<H", words[0]))[0])
        return int(words[0])


async def write_typed(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    dtype: str,
    value: int | float,
) -> None:
    """Write one logical value using the requested application type.

    Args:
        client: Connected high-level or raw async SLMP client.
        device: Starting device address.
        dtype: Type code accepted by :func:`read_typed`.
        value: Application value to encode and write.
    """
    ref = _parse_device_for_client(client, device)
    key = dtype.upper()
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        await _write_long_family_value(client, ref, key, value, long_read)
        return
    if key == "BIT":
        await client.write_devices(device, [bool(value)], bit_unit=True)
        return
    if key == "F":
        raw = struct.pack("<f", float(value))
    elif key == "L":
        raw = struct.pack("<i", int(value))
    elif key == "D":
        raw = struct.pack("<I", int(value))
    else:
        await client.write_devices(device, [int(value) & 0xFFFF], bit_unit=False)
        return
    words = list(struct.unpack("<HH", raw))
    await client.write_devices(device, words, bit_unit=False)


# ---------------------------------------------------------------------------
# Typed single-device read / write  (sync)
# ---------------------------------------------------------------------------


def read_typed_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    dtype: str,
) -> int | float:
    """Synchronously read one logical value as a Python scalar."""
    ref = _parse_device_for_client(client, device)
    key = dtype.upper()
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        return _read_long_family_value_sync(client, ref, key, long_read)
    if key == "BIT":
        values = client.read_devices(ref, 1, bit_unit=True)
        return bool(values[0])
    if key in ("D", "L", "F"):
        words = client.read_devices(ref, 2, bit_unit=False)
        raw = struct.pack("<HH", words[0], words[1])
        if key == "F":
            return cast(float, struct.unpack("<f", raw)[0])
        elif key == "L":
            return cast(int, struct.unpack("<i", raw)[0])
        else:
            return cast(int, struct.unpack("<I", raw)[0])
    else:
        words = client.read_devices(ref, 1, bit_unit=False)
        if key == "S":
            return cast(int, struct.unpack("<h", struct.pack("<H", words[0]))[0])
        return int(words[0])


def write_typed_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    dtype: str,
    value: int | float,
) -> None:
    """Synchronously write one logical value using the requested type."""
    ref = _parse_device_for_client(client, device)
    key = dtype.upper()
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        _write_long_family_value_sync(client, ref, key, value, long_read)
        return
    if key == "BIT":
        client.write_devices(device, [bool(value)], bit_unit=True)
        return
    if key == "F":
        raw = struct.pack("<f", float(value))
    elif key == "L":
        raw = struct.pack("<i", int(value))
    elif key == "D":
        raw = struct.pack("<I", int(value))
    else:
        client.write_devices(device, [int(value) & 0xFFFF], bit_unit=False)
        return
    words = list(struct.unpack("<HH", raw))
    client.write_devices(device, words, bit_unit=False)


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
    if not 0 <= bit_index <= 15:
        raise ValueError(f"bit_index must be 0-15, got {bit_index}")
    words = await client.read_devices(device, 1, bit_unit=False)
    current = int(words[0])
    if value:
        current |= 1 << bit_index
    else:
        current &= ~(1 << bit_index)
    await client.write_devices(device, [current & 0xFFFF], bit_unit=False)


def write_bit_in_word_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    bit_index: int,
    value: bool,
) -> None:
    """Synchronously set or clear one bit inside one word device."""
    if not 0 <= bit_index <= 15:
        raise ValueError(f"bit_index must be 0-15, got {bit_index}")
    words = client.read_devices(device, 1, bit_unit=False)
    current = int(words[0])
    if value:
        current |= 1 << bit_index
    else:
        current &= ~(1 << bit_index)
    client.write_devices(device, [current & 0xFFFF], bit_unit=False)


async def read_bits(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[bool]:
    """Read a contiguous bit-device range as booleans."""
    return [bool(v) for v in await client.read_devices(device, count, bit_unit=True)]


def read_bits_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
) -> list[bool]:
    """Synchronously read a contiguous bit-device range as booleans."""
    return [bool(v) for v in client.read_devices(device, count, bit_unit=True)]


async def write_bits(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    values: list[bool],
) -> None:
    """Write a contiguous bit-device range from booleans."""
    await client.write_devices(device, [bool(v) for v in values], bit_unit=True)


def write_bits_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    values: list[bool],
) -> None:
    """Synchronously write a contiguous bit-device range from booleans."""
    client.write_devices(device, [bool(v) for v in values], bit_unit=True)


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
    plan = _compile_read_plan(addresses, family=_client_device_family(client))
    return await _read_named_with_plan(client, plan)


def read_named_sync(
    client: SlmpClient,
    addresses: list[str],
) -> dict[str, int | float | bool]:
    """Synchronously read a mixed logical snapshot by address string."""
    plan = _compile_read_plan(addresses, family=_client_device_family(client))
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
    family = _client_device_family(client)
    for address, value in updates.items():
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            _validate_bit_in_word_target(address, _parse_device_for_family(base, family))
            await write_bit_in_word(client, base, bit_idx or 0, bool(value))
        else:
            device = _parse_device_for_family(base, family)
            resolved_dtype = _resolve_dtype_for_address(address, device, dtype, bit_idx)
            _validate_long_timer_entry(address, device, resolved_dtype)
            await write_typed(client, base, resolved_dtype, value)


def write_named_sync(
    client: SlmpClient,
    updates: dict[str, int | float | bool],
) -> None:
    """Synchronously write a mixed logical snapshot by address string."""
    family = _client_device_family(client)
    for address, value in updates.items():
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            _validate_bit_in_word_target(address, _parse_device_for_family(base, family))
            write_bit_in_word_sync(client, base, bit_idx or 0, bool(value))
        else:
            device = _parse_device_for_family(base, family)
            resolved_dtype = _resolve_dtype_for_address(address, device, dtype, bit_idx)
            _validate_long_timer_entry(address, device, resolved_dtype)
            write_typed_sync(client, base, resolved_dtype, value)


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
        return base.strip(), dtype.strip().upper(), None
    if "." in address:
        base, bit_str = address.split(".", 1)
        try:
            return base.strip(), "BIT_IN_WORD", int(bit_str, 16)
        except ValueError:
            pass
    return address.strip(), "U", None


def normalize_address(
    address: str | DeviceRef,
    *,
    plc_family: object | None = None,
    family: object | None = None,
) -> str:
    """Return the canonical helper-layer form of one SLMP device address.

    The helper accepts free-form user text such as ``" d200:f "`` or an
    already parsed :class:`DeviceRef`. The result is suitable for logs,
    configuration files, and cache keys.
    """

    if not isinstance(address, str):
        return str(address)

    if plc_family is not None and family is not None:
        raise ValueError("Pass either plc_family or family to normalize_address(), not both.")
    effective_family = family
    if plc_family is not None:
        defaults = _resolve_plc_family_defaults(plc_family)
        effective_family = None if defaults is None else defaults.device_family
    elif family is not None:
        effective_family = _normalize_device_family_hint(family)

    text = address.strip()
    if ":" not in text and "." not in text:
        return str(parse_device(text, family=effective_family))

    base, dtype, bit_index = _parse_address(text)
    canonical_base = str(parse_device(base, family=effective_family))
    if bit_index is not None:
        return f"{canonical_base}.{bit_index:X}"
    if ":" in text:
        return f"{canonical_base}:{dtype}"
    return canonical_base


def _is_batchable_word_device(device: DeviceRef) -> bool:
    code = DEVICE_CODES.get(device.code)
    return code is not None and code.unit == DeviceUnit.WORD and device.code not in _UNBATCHED_DEVICE_CODES


def _address_has_explicit_dtype(address: str) -> bool:
    return ":" in address


def _normalize_dtype_for_device(device: DeviceRef, dtype: str) -> str:
    code = DEVICE_CODES.get(device.code)
    if code is not None and code.unit == DeviceUnit.BIT and dtype == "U":
        return "BIT"
    return dtype


def _resolve_dtype_for_address(address: str, device: DeviceRef, dtype: str, bit_index: int | None) -> str:
    normalized = _normalize_dtype_for_device(device, dtype or "U")
    if not _address_has_explicit_dtype(address) and bit_index is None and device.code in _DEFAULT_DWORD_DEVICE_CODES:
        return "D"
    return normalized


def _get_long_timer_read(device: DeviceRef) -> tuple[str, str] | None:
    return _LONG_TIMER_READ_FAMILIES.get(device.code)


def _validate_long_timer_entry(address: str, device: DeviceRef, dtype: str) -> None:
    long_read = _get_long_timer_read(device)
    if long_read is None:
        return
    _, role = long_read
    if role == "current":
        if dtype not in {"D", "L"}:
            raise ValueError(
                f"Address '{address}' uses a 32-bit long current value. Use the plain form or ':D' / ':L'."
            )
        return
    if dtype != "BIT":
        raise ValueError(
            f"Address '{address}' is a long timer state device. Use the plain device form without a dtype override."
        )


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
            dword_values={device: int(value) & 0xFFFFFFFF},
            series=client.plc_series,
        )
        return
    if device.code == "LCS":
        await client.write_devices(device, [1 if bool(value) else 0], bit_unit=False)
        return
    await client.write_random_bits({device: bool(value)}, series=client.plc_series)


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
            dword_values={device: int(value) & 0xFFFFFFFF},
            series=client.plc_series,
        )
        return
    if device.code == "LCS":
        client.write_devices(device, [1 if bool(value) else 0], bit_unit=False)
        return
    client.write_random_bits({device: bool(value)}, series=client.plc_series)


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
    words = await client.read_devices(DeviceRef("LCN", head_no), 4, bit_unit=False)
    return _decode_long_family_words(list(words))


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
    words = client.read_devices(DeviceRef("LCN", head_no), 4, bit_unit=False)
    return _decode_long_family_words(list(words))


async def _read_long_family_value(
    client: AsyncSlmpClient,
    device: DeviceRef,
    dtype: str,
    long_read: tuple[str, str],
) -> int | bool:
    prefix, role = long_read
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
    current_value, contact, coil = _read_long_family_point_sync(client, prefix, device.number)
    if role == "current":
        return _coerce_long_current_value(current_value, dtype)
    if role == "contact":
        return contact
    return coil


def _compile_read_plan(
    addresses: list[str],
    *,
    family: object | None = None,
) -> _ReadPlan:
    entries: list[_ReadPlanEntry] = []
    word_devices: list[DeviceRef] = []
    dword_devices: list[DeviceRef] = []
    seen_words: set[DeviceRef] = set()
    seen_dwords: set[DeviceRef] = set()

    for address in addresses:
        base, dtype, bit_index = _parse_address(address)
        device = _parse_device_for_family(base, family)
        dtype = _resolve_dtype_for_address(address, device, dtype, bit_index)
        _validate_long_timer_entry(address, device, dtype)
        batch_kind: str | None = None
        long_timer_read = _get_long_timer_read(device)

        if long_timer_read is not None:
            batch_kind = "LONG_TIMER"
        elif dtype == "BIT_IN_WORD":
            _validate_bit_in_word_target(address, device)
            if _is_batchable_word_device(device):
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


async def _read_random_maps(
    client: AsyncSlmpClient,
    plan: _ReadPlan,
) -> tuple[dict[str, int], dict[str, int]]:
    word_values: dict[str, int] = {}
    dword_values: dict[str, int] = {}
    word_devices = list(plan.word_devices)
    dword_devices = list(plan.dword_devices)
    word_index = 0
    dword_index = 0

    while word_index < len(word_devices) or dword_index < len(dword_devices):
        word_chunk = word_devices[word_index : word_index + 0xFF]
        dword_chunk = dword_devices[dword_index : dword_index + 0xFF]
        word_index += len(word_chunk)
        dword_index += len(dword_chunk)
        if not word_chunk and not dword_chunk:
            break
        result = await client.read_random(word_devices=word_chunk, dword_devices=dword_chunk)
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
    word_index = 0
    dword_index = 0

    while word_index < len(word_devices) or dword_index < len(dword_devices):
        word_chunk = word_devices[word_index : word_index + 0xFF]
        dword_chunk = dword_devices[dword_index : dword_index + 0xFF]
        word_index += len(word_chunk)
        dword_index += len(dword_chunk)
        if not word_chunk and not dword_chunk:
            break
        result = client.read_random(word_devices=word_chunk, dword_devices=dword_chunk)
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
                result[entry.address] = bool((word >> (entry.bit_index or 0)) & 1)
            else:
                result[entry.address] = _decode_word_value(word, entry.dtype)
            continue
        if entry.batch_kind == "DWORD":
            result[entry.address] = _decode_dword_value(dword_values[str(entry.device)], entry.dtype)
            continue
        if entry.dtype == "BIT_IN_WORD":
            words = await client.read_devices(entry.device, 1, bit_unit=False)
            result[entry.address] = bool((words[0] >> (entry.bit_index or 0)) & 1)
        else:
            result[entry.address] = await read_typed(client, entry.device, entry.dtype or "U")

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
                result[entry.address] = bool((word >> (entry.bit_index or 0)) & 1)
            else:
                result[entry.address] = _decode_word_value(word, entry.dtype)
            continue
        if entry.batch_kind == "DWORD":
            result[entry.address] = _decode_dword_value(dword_values[str(entry.device)], entry.dtype)
            continue
        if entry.dtype == "BIT_IN_WORD":
            words = client.read_devices(entry.device, 1, bit_unit=False)
            result[entry.address] = bool((words[0] >> (entry.bit_index or 0)) & 1)
        else:
            result[entry.address] = read_typed_sync(client, entry.device, entry.dtype or "U")

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
    plan = _compile_read_plan(addresses, family=_client_device_family(client))
    while True:
        yield await _read_named_with_plan(client, plan)
        await asyncio.sleep(interval)


def poll_sync(
    client: SlmpClient,
    addresses: list[str],
    interval: float,
) -> Iterator[dict[str, int | float | bool]]:
    """Synchronously yield mixed snapshots at a fixed interval."""
    plan = _compile_read_plan(addresses, family=_client_device_family(client))
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

    This is the explicit atomic path for one contiguous word range. If the
    caller wants multi-request behavior, use :func:`read_words_chunked`.
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

    words = await read_words_single_request(client, device, count * 2)
    return [struct.unpack("<I", struct.pack("<HH", words[i], words[i + 1]))[0] for i in range(0, count * 2, 2)]


async def write_words_single_request(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    values: list[int],
) -> None:
    """Write contiguous 16-bit values using one protocol request.

    Use this helper for logical ranges that should stay within one protocol
    write operation.
    """

    await client.write_devices(device, [int(value) & 0xFFFF for value in values], bit_unit=False)


async def write_dwords_single_request(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    values: list[int],
) -> None:
    """Write contiguous unsigned 32-bit values using one protocol request.

    Each Python ``int`` is encoded as two PLC words in little-endian order.
    """

    words: list[int] = []
    for value in values:
        words.extend(struct.unpack("<HH", struct.pack("<I", int(value) & 0xFFFFFFFF)))
    await write_words_single_request(client, device, words)


async def read_words_chunked(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
    max_per_request: int = 960,
) -> list[int]:
    """Read contiguous 16-bit values across multiple aligned requests.

    Chunking is explicit here. Use this helper only when multi-request read
    semantics are acceptable to the caller.
    """


    effective_max = (max_per_request // 2) * 2
    if effective_max <= 0:
        raise ValueError("max_per_request must be at least 2")

    ref = _parse_device_for_client(client, device)
    result: list[int] = []
    remaining = count
    offset = 0
    while remaining > 0:
        chunk = min(remaining, effective_max)
        chunk_ref = replace(ref, number=ref.number + offset)
        words = await read_words_single_request(client, chunk_ref, chunk)
        result.extend(words)
        offset += chunk
        remaining -= chunk
    return result


async def read_dwords_chunked(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
    max_dwords_per_request: int = 480,
) -> list[int]:
    """Read contiguous unsigned 32-bit values across multiple aligned requests.

    Chunk boundaries stay aligned to full dwords so one logical 32-bit value
    is never torn across requests.
    """

    words = await read_words_chunked(client, device, count * 2, max_per_request=max_dwords_per_request * 2)
    return [struct.unpack("<I", struct.pack("<HH", words[i], words[i + 1]))[0] for i in range(0, count * 2, 2)]


async def write_words_chunked(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    values: list[int],
    max_per_request: int = 960,
) -> None:
    """Write contiguous 16-bit values across multiple aligned requests.

    Use this helper only when multiple write operations are acceptable to the
    caller.
    """


    effective_max = (max_per_request // 2) * 2
    if effective_max <= 0:
        raise ValueError("max_per_request must be at least 2")

    ref = _parse_device_for_client(client, device)
    offset = 0
    while offset < len(values):
        chunk = min(len(values) - offset, effective_max)
        chunk_ref = replace(ref, number=ref.number + offset)
        await write_words_single_request(client, chunk_ref, values[offset : offset + chunk])
        offset += chunk


async def write_dwords_chunked(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    values: list[int],
    max_dwords_per_request: int = 480,
) -> None:
    """Write contiguous unsigned 32-bit values across multiple aligned requests.

    Each chunk boundary is aligned to full dwords so one logical value remains
    intact inside one request.
    """


    if max_dwords_per_request <= 0:
        raise ValueError("max_dwords_per_request must be at least 1")

    ref = _parse_device_for_client(client, device)
    offset = 0
    while offset < len(values):
        chunk = min(len(values) - offset, max_dwords_per_request)
        chunk_ref = replace(ref, number=ref.number + (offset * 2))
        await write_dwords_single_request(client, chunk_ref, values[offset : offset + chunk])
        offset += chunk


async def read_words(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
    max_per_request: int = 960,
    *,
    allow_split: bool = False,
) -> list[int]:
    """Read a contiguous word-device range with optional chunk splitting.

    Chunk boundaries stay aligned to 2-word boundaries so 32-bit values are
    not torn across split requests.
    """
    if not allow_split:
        effective_max = (max_per_request // 2) * 2
        if effective_max <= 0:
            raise ValueError("max_per_request must be at least 2")
        if count > effective_max:
            raise ValueError(
                f"count {count} exceeds max_per_request {effective_max};"
                " pass allow_split=True to split the read across multiple requests"
            )
        return await read_words_single_request(client, device, count)

    return await read_words_chunked(client, device, count, max_per_request=max_per_request)


async def read_dwords(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
    max_dwords_per_request: int = 480,
    *,
    allow_split: bool = False,
) -> list[int]:
    """Read a contiguous DWord range as unsigned 32-bit integers."""
    if not allow_split:
        effective_max = max_dwords_per_request
        if effective_max <= 0:
            raise ValueError("max_dwords_per_request must be at least 1")
        if count > effective_max:
            raise ValueError(
                f"count {count} exceeds max_dwords_per_request {effective_max};"
                " pass allow_split=True to split the read across multiple requests"
            )
        return await read_dwords_single_request(client, device, count)

    return await read_dwords_chunked(client, device, count, max_dwords_per_request=max_dwords_per_request)


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

    words = read_words_single_request_sync(client, device, count * 2)
    return [struct.unpack("<I", struct.pack("<HH", words[i], words[i + 1]))[0] for i in range(0, count * 2, 2)]


def write_words_single_request_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    values: list[int],
) -> None:
    """Synchronously write contiguous 16-bit values using one protocol request."""

    client.write_devices(device, [int(value) & 0xFFFF for value in values], bit_unit=False)


def write_dwords_single_request_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    values: list[int],
) -> None:
    """Synchronously write contiguous unsigned 32-bit values using one protocol request."""

    words: list[int] = []
    for value in values:
        words.extend(struct.unpack("<HH", struct.pack("<I", int(value) & 0xFFFFFFFF)))
    write_words_single_request_sync(client, device, words)


def read_words_chunked_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
    max_per_request: int = 960,
) -> list[int]:
    """Synchronously read contiguous 16-bit values across multiple aligned requests."""


    effective_max = (max_per_request // 2) * 2
    if effective_max <= 0:
        raise ValueError("max_per_request must be at least 2")

    ref = _parse_device_for_client(client, device)
    result: list[int] = []
    remaining = count
    offset = 0
    while remaining > 0:
        chunk = min(remaining, effective_max)
        chunk_ref = replace(ref, number=ref.number + offset)
        words = read_words_single_request_sync(client, chunk_ref, chunk)
        result.extend(words)
        offset += chunk
        remaining -= chunk
    return result


def read_dwords_chunked_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
    max_dwords_per_request: int = 480,
) -> list[int]:
    """Synchronously read contiguous unsigned 32-bit values across multiple aligned requests."""

    words = read_words_chunked_sync(client, device, count * 2, max_per_request=max_dwords_per_request * 2)
    return [struct.unpack("<I", struct.pack("<HH", words[i], words[i + 1]))[0] for i in range(0, count * 2, 2)]


def write_words_chunked_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    values: list[int],
    max_per_request: int = 960,
) -> None:
    """Synchronously write contiguous 16-bit values across multiple aligned requests."""


    effective_max = (max_per_request // 2) * 2
    if effective_max <= 0:
        raise ValueError("max_per_request must be at least 2")

    ref = _parse_device_for_client(client, device)
    offset = 0
    while offset < len(values):
        chunk = min(len(values) - offset, effective_max)
        chunk_ref = replace(ref, number=ref.number + offset)
        write_words_single_request_sync(client, chunk_ref, values[offset : offset + chunk])
        offset += chunk


def write_dwords_chunked_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    values: list[int],
    max_dwords_per_request: int = 480,
) -> None:
    """Synchronously write contiguous unsigned 32-bit values across multiple aligned requests."""


    if max_dwords_per_request <= 0:
        raise ValueError("max_dwords_per_request must be at least 1")

    ref = _parse_device_for_client(client, device)
    offset = 0
    while offset < len(values):
        chunk = min(len(values) - offset, max_dwords_per_request)
        chunk_ref = replace(ref, number=ref.number + (offset * 2))
        write_dwords_single_request_sync(client, chunk_ref, values[offset : offset + chunk])
        offset += chunk


def read_words_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
    max_per_request: int = 960,
    *,
    allow_split: bool = False,
) -> list[int]:
    """Synchronously read a contiguous word-device range."""
    if not allow_split:
        effective_max = (max_per_request // 2) * 2
        if effective_max <= 0:
            raise ValueError("max_per_request must be at least 2")
        if count > effective_max:
            raise ValueError(
                f"count {count} exceeds max_per_request {effective_max};"
                " pass allow_split=True to split the read across multiple requests"
            )
        return read_words_single_request_sync(client, device, count)

    return read_words_chunked_sync(client, device, count, max_per_request=max_per_request)


def read_dwords_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
    max_dwords_per_request: int = 480,
    *,
    allow_split: bool = False,
) -> list[int]:
    """Synchronously read a contiguous DWord range."""
    if not allow_split:
        effective_max = max_dwords_per_request
        if effective_max <= 0:
            raise ValueError("max_dwords_per_request must be at least 1")
        if count > effective_max:
            raise ValueError(
                f"count {count} exceeds max_dwords_per_request {effective_max};"
                " pass allow_split=True to split the read across multiple requests"
            )
        return read_dwords_single_request_sync(client, device, count)

    return read_dwords_chunked_sync(client, device, count, max_dwords_per_request=max_dwords_per_request)


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
        plc_family=options.plc_family,
        default_target=options.default_target,
        monitoring_timer=options.monitoring_timer,
        raise_on_error=options.raise_on_error,
        trace_hook=options.trace_hook,
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
        plc_family=options.plc_family,
        default_target=options.default_target,
        monitoring_timer=options.monitoring_timer,
        raise_on_error=options.raise_on_error,
        trace_hook=options.trace_hook,
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
