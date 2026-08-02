"""High-level utility helpers for the SLMP client."""

from __future__ import annotations

import asyncio
import math
import struct
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from . import _operations
from .constants import DeviceUnit, FrameType, PLCSeries
from .core import (
    DeviceRef,
    SlmpTarget,
    _check_direct_device_points,
    _check_temporarily_unsupported_device,
    _device_unit,
    _normalize_plc_profile_hint,
    _require_explicit_plc_profile_for_xy,
    _require_write_u16,
    _require_write_u32,
    _resolve_connection_profile,
    _resolve_port,
    _validate_direct_dword_read_device,
    _validate_direct_read_device,
    _validate_direct_write_device,
    encode_device_spec,
    parse_device,
    resolve_device_subcommand,
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
    batch_index: int | None


@dataclass(frozen=True)
class _ReadPlan:
    entries: tuple[_ReadPlanEntry, ...]
    word_devices: tuple[DeviceRef, ...]
    dword_devices: tuple[DeviceRef, ...]


@dataclass(frozen=True)
class _PreparedReadPlan:
    owner: AsyncSlmpClient | SlmpClient
    plc_profile: object
    plc_series: object
    frame_type: object
    operation: _operations.RandomReadOperation


@dataclass(frozen=True)
class SlmpConnectionOptions:
    """Stable connection settings for one SLMP session.

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
        timeout: One absolute deadline for each admitted operation, covering
            explicit connection establishment or lazy connection through the
            complete request exchange, in seconds.
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
    _validate_device_dtype(str(ref), ref, key)
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
    _validate_device_dtype(str(ref), ref, key)
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        _validate_long_timer_entry(str(ref), ref, key)
        await _write_long_family_value(client, ref, key, value, long_read)
        return
    if key == "BIT":
        await client.write_devices(device, [_require_typed_bool(value)], bit_unit=True)
        return
    if key in {"D", "L", "F"} and ref.code in _RANDOM_DWORD_SCALAR_DEVICE_CODES:
        await client.write_random_words(
            dword_values={ref: _encode_typed_float32(value) if key == "F" else _encode_typed_dword(value, key)},
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
    _validate_device_dtype(str(ref), ref, key)
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
    _validate_device_dtype(str(ref), ref, key)
    long_read = _get_long_timer_read(ref)
    if long_read is not None:
        _validate_long_timer_entry(str(ref), ref, key)
        _write_long_family_value_sync(client, ref, key, value, long_read)
        return
    if key == "BIT":
        client.write_devices(device, [_require_typed_bool(value)], bit_unit=True)
        return
    if key in {"D", "L", "F"} and ref.code in _RANDOM_DWORD_SCALAR_DEVICE_CODES:
        client.write_random_words(
            dword_values={ref: _encode_typed_float32(value) if key == "F" else _encode_typed_dword(value, key)},
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
    ``"BIT"``. It holds one client FIFO turn across a word read followed by a
    word write. That prevents same-client interleaving but is not atomic at the
    PLC: another connection or PLC logic can change the word between requests.
    A possibly-sent write uses the outcome-unknown error contract. The helper
    never retries automatically.
    """
    ref, normalized_index, normalized_value = _prepare_bit_in_word_rmw(client, device, bit_index, value)
    from .async_client import AsyncSlmpClient

    turn = client._operation_queue.turn() if isinstance(client, AsyncSlmpClient) else _noop_async_context()
    async with turn:
        words = await client.read_devices(ref, 1, bit_unit=False)
        updated = _update_bit_in_word_value(int(words[0]), normalized_index, normalized_value)
        await client.write_devices(ref, [updated], bit_unit=False)


def write_bit_in_word_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    bit_index: int,
    value: bool,
) -> None:
    """Synchronously update one word bit while holding one client FIFO turn.

    The read and write are two non-atomic PLC requests. Another connection or
    PLC logic can race with them, possibly-sent writes use the outcome-unknown
    error contract, and the helper never retries automatically.
    """
    ref, normalized_index, normalized_value = _prepare_bit_in_word_rmw(client, device, bit_index, value)
    from .client import SlmpClient

    turn = client._operation_queue.turn() if isinstance(client, SlmpClient) else nullcontext()
    with turn:
        words = client.read_devices(ref, 1, bit_unit=False)
        updated = _update_bit_in_word_value(int(words[0]), normalized_index, normalized_value)
        client.write_devices(ref, [updated], bit_unit=False)


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
    """Read a mixed logical collection by address string.

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
    """Synchronously read a mixed logical collection by address string."""
    plan = _compile_read_plan(addresses, address_profile=_client_address_profile(client))
    return _read_named_with_plan_sync(client, plan)


# ---------------------------------------------------------------------------
# Named-device write  (async + sync)
# ---------------------------------------------------------------------------


async def write_named(
    client: AsyncSlmpClient,
    updates: dict[str, int | float | bool],
) -> None:
    """Write a mixed logical collection by address string.

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
    """Synchronously write a mixed logical collection by address string."""
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
    return _device_unit(device) == DeviceUnit.WORD and device.code not in _UNBATCHED_DEVICE_CODES


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
    is_bit_device = _device_unit(device) == DeviceUnit.BIT
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
    if _device_unit(device) != DeviceUnit.WORD:
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
    if len(set(addresses)) != len(addresses):
        raise ValueError("addresses must not contain duplicate result keys")
    entries: list[_ReadPlanEntry] = []
    word_devices: list[DeviceRef] = []
    dword_devices: list[DeviceRef] = []
    word_indexes: dict[DeviceRef, int] = {}
    dword_indexes: dict[DeviceRef, int] = {}

    for address in addresses:
        base, dtype, bit_index = _parse_address(address)
        device = _parse_device_for_address_profile(base, address_profile)
        batch_kind: str | None = None
        batch_index: int | None = None
        long_timer_read = _get_long_timer_read(device)

        if dtype == "BIT_IN_WORD":
            dtype = _resolve_dtype_for_address(address, device, dtype, bit_index)
            bit_index = _require_bit_in_word_index(address, bit_index)
            _validate_bit_in_word_target(address, device)
            if _is_batchable_word_device(device):
                batch_kind = "WORD"
                if device not in word_indexes:
                    word_indexes[device] = len(word_devices)
                    word_devices.append(device)
                batch_index = word_indexes[device]
        else:
            dtype = _resolve_dtype_for_address(address, device, dtype, bit_index)
            _validate_device_dtype(address, device, dtype)
            _validate_long_timer_entry(address, device, dtype)

        if long_timer_read is not None and not (device.code == "LCN" and long_timer_read[1] == "current"):
            raise ValueError(
                f"read_named cannot route '{address}' through a hidden Direct long-timer read; "
                "use read_typed or an explicit long-timer helper"
            )
        if long_timer_read is not None:
            batch_kind = "DWORD"
            if device not in dword_indexes:
                dword_indexes[device] = len(dword_devices)
                dword_devices.append(device)
            batch_index = dword_indexes[device]
        elif dtype == "BIT":
            bit_word = _plain_bit_word_read(device)
            if bit_word is not None:
                device, bit_index = bit_word
                dtype = "BIT_IN_WORD"
                batch_kind = "WORD"
                if device not in word_indexes:
                    word_indexes[device] = len(word_devices)
                    word_devices.append(device)
                batch_index = word_indexes[device]
        elif dtype in _WORD_DTYPES:
            if _is_batchable_word_device(device):
                batch_kind = "WORD"
                if device not in word_indexes:
                    word_indexes[device] = len(word_devices)
                    word_devices.append(device)
                batch_index = word_indexes[device]
        elif dtype in _DWORD_DTYPES:
            if _is_batchable_word_device(device):
                batch_kind = "DWORD"
                if device not in dword_indexes:
                    dword_indexes[device] = len(dword_devices)
                    dword_devices.append(device)
                batch_index = dword_indexes[device]

        entries.append(_ReadPlanEntry(address, device, dtype, bit_index, batch_kind, batch_index))

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


