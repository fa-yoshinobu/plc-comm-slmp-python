"""High-level utility helpers for the SLMP client."""

from __future__ import annotations

import asyncio
import struct
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from .constants import DEVICE_CODES, DeviceUnit
from .core import DeviceRef, parse_device

if TYPE_CHECKING:
    from .async_client import AsyncSlmpClient
    from .client import SlmpClient


_WORD_DTYPES = frozenset({"U", "S"})
_DWORD_DTYPES = frozenset({"D", "L", "F"})
_UNBATCHED_DEVICE_CODES = frozenset({"G", "HG"})


@dataclass(frozen=True)
class _ReadPlanEntry:
    address: str
    device: DeviceRef
    dtype: str
    bit_index: int | None
    batch_kind: str | None


@dataclass(frozen=True)
class _ReadPlan:
    entries: tuple[_ReadPlanEntry, ...]
    word_devices: tuple[DeviceRef, ...]
    dword_devices: tuple[DeviceRef, ...]


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


async def open_and_connect(
    host: str,
    port: int = 5000,
    timeout: float = 1.5,
) -> AsyncSlmpClient:
    """Open one connection and resolve a stable SLMP profile before use.

    This helper probes supported frame/profile combinations, keeps the client
    connected, and returns it ready for high-level calls such as
    :func:`read_typed`, :func:`read_named`, and :func:`poll`.

    Args:
        host: PLC IP address or hostname.
        port: SLMP port number. Typical values are ``1025`` for iQ-R/iQ-F,
            ``5007`` for Q/L, and ``5000`` for simulator setups.
        timeout: Per-profile connect timeout in seconds.

    Returns:
        A connected :class:`~slmp.async_client.AsyncSlmpClient` with
        ``frame_type`` and ``plc_series`` already resolved.

    Raises:
        ConnectionError: If no supported profile can talk to the PLC.
    """
    from .async_client import AsyncSlmpClient

    client = AsyncSlmpClient(host, port, timeout=timeout)
    rec = await client.resolve_profile()
    if not rec.is_confident:
        raise ConnectionError(f"Could not detect PLC profile at {host}:{port}")
    return client


async def open_and_connect_queued(
    host: str,
    port: int = 5000,
    timeout: float = 1.5,
) -> QueuedAsyncSlmpClient:
    """Open one connection and wrap it in a queued high-level client.

    This is the recommended entry point when multiple coroutines share one PLC
    connection, for example a poller and one or more writers.
    """
    return QueuedAsyncSlmpClient(await open_and_connect(host, port=port, timeout=timeout))


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
    key = dtype.upper()
    if key == "BIT":
        values = await client.read_devices(device, 1, bit_unit=True)
        return bool(values[0])
    if key in ("D", "L", "F"):
        words = await client.read_devices(device, 2, bit_unit=False)
        raw = struct.pack("<HH", words[0], words[1])
        if key == "F":
            return cast(float, struct.unpack("<f", raw)[0])
        elif key == "L":
            return cast(int, struct.unpack("<i", raw)[0])
        else:
            return cast(int, struct.unpack("<I", raw)[0])
    else:
        words = await client.read_devices(device, 1, bit_unit=False)
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
    key = dtype.upper()
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
    key = dtype.upper()
    if key == "BIT":
        values = client.read_devices(device, 1, bit_unit=True)
        return bool(values[0])
    if key in ("D", "L", "F"):
        words = client.read_devices(device, 2, bit_unit=False)
        raw = struct.pack("<HH", words[0], words[1])
        if key == "F":
            return cast(float, struct.unpack("<f", raw)[0])
        elif key == "L":
            return cast(int, struct.unpack("<i", raw)[0])
        else:
            return cast(int, struct.unpack("<I", raw)[0])
    else:
        words = client.read_devices(device, 1, bit_unit=False)
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
    key = dtype.upper()
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
    plan = _compile_read_plan(addresses)
    return await _read_named_with_plan(client, plan)


def read_named_sync(
    client: SlmpClient,
    addresses: list[str],
) -> dict[str, int | float | bool]:
    """Synchronously read a mixed logical snapshot by address string."""
    plan = _compile_read_plan(addresses)
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
    for address, value in updates.items():
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            _validate_bit_in_word_target(address, parse_device(base))
            await write_bit_in_word(client, base, bit_idx or 0, bool(value))
        else:
            device = parse_device(base)
            await write_typed(client, base, _normalize_dtype_for_device(device, dtype or "U"), value)


def write_named_sync(
    client: SlmpClient,
    updates: dict[str, int | float | bool],
) -> None:
    """Synchronously write a mixed logical snapshot by address string."""
    for address, value in updates.items():
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            _validate_bit_in_word_target(address, parse_device(base))
            write_bit_in_word_sync(client, base, bit_idx or 0, bool(value))
        else:
            device = parse_device(base)
            write_typed_sync(client, base, _normalize_dtype_for_device(device, dtype or "U"), value)


# ---------------------------------------------------------------------------
# Address parser (shared)
# ---------------------------------------------------------------------------


def _parse_address(address: str) -> tuple[str, str, int | None]:
    """Parse extended address notation.

    Returns (base_device, dtype, bit_index).
    """
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


def _is_batchable_word_device(device: DeviceRef) -> bool:
    code = DEVICE_CODES.get(device.code)
    return code is not None and code.unit == DeviceUnit.WORD and device.code not in _UNBATCHED_DEVICE_CODES


def _normalize_dtype_for_device(device: DeviceRef, dtype: str) -> str:
    code = DEVICE_CODES.get(device.code)
    if code is not None and code.unit == DeviceUnit.BIT and dtype == "U":
        return "BIT"
    return dtype


