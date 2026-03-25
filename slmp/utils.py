"""High-level utility helpers for the SLMP client."""

from __future__ import annotations

import asyncio
import struct
import time
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .async_client import AsyncSlmpClient
    from .client import SlmpClient
    from .core import DeviceRef


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


async def open_and_connect(
    host: str,
    port: int = 5000,
    timeout: float = 1.5,
) -> AsyncSlmpClient:
    """Connect to a PLC with automatic frame-type and PLC-series detection.

    Internally calls :meth:`~slmp.async_client.AsyncSlmpClient.resolve_profile`
    which tries four frame/series combinations in order:
    (4E, iQ-R) ↁE(3E, Q/L) ↁE(3E, iQ-R) ↁE(4E, Q/L).

    After a successful detection the client's :attr:`frame_type` and
    :attr:`plc_series` are set to the detected values and the connection is
    left open.

    Args:
        host: PLC IP address or hostname.
        port: SLMP port. Defaults to 5000 (GX Works3 / GX Works2 simulator default).
            Common port values:

            - ``5000``  EGX Works3 / GX Works2 built-in simulator (default here)
            - ``1025``  EiQ-R / iQ-F series built-in Ethernet SLMP port
            - ``5007``  EQ/L series built-in Ethernet SLMP port

            Check the PLC or simulator network settings when the default does not work.
        timeout: Per-candidate connection timeout in seconds.

    Raises:
        ConnectionError: If no candidate could reach the PLC.
    """
    from .async_client import AsyncSlmpClient

    client = AsyncSlmpClient(host, port, timeout=timeout)
    rec = await client.resolve_profile()
    if not rec.is_confident:
        raise ConnectionError(f"Could not detect PLC profile at {host}:{port}")
    return client


# ---------------------------------------------------------------------------
# Typed single-device read / write  (async)
# ---------------------------------------------------------------------------