def _prepare_bit_in_word_rmw(
    client: object,
    device: str | DeviceRef,
    bit_index: int,
    value: bool,
) -> tuple[DeviceRef, int, bool]:
    if type(bit_index) is not int or not 0 <= bit_index <= 15:
        raise ValueError(f"bit_index must be 0-15, got {bit_index}")
    normalized_value = _require_typed_bool(value)
    ref = _parse_device_for_client(client, device)
    if _device_unit(ref) is not DeviceUnit.WORD:
        raise ValueError("write_bit_in_word is only valid for word devices; use write_typed for bit devices")

    from .async_client import AsyncSlmpClient
    from .client import SlmpClient

    if isinstance(client, (SlmpClient, AsyncSlmpClient)):
        client._ensure_profile_feature_allowed("direct")  # noqa: SLF001 - same-package aggregate preflight
        _check_direct_device_points(
            1,
            bit_unit=False,
            name="write_bit_in_word read",
            plc_profile=client.plc_profile,
        )
        _check_direct_device_points(
            1,
            bit_unit=False,
            name="write_bit_in_word write",
            write=True,
            plc_profile=client.plc_profile,
        )
        _validate_direct_read_device(ref, points=1, bit_unit=False)
        _validate_direct_write_device(ref, bit_unit=False, plc_profile=client.plc_profile)
        _check_temporarily_unsupported_device(ref)
        encode_device_spec(ref, series=client.plc_series)
        resolve_device_subcommand(bit_unit=False, series=client.plc_series, extension=False)
    return ref, bit_index, normalized_value


