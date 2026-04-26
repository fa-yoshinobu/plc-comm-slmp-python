"""SLMP binary client (asynchronous)."""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from .client import SlmpClient
from .constants import DIRECT_MEMORY_LINK_DIRECT, Command, FrameType, PLCSeries
from .core import (
    _MIXED_BLOCK_RETRY_END_CODES,
    BlockReadResult,
    CpuOperationState,
    DeviceBlockResult,
    DeviceRef,
    ExtensionSpec,
    LabelArrayReadPoint,
    LabelArrayReadResult,
    LabelArrayWritePoint,
    LabelRandomReadResult,
    LabelRandomWritePoint,
    LongTimerResult,
    MonitorResult,
    RandomReadResult,
    SlmpResponse,
    SlmpTarget,
    SlmpTraceFrame,
    TypeNameInfo,
    _check_block_request_limits,
    _check_points_u16,
    _check_random_bit_write_count,
    _check_random_read_like_counts,
    _check_temporarily_unsupported_device,
    _check_temporarily_unsupported_devices,
    _check_u16,
    _check_u32,
    _encode_label_name,
    _encode_remote_password_payload,
    _label_array_data_bytes,
    _normalize_items,
    _raise_response_error,
    _require_explicit_device_family_for_xy,
    _resolve_connection_profile,
    _validate_block_read_devices,
    _validate_block_write_devices,
    _validate_direct_dword_read_device,
    _validate_direct_read_device,
    _validate_direct_write_device,
    _validate_monitor_register_devices,
    _validate_random_read_devices,
    _validate_random_write_word_devices,
    _warn_boundary_behavior,
    _warn_practical_device_path,
    build_device_modification_flags,
    decode_cpu_operation_state,
    decode_device_dwords,
    decode_device_words,
    decode_response,
    encode_device_spec,
    encode_extended_device_spec,
    encode_request,
    pack_bit_values,
    parse_device,
    resolve_device_subcommand,
    resolve_extended_device_and_extension,
    unpack_bit_values,
)
from .errors import SlmpError

if TYPE_CHECKING:
    from .device_ranges import SlmpDeviceRangeCatalog, SlmpDeviceRangeFamily