async def read_typed(
    client: AsyncSlmpClient,
    device: str | DeviceRef,
    dtype: str,
) -> int | float:
    """Read one device value and convert it to the specified Python type.

    Args:
        client: Connected AsyncSlmpClient.
        device: Device address string or DeviceRef.
        dtype: Type code  E
            "U" unsigned 16-bit int,
            "S" signed 16-bit int,
            "D" unsigned 32-bit int,
            "L" signed 32-bit int,
            "F" float32.

    Returns:
        Converted value as int or float.
    """
    key = dtype.upper()
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
    """Write one device value using the specified type format.

    Args:
        client: Connected AsyncSlmpClient.
        device: Device address string or DeviceRef.
        dtype: Type code  Esame as :func:`read_typed`.
        value: Value to write.
    """
    key = dtype.upper()
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
    """Synchronous version of :func:`read_typed`.

    Args:
        client: Connected SlmpClient.
        device: Device address string or DeviceRef.
        dtype: Type code  E"U", "S", "D", "L", "F".

    Returns:
        Converted value as int or float.
    """
    key = dtype.upper()
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
    """Synchronous version of :func:`write_typed`.

    Args:
        client: Connected SlmpClient.
        device: Device address string or DeviceRef.
        dtype: Type code  E"U", "S", "D", "L", "F".
        value: Value to write.
    """
    key = dtype.upper()
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
    """Set or clear a single bit within a word device (read-modify-write).

    Args:
        client: Connected AsyncSlmpClient.
        device: Word device address.
        bit_index: Bit position within the word (0 E5).
        value: New bit state.
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
    """Synchronous version of :func:`write_bit_in_word`.

    Args:
        client: Connected SlmpClient.
        device: Word device address.
        bit_index: Bit position within the word (0 E5).
        value: New bit state.
    """
    if not 0 <= bit_index <= 15:
        raise ValueError(f"bit_index must be 0-15, got {bit_index}")
    words = client.read_devices(device, 1, bit_unit=False)
    current = int(words[0])
    if value:
        current |= 1 << bit_index
    else:
        current &= ~(1 << bit_index)
    client.write_devices(device, [current & 0xFFFF], bit_unit=False)


# ---------------------------------------------------------------------------
# Named-device read  (async + sync)
# ---------------------------------------------------------------------------


async def read_named(
    client: AsyncSlmpClient,
    addresses: list[str],
) -> dict[str, int | float | bool]:
    """Read multiple devices by address string and return results as a dict.

    Address format examples:

    - ``"D100"``  Eunsigned 16-bit int
    - ``"D100:F"``  Efloat32
    - ``"D100:S"``  Esigned 16-bit int
    - ``"D100:D"``  Eunsigned 32-bit int
    - ``"D100:L"``  Esigned 32-bit int
    - ``"D100.3"``  Ebit 3 within word (bool)

    Args:
        client: Connected AsyncSlmpClient.
        addresses: List of address strings.

    Returns:
        Dictionary mapping each address string to its value.
    """
    result: dict[str, int | float | bool] = {}
    for address in addresses:
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            words = await client.read_devices(base, 1, bit_unit=False)
            result[address] = bool((words[0] >> (bit_idx or 0)) & 1)
        else:
            result[address] = await read_typed(client, base, dtype or "U")
    return result


def read_named_sync(
    client: SlmpClient,
    addresses: list[str],
) -> dict[str, int | float | bool]:
    """Synchronous version of :func:`read_named`.

    Args:
        client: Connected SlmpClient.
        addresses: List of address strings (same format as :func:`read_named`).

    Returns:
        Dictionary mapping each address string to its value.
    """
    result: dict[str, int | float | bool] = {}
    for address in addresses:
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            words = client.read_devices(base, 1, bit_unit=False)
            result[address] = bool((words[0] >> (bit_idx or 0)) & 1)
        else:
            result[address] = read_typed_sync(client, base, dtype or "U")
    return result


# ---------------------------------------------------------------------------
# Named-device write  (async + sync)
# ---------------------------------------------------------------------------


async def write_named(
    client: AsyncSlmpClient,
    updates: dict[str, int | float | bool],
) -> None:
    """Write multiple devices by address string.

    Address format is the same as :func:`read_named`.  Values are written
    one device at a time in iteration order.

    Args:
        client: Connected AsyncSlmpClient.
        updates: Mapping of address string to value.

    Example::

        await write_named(client, {
            "D100": 42,
            "D101:F": 3.14,
            "D0.3": True,
        })
    """
    for address, value in updates.items():
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            await write_bit_in_word(client, base, bit_idx or 0, bool(value))
        else:
            await write_typed(client, base, dtype or "U", value)


def write_named_sync(
    client: SlmpClient,
    updates: dict[str, int | float | bool],
) -> None:
    """Synchronous version of :func:`write_named`.

    Args:
        client: Connected SlmpClient.
        updates: Mapping of address string to value.

    Example::

        write_named_sync(client, {
            "D100": 42,
            "D101:F": 3.14,
            "D0.3": True,
        })
    """
    for address, value in updates.items():
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            write_bit_in_word_sync(client, base, bit_idx or 0, bool(value))
        else:
            write_typed_sync(client, base, dtype or "U", value)


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


# ---------------------------------------------------------------------------
# Polling  (async + sync)
# ---------------------------------------------------------------------------


async def poll(
    client: AsyncSlmpClient,
    addresses: list[str],
    interval: float,
) -> AsyncIterator[dict[str, int | float | bool]]:
    """Yield a snapshot of all devices every *interval* seconds.

    Args:
        client: Connected AsyncSlmpClient.
        addresses: Address strings (same format as :func:`read_named`).
        interval: Poll interval in seconds.

    Usage::

        async for snapshot in poll(client, ["D100", "D200:F"], interval=1.0):
            print(snapshot)
    """
    while True:
        yield await read_named(client, addresses)
        await asyncio.sleep(interval)


def poll_sync(
    client: SlmpClient,
    addresses: list[str],
    interval: float,
) -> Iterator[dict[str, int | float | bool]]:
    """Synchronous version of :func:`poll`.

    Yields a snapshot every *interval* seconds.  Use ``break`` or
    ``KeyboardInterrupt`` to stop the loop.

    Args:
        client: Connected SlmpClient.
        addresses: Address strings (same format as :func:`read_named_sync`).
        interval: Poll interval in seconds.

    Usage::

        for snapshot in poll_sync(client, ["D100", "D200:F"], interval=1.0):
            print(snapshot)
    """
    while True:
        yield read_named_sync(client, addresses)
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
    """Read word devices in one or more SLMP requests.

    The SLMP protocol limit is 960 words per request.  Chunk boundaries are
    always aligned to 2-word (DWord) boundaries to prevent Float32 / DWord
    data tearing across requests.

    Args:
        client: Connected AsyncSlmpClient.
        device: Starting device address.
        count: Total number of words to read.
        max_per_request: Maximum words per SLMP request (default 960).
        allow_split: When ``False`` (default), the entire read must fit within
            a single request; a :exc:`ValueError` is raised if ``count``
            exceeds ``max_per_request``.  When ``True``, large reads are
            automatically split across multiple requests.

    Returns:
        Flat list of word values.

    Raises:
        ValueError: If ``allow_split=False`` and ``count > max_per_request``.
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
    """Read DWord (32-bit unsigned) values in one or more SLMP requests.

    DWord boundaries are always aligned to prevent data tearing.

    Args:
        client: Connected AsyncSlmpClient.
        device: Starting device address.
        count: Number of DWords to read.
        max_dwords_per_request: Maximum DWords per request (default 480 = 960 words / 2).
        allow_split: When ``False`` (default), raises :exc:`ValueError` if
            ``count`` exceeds ``max_dwords_per_request``.  When ``True``,
            large reads are split across multiple requests.

    Returns:
        List of uint32 values (as Python int).
    """
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
    """Synchronous version of :func:`read_words`.

    Args:
        client: Connected SlmpClient.
        device: Starting device address.
        count: Total number of words to read.
        max_per_request: Maximum words per SLMP request (default 960).
        allow_split: When ``False`` (default), raises :exc:`ValueError` if
            ``count`` exceeds ``max_per_request``.  When ``True``, large
            reads are automatically split across multiple requests.

    Returns:
        Flat list of word values.
    """
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
    """Synchronous version of :func:`read_dwords`.

    Args:
        client: Connected SlmpClient.
        device: Starting device address.
        count: Number of DWords to read.
        max_dwords_per_request: Maximum DWords per request (default 480).
        allow_split: When ``False`` (default), raises :exc:`ValueError` if
            ``count`` exceeds ``max_dwords_per_request``.  When ``True``,
            large reads are split across multiple requests.

    Returns:
        List of uint32 values (as Python int).
    """
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
    """Wraps :class:`AsyncSlmpClient` and serializes all async calls via a lock.

    Useful when multiple coroutines share one SLMP connection (e.g. a
    background poller and a foreground writer).

    Usage::

        inner = AsyncSlmpClient("192.168.250.100")
        client = QueuedAsyncSlmpClient(inner)
        async with client:
            value = await client.read_devices("D100", 1)
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