def _update_bit_in_word_value(current: int, bit_index: int, value: bool) -> int:
    if type(bit_index) is not int or not 0 <= bit_index <= 15:
        raise ValueError(f"bit_index must be 0-15, got {bit_index}")
    value = _require_typed_bool(value)
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


def _prepare_read_plan(
    client: AsyncSlmpClient | SlmpClient,
    plan: _ReadPlan,
) -> _PreparedReadPlan:
    """Validate and encode the one named-read request before transport."""
    client._ensure_profile_feature_allowed("random")
    _, default_series, _, _, _ = _resolve_connection_profile(
        plc_profile=client.plc_profile,
        plc_series=None,
        frame_type=None,
        address_profile=None,
    )
    operation = _operations.build_read_random_request(
        word_devices=plan.word_devices,
        dword_devices=plan.dword_devices,
        series=None,
        default_series=default_series,
        address_profile=client.plc_profile,
    )
    return _PreparedReadPlan(
        owner=client,
        plc_profile=client.plc_profile,
        plc_series=client.plc_series,
        frame_type=client.frame_type,
        operation=operation,
    )


def _decode_read_plan(
    output: dict[str, int | float | bool],
    plan: _ReadPlan,
    random_values: tuple[list[int], list[int]],
) -> None:
    word_values, dword_values = random_values
    for entry in plan.entries:
        if entry.batch_index is None:
            raise RuntimeError(f"read plan has no compact decode index for {entry.address!r}")
        if entry.batch_kind == "WORD":
            word = word_values[entry.batch_index]
            if entry.dtype == "BIT_IN_WORD":
                bit_index = _require_bit_in_word_index(entry.address, entry.bit_index)
                output[entry.address] = bool((word >> bit_index) & 1)
            else:
                output[entry.address] = _decode_word_value(word, entry.dtype)
        else:
            output[entry.address] = _decode_dword_value(dword_values[entry.batch_index], entry.dtype)


def _validate_prepared_read_binding(
    client: AsyncSlmpClient | SlmpClient,
    prepared: _PreparedReadPlan,
) -> None:
    if prepared.owner is not client:
        raise ValueError("prepared named-read plan belongs to a different client")
    if (
        prepared.plc_profile != client.plc_profile
        or prepared.plc_series != client.plc_series
        or prepared.frame_type != client.frame_type
    ):
        raise ValueError("prepared named-read plan does not match the client profile, frame, or compatibility mode")