class SLMPDatagramProtocol(asyncio.DatagramProtocol):
    """Internal protocol for async UDP communication."""

    def __init__(self, frame_type: FrameType) -> None:
        """Initialize the protocol with a frame type."""
        self.frame_type = frame_type
        self.transport: asyncio.DatagramTransport | None = None
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle connection made."""
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data: bytes, _addr: tuple[str | Any, int]) -> None:
        """Handle received datagram."""
        self.queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        """Handle received error."""
        pass


class AsyncSlmpClient:
    """Asynchronous SLMP client supporting 3E and 4E frames (binary) over TCP and UDP."""

    def __init__(
        self,
        host: str,
        port: int = 5000,
        *,
        transport: str = "tcp",
        timeout: float = 3.0,
        plc_family: object | None = None,
        plc_series: PLCSeries | str | None = None,
        frame_type: FrameType | str | None = None,
        default_target: SlmpTarget | None = None,
        monitoring_timer: int = 0x0010,
        raise_on_error: bool = True,
        trace_hook: Callable[[SlmpTraceFrame], Any] | None = None,
        device_family: object | None = None,
        _allow_manual_profile: bool = False,
    ) -> None:
        """Initialize the asynchronous SLMP client.

        The standard async client route requires ``plc_family`` and fixes the
        frame type, access profile, and address/range handling from that one
        explicit family.
        """
        self.host = host
        self.port = port
        self.transport_type = transport.lower()
        if self.transport_type not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.timeout = timeout
        if not _allow_manual_profile:
            if plc_family is None and all(value is None for value in (plc_series, frame_type, device_family)):
                raise ValueError(
                    "plc_family is required for the standard AsyncSlmpClient route "
                    "unless you explicitly opt into a low-level frame/profile path."
                )
            if plc_family is not None and any(
                value is not None for value in (plc_series, frame_type, device_family)
            ):
                raise ValueError(
                    "plc_family is the only supported PLC selector for the standard AsyncSlmpClient route."
                )
        (
            self.plc_family,
            self.plc_series,
            self.frame_type,
            self.device_family,
            self.device_range_family,
        ) = _resolve_connection_profile(
            plc_family=plc_family,
            plc_series=plc_series,
            frame_type=frame_type,
            device_family=device_family,
        )
        self.default_target = default_target or SlmpTarget()
        self.monitoring_timer = monitoring_timer
        self.raise_on_error = raise_on_error
        self.trace_hook = trace_hook

        self._serial = 0
        self._lock = asyncio.Lock()

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._udp_transport: asyncio.DatagramTransport | None = None
        self._udp_protocol: SLMPDatagramProtocol | None = None

    def _parse_device(self, device: str | DeviceRef) -> DeviceRef:
        ref = parse_device(device, family=self.device_family)
        return _require_explicit_device_family_for_xy(device, self.device_family, ref)

    def _resolve_extended_device_and_extension(
        self,
        device: str | DeviceRef,
        extension: ExtensionSpec,
    ) -> tuple[DeviceRef, ExtensionSpec]:
        ref, effective_extension = resolve_extended_device_and_extension(device, extension, family=self.device_family)
        return _require_explicit_device_family_for_xy(device, self.device_family, ref), effective_extension

    async def connect(self) -> None:
        """Open the connection to the PLC."""
        async with self._lock:
            if self.transport_type == "tcp":
                if self._writer is not None:
                    return
                fut = asyncio.open_connection(self.host, self.port)
                try:
                    self._reader, self._writer = await asyncio.wait_for(fut, timeout=self.timeout)
                except asyncio.TimeoutError as err:
                    raise ConnectionError(f"TCP connection timed out to {self.host}:{self.port}") from err
            else:
                if self._udp_transport is not None:
                    return
                loop = asyncio.get_running_loop()
                try:
                    self._udp_transport, self._udp_protocol = await asyncio.wait_for(
                        loop.create_datagram_endpoint(
                            lambda: SLMPDatagramProtocol(self.frame_type), remote_addr=(self.host, self.port)
                        ),
                        timeout=self.timeout,
                    )
                except asyncio.TimeoutError as err:
                    raise ConnectionError(f"UDP endpoint creation timed out for {self.host}:{self.port}") from err

    async def close(self) -> None:
        """Close the connection to the PLC."""
        async with self._lock:
            if self.transport_type == "tcp":
                if self._writer is None:
                    return
                self._writer.close()
                try:
                    await self._writer.wait_closed()
                except Exception:
                    pass
                self._reader = None
                self._writer = None
            else:
                if self._udp_transport is None:
                    return
                self._udp_transport.close()
                self._udp_transport = None
                self._udp_protocol = None

    async def __aenter__(self) -> AsyncSlmpClient:
        """Enter the async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Exit the async context manager."""
        await self.close()

    async def request(
        self,
        command: int | Command,
        subcommand: int = 0x0000,
        data: bytes = b"",
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
    ) -> SlmpResponse:
        """Send an SLMP request and receive a response."""
        serial_no = self._next_serial() if serial is None else serial
        target_info = target or self.default_target
        monitor = self.monitoring_timer if monitoring_timer is None else monitoring_timer
        cmd = int(command)

        frame = encode_request(
            frame_type=self.frame_type,
            serial=serial_no,
            target=target_info,
            monitoring_timer=monitor,
            command=cmd,
            subcommand=subcommand,
            data=data,
        )
        raw = await self._send_and_receive(frame)
        resp = decode_response(raw, frame_type=self.frame_type)

        if self.trace_hook:
            await self._emit_trace(
                SlmpTraceFrame(
                    serial=serial_no,
                    command=cmd,
                    subcommand=subcommand,
                    request_data=data,
                    request_frame=frame,
                    response_frame=raw,
                    response_end_code=resp.end_code,
                    target=target_info,
                    monitoring_timer=monitor,
                )
            )

        do_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        if do_raise and resp.end_code != 0:
            raise SlmpError(
                f"SLMP error end_code=0x{resp.end_code:04X} command=0x{cmd:04X} subcommand=0x{subcommand:04X}",
                end_code=resp.end_code,
                data=resp.data,
            )
        return resp

    async def raw_command(
        self,
        command: int | Command,
        *,
        subcommand: int = 0x0000,
        payload: bytes = b"",
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
    ) -> SlmpResponse:
        """Send a raw SLMP command."""
        return await self.request(
            command=command,
            subcommand=subcommand,
            data=payload,
            serial=serial,
            target=target,
            monitoring_timer=monitoring_timer,
            raise_on_error=raise_on_error,
        )

    @staticmethod
    def make_extension_spec(
        *,
        extension_specification: int = 0x0000,
        extension_specification_modification: int = 0x00,
        device_modification_index: int = 0x00,
        use_indirect_specification: bool = False,
        register_mode: str = "none",
        direct_memory_specification: int = 0x00,
        series: PLCSeries | str = PLCSeries.QL,
    ) -> ExtensionSpec:
        """Create an extension specification for Extended Device commands."""
        s = PLCSeries(series)
        flags = build_device_modification_flags(
            series=s,
            use_indirect_specification=use_indirect_specification,
            register_mode=register_mode,
        )
        return ExtensionSpec(
            extension_specification=extension_specification,
            extension_specification_modification=extension_specification_modification,
            device_modification_index=device_modification_index,
            device_modification_flags=flags,
            direct_memory_specification=direct_memory_specification,
        )

    # --------------------
    # Device commands (typed)
    # --------------------

    async def read_devices(
        self,
        device: str | DeviceRef,
        points: int,
        *,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> list[int] | list[bool]:
        """Read device values from the PLC."""
        _check_points_u16(points, "points")
        s = PLCSeries(series) if series is not None else self.plc_series
        ref = self._parse_device(device)
        _validate_direct_read_device(ref, points=points, bit_unit=bit_unit)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=s, access_kind="direct")
        _warn_boundary_behavior(ref, series=s, points=points, write=False, bit_unit=bit_unit, access_kind="direct")
        sub = resolve_device_subcommand(bit_unit=bit_unit, series=s, extension=False)
        payload = encode_device_spec(ref, series=s) + points.to_bytes(2, "little")
        resp = await self.request(Command.DEVICE_READ, subcommand=sub, data=payload)
        if bit_unit:
            return unpack_bit_values(resp.data, points)
        words = decode_device_words(resp.data)
        if len(words) != points:
            raise SlmpError(f"word count mismatch: expected={points}, actual={len(words)}")
        return words

    async def write_devices(
        self,
        device: str | DeviceRef,
        values: Sequence[int | bool],
        *,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write device values to the PLC."""
        if not values:
            raise ValueError("values must not be empty")
        s = PLCSeries(series) if series is not None else self.plc_series
        ref = self._parse_device(device)
        _validate_direct_write_device(ref, bit_unit=bit_unit)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=s, access_kind="direct")
        _warn_boundary_behavior(ref, series=s, points=len(values), write=True, bit_unit=bit_unit, access_kind="direct")
        sub = resolve_device_subcommand(bit_unit=bit_unit, series=s, extension=False)
        payload = bytearray()
        payload += encode_device_spec(ref, series=s)
        payload += len(values).to_bytes(2, "little")
        if bit_unit:
            payload += pack_bit_values(values)
        else:
            for value in values:
                payload += int(value).to_bytes(2, "little", signed=False)
        await self.request(Command.DEVICE_WRITE, subcommand=sub, data=bytes(payload))

    async def read_dword(
        self,
        device: str | DeviceRef,
        *,
        series: PLCSeries | str | None = None,
    ) -> int:
        """Read one 32-bit value from two consecutive word devices."""
        return (await self.read_dwords(device, 1, series=series))[0]

    async def write_dword(
        self,
        device: str | DeviceRef,
        value: int,
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write one 32-bit value to two consecutive word devices."""
        await self.write_dwords(device, [value], series=series)

    async def read_dwords(
        self,
        device: str | DeviceRef,
        count: int,
        *,
        series: PLCSeries | str | None = None,
    ) -> list[int]:
        """Read one or more 32-bit values from two consecutive word devices."""
        if count < 1:
            raise ValueError("count must be >= 1")
        ref = self._parse_device(device)
        _validate_direct_dword_read_device(ref)
        words = [int(value) for value in await self.read_devices(ref, count * 2, series=series)]
        values: list[int] = []
        for offset in range(0, len(words), 2):
            values.append(words[offset] | (words[offset + 1] << 16))
        return values

    async def write_dwords(
        self,
        device: str | DeviceRef,
        values: Sequence[int],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write one or more 32-bit values to two consecutive word devices."""
        if not values:
            raise ValueError("values must not be empty")
        words: list[int] = []
        for value in values:
            bits = int(value) & 0xFFFFFFFF
            words.append(bits & 0xFFFF)
            words.append((bits >> 16) & 0xFFFF)
        await self.write_devices(device, words, series=series)

    async def read_float32(
        self,
        device: str | DeviceRef,
        *,
        series: PLCSeries | str | None = None,
    ) -> float:
        """Read one IEEE-754 float32 from two consecutive word devices."""
        return (await self.read_float32s(device, 1, series=series))[0]

    async def write_float32(
        self,
        device: str | DeviceRef,
        value: float,
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write one IEEE-754 float32 to two consecutive word devices."""
        await self.write_float32s(device, [value], series=series)

    async def read_float32s(
        self,
        device: str | DeviceRef,
        count: int,
        *,
        series: PLCSeries | str | None = None,
    ) -> list[float]:
        """Read one or more IEEE-754 float32 values from two consecutive word devices."""
        values: list[float] = []
        for bits in await self.read_dwords(device, count, series=series):
            values.append(struct.unpack("<f", struct.pack("<I", bits))[0])
        return values

    async def write_float32s(
        self,
        device: str | DeviceRef,
        values: Sequence[float],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write one or more IEEE-754 float32 values to two consecutive word devices."""
        dwords: list[int] = []
        for value in values:
            dwords.append(struct.unpack("<I", struct.pack("<f", float(value)))[0])
        await self.write_dwords(device, dwords, series=series)

    async def read_devices_ext(
        self,
        device: str | DeviceRef,
        points: int,
        *,
        extension: ExtensionSpec,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> list[int] | list[bool]:
        """Read device values using Extended Device extension."""
        _check_points_u16(points, "points")
        s = PLCSeries(series) if series is not None else self.plc_series
        ref, effective_extension = self._resolve_extended_device_and_extension(device, extension)
        _validate_direct_read_device(ref, points=points, bit_unit=bit_unit)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _warn_practical_device_path(ref, series=s, access_kind="extended_device")
        if effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
            s = PLCSeries.QL
        sub = resolve_device_subcommand(bit_unit=bit_unit, series=s, extension=True)
        payload = bytearray()
        payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        payload += points.to_bytes(2, "little")
        resp = await self.request(Command.DEVICE_READ, subcommand=sub, data=bytes(payload))
        if bit_unit:
            return unpack_bit_values(resp.data, points)
        words = decode_device_words(resp.data)
        if len(words) != points:
            raise SlmpError(f"word count mismatch: expected={points}, actual={len(words)}")
        return words

    async def write_devices_ext(
        self,
        device: str | DeviceRef,
        values: Sequence[int | bool],
        *,
        extension: ExtensionSpec,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write device values using Extended Device extension."""
        if not values:
            raise ValueError("values must not be empty")
        s = PLCSeries(series) if series is not None else self.plc_series
        ref, effective_extension = self._resolve_extended_device_and_extension(device, extension)
        _validate_direct_write_device(ref, bit_unit=bit_unit)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _warn_practical_device_path(ref, series=s, access_kind="extended_device")
        if effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
            s = PLCSeries.QL
        sub = resolve_device_subcommand(bit_unit=bit_unit, series=s, extension=True)
        payload = bytearray()
        payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        payload += len(values).to_bytes(2, "little")
        if bit_unit:
            payload += pack_bit_values(values)
        else:
            for value in values:
                payload += int(value).to_bytes(2, "little", signed=False)
        await self.request(Command.DEVICE_WRITE, subcommand=sub, data=bytes(payload))

    async def read_random(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
        series: PLCSeries | str | None = None,
    ) -> RandomReadResult:
        """Read multiple word and double-word devices in a single request."""
        if not word_devices and not dword_devices:
            raise ValueError("word_devices and dword_devices must not both be empty")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_read_like_counts(len(word_devices), len(dword_devices), series=s, name="read_random")
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=False)
        words = [self._parse_device(d) for d in word_devices]
        dwords = [self._parse_device(d) for d in dword_devices]
        _validate_random_read_devices(words, dwords)
        _check_temporarily_unsupported_devices(words)
        _check_temporarily_unsupported_devices(dwords)
        payload = bytearray([len(words), len(dwords)])
        for dev in words:
            payload += encode_device_spec(dev, series=s)
        for dev in dwords:
            payload += encode_device_spec(dev, series=s)
        resp = await self.request(Command.DEVICE_READ_RANDOM, subcommand=sub, data=bytes(payload))
        expected = len(words) * 2 + len(dwords) * 4
        if len(resp.data) != expected:
            raise SlmpError(f"random read size mismatch: expected={expected}, actual={len(resp.data)}")
        offset = 0
        word_values = decode_device_words(resp.data[offset : offset + (len(words) * 2)])
        offset += len(words) * 2
        dword_values = decode_device_dwords(resp.data[offset:])
        return RandomReadResult(
            word={str(dev): value for dev, value in zip(words, word_values, strict=True)},
            dword={str(dev): value for dev, value in zip(dwords, dword_values, strict=True)},
        )

    async def read_random_ext(
        self,
        *,
        word_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        dword_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> RandomReadResult:
        """Read multiple word and double-word devices using Extended Device extension."""
        if not word_devices and not dword_devices:
            raise ValueError("word_devices and dword_devices must not both be empty")
        if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
            raise ValueError("word_devices and dword_devices must be <= 255 each")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_read_like_counts(len(word_devices), len(dword_devices), series=s, name="read_random_ext")
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=True)
        payload = bytearray([len(word_devices), len(dword_devices)])
        words: list[tuple[DeviceRef, ExtensionSpec]] = []
        dwords: list[tuple[DeviceRef, ExtensionSpec]] = []
        for dev, ext in word_devices:
            ref, effective_extension = self._resolve_extended_device_and_extension(dev, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            words.append((ref, effective_extension))
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        for dev, ext in dword_devices:
            ref, effective_extension = self._resolve_extended_device_and_extension(dev, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            dwords.append((ref, effective_extension))
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        _validate_random_read_devices([ref for ref, _ in words], [ref for ref, _ in dwords])

        resp = await self.request(Command.DEVICE_READ_RANDOM, subcommand=sub, data=bytes(payload))
        expected = len(words) * 2 + len(dwords) * 4
        if len(resp.data) != expected:
            raise SlmpError(f"random read response size mismatch: expected={expected}, actual={len(resp.data)}")

        offset = 0
        word_values = decode_device_words(resp.data[offset : offset + (len(words) * 2)])
        offset += len(words) * 2
        dword_values = decode_device_dwords(resp.data[offset:])
        return RandomReadResult(
            word={str(dev): value for (dev, _), value in zip(words, word_values, strict=True)},
            dword={str(dev): value for (dev, _), value in zip(dwords, dword_values, strict=True)},
        )

    async def write_random_words(
        self,
        *,
        word_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]] = (),
        dword_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple word and double-word devices in a single request."""
        word_items = _normalize_items(word_values)
        dword_items = _normalize_items(dword_values)
        if not word_items and not dword_items:
            raise ValueError("word_values and dword_values must not both be empty")
        s = PLCSeries(series) if series is not None else self.plc_series
        _validate_random_write_word_devices([device for device, _ in word_items])
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=False)
        payload = bytearray([len(word_items), len(dword_items)])
        for dev, val in word_items:
            _check_temporarily_unsupported_device(dev)
            payload += encode_device_spec(dev, series=s) + int(val).to_bytes(2, "little")
        for dev, val in dword_items:
            _check_temporarily_unsupported_device(dev)
            payload += encode_device_spec(dev, series=s) + int(val).to_bytes(4, "little")
        await self.request(Command.DEVICE_WRITE_RANDOM, subcommand=sub, data=bytes(payload))

    async def write_random_words_ext(
        self,
        *,
        word_values: Sequence[tuple[str | DeviceRef, int, ExtensionSpec]] = (),
        dword_values: Sequence[tuple[str | DeviceRef, int, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple word and double-word devices using Extended Device extension."""
        if not word_values and not dword_values:
            raise ValueError("word_values and dword_values must not both be empty")
        if len(word_values) > 0xFF or len(dword_values) > 0xFF:
            raise ValueError("word_values and dword_values must be <= 255 each")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_read_like_counts(len(word_values), len(dword_values), series=s, name="write_random_words_ext")
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=True)
        payload = bytearray([len(word_values), len(dword_values)])
        word_refs: list[DeviceRef] = []
        for dev, val, ext in word_values:
            ref, effective_extension = self._resolve_extended_device_and_extension(dev, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            word_refs.append(ref)
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
            payload += int(val).to_bytes(2, "little")
        for dev, val, ext in dword_values:
            ref, effective_extension = self._resolve_extended_device_and_extension(dev, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
            payload += int(val).to_bytes(4, "little")
        _validate_random_write_word_devices(word_refs)
        await self.request(Command.DEVICE_WRITE_RANDOM, subcommand=sub, data=bytes(payload))

    async def write_random_bits(
        self,
        bit_values: Mapping[str | DeviceRef, bool | int] | Sequence[tuple[str | DeviceRef, bool | int]],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple bit devices in a single request."""
        items = _normalize_items(bit_values)
        if not items:
            raise ValueError("bit_values must not be empty")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_bit_write_count(len(items), series=s, name="write_random_bits")
        sub = resolve_device_subcommand(bit_unit=True, series=s, extension=False)
        payload = bytearray([len(items)])
        for device, state in items:
            _check_temporarily_unsupported_device(device)
            payload += encode_device_spec(device, series=s)
            val = b"\x01\x00" if s == PLCSeries.IQR else b"\x01"
            payload += val if bool(state) else (b"\x00\x00" if s == PLCSeries.IQR else b"\x00")
        await self.request(Command.DEVICE_WRITE_RANDOM, subcommand=sub, data=bytes(payload))

    async def write_random_bits_ext(
        self,
        bit_values: Sequence[tuple[str | DeviceRef, bool | int, ExtensionSpec]],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple bit devices using Extended Device extension."""
        if not bit_values:
            raise ValueError("bit_values must not be empty")
        if len(bit_values) > 0xFF:
            raise ValueError("bit_values must be <= 255")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_bit_write_count(len(bit_values), series=s, name="write_random_bits_ext")
        sub = resolve_device_subcommand(bit_unit=True, series=s, extension=True)
        payload = bytearray([len(bit_values)])
        for device, state, ext in bit_values:
            ref, effective_extension = self._resolve_extended_device_and_extension(device, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
            if s == PLCSeries.IQR:
                payload += b"\x01\x00" if bool(state) else b"\x00\x00"
            else:
                payload += b"\x01" if bool(state) else b"\x00"
        await self.request(Command.DEVICE_WRITE_RANDOM, subcommand=sub, data=bytes(payload))

    async def register_monitor_devices(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Register devices for monitoring."""
        if not word_devices and not dword_devices:
            raise ValueError("word_devices and dword_devices must not both be empty")
        if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
            raise ValueError("word_devices and dword_devices must be <= 255 each")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_read_like_counts(len(word_devices), len(dword_devices), series=s, name="register_monitor_devices")
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=False)
        payload = bytearray([len(word_devices), len(dword_devices)])
        word_refs: list[DeviceRef] = []
        dword_refs: list[DeviceRef] = []
        for dev in word_devices:
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            payload += encode_device_spec(ref, series=s)
            word_refs.append(ref)
        for dev in dword_devices:
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            payload += encode_device_spec(ref, series=s)
            dword_refs.append(ref)
        _validate_monitor_register_devices(word_refs, dword_refs)
        await self.request(Command.DEVICE_ENTRY_MONITOR, subcommand=sub, data=bytes(payload))

    async def register_monitor_devices_ext(
        self,
        *,
        word_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        dword_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Register devices for monitoring using Extended Device extension."""
        if not word_devices and not dword_devices:
            raise ValueError("word_devices and dword_devices must not both be empty")
        if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
            raise ValueError("word_devices and dword_devices must be <= 255 each")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_read_like_counts(
            len(word_devices),
            len(dword_devices),
            series=s,
            name="register_monitor_devices_ext",
        )
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=True)
        payload = bytearray([len(word_devices), len(dword_devices)])
        word_refs: list[DeviceRef] = []
        dword_refs: list[DeviceRef] = []
        for dev, ext in word_devices:
            ref, effective_extension = self._resolve_extended_device_and_extension(dev, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            word_refs.append(ref)
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        for dev, ext in dword_devices:
            ref, effective_extension = self._resolve_extended_device_and_extension(dev, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            dword_refs.append(ref)
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        _validate_monitor_register_devices(word_refs, dword_refs)
        await self.request(Command.DEVICE_ENTRY_MONITOR, subcommand=sub, data=bytes(payload))

    async def run_monitor_cycle(self, *, word_points: int, dword_points: int) -> MonitorResult:
        """Execute one cycle of monitoring and return the results."""
        if word_points < 0 or dword_points < 0:
            raise ValueError("word_points and dword_points must be >= 0")
        resp = await self.request(Command.DEVICE_EXECUTE_MONITOR, subcommand=0x0000, data=b"")
        expected = word_points * 2 + dword_points * 4
        if len(resp.data) != expected:
            raise SlmpError(f"monitor response size mismatch: expected={expected}, actual={len(resp.data)}")
        offset = 0
        words = decode_device_words(resp.data[offset : offset + word_points * 2])
        offset += word_points * 2
        dwords = decode_device_dwords(resp.data[offset:])
        return MonitorResult(word=words, dword=dwords)

    async def read_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, int]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, int]] = (),
        series: PLCSeries | str | None = None,
        split_mixed_blocks: bool = False,
    ) -> BlockReadResult:
        """Read multiple blocks of devices."""
        if not word_blocks and not bit_blocks:
            raise ValueError("word_blocks and bit_blocks must not both be empty")
        if split_mixed_blocks and word_blocks and bit_blocks:
            w = await self.read_block(word_blocks=word_blocks, bit_blocks=(), series=series)
            b = await self.read_block(word_blocks=(), bit_blocks=bit_blocks, series=series)
            return BlockReadResult(word_blocks=w.word_blocks, bit_blocks=b.bit_blocks)
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_block_request_limits(word_blocks, bit_blocks, series=s, name="read_block")
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=False)
        payload = bytearray([len(word_blocks), len(bit_blocks)])
        norm_word = []
        for dev, pts in word_blocks:
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            norm_word.append((ref, pts))
            payload += encode_device_spec(ref, series=s) + pts.to_bytes(2, "little")
        norm_bit = []
        for dev, pts in bit_blocks:
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            norm_bit.append((ref, pts))
            payload += encode_device_spec(ref, series=s) + pts.to_bytes(2, "little")
        _validate_block_read_devices(norm_word, norm_bit)
        resp = await self.request(Command.DEVICE_READ_BLOCK, subcommand=sub, data=bytes(payload))
        offset = 0
        word_res = []
        for ref, pts in norm_word:
            words = decode_device_words(resp.data[offset : offset + pts * 2])
            word_res.append(DeviceBlockResult(device=str(ref), values=words))
            offset += pts * 2
        bit_res = []
        for ref, pts in norm_bit:
            words = decode_device_words(resp.data[offset : offset + pts * 2])
            bit_res.append(DeviceBlockResult(device=str(ref), values=words))
            offset += pts * 2
        return BlockReadResult(word_blocks=word_res, bit_blocks=bit_res)

    async def write_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
        series: PLCSeries | str | None = None,
        split_mixed_blocks: bool = False,
        retry_mixed_on_error: bool = False,
    ) -> None:
        """Write multiple blocks of devices."""
        if not word_blocks and not bit_blocks:
            raise ValueError("word_blocks and bit_blocks must not both be empty")
        if split_mixed_blocks and word_blocks and bit_blocks:
            await self.write_block(word_blocks=word_blocks, bit_blocks=(), series=series)
            await self.write_block(word_blocks=(), bit_blocks=bit_blocks, series=series)
            return
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_block_request_limits(word_blocks, bit_blocks, series=s, name="write_block")
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=False)
        payload = bytearray([len(word_blocks), len(bit_blocks)])
        word_refs = []
        for dev, vals in word_blocks:
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            payload += encode_device_spec(ref, series=s) + len(vals).to_bytes(2, "little")
            word_refs.append(ref)
        bit_refs = []
        for dev, vals in bit_blocks:
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            payload += encode_device_spec(ref, series=s) + len(vals).to_bytes(2, "little")
            bit_refs.append(ref)
        _validate_block_write_devices(word_refs, bit_refs)
        for _, vals in word_blocks:
            for v in vals:
                payload += int(v).to_bytes(2, "little")
        for _, vals in bit_blocks:
            for v in vals:
                payload += int(v).to_bytes(2, "little")
        resp = await self.request(Command.DEVICE_WRITE_BLOCK, subcommand=sub, data=bytes(payload), raise_on_error=False)
        if resp.end_code == 0:
            return
        if retry_mixed_on_error and word_blocks and bit_blocks and resp.end_code in _MIXED_BLOCK_RETRY_END_CODES:
            await self.write_block(word_blocks=word_blocks, bit_blocks=(), series=series)
            await self.write_block(word_blocks=(), bit_blocks=bit_blocks, series=series)
            return
        if self.raise_on_error:
            _raise_response_error(resp, command=Command.DEVICE_WRITE_BLOCK, subcommand=sub)

    # --------------------
    # Remote / Administrative
    # --------------------

    async def read_type_name(self) -> TypeNameInfo:
        """Read the PLC type name and model code."""
        resp = await self.request(Command.READ_TYPE_NAME, 0x0000, b"")
        data = resp.data
        model = ""
        if len(data) >= 16:
            model = data[:16].split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        mcode = int.from_bytes(data[16:18], "little") if len(data) >= 18 else None
        return TypeNameInfo(raw=data, model=model, model_code=mcode)

    async def read_device_range_catalog_for_family(
        self,
        family: SlmpDeviceRangeFamily | str,
    ) -> SlmpDeviceRangeCatalog:
        """Read the configured device-range catalog for one canonical explicit PLC family."""
        from .device_ranges import read_device_range_catalog_for_family

        return await read_device_range_catalog_for_family(self, family)

    async def read_device_range_catalog(self) -> SlmpDeviceRangeCatalog:
        """Read the configured device-range catalog for this client's explicit PLC family."""
        if self.device_range_family is None:
            raise ValueError("read_device_range_catalog() requires explicit plc_family on the client.")
        return await self.read_device_range_catalog_for_family(self.device_range_family)

    async def read_cpu_operation_state(self) -> CpuOperationState:
        """Read SD203 and decode the CPU operation state from the lower 4 bits."""
        return decode_cpu_operation_state((await self.read_devices("SD203", 1, bit_unit=False))[0])

    async def remote_run(self, *, force: bool = False, clear_mode: int = 2) -> None:
        """Remote run the PLC."""
        if clear_mode not in {0, 1, 2}:
            raise ValueError(f"clear_mode must be one of 0,1,2: {clear_mode}")
        mode = 0x0003 if force else 0x0001
        payload = mode.to_bytes(2, "little") + clear_mode.to_bytes(2, "little")
        await self.request(Command.REMOTE_RUN, 0x0000, payload)

    async def remote_stop(self) -> None:
        """Remote stop the PLC."""
        await self.request(Command.REMOTE_STOP, 0x0000, b"\x01\x00")

    async def remote_pause(self, *, force: bool = False) -> None:
        """Remote pause the PLC."""
        mode = 0x0003 if force else 0x0001
        await self.request(Command.REMOTE_PAUSE, 0x0000, mode.to_bytes(2, "little"))

    async def remote_latch_clear(self) -> None:
        """Remote latch clear the PLC."""
        await self.request(Command.REMOTE_LATCH_CLEAR, 0x0000, b"\x01\x00")

    async def remote_reset(self, *, subcommand: int = 0x0000, expect_response: bool | None = None) -> None:
        """Remote reset the PLC."""
        if subcommand not in {0x0000, 0x0001}:
            raise ValueError(f"remote reset subcommand must be 0x0000 or 0x0001: 0x{subcommand:04X}")
        should_wait = (subcommand != 0x0000) if expect_response is None else expect_response
        if should_wait:
            await self.request(Command.REMOTE_RESET, subcommand, b"")
            return
        await self._send_no_response(Command.REMOTE_RESET, subcommand, b"")

    async def remote_password_lock(self, password: str, *, series: PLCSeries | str | None = None) -> None:
        """Remote password lock the PLC."""
        s = PLCSeries(series) if series is not None else self.plc_series
        payload = _encode_remote_password_payload(password, series=s)
        await self.request(Command.REMOTE_PASSWORD_LOCK, 0x0000, payload)

    async def remote_password_unlock(self, password: str, *, series: PLCSeries | str | None = None) -> None:
        """Remote password unlock the PLC."""
        s = PLCSeries(series) if series is not None else self.plc_series
        payload = _encode_remote_password_payload(password, series=s)
        await self.request(Command.REMOTE_PASSWORD_UNLOCK, 0x0000, payload)

    async def self_test_loopback(self, data: bytes | str) -> bytes:
        """Execute a self-test loopback."""
        loopback = data.encode("ascii") if isinstance(data, str) else bytes(data)
        payload = len(loopback).to_bytes(2, "little") + loopback
        resp = await self.request(Command.SELF_TEST, 0x0000, payload)
        return resp.data[2:]

    # --------------------
    # Label commands
    # --------------------

    async def read_array_labels(
        self, points: Sequence[LabelArrayReadPoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> list[LabelArrayReadResult]:
        """Read array labels from the PLC."""
        payload = bytearray()
        payload += len(points).to_bytes(2, "little") + len(abbreviation_labels).to_bytes(2, "little")
        for name in abbreviation_labels:
            payload += _encode_label_name(name)
        for pt in points:
            payload += (
                _encode_label_name(pt.label)
                + pt.unit_specification.to_bytes(1, "little")
                + b"\x00"
                + pt.array_data_length.to_bytes(2, "little")
            )
        resp = await self.request(Command.LABEL_ARRAY_READ, 0x0000, bytes(payload))
        data = resp.data
        count = int.from_bytes(data[:2], "little")
        offset = 2
        res = []
        for _ in range(count):
            dt_id, u_spec = data[offset], data[offset + 1]
            a_len = int.from_bytes(data[offset + 2 : offset + 4], "little")
            offset += 4
            d_size = _label_array_data_bytes(u_spec, a_len)
            res.append(
                LabelArrayReadResult(
                    data_type_id=dt_id,
                    unit_specification=u_spec,
                    array_data_length=a_len,
                    data=data[offset : offset + d_size],
                )
            )
            offset += d_size
        return res

    async def write_array_labels(
        self, points: Sequence[LabelArrayWritePoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> None:
        """Write array labels to the PLC."""
        payload = bytearray()
        payload += len(points).to_bytes(2, "little") + len(abbreviation_labels).to_bytes(2, "little")
        for name in abbreviation_labels:
            payload += _encode_label_name(name)
        for point in points:
            payload += (
                _encode_label_name(point.label)
                + point.unit_specification.to_bytes(1, "little")
                + b"\x00"
                + point.array_data_length.to_bytes(2, "little")
                + bytes(point.data)
            )
        await self.request(Command.LABEL_ARRAY_WRITE, 0x0000, bytes(payload))

    async def read_random_labels(
        self, labels: Sequence[str], *, abbreviation_labels: Sequence[str] = ()
    ) -> list[LabelRandomReadResult]:
        """Read random labels from the PLC."""
        payload = bytearray()
        payload += len(labels).to_bytes(2, "little") + len(abbreviation_labels).to_bytes(2, "little")
        for name in abbreviation_labels:
            payload += _encode_label_name(name)
        for label in labels:
            payload += _encode_label_name(label)
        resp = await self.request(Command.LABEL_READ_RANDOM, 0x0000, bytes(payload))
        data = resp.data
        count = int.from_bytes(data[:2], "little")
        offset = 2
        res = []
        for _ in range(count):
            dt_id, spare = data[offset], data[offset + 1]
            r_len = int.from_bytes(data[offset + 2 : offset + 4], "little")
            offset += 4
            res.append(
                LabelRandomReadResult(
                    data_type_id=dt_id, spare=spare, read_data_length=r_len, data=data[offset : offset + r_len]
                )
            )
            offset += r_len
        return res

    async def write_random_labels(
        self, points: Sequence[LabelRandomWritePoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> None:
        """Write random labels to the PLC."""
        payload = bytearray()
        payload += len(points).to_bytes(2, "little") + len(abbreviation_labels).to_bytes(2, "little")
        for name in abbreviation_labels:
            payload += _encode_label_name(name)
        for point in points:
            payload += _encode_label_name(point.label)
            payload += len(point.data).to_bytes(2, "little")
            payload += bytes(point.data)
        await self.request(Command.LABEL_WRITE_RANDOM, 0x0000, bytes(payload))

    # --------------------
    # Memory
    # --------------------

    async def memory_read_words(self, head_address: int, word_length: int) -> list[int]:
        """Read memory words from the PLC."""
        _check_u32(head_address, "head_address")
        payload = head_address.to_bytes(4, "little") + word_length.to_bytes(2, "little")
        resp = await self.request(Command.MEMORY_READ, 0x0000, payload)
        return decode_device_words(resp.data)

    async def memory_write_words(self, head_address: int, values: Sequence[int]) -> None:
        """Write memory words to the PLC."""
        _check_u32(head_address, "head_address")
        payload = head_address.to_bytes(4, "little") + len(values).to_bytes(2, "little")
        for v in values:
            payload += int(v).to_bytes(2, "little")
        await self.request(Command.MEMORY_WRITE, 0x0000, bytes(payload))

    async def extend_unit_read_words(self, head_address: int, word_length: int, module_no: int) -> list[int]:
        """Read words from an extend unit."""
        payload = (
            head_address.to_bytes(4, "little")
            + (word_length * 2).to_bytes(2, "little")
            + module_no.to_bytes(2, "little")
        )
        resp = await self.request(Command.EXTEND_UNIT_READ, 0x0000, payload)
        return decode_device_words(resp.data)

    async def extend_unit_write_words(self, head_address: int, module_no: int, values: Sequence[int]) -> None:
        """Write words to an extend unit."""
        data = bytearray()
        for v in values:
            data += int(v).to_bytes(2, "little")
        payload = (
            head_address.to_bytes(4, "little")
            + len(data).to_bytes(2, "little")
            + module_no.to_bytes(2, "little")
            + data
        )
        await self.request(Command.EXTEND_UNIT_WRITE, 0x0000, bytes(payload))

    async def cpu_buffer_read_words(self, head_address: int, word_length: int, *, module_no: int = 0x03E0) -> list[int]:
        """Read words from the CPU buffer."""
        return await self.extend_unit_read_words(head_address, word_length, module_no)

    async def cpu_buffer_write_words(
        self, head_address: int, values: Sequence[int], *, module_no: int = 0x03E0
    ) -> None:
        """Write words to the CPU buffer."""
        await self.extend_unit_write_words(head_address, module_no, values)

    async def read_long_timer(
        self, *, head_no: int = 0, points: int = 1, series: PLCSeries | str | None = None
    ) -> list[LongTimerResult]:
        """Read long timers from the PLC."""
        words_raw = await self.read_devices(f"LTN{head_no}", points * 4, series=series)
        result = []
        int_words = cast(list[int], words_raw)
        for i in range(points):
            blk = int_words[i * 4 : i * 4 + 4]
            result.append(
                LongTimerResult(
                    index=head_no + i,
                    device=f"LTN{head_no + i}",
                    current_value=(blk[1] << 16) | blk[0],
                    contact=bool(blk[2] & 0x0002),
                    coil=bool(blk[2] & 0x0001),
                    status_word=blk[2],
                    raw_words=blk,
                )
            )
        return result

    async def read_long_retentive_timer(
        self, *, head_no: int = 0, points: int = 1, series: PLCSeries | str | None = None
    ) -> list[LongTimerResult]:
        """Read long retentive timers from the PLC."""
        words_raw = await self.read_devices(f"LSTN{head_no}", points * 4, series=series)
        result = []
        int_words = cast(list[int], words_raw)
        for i in range(points):
            blk = int_words[i * 4 : i * 4 + 4]
            result.append(
                LongTimerResult(
                    index=head_no + i,
                    device=f"LSTN{head_no + i}",
                    current_value=(blk[1] << 16) | blk[0],
                    contact=bool(blk[2] & 0x0002),
                    coil=bool(blk[2] & 0x0001),
                    status_word=blk[2],
                    raw_words=blk,
                )
            )
        return result

    async def read_ltc_states(
        self, *, head_no: int = 0, points: int = 1, series: PLCSeries | str | None = None
    ) -> list[bool]:
        """Read long timer coil states."""
        return [item.coil for item in await self.read_long_timer(head_no=head_no, points=points, series=series)]

    async def read_lts_states(
        self, *, head_no: int = 0, points: int = 1, series: PLCSeries | str | None = None
    ) -> list[bool]:
        """Read long timer contact states."""
        return [item.contact for item in await self.read_long_timer(head_no=head_no, points=points, series=series)]

    async def read_lstc_states(
        self, *, head_no: int = 0, points: int = 1, series: PLCSeries | str | None = None
    ) -> list[bool]:
        """Read long retentive timer coil states."""
        items = await self.read_long_retentive_timer(head_no=head_no, points=points, series=series)
        return [item.coil for item in items]

    async def read_lsts_states(
        self, *, head_no: int = 0, points: int = 1, series: PLCSeries | str | None = None
    ) -> list[bool]:
        """Read long retentive timer contact states."""
        items = await self.read_long_retentive_timer(head_no=head_no, points=points, series=series)
        return [item.contact for item in items]

    async def extend_unit_read_bytes(self, head_address: int, byte_length: int, module_no: int) -> bytes:
        """Read bytes from an extend unit."""
        _check_u32(head_address, "head_address")
        _check_u16(module_no, "module_no")
        payload = (
            head_address.to_bytes(4, "little") + byte_length.to_bytes(2, "little") + module_no.to_bytes(2, "little")
        )
        resp = await self.request(Command.EXTEND_UNIT_READ, 0x0000, payload)
        return resp.data

    async def extend_unit_read_word(self, head_address: int, module_no: int) -> int:
        """Read a single word from an extend unit."""
        return (await self.extend_unit_read_words(head_address, 1, module_no))[0]

    async def extend_unit_read_dword(self, head_address: int, module_no: int) -> int:
        """Read a double word from an extend unit."""
        return int.from_bytes(await self.extend_unit_read_bytes(head_address, 4, module_no), "little", signed=False)

    async def extend_unit_write_bytes(self, head_address: int, module_no: int, data: bytes) -> None:
        """Write bytes to an extend unit."""
        _check_u32(head_address, "head_address")
        _check_u16(module_no, "module_no")
        payload = (
            head_address.to_bytes(4, "little")
            + len(data).to_bytes(2, "little")
            + module_no.to_bytes(2, "little")
            + data
        )
        await self.request(Command.EXTEND_UNIT_WRITE, 0x0000, payload)

    async def extend_unit_write_word(self, head_address: int, module_no: int, value: int) -> None:
        """Write a single word to an extend unit."""
        await self.extend_unit_write_words(head_address, module_no, [value])

    async def extend_unit_write_dword(self, head_address: int, module_no: int, value: int) -> None:
        """Write a double word to an extend unit."""
        await self.extend_unit_write_bytes(head_address, module_no, int(value).to_bytes(4, "little", signed=False))

    async def cpu_buffer_read_bytes(self, head_address: int, byte_length: int, *, module_no: int = 0x03E0) -> bytes:
        """Read bytes from the CPU buffer."""
        return await self.extend_unit_read_bytes(head_address, byte_length, module_no)

    async def cpu_buffer_read_word(self, head_address: int, *, module_no: int = 0x03E0) -> int:
        """Read a single word from the CPU buffer."""
        return await self.extend_unit_read_word(head_address, module_no)

    async def cpu_buffer_read_dword(self, head_address: int, *, module_no: int = 0x03E0) -> int:
        """Read a double word from the CPU buffer."""
        return await self.extend_unit_read_dword(head_address, module_no)

    async def cpu_buffer_write_bytes(self, head_address: int, data: bytes, *, module_no: int = 0x03E0) -> None:
        """Write bytes to the CPU buffer."""
        await self.extend_unit_write_bytes(head_address, module_no, data)

    async def cpu_buffer_write_word(self, head_address: int, value: int, *, module_no: int = 0x03E0) -> None:
        """Write a single word to the CPU buffer."""
        await self.extend_unit_write_word(head_address, module_no, value)

    async def cpu_buffer_write_dword(self, head_address: int, value: int, *, module_no: int = 0x03E0) -> None:
        """Write a double word to the CPU buffer."""
        await self.extend_unit_write_dword(head_address, module_no, value)

    @staticmethod
    def build_array_label_read_payload(
        points: Sequence[LabelArrayReadPoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> bytes:
        """Build the payload for an array label read request."""
        return SlmpClient.build_array_label_read_payload(points, abbreviation_labels=abbreviation_labels)

    @staticmethod
    def build_array_label_write_payload(
        points: Sequence[LabelArrayWritePoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> bytes:
        """Build the payload for an array label write request."""
        return SlmpClient.build_array_label_write_payload(points, abbreviation_labels=abbreviation_labels)

    @staticmethod
    def build_label_read_random_payload(labels: Sequence[str], *, abbreviation_labels: Sequence[str] = ()) -> bytes:
        """Build the payload for a random label read request."""
        return SlmpClient.build_label_read_random_payload(labels, abbreviation_labels=abbreviation_labels)

    @staticmethod
    def build_label_write_random_payload(
        points: Sequence[LabelRandomWritePoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> bytes:
        """Build the payload for a random label write request."""
        return SlmpClient.build_label_write_random_payload(points, abbreviation_labels=abbreviation_labels)

    @staticmethod
    def parse_array_label_read_response(
        data: bytes, *, expected_points: int | None = None
    ) -> list[LabelArrayReadResult]:
        """Parse the response from an array label read request."""
        return SlmpClient.parse_array_label_read_response(data, expected_points=expected_points)

    @staticmethod
    def parse_label_read_random_response(
        data: bytes, *, expected_points: int | None = None
    ) -> list[LabelRandomReadResult]:
        """Parse the response from a random label read request."""
        return SlmpClient.parse_label_read_random_response(data, expected_points=expected_points)

    async def array_label_read(self, payload: bytes = b"") -> bytes:
        """Execute a raw array label read command."""
        return (await self.request(Command.LABEL_ARRAY_READ, 0x0000, payload)).data

    async def array_label_write(self, payload: bytes = b"") -> None:
        """Execute a raw array label write command."""
        await self.request(Command.LABEL_ARRAY_WRITE, 0x0000, payload)

    async def label_read_random(self, payload: bytes = b"") -> bytes:
        """Execute a raw random label read command."""
        return (await self.request(Command.LABEL_READ_RANDOM, 0x0000, payload)).data

    async def label_write_random(self, payload: bytes = b"") -> None:
        """Execute a raw random label write command."""
        await self.request(Command.LABEL_WRITE_RANDOM, 0x0000, payload)

    async def memory_read(self, payload: bytes = b"") -> bytes:
        """Execute a raw memory read command."""
        return (await self.request(Command.MEMORY_READ, 0x0000, payload)).data

    async def memory_write(self, payload: bytes = b"") -> None:
        """Execute a raw memory write command."""
        await self.request(Command.MEMORY_WRITE, 0x0000, payload)

    async def extend_unit_read(self, payload: bytes = b"") -> bytes:
        """Execute a raw extend unit read command."""
        return (await self.request(Command.EXTEND_UNIT_READ, 0x0000, payload)).data

    async def extend_unit_write(self, payload: bytes = b"") -> None:
        """Execute a raw extend unit write command."""
        await self.request(Command.EXTEND_UNIT_WRITE, 0x0000, payload)

    async def remote_run_raw(self, payload: bytes = b"") -> None:
        """Execute a raw remote run command."""
        await self.request(Command.REMOTE_RUN, 0x0000, payload)

    async def remote_stop_raw(self, payload: bytes = b"") -> None:
        """Execute a raw remote stop command."""
        await self.request(Command.REMOTE_STOP, 0x0000, payload)

    async def remote_pause_raw(self, payload: bytes = b"") -> None:
        """Execute a raw remote pause command."""
        await self.request(Command.REMOTE_PAUSE, 0x0000, payload)

    async def remote_latch_clear_raw(self, payload: bytes = b"") -> None:
        """Execute a raw remote latch clear command."""
        await self.request(Command.REMOTE_LATCH_CLEAR, 0x0000, payload)

    async def remote_reset_raw(self, payload: bytes = b"") -> None:
        """Execute a raw remote reset command."""
        if payload:
            raise ValueError("remote reset does not use request data")
        await self._send_no_response(Command.REMOTE_RESET, 0x0000, b"")

    async def remote_password_lock_raw(self, payload: bytes = b"") -> None:
        """Execute a raw remote password lock command."""
        await self.request(Command.REMOTE_PASSWORD_LOCK, 0x0000, payload)

    async def remote_password_unlock_raw(self, payload: bytes = b"") -> None:
        """Execute a raw remote password unlock command."""
        await self.request(Command.REMOTE_PASSWORD_UNLOCK, 0x0000, payload)

    async def self_test(self, payload: bytes = b"") -> bytes:
        """Execute a raw self test command."""
        return (await self.request(Command.SELF_TEST, 0x0000, payload)).data

    async def clear_error(self, payload: bytes = b"") -> None:
        """Execute a raw clear error command."""
        await self.request(Command.CLEAR_ERROR, 0x0000, payload)

    def _next_serial(self) -> int:
        """Get the next serial number for the request."""
        serial = self._serial & 0xFFFF
        self._serial = (self._serial + 1) & 0xFFFF
        return serial

    async def _send_no_response(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
    ) -> None:
        """Send an SLMP request without waiting for a response."""
        serial_no = self._next_serial() if serial is None else serial
        target_info = target or self.default_target
        monitor = self.monitoring_timer if monitoring_timer is None else monitoring_timer

        frame = encode_request(
            frame_type=self.frame_type,
            serial=serial_no,
            target=target_info,
            monitoring_timer=monitor,
            command=int(command),
            subcommand=subcommand,
            data=data,
        )

        await self.connect()
        async with self._lock:
            if self.transport_type == "tcp":
                assert self._writer is not None
                self._writer.write(frame)
                await self._writer.drain()
            else:
                assert self._udp_transport is not None
                self._udp_transport.sendto(frame)

        await self._emit_trace(
            SlmpTraceFrame(
                serial=serial_no,
                command=int(command),
                subcommand=subcommand,
                request_data=data,
                request_frame=frame,
                response_frame=b"",
                response_end_code=None,
                target=target_info,
                monitoring_timer=monitor,
            )
        )

    async def _send_and_receive(self, frame: bytes) -> bytes:
        """Send a frame and receive the response."""
        await self.connect()
        async with self._lock:
            if self.transport_type == "tcp":
                assert self._writer is not None
                self._writer.write(frame)
                await self._writer.drain()
                return await self._receive_frame()
            else:
                assert self._udp_transport is not None
                assert self._udp_protocol is not None
                while not self._udp_protocol.queue.empty():
                    self._udp_protocol.queue.get_nowait()
                self._udp_transport.sendto(frame)
                try:
                    return await asyncio.wait_for(self._udp_protocol.queue.get(), timeout=self.timeout)
                except asyncio.TimeoutError as err:
                    raise SlmpError("UDP communication timeout") from err

    async def _receive_frame(self) -> bytes:
        """Receive a single SLMP frame."""
        assert self._reader is not None
        head_size = 13 if self.frame_type == FrameType.FRAME_4E else 9
        try:
            head = await asyncio.wait_for(self._reader.readexactly(head_size), timeout=self.timeout)
            response_data_length = int.from_bytes(head[-2:], "little")
            tail = await asyncio.wait_for(self._reader.readexactly(response_data_length), timeout=self.timeout)
            return head + tail
        except (asyncio.TimeoutError, asyncio.IncompleteReadError) as err:
            raise SlmpError("communication timeout or connection closed") from err

    async def _emit_trace(self, trace: SlmpTraceFrame) -> None:
        """Emit a trace event if a trace hook is registered."""
        if self.trace_hook:
            try:
                if asyncio.iscoroutinefunction(self.trace_hook):
                    await self.trace_hook(trace)
                else:
                    self.trace_hook(trace)
            except Exception:
                pass