def _validate_bit_in_word_target(address: str, device: DeviceRef) -> None:
    code = DEVICE_CODES.get(device.code)
    if code is None or code.unit != DeviceUnit.WORD:
        raise ValueError(
            f"Address '{address}' uses '.bit' notation, which is only valid for word devices. "
            "Address bit devices directly, for example 'M1000' instead of 'M1000.0'."
        )


def _compile_read_plan(addresses: list[str]) -> _ReadPlan:
    entries: list[_ReadPlanEntry] = []
    word_devices: list[DeviceRef] = []
    dword_devices: list[DeviceRef] = []
    seen_words: set[DeviceRef] = set()
    seen_dwords: set[DeviceRef] = set()

    for address in addresses:
        base, dtype, bit_index = _parse_address(address)
        device = parse_device(base)
        dtype = _normalize_dtype_for_device(device, dtype)
        batch_kind: str | None = None

        if dtype == "BIT_IN_WORD":
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

        entries.append(_ReadPlanEntry(address, device, dtype, bit_index, batch_kind))

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

    for entry in plan.entries:
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

    for entry in plan.entries:
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
    plan = _compile_read_plan(addresses)
    while True:
        yield await _read_named_with_plan(client, plan)
        await asyncio.sleep(interval)


def poll_sync(
    client: SlmpClient,
    addresses: list[str],
    interval: float,
) -> Iterator[dict[str, int | float | bool]]:
    """Synchronously yield mixed snapshots at a fixed interval."""
    plan = _compile_read_plan(addresses)
    while True:
        yield _read_named_with_plan_sync(client, plan)
        time.sleep(interval)


# ---------------------------------------------------------------------------
# Chunked reads  (async)
# ---------------------------------------------------------------------------


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
    from .core import DeviceRef, parse_device

    # Always use an even effective_max to keep DWord boundaries aligned.
    effective_max = (max_per_request // 2) * 2
    if effective_max <= 0:
        raise ValueError("max_per_request must be at least 2")

    if not allow_split:
        if count > effective_max:
            raise ValueError(
                f"count {count} exceeds max_per_request {effective_max};"
                " pass allow_split=True to split the read across multiple requests"
            )
        ref = parse_device(device) if isinstance(device, str) else device
        return list(await client.read_devices(ref, count, bit_unit=False))

    ref = parse_device(device) if isinstance(device, str) else device
    result: list[int] = []
    remaining = count
    offset = 0
    while remaining > 0:
        chunk = min(remaining, effective_max)
        chunk_ref = DeviceRef(ref.code, ref.number + offset)
        words = await client.read_devices(chunk_ref, chunk, bit_unit=False)
        result.extend(words)
        offset += chunk
        remaining -= chunk
    return result


async def read_dwords(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    count: int,
    max_dwords_per_request: int = 480,
    *,
    allow_split: bool = False,
) -> list[int]:
    """Read a contiguous DWord range as unsigned 32-bit integers."""
    words = await read_words(
        client,
        device,
        count * 2,
        max_per_request=max_dwords_per_request * 2,
        allow_split=allow_split,
    )
    result: list[int] = []
    for i in range(count):
        raw = struct.pack("<HH", words[i * 2], words[i * 2 + 1])
        result.append(struct.unpack("<I", raw)[0])
    return result


# ---------------------------------------------------------------------------
# Chunked reads  (sync)
# ---------------------------------------------------------------------------


def read_words_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
    max_per_request: int = 960,
    *,
    allow_split: bool = False,
) -> list[int]:
    """Synchronously read a contiguous word-device range."""
    from .core import DeviceRef, parse_device

    effective_max = (max_per_request // 2) * 2
    if effective_max <= 0:
        raise ValueError("max_per_request must be at least 2")

    if not allow_split:
        if count > effective_max:
            raise ValueError(
                f"count {count} exceeds max_per_request {effective_max};"
                " pass allow_split=True to split the read across multiple requests"
            )
        ref = parse_device(device) if isinstance(device, str) else device
        return list(client.read_devices(ref, count, bit_unit=False))

    ref = parse_device(device) if isinstance(device, str) else device
    result: list[int] = []
    remaining = count
    offset = 0
    while remaining > 0:
        chunk = min(remaining, effective_max)
        chunk_ref = DeviceRef(ref.code, ref.number + offset)
        words = client.read_devices(chunk_ref, chunk, bit_unit=False)
        result.extend(words)
        offset += chunk
        remaining -= chunk
    return result


def read_dwords_sync(
    client: SlmpClient,
    device: str | DeviceRef,
    count: int,
    max_dwords_per_request: int = 480,
    *,
    allow_split: bool = False,
) -> list[int]:
    """Synchronously read a contiguous DWord range."""
    words = read_words_sync(
        client,
        device,
        count * 2,
        max_per_request=max_dwords_per_request * 2,
        allow_split=allow_split,
    )
    result: list[int] = []
    for i in range(count):
        raw = struct.pack("<HH", words[i * 2], words[i * 2 + 1])
        result.append(struct.unpack("<I", raw)[0])
    return result


# ---------------------------------------------------------------------------
# Queued client
# ---------------------------------------------------------------------------


class QueuedAsyncSlmpClient:
    """Serialize all async calls on one shared SLMP connection.

    The wrapper exposes the same methods as :class:`AsyncSlmpClient`, but every
    coroutine call is executed under one lock. Use it when one connection is
    shared by polling, snapshot, and write tasks.
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