async def _read_named_with_plan(
    client: AsyncSlmpClient,
    plan: _ReadPlan,
    prepared: _PreparedReadPlan | None = None,
) -> dict[str, int | float | bool]:
    prepared = _prepare_read_plan(client, plan) if prepared is None else prepared
    _validate_prepared_read_binding(client, prepared)
    operation = prepared.operation
    result: dict[str, int | float | bool] = {}
    from .async_client import AsyncSlmpClient

    if isinstance(client, AsyncSlmpClient) and type(client).read_random is AsyncSlmpClient.read_random:
        request = operation.request
        random_values = await client._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_prepared_random_read_values(response, operation),
        )
    else:
        turn = client._operation_queue.turn() if isinstance(client, AsyncSlmpClient) else _noop_async_context()
        async with turn:
            random_result = await client.read_random(
                word_devices=list(operation.word_refs),
                dword_devices=list(operation.dword_refs),
            )
        random_values = (
            [random_result.word[key] for key in operation.word_keys],
            [random_result.dword[key] for key in operation.dword_keys],
        )
    _decode_read_plan(result, plan, random_values)
    return result


def _read_named_with_plan_sync(
    client: SlmpClient,
    plan: _ReadPlan,
    prepared: _PreparedReadPlan | None = None,
) -> dict[str, int | float | bool]:
    prepared = _prepare_read_plan(client, plan) if prepared is None else prepared
    _validate_prepared_read_binding(client, prepared)
    operation = prepared.operation
    result: dict[str, int | float | bool] = {}
    from .client import SlmpClient

    if isinstance(client, SlmpClient) and type(client).read_random is SlmpClient.read_random:
        request = operation.request
        random_values = client._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_prepared_random_read_values(response, operation),
        )
    else:
        turn = client._operation_queue.turn() if isinstance(client, SlmpClient) else nullcontext()
        with turn:
            random_result = client.read_random(
                word_devices=list(operation.word_refs),
                dword_devices=list(operation.dword_refs),
            )
        random_values = (
            [random_result.word[key] for key in operation.word_keys],
            [random_result.dword[key] for key in operation.dword_keys],
        )
    _decode_read_plan(result, plan, random_values)
    return result


@asynccontextmanager
async def _noop_async_context() -> AsyncIterator[None]:
    yield


# ---------------------------------------------------------------------------
# Polling  (async + sync)
# ---------------------------------------------------------------------------


async def poll(
    client: AsyncSlmpClient,
    addresses: list[str],
    interval: float,
) -> AsyncIterator[dict[str, int | float | bool]]:
    """Continuously yield mixed read results at a fixed interval.

    The address list is compiled once and reused for every cycle.
    """
    plan = _compile_read_plan(addresses, address_profile=_client_address_profile(client))
    prepared = _prepare_read_plan(client, plan)
    while True:
        yield await _read_named_with_plan(client, plan, prepared)
        await asyncio.sleep(interval)


def poll_sync(
    client: SlmpClient,
    addresses: list[str],
    interval: float,
) -> Iterator[dict[str, int | float | bool]]:
    """Synchronously yield mixed read results at a fixed interval."""
    plan = _compile_read_plan(addresses, address_profile=_client_address_profile(client))
    prepared = _prepare_read_plan(client, plan)
    while True:
        yield _read_named_with_plan_sync(client, plan, prepared)
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
) -> AsyncSlmpClient:
    """Create and connect one async SLMP client.

    This is the recommended async entry point for applications that share one
    connection across polling, named reads, and writes.

    Args:
        options: Stable connection settings for the session.

    Returns:
        A connected :class:`AsyncSlmpClient`. The ordinary client owns the
        FIFO operation queue; no wrapper is required.
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
    return inner


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
