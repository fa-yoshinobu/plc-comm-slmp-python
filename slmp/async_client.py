"""SLMP binary client (asynchronous)."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from . import _operations
from .client import SlmpClient
from .constants import Command, FrameType, PLCSeries
from .core import (
    BlockReadResult,
    CpuOperationState,
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
    _raise_response_error,
    _require_explicit_plc_profile_for_xy,
    _resolve_connection_profile,
    build_device_modification_flags,
    decode_cpu_operation_state,
    decode_response,
    encode_request,
    parse_device,
    resolve_extended_device_and_extension,
)
from .errors import SlmpError

if TYPE_CHECKING:
    from .core import SlmpPlcProfile
    from .device_ranges import SlmpDeviceRangeCatalog


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
        plc_profile: object | None = None,
        plc_series: PLCSeries | str | None = None,
        frame_type: FrameType | str | None = None,
        default_target: SlmpTarget | None = None,
        monitoring_timer: int = 0x0010,
        raise_on_error: bool = True,
        trace_hook: Callable[[SlmpTraceFrame], Any] | None = None,
        address_profile: object | None = None,
        _allow_manual_profile: bool = False,
    ) -> None:
        """Initialize the asynchronous SLMP client.

        The standard async client route requires ``plc_profile`` and fixes the
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
            if plc_profile is None:
                raise ValueError(
                    "plc_profile is required for the standard AsyncSlmpClient route "
                    "unless you explicitly opt into a low-level frame/profile path."
                )
            if plc_profile is not None and any(value is not None for value in (plc_series, frame_type, address_profile)):
                raise ValueError(
                    "plc_profile is the only supported PLC selector for the standard AsyncSlmpClient route."
                )
        (
            self.plc_profile,
            self.plc_series,
            self.frame_type,
            self.address_profile,
            self.range_profile,
        ) = _resolve_connection_profile(
            plc_profile=plc_profile,
            plc_series=plc_series,
            frame_type=frame_type,
            address_profile=address_profile,
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
        ref = parse_device(device, plc_profile=self.address_profile)
        return _require_explicit_plc_profile_for_xy(device, self.address_profile, ref)

    def _resolve_extended_device_and_extension(
        self,
        device: str | DeviceRef,
        extension: ExtensionSpec,
    ) -> tuple[DeviceRef, ExtensionSpec]:
        ref, effective_extension = resolve_extended_device_and_extension(device, extension, plc_profile=self.address_profile)
        return _require_explicit_plc_profile_for_xy(device, self.address_profile, ref), effective_extension

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
                writer = self._writer
                assert writer is not None
                raw_socket = writer.get_extra_info("socket")
                if raw_socket is not None:
                    raw_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
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
        request = _operations.build_read_devices_request(
            device,
            points,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = await self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_devices_response(resp, points=points, bit_unit=bit_unit)

    async def write_devices(
        self,
        device: str | DeviceRef,
        values: Sequence[int | bool],
        *,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write device values to the PLC."""
        request = _operations.build_write_devices_request(
            device,
            values,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

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
        request = _operations.build_read_dwords_request(
            device,
            count,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = await self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_dwords_response(resp, count=count)

    async def write_dwords(
        self,
        device: str | DeviceRef,
        values: Sequence[int],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write one or more 32-bit values to two consecutive word devices."""
        request = _operations.build_write_dwords_request(
            device,
            values,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

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
        request = _operations.build_read_dwords_request(
            device,
            count,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = await self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_float32s_response(resp, count=count)

    async def write_float32s(
        self,
        device: str | DeviceRef,
        values: Sequence[float],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write one or more IEEE-754 float32 values to two consecutive word devices."""
        request = _operations.build_write_float32s_request(
            device,
            values,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

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
        request = _operations.build_read_devices_ext_request(
            device,
            points,
            extension=extension,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = await self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_devices_response(resp, points=points, bit_unit=bit_unit)

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
        request = _operations.build_write_devices_ext_request(
            device,
            values,
            extension=extension,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

    async def read_random(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
        series: PLCSeries | str | None = None,
    ) -> RandomReadResult:
        """Read multiple word and double-word devices in a single request."""
        operation = _operations.build_read_random_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        request = operation.request
        resp = await self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_random_response(resp, operation)

    async def read_random_ext(
        self,
        *,
        word_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        dword_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> RandomReadResult:
        """Read multiple word and double-word devices using Extended Device extension."""
        operation = _operations.build_read_random_ext_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        request = operation.request
        resp = await self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_random_response(resp, operation)

    async def write_random_words(
        self,
        *,
        word_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]] = (),
        dword_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple word and double-word devices in a single request."""
        request = _operations.build_write_random_words_request(
            word_values=word_values,
            dword_values=dword_values,
            series=series,
            default_series=self.plc_series,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

    async def write_random_words_ext(
        self,
        *,
        word_values: Sequence[tuple[str | DeviceRef, int, ExtensionSpec]] = (),
        dword_values: Sequence[tuple[str | DeviceRef, int, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple word and double-word devices using Extended Device extension."""
        request = _operations.build_write_random_words_ext_request(
            word_values=word_values,
            dword_values=dword_values,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

    async def write_random_bits(
        self,
        bit_values: Mapping[str | DeviceRef, bool | int] | Sequence[tuple[str | DeviceRef, bool | int]],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple bit devices in a single request."""
        request = _operations.build_write_random_bits_request(
            bit_values,
            series=series,
            default_series=self.plc_series,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

    async def write_random_bits_ext(
        self,
        bit_values: Sequence[tuple[str | DeviceRef, bool | int, ExtensionSpec]],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple bit devices using Extended Device extension."""
        request = _operations.build_write_random_bits_ext_request(
            bit_values,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

    async def register_monitor_devices(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Register devices for monitoring."""
        request = _operations.build_register_monitor_devices_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

    async def register_monitor_devices_ext(
        self,
        *,
        word_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        dword_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Register devices for monitoring using Extended Device extension."""
        request = _operations.build_register_monitor_devices_ext_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        await self.request(request.command, subcommand=request.subcommand, data=request.payload)

    async def run_monitor_cycle(self, *, word_points: int, dword_points: int) -> MonitorResult:
        """Execute one cycle of monitoring and return the results."""
        request = _operations.build_run_monitor_cycle_request(word_points=word_points, dword_points=dword_points)
        resp = await self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_run_monitor_cycle_response(resp, word_points=word_points, dword_points=dword_points)

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
        if len(word_blocks) > 0xFF or len(bit_blocks) > 0xFF:
            raise ValueError("word_blocks and bit_blocks must be <= 255 each")
        if split_mixed_blocks and word_blocks and bit_blocks:
            w = await self.read_block(
                word_blocks=word_blocks,
                bit_blocks=(),
                series=series,
                split_mixed_blocks=False,
            )
            b = await self.read_block(
                word_blocks=(),
                bit_blocks=bit_blocks,
                series=series,
                split_mixed_blocks=False,
            )
            return BlockReadResult(word_blocks=w.word_blocks, bit_blocks=b.bit_blocks)
        operation = _operations.build_read_block_request(
            word_blocks=word_blocks,
            bit_blocks=bit_blocks,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        request = operation.request
        resp = await self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_block_response(resp, operation)

    async def write_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
        series: PLCSeries | str | None = None,
        split_mixed_blocks: bool = False,
    ) -> None:
        """Write multiple blocks of devices."""
        if not word_blocks and not bit_blocks:
            raise ValueError("word_blocks and bit_blocks must not both be empty")
        if len(word_blocks) > 0xFF or len(bit_blocks) > 0xFF:
            raise ValueError("word_blocks and bit_blocks must be <= 255 each")
        if split_mixed_blocks and word_blocks and bit_blocks:
            await self.write_block(
                word_blocks=word_blocks,
                bit_blocks=(),
                series=series,
                split_mixed_blocks=False,
            )
            await self.write_block(
                word_blocks=(),
                bit_blocks=bit_blocks,
                series=series,
                split_mixed_blocks=False,
            )
            return
        request = _operations.build_write_block_request(
            word_blocks=word_blocks,
            bit_blocks=bit_blocks,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = await self.request(
            request.command,
            subcommand=request.subcommand,
            data=request.payload,
            raise_on_error=False,
        )
        if resp.end_code == 0:
            return
        if self.raise_on_error:
            _raise_response_error(resp, command=request.command, subcommand=request.subcommand)

    # --------------------
    # Remote / Administrative
    # --------------------

    async def read_type_name(self) -> TypeNameInfo:
        """Read the PLC type name and model code."""
        request = _operations.build_read_type_name_request()
        resp = await self.request(request.command, request.subcommand, request.payload)
        return _operations.decode_read_type_name_response(resp)

    async def read_device_range_catalog_for_plc_profile(
        self,
        plc_profile: SlmpPlcProfile | str,
    ) -> SlmpDeviceRangeCatalog:
        """Read the configured device-range catalog for one canonical explicit PLC profile."""
        from .device_ranges import read_device_range_catalog_for_plc_profile

        return await read_device_range_catalog_for_plc_profile(self, plc_profile)

    async def read_device_range_catalog(self) -> SlmpDeviceRangeCatalog:
        """Read the configured device-range catalog for this client's explicit PLC profile."""
        if self.range_profile is None:
            raise ValueError("read_device_range_catalog() requires explicit plc_profile on the client.")
        return await self.read_device_range_catalog_for_plc_profile(self.range_profile)

    async def read_cpu_operation_state(self) -> CpuOperationState:
        """Read SD203 and decode the CPU operation state from the lower 4 bits."""
        return decode_cpu_operation_state((await self.read_devices("SD203", 1, bit_unit=False))[0])

    async def remote_run(self, *, force: bool = False, clear_mode: int = 0) -> None:
        """Remote run the PLC."""
        request = _operations.build_remote_run_request(force=force, clear_mode=clear_mode)
        await self.request(request.command, request.subcommand, request.payload)

    async def remote_stop(self) -> None:
        """Remote stop the PLC."""
        request = _operations.build_remote_stop_request()
        await self.request(request.command, request.subcommand, request.payload)

    async def remote_pause(self, *, force: bool = False) -> None:
        """Remote pause the PLC."""
        request = _operations.build_remote_pause_request(force=force)
        await self.request(request.command, request.subcommand, request.payload)

    async def remote_latch_clear(self) -> None:
        """Remote latch clear the PLC."""
        request = _operations.build_remote_latch_clear_request()
        await self.request(request.command, request.subcommand, request.payload)

    async def remote_reset(self, *, subcommand: int = 0x0000, expect_response: bool | None = None) -> None:
        """Remote reset the PLC."""
        request = _operations.build_remote_reset_request(subcommand=subcommand)
        should_wait = False if expect_response is None else expect_response
        if should_wait:
            await self.request(request.command, request.subcommand, request.payload)
            return
        await self._send_no_response(request.command, request.subcommand, request.payload)

    async def remote_password_lock(self, password: str, *, series: PLCSeries | str | None = None) -> None:
        """Remote password lock the PLC."""
        request = _operations.build_remote_password_lock_request(
            password,
            series=series,
            default_series=self.plc_series,
        )
        await self.request(request.command, request.subcommand, request.payload)

    async def remote_password_unlock(self, password: str, *, series: PLCSeries | str | None = None) -> None:
        """Remote password unlock the PLC."""
        request = _operations.build_remote_password_unlock_request(
            password,
            series=series,
            default_series=self.plc_series,
        )
        await self.request(request.command, request.subcommand, request.payload)

    async def self_test_loopback(self, data: bytes | str) -> bytes:
        """Execute a self-test loopback."""
        request = _operations.build_self_test_loopback_request(data)
        resp = await self.request(request.command, request.subcommand, request.payload)
        return _operations.decode_self_test_loopback_response(resp)

    # --------------------
    # Label commands
    # --------------------

    async def read_array_labels(
        self, points: Sequence[LabelArrayReadPoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> list[LabelArrayReadResult]:
        """Read array labels from the PLC."""
        request = _operations.build_read_array_labels_request(points, abbreviation_labels=abbreviation_labels)
        resp = await self.request(request.command, request.subcommand, request.payload)
        return _operations.parse_array_label_read_response(resp.data, expected_points=len(points))

    async def write_array_labels(
        self, points: Sequence[LabelArrayWritePoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> None:
        """Write array labels to the PLC."""
        request = _operations.build_write_array_labels_request(points, abbreviation_labels=abbreviation_labels)
        await self.request(request.command, request.subcommand, request.payload)

    async def read_random_labels(
        self, labels: Sequence[str], *, abbreviation_labels: Sequence[str] = ()
    ) -> list[LabelRandomReadResult]:
        """Read random labels from the PLC."""
        request = _operations.build_read_random_labels_request(labels, abbreviation_labels=abbreviation_labels)
        resp = await self.request(request.command, request.subcommand, request.payload)
        return _operations.parse_label_read_random_response(resp.data, expected_points=len(labels))

    async def write_random_labels(
        self, points: Sequence[LabelRandomWritePoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> None:
        """Write random labels to the PLC."""
        request = _operations.build_write_random_labels_request(points, abbreviation_labels=abbreviation_labels)
        await self.request(request.command, request.subcommand, request.payload)

    # --------------------
    # Memory
    # --------------------

    async def memory_read_words(self, head_address: int, word_length: int) -> list[int]:
        """Read memory words from the PLC."""
        request = _operations.build_memory_read_words_request(head_address, word_length)
        resp = await self.request(request.command, request.subcommand, request.payload)
        return _operations.decode_memory_read_words_response(resp, word_length=word_length)

    async def memory_write_words(self, head_address: int, values: Sequence[int]) -> None:
        """Write memory words to the PLC."""
        request = _operations.build_memory_write_words_request(head_address, values)
        await self.request(request.command, request.subcommand, request.payload)

    async def extend_unit_read_words(self, head_address: int, word_length: int, module_no: int) -> list[int]:
        """Read words from an extend unit."""
        request = _operations.build_extend_unit_read_words_request(head_address, word_length, module_no)
        resp = await self.request(request.command, request.subcommand, request.payload)
        return _operations.decode_extend_unit_read_words_response(resp, word_length=word_length)

    async def extend_unit_write_words(self, head_address: int, module_no: int, values: Sequence[int]) -> None:
        """Write words to an extend unit."""
        request = _operations.build_extend_unit_write_words_request(head_address, module_no, values)
        await self.request(request.command, request.subcommand, request.payload)

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
        request = _operations.build_extend_unit_read_bytes_request(head_address, byte_length, module_no)
        resp = await self.request(request.command, request.subcommand, request.payload)
        return _operations.decode_extend_unit_read_bytes_response(resp, byte_length=byte_length)

    async def extend_unit_read_word(self, head_address: int, module_no: int) -> int:
        """Read a single word from an extend unit."""
        return (await self.extend_unit_read_words(head_address, 1, module_no))[0]

    async def extend_unit_read_dword(self, head_address: int, module_no: int) -> int:
        """Read a double word from an extend unit."""
        return int.from_bytes(await self.extend_unit_read_bytes(head_address, 4, module_no), "little", signed=False)

    async def extend_unit_write_bytes(self, head_address: int, module_no: int, data: bytes) -> None:
        """Write bytes to an extend unit."""
        request = _operations.build_extend_unit_write_bytes_request(head_address, module_no, data)
        await self.request(request.command, request.subcommand, request.payload)

    async def extend_unit_write_word(self, head_address: int, module_no: int, value: int) -> None:
        """Write a single word to an extend unit."""
        request = _operations.build_extend_unit_write_word_request(head_address, module_no, value)
        await self.request(request.command, request.subcommand, request.payload)

    async def extend_unit_write_dword(self, head_address: int, module_no: int, value: int) -> None:
        """Write a double word to an extend unit."""
        request = _operations.build_extend_unit_write_dword_request(head_address, module_no, value)
        await self.request(request.command, request.subcommand, request.payload)

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

    async def remote_reset_raw(self, payload: bytes = b"\x01\x00") -> None:
        """Execute a raw remote reset command."""
        await self._send_no_response(Command.REMOTE_RESET, 0x0000, payload)

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
