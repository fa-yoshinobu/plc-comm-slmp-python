"""SLMP binary client (asynchronous)."""

from __future__ import annotations

import asyncio
import math
import socket
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, NoReturn, TypeVar, cast

from . import _operations
from ._command_policy import classify_command_state
from ._network import normalize_ipv4_host, resolve_ipv4_endpoint_async
from ._operation_queue import _AsyncFifoOperationQueue
from ._socket_options import configure_tcp_keepalive
from .capability_profiles import ensure_extended_profile_feature_allowed, ensure_profile_feature_allowed
from .constants import Command, FrameType, RemoteClearMode
from .core import (
    BlockReadResult,
    CpuOperationState,
    DeviceRef,
    LabelArrayReadPoint,
    LabelArrayReadResult,
    LabelArrayWritePoint,
    LabelRandomReadResult,
    LabelRandomWritePoint,
    LongTimerResult,
    MonitorResult,
    RandomReadResult,
    SlmpExtendedDevice,
    SlmpResponse,
    SlmpTarget,
    SlmpTrafficStats,
    TypeNameInfo,
    _apply_semantic_device_modification,
    _ExtensionSpec,
    _format_semantic_extended_device_key,
    _parse_extended_device,
    _raise_response_error,
    _request_payload_limit,
    _require_explicit_plc_profile_for_xy,
    _resolve_connection_profile,
    _resolve_extended_device_and_extension,
    _resolve_port,
    _SlmpTraceFrame,
    _validate_request_payload_length,
    decode_cpu_operation_state,
    decode_response,
    encode_request,
    parse_device,
)
from .errors import (
    SlmpClosedError,
    SlmpError,
    SlmpNotConnectedError,
    SlmpOutcomeUnknownError,
    SlmpOutcomeUnknownReason,
    SlmpTimeoutError,
    SlmpTransportError,
)

_COMMUNICATION_TIMEOUT_MESSAGE = "SLMP communication timeout"
_DecodedT = TypeVar("_DecodedT")

if TYPE_CHECKING:
    from .core import SlmpPlcProfile
    from .device_ranges import SlmpDeviceRangeCatalog


class SLMPDatagramProtocol(asyncio.DatagramProtocol):
    """Internal single-waiter protocol for async UDP communication."""

    def __init__(
        self,
        frame_type: FrameType,
        on_datagram: Callable[[int], None] | None = None,
        on_transport_lost: Callable[[SLMPDatagramProtocol, BaseException], None] | None = None,
    ) -> None:
        """Initialize the protocol with a frame type and optional accounting hook."""
        self.frame_type = frame_type
        self.transport: asyncio.DatagramTransport | None = None
        self._on_datagram = on_datagram
        self._on_transport_lost = on_transport_lost
        self._response_waiter: asyncio.Future[bytes] | None = None
        self._expected_identity: tuple[int | None, SlmpTarget] | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle connection made."""
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data: bytes, _addr: tuple[str | Any, int]) -> None:
        """Resolve the one matching active waiter without retaining datagrams."""
        if self._on_datagram is not None:
            self._on_datagram(len(data))
        waiter = self._response_waiter
        expected_identity = self._expected_identity
        if waiter is None or waiter.done() or expected_identity is None:
            return
        try:
            matches = _response_matches_request(
                data,
                frame_type=self.frame_type,
                expected_identity=expected_identity,
            )
        except BaseException as err:
            waiter.set_exception(err)
            return
        if matches:
            waiter.set_result(bytes(data))

    def error_received(self, exc: Exception) -> None:
        """Fail the active waiter on a connected UDP socket error."""
        error = SlmpTransportError(f"SLMP UDP transport failed: {exc}")
        error.__cause__ = exc
        self._report_transport_loss(error)

    def connection_lost(self, exc: Exception | None) -> None:
        """Fail the active waiter when its exact UDP generation is lost."""
        self.transport = None
        if exc is None:
            self._report_transport_loss(SlmpClosedError("SLMP UDP transport was closed"))
        else:
            error = SlmpTransportError(f"SLMP UDP transport failed: {exc}")
            error.__cause__ = exc
            self._report_transport_loss(error)

    def begin_response_wait(
        self,
        expected_identity: tuple[int | None, SlmpTarget],
    ) -> asyncio.Future[bytes]:
        """Install the one response waiter owned by the active request."""
        if self._response_waiter is not None and not self._response_waiter.done():
            raise RuntimeError("an SLMP UDP response waiter is already active")
        waiter = asyncio.get_running_loop().create_future()
        self._response_waiter = waiter
        self._expected_identity = expected_identity
        return waiter

    def set_datagram_accounting(self, callback: Callable[[int], None]) -> None:
        """Bind receive accounting to the client that owns this generation."""
        self._on_datagram = callback

    def forget_response_wait(self, waiter: asyncio.Future[bytes]) -> None:
        """Forget and cancel the exact active waiter without retaining a result."""
        if self._response_waiter is not waiter:
            return
        self._response_waiter = None
        self._expected_identity = None
        if not waiter.done():
            waiter.cancel()

    def fail_pending(self, error: BaseException) -> None:
        """Wake the exact active waiter with a transport-generation failure."""
        waiter = self._response_waiter
        if waiter is not None and not waiter.done():
            waiter.set_exception(error)

    def _report_transport_loss(self, error: BaseException) -> None:
        self.fail_pending(error)
        if self._on_transport_lost is not None:
            self._on_transport_lost(self, error)


class AsyncSlmpClient:
    """Asynchronous SLMP client supporting 3E and 4E frames (binary) over TCP and UDP."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        transport: str,
        default_target: SlmpTarget,
        plc_profile: object,
        timeout: float = 3.0,
        monitoring_timer: int = 0x0010,
        raise_on_error: bool = True,
        _maintainer_trace_hook: Callable[[_SlmpTraceFrame], Any] | None = None,
        _maintainer_strict_profile: bool = True,
    ) -> None:
        """Initialize the asynchronous SLMP client.

        The standard async client route requires ``plc_profile`` and fixes the
        frame type, access profile, and address/range handling from that one
        explicit PLC profile. ``timeout`` is one complete-operation deadline
        covering connection establishment, request send, and matching response.
        ``host`` must be an IPv4 literal or a hostname that resolves to IPv4;
        IPv6 is unsupported.
        """
        self.host = normalize_ipv4_host(host)
        if not isinstance(transport, str):
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.transport_type = transport.strip().lower()
        if self.transport_type not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.port = _resolve_port(port, self.transport_type)
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a finite number greater than zero")
        self.timeout = float(timeout)
        if plc_profile is None:
            raise ValueError("plc_profile is required for AsyncSlmpClient")
        (
            self.plc_profile,
            self.plc_series,
            self.frame_type,
            self.address_profile,
            self.range_profile,
        ) = _resolve_connection_profile(
            plc_profile=plc_profile,
            plc_series=None,
            frame_type=None,
            address_profile=None,
        )
        if not isinstance(default_target, SlmpTarget):
            raise ValueError("default_target is required and must be a complete SlmpTarget")
        self.default_target = default_target
        if (
            isinstance(monitoring_timer, bool)
            or not isinstance(monitoring_timer, int)
            or not 0 <= monitoring_timer <= 0xFFFF
        ):
            raise ValueError("monitoring_timer must be an integer in range 0..65535")
        self.monitoring_timer = monitoring_timer
        if type(raise_on_error) is not bool:
            raise ValueError("raise_on_error must be a boolean")
        self.raise_on_error = raise_on_error
        if type(_maintainer_strict_profile) is not bool:
            raise ValueError("_maintainer_strict_profile must be a boolean")
        if _maintainer_trace_hook is not None and not callable(_maintainer_trace_hook):
            raise ValueError("_maintainer_trace_hook must be callable or None")
        self._trace_hook = _maintainer_trace_hook
        self._strict_profile = _maintainer_strict_profile

        self._serial = 0
        self._operation_queue = _AsyncFifoOperationQueue()
        # Retained as a private test/diagnostic alias; operation ownership is
        # managed by _operation_queue.
        self._lock = self._operation_queue.lock
        self._active_state_changing = False

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_count = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._udp_transport: asyncio.DatagramTransport | None = None
        self._udp_protocol: SLMPDatagramProtocol | None = None

    def traffic_stats(self) -> SlmpTrafficStats:
        """Return a read-only snapshot of cumulative traffic for this client lifetime."""
        return SlmpTrafficStats(self._request_count, self._tx_bytes, self._rx_bytes)

    def _record_send(self, frame_length: int) -> None:
        self._request_count += 1
        self._tx_bytes += frame_length

    def _record_receive(self, frame_length: int) -> None:
        self._rx_bytes += frame_length

    def _parse_device(self, device: str | DeviceRef) -> DeviceRef:
        ref = parse_device(device, plc_profile=self.plc_profile)
        return _require_explicit_plc_profile_for_xy(device, self.plc_profile, ref)

    def _resolve_semantic_extended_device(
        self,
        device: str | SlmpExtendedDevice,
    ) -> tuple[str, DeviceRef, _ExtensionSpec]:
        address = device.address if isinstance(device, SlmpExtendedDevice) else device
        modification = device.modification if isinstance(device, SlmpExtendedDevice) else None
        parsed = _parse_extended_device(address, plc_profile=self.plc_profile)
        if parsed.qualifier not in {"J", "U"}:
            raise ValueError("Extended Device semantic APIs require a qualified address such as U1\\G0 or J2\\SW10")
        ref, effective_extension = _resolve_extended_device_and_extension(
            address,
            _ExtensionSpec(),
            plc_profile=self.plc_profile,
        )
        ref = _require_explicit_plc_profile_for_xy(address, self.plc_profile, ref)
        effective_extension = _apply_semantic_device_modification(
            effective_extension,
            modification,
            series=self.plc_series,
        )
        ensure_extended_profile_feature_allowed(
            self.plc_profile,
            ref,
            effective_extension,
            strict_profile=self._strict_profile,
        )
        return address, ref, effective_extension

    def _ensure_profile_feature_allowed(self, feature_key: str) -> None:
        ensure_profile_feature_allowed(self.plc_profile, feature_key, strict_profile=self._strict_profile)

    async def connect(self) -> None:
        """Open the connection to the PLC."""
        async with self._operation_queue.turn():
            try:
                loop = asyncio.get_running_loop()
                await self._connect_unlocked(deadline=loop.time() + self.timeout)
            except (SlmpError, asyncio.CancelledError):
                raise
            except (OSError, ConnectionError) as err:
                raise SlmpTransportError(f"SLMP connection failed: {err}") from err

    async def _connect_unlocked(self, *, deadline: float) -> None:
        self._operation_queue.ensure_current()
        if self.transport_type == "tcp" and self._writer is not None:
            return
        if self.transport_type == "udp" and self._udp_transport is not None:
            return
        loop = asyncio.get_running_loop()
        socket_type = socket.SOCK_STREAM if self.transport_type == "tcp" else socket.SOCK_DGRAM
        try:
            endpoint = await asyncio.wait_for(
                resolve_ipv4_endpoint_async(self.host, self.port, socket_type),
                timeout=_connection_remaining_timeout(deadline, loop=loop),
            )
        except asyncio.TimeoutError as err:
            _raise_connection_timeout_or_transport(err, deadline=deadline, loop=loop)
        _connection_remaining_timeout(deadline, loop=loop)
        self._operation_queue.ensure_current()
        if self.transport_type == "tcp":
            fut = asyncio.open_connection(endpoint[0], endpoint[1], family=socket.AF_INET)
            try:
                reader, writer = await asyncio.wait_for(
                    fut,
                    timeout=_connection_remaining_timeout(deadline, loop=loop),
                )
            except asyncio.TimeoutError as err:
                _raise_connection_timeout_or_transport(err, deadline=deadline, loop=loop)
            try:
                raw_socket = writer.get_extra_info("socket")
                if raw_socket is None:
                    raise ConnectionError("TCP socket is unavailable; required keepalive policy cannot be applied")
                raw_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                configure_tcp_keepalive(raw_socket, idle_seconds=30)
                _connection_remaining_timeout(deadline, loop=loop)
                self._operation_queue.ensure_current()
            except BaseException:
                try:
                    writer.close()
                except Exception:
                    pass
                else:
                    cleanup_timeout = deadline - loop.time()
                    if cleanup_timeout > 0:
                        try:
                            await asyncio.wait_for(writer.wait_closed(), timeout=cleanup_timeout)
                        except BaseException:
                            pass
                raise
            self._reader = reader
            self._writer = writer
        else:
            try:
                udp_transport, udp_protocol = await asyncio.wait_for(
                    loop.create_datagram_endpoint(
                        lambda: SLMPDatagramProtocol(
                            self.frame_type,
                            self._record_receive,
                            self._retire_lost_udp_generation,
                        ),
                        remote_addr=endpoint,
                        family=socket.AF_INET,
                    ),
                    timeout=_connection_remaining_timeout(deadline, loop=loop),
                )
            except asyncio.TimeoutError as err:
                _raise_connection_timeout_or_transport(err, deadline=deadline, loop=loop)
            try:
                _connection_remaining_timeout(deadline, loop=loop)
                self._operation_queue.ensure_current()
            except BaseException:
                udp_protocol.fail_pending(SlmpClosedError("SLMP UDP transport was closed"))
                udp_transport.close()
                raise
            self._udp_transport = udp_transport
            self._udp_protocol = udp_protocol

    async def close(self) -> None:
        """Close transport and reject the active and queued operation generation."""
        self._operation_queue.invalidate()
        if self.transport_type == "tcp":
            await self._close_tcp_unlocked()
        else:
            self._close_udp_unlocked()

    async def _close_tcp_unlocked(self) -> None:
        writer = self._writer
        self._reader = None
        self._writer = None
        if writer is None:
            return
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    def _close_udp_unlocked(self) -> None:
        transport = self._udp_transport
        protocol = self._udp_protocol
        self._udp_transport = None
        self._udp_protocol = None
        if protocol is not None:
            protocol.fail_pending(SlmpClosedError("SLMP UDP transport was closed"))
        if transport is not None:
            transport.close()

    def _retire_lost_udp_generation(
        self,
        protocol: SLMPDatagramProtocol,
        _error: BaseException,
    ) -> None:
        """Retire only the UDP generation that reported asynchronous loss."""
        if self._udp_protocol is not protocol:
            return
        transport = self._udp_transport
        self._udp_transport = None
        self._udp_protocol = None
        if transport is not None:
            transport.close()

    async def __aenter__(self) -> AsyncSlmpClient:
        """Enter the async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Exit the async context manager."""
        await self.close()

    async def _request(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
        state_changing: bool | None = None,
    ) -> SlmpResponse:
        """Send an SLMP request and receive a response."""
        if monitoring_timer is not None and (
            isinstance(monitoring_timer, bool)
            or not isinstance(monitoring_timer, int)
            or not 0 <= monitoring_timer <= 0xFFFF
        ):
            raise ValueError("monitoring_timer must be an integer in range 0..65535 when provided")
        if raise_on_error is not None and type(raise_on_error) is not bool:
            raise ValueError("raise_on_error must be a boolean when provided")
        effective_state_changing = classify_command_state(int(command), state_changing)
        _validate_request_payload_length(len(data), _request_payload_limit(self.transport_type, self.frame_type))
        async with self._operation_queue.turn():
            return await self._request_unlocked(
                command,
                subcommand,
                data,
                serial=serial,
                target=target,
                monitoring_timer=monitoring_timer,
                raise_on_error=raise_on_error,
                state_changing=effective_state_changing,
                response_is_final=True,
            )

    async def _request_decoded(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        decoder: Callable[[SlmpResponse], _DecodedT],
    ) -> _DecodedT:
        """Execute a read and publish lifecycle completion after command decoding."""
        if type(self)._request is not AsyncSlmpClient._request:
            return decoder(await self._request(command, subcommand, data))
        effective_state_changing = classify_command_state(int(command), False)
        _validate_request_payload_length(len(data), _request_payload_limit(self.transport_type, self.frame_type))
        async with self._operation_queue.turn():
            response = await self._request_unlocked(
                command,
                subcommand,
                data,
                raise_on_error=self.raise_on_error,
                state_changing=effective_state_changing,
                response_is_final=False,
            )
            if response.end_code != 0:
                # A completely framed PLC end-code is definitive even when
                # raise_on_error=False delegates structured error construction
                # to the command decoder.
                return decoder(response)
            try:
                result = decoder(response)
            except BaseException:
                # A command decoder failure is published at the same lifecycle
                # boundary as a decoded value. If close linearized first, the
                # read is still incomplete and the typed closed error wins.
                self._operation_queue.ensure_current()
                raise
            self._operation_queue.ensure_current()
            return result

    async def _request_unlocked(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
        state_changing: bool | None = None,
        response_is_final: bool = True,
    ) -> SlmpResponse:
        _validate_request_payload_length(len(data), _request_payload_limit(self.transport_type, self.frame_type))
        do_raise = self.raise_on_error if raise_on_error is None else raise_on_error
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
        previous_state_changing = self._active_state_changing
        self._active_state_changing = classify_command_state(cmd, state_changing)
        try:
            raw = await self._send_and_receive(frame)
        finally:
            self._active_state_changing = previous_state_changing
        resp = decode_response(raw, frame_type=self.frame_type)

        if self._trace_hook:
            await self._emit_trace(
                _SlmpTraceFrame(
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
        if resp.end_code != 0:
            if do_raise:
                raise SlmpError(
                    f"SLMP error end_code=0x{resp.end_code:04X} command=0x{cmd:04X} subcommand=0x{subcommand:04X}",
                    end_code=resp.end_code,
                    data=resp.data,
                    error_info=resp.error_info,
                )
            return resp
        if not response_is_final:
            self._operation_queue.ensure_current()
        return resp

    async def raw_command(
        self,
        command: int | Command,
        *,
        subcommand: int,
        payload: bytes,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
        state_changing: bool | None = None,
    ) -> SlmpResponse:
        """Send one maintainer-level raw SLMP command.

        The frame serial is always allocated by the client so response
        correlation cannot be bypassed by public callers. Unknown raw commands
        are state-changing by default. Pass ``state_changing=False`` only for a
        known or vendor-specific read-only command; known state-changing
        commands cannot be downgraded.
        """
        effective_state_changing = classify_command_state(int(command), state_changing)
        return await self._request(
            command=command,
            subcommand=subcommand,
            data=payload,
            target=target,
            monitoring_timer=monitoring_timer,
            raise_on_error=raise_on_error,
            state_changing=effective_state_changing,
        )

    # --------------------
    # Device commands (typed)
    # --------------------

    async def read_devices(
        self,
        device: str | DeviceRef,
        points: int,
        *,
        bit_unit: bool,
    ) -> list[int] | list[bool]:
        """Read device values from the PLC."""
        self._ensure_profile_feature_allowed("direct")
        request = _operations.build_read_devices_request(
            device,
            points,
            bit_unit=bit_unit,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_read_devices_response(
                response,
                points=points,
                bit_unit=bit_unit,
            ),
        )

    async def write_devices(
        self,
        device: str | DeviceRef,
        values: Sequence[int | bool],
        *,
        bit_unit: bool,
    ) -> None:
        """Write device values to the PLC."""
        self._ensure_profile_feature_allowed("direct")
        request = _operations.build_write_devices_request(
            device,
            values,
            bit_unit=bit_unit,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def read_dword(
        self,
        device: str | DeviceRef,
    ) -> int:
        """Read one 32-bit value from two consecutive word devices."""
        return (await self.read_dwords(device, 1))[0]

    async def write_dword(
        self,
        device: str | DeviceRef,
        value: int,
    ) -> None:
        """Write one 32-bit value to two consecutive word devices."""
        await self.write_dwords(device, [value])

    async def read_dwords(
        self,
        device: str | DeviceRef,
        count: int,
    ) -> list[int]:
        """Read one or more 32-bit values from two consecutive word devices."""
        request = _operations.build_read_dwords_request(
            device,
            count,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_read_dwords_response(response, count=count),
        )

    async def write_dwords(
        self,
        device: str | DeviceRef,
        values: Sequence[int],
    ) -> None:
        """Write one or more 32-bit values to two consecutive word devices."""
        request = _operations.build_write_dwords_request(
            device,
            values,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def read_float32(
        self,
        device: str | DeviceRef,
    ) -> float:
        """Read one IEEE-754 float32 from two consecutive word devices."""
        return (await self.read_float32s(device, 1))[0]

    async def write_float32(
        self,
        device: str | DeviceRef,
        value: float,
    ) -> None:
        """Write one IEEE-754 float32 to two consecutive word devices."""
        await self.write_float32s(device, [value])

    async def read_float32s(
        self,
        device: str | DeviceRef,
        count: int,
    ) -> list[float]:
        """Read one or more IEEE-754 float32 values from two consecutive word devices."""
        request = _operations.build_read_dwords_request(
            device,
            count,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_read_float32s_response(response, count=count),
        )

    async def write_float32s(
        self,
        device: str | DeviceRef,
        values: Sequence[float],
    ) -> None:
        """Write one or more IEEE-754 float32 values to two consecutive word devices."""
        request = _operations.build_write_float32s_request(
            device,
            values,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def read_devices_ext(
        self,
        device: str | SlmpExtendedDevice,
        points: int,
        *,
        bit_unit: bool,
    ) -> list[int] | list[bool]:
        """Read device values using Extended Device extension."""
        self._ensure_profile_feature_allowed("direct")
        address, _, extension = self._resolve_semantic_extended_device(device)
        request = _operations.build_read_devices_ext_request(
            address,
            points,
            extension=extension,
            bit_unit=bit_unit,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_read_devices_response(
                response,
                points=points,
                bit_unit=bit_unit,
            ),
        )

    async def write_devices_ext(
        self,
        device: str | SlmpExtendedDevice,
        values: Sequence[int | bool],
        *,
        bit_unit: bool,
    ) -> None:
        """Write device values using Extended Device extension."""
        self._ensure_profile_feature_allowed("direct")
        address, _, extension = self._resolve_semantic_extended_device(device)
        request = _operations.build_write_devices_ext_request(
            address,
            values,
            extension=extension,
            bit_unit=bit_unit,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def read_random(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
    ) -> RandomReadResult:
        """Read multiple word and double-word devices in a single request."""
        self._ensure_profile_feature_allowed("random")
        operation = _operations.build_read_random_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        request = operation.request
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_read_random_response(response, operation),
        )

    async def read_random_ext(
        self,
        *,
        word_devices: Sequence[str | SlmpExtendedDevice] = (),
        dword_devices: Sequence[str | SlmpExtendedDevice] = (),
    ) -> RandomReadResult:
        """Read multiple word and double-word devices using Extended Device extension."""
        self._ensure_profile_feature_allowed("random")
        resolved_words = [
            (address, extension, _format_semantic_extended_device_key(device, plc_profile=self.plc_profile))
            for device in word_devices
            for address, _, extension in (self._resolve_semantic_extended_device(device),)
        ]
        resolved_dwords = [
            (address, extension, _format_semantic_extended_device_key(device, plc_profile=self.plc_profile))
            for device in dword_devices
            for address, _, extension in (self._resolve_semantic_extended_device(device),)
        ]
        operation = _operations.build_read_random_ext_request(
            word_devices=resolved_words,
            dword_devices=resolved_dwords,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        request = operation.request
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_read_random_response(response, operation),
        )

    async def write_random_words(
        self,
        *,
        word_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]] = (),
        dword_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]] = (),
    ) -> None:
        """Write multiple word and double-word devices in a single request."""
        self._ensure_profile_feature_allowed("random")
        request = _operations.build_write_random_words_request(
            word_values=word_values,
            dword_values=dword_values,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def write_random_words_ext(
        self,
        *,
        word_values: Sequence[tuple[str | SlmpExtendedDevice, int]] = (),
        dword_values: Sequence[tuple[str | SlmpExtendedDevice, int]] = (),
    ) -> None:
        """Write multiple word and double-word devices using Extended Device extension."""
        self._ensure_profile_feature_allowed("random")
        resolved_words = [
            (address, value, extension)
            for device, value in word_values
            for address, _, extension in (self._resolve_semantic_extended_device(device),)
        ]
        resolved_dwords = [
            (address, value, extension)
            for device, value in dword_values
            for address, _, extension in (self._resolve_semantic_extended_device(device),)
        ]
        request = _operations.build_write_random_words_ext_request(
            word_values=resolved_words,
            dword_values=resolved_dwords,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def write_random_bits(
        self,
        bit_values: Mapping[str | DeviceRef, bool] | Sequence[tuple[str | DeviceRef, bool]],
    ) -> None:
        """Write multiple bit devices in a single request."""
        self._ensure_profile_feature_allowed("random")
        request = _operations.build_write_random_bits_request(
            bit_values,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def write_random_bits_ext(
        self,
        bit_values: Sequence[tuple[str | SlmpExtendedDevice, bool]],
    ) -> None:
        """Write multiple bit devices using Extended Device extension."""
        self._ensure_profile_feature_allowed("random")
        resolved_values = [
            (address, value, extension)
            for device, value in bit_values
            for address, _, extension in (self._resolve_semantic_extended_device(device),)
        ]
        request = _operations.build_write_random_bits_ext_request(
            resolved_values,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def register_monitor_devices(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
    ) -> None:
        """Register devices for monitoring."""
        self._ensure_profile_feature_allowed("monitor")
        request = _operations.build_register_monitor_devices_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def register_monitor_devices_ext(
        self,
        *,
        word_devices: Sequence[str | SlmpExtendedDevice] = (),
        dword_devices: Sequence[str | SlmpExtendedDevice] = (),
    ) -> None:
        """Register devices for monitoring using Extended Device extension."""
        self._ensure_profile_feature_allowed("monitor")
        resolved_words = [
            (address, extension)
            for device in word_devices
            for address, _, extension in (self._resolve_semantic_extended_device(device),)
        ]
        resolved_dwords = [
            (address, extension)
            for device in dword_devices
            for address, _, extension in (self._resolve_semantic_extended_device(device),)
        ]
        request = _operations.build_register_monitor_devices_ext_request(
            word_devices=resolved_words,
            dword_devices=resolved_dwords,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        await self._request(request.command, subcommand=request.subcommand, data=request.payload)

    async def run_monitor_cycle(self, *, word_points: int, dword_points: int) -> MonitorResult:
        """Execute one cycle with a nonzero count within the profile monitor limit."""
        self._ensure_profile_feature_allowed("monitor")
        request = _operations.build_run_monitor_cycle_request(
            word_points=word_points,
            dword_points=dword_points,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_run_monitor_cycle_response(
                response,
                word_points=word_points,
                dword_points=dword_points,
            ),
        )

    async def read_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, int]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, int]] = (),
    ) -> BlockReadResult:
        """Read multiple blocks of devices."""
        self._ensure_profile_feature_allowed("block")
        if not word_blocks and not bit_blocks:
            raise ValueError("word_blocks and bit_blocks must not both be empty")
        if len(word_blocks) > 0xFF or len(bit_blocks) > 0xFF:
            raise ValueError("word_blocks and bit_blocks must be <= 255 each")
        operation = _operations.build_read_block_request(
            word_blocks=word_blocks,
            bit_blocks=bit_blocks,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        request = operation.request
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_read_block_response(response, operation),
        )

    async def write_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
    ) -> None:
        """Write multiple blocks of devices."""
        self._ensure_profile_feature_allowed("block")
        if not word_blocks and not bit_blocks:
            raise ValueError("word_blocks and bit_blocks must not both be empty")
        if len(word_blocks) > 0xFF or len(bit_blocks) > 0xFF:
            raise ValueError("word_blocks and bit_blocks must be <= 255 each")
        request = _operations.build_write_block_request(
            word_blocks=word_blocks,
            bit_blocks=bit_blocks,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        effective_raise_on_error = self.raise_on_error
        resp = await self._request(
            request.command,
            subcommand=request.subcommand,
            data=request.payload,
            raise_on_error=False,
        )
        if resp.end_code == 0:
            return
        if effective_raise_on_error:
            _raise_response_error(resp, command=request.command, subcommand=request.subcommand)

    # --------------------
    # Remote / Administrative
    # --------------------

    async def read_type_name(self) -> TypeNameInfo:
        """Read the PLC type name and model code."""
        self._ensure_profile_feature_allowed("type_name")
        request = _operations.build_read_type_name_request()
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            _operations.decode_read_type_name_response,
        )

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

    async def remote_run(self, *, force: bool, clear_mode: RemoteClearMode) -> None:
        """Remote run the PLC."""
        if type(force) is not bool:
            raise ValueError("force must be a boolean")
        if not isinstance(clear_mode, RemoteClearMode):
            raise ValueError("clear_mode must be a RemoteClearMode")
        request = _operations.build_remote_run_request(force=force, clear_mode=int(clear_mode))
        await self._request(request.command, request.subcommand, request.payload)

    async def remote_stop(self) -> None:
        """Remote stop the PLC."""
        request = _operations.build_remote_stop_request()
        await self._request(request.command, request.subcommand, request.payload)

    async def remote_pause(self, *, force: bool) -> None:
        """Remote pause the PLC."""
        if type(force) is not bool:
            raise ValueError("force must be a boolean")
        request = _operations.build_remote_pause_request(force=force)
        await self._request(request.command, request.subcommand, request.payload)

    async def remote_latch_clear(self) -> None:
        """Remote latch clear the PLC."""
        request = _operations.build_remote_latch_clear_request()
        await self._request(request.command, request.subcommand, request.payload)

    async def clear_error(self) -> None:
        """Clear the current PLC error using the fixed semantic command."""
        request = _operations.build_clear_error_request()
        await self._request(request.command, request.subcommand, request.payload)

    async def remote_reset(self) -> None:
        """Remote reset the PLC without waiting for a response."""
        request = _operations.build_remote_reset_request(subcommand=0x0000)
        await self._send_no_response(request.command, request.subcommand, request.payload)

    async def remote_password_lock(self, password: str) -> None:
        """Remote password lock the PLC."""
        request = _operations.build_remote_password_lock_request(
            password,
            series=None,
            default_series=self.plc_series,
        )
        await self._request(request.command, request.subcommand, request.payload)

    async def remote_password_unlock(self, password: str) -> None:
        """Remote password unlock the PLC."""
        request = _operations.build_remote_password_unlock_request(
            password,
            series=None,
            default_series=self.plc_series,
        )
        await self._request(request.command, request.subcommand, request.payload)

    async def self_test_loopback(self, data: bytes | str) -> bytes:
        """Execute a self-test loopback."""
        request = _operations.build_self_test_loopback_request(data)
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_self_test_loopback_response(
                response,
                expected=request.payload[2:],
            ),
        )

    # --------------------
    # Label commands
    # --------------------

    async def read_array_labels(
        self, points: Sequence[LabelArrayReadPoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> list[LabelArrayReadResult]:
        """Read array labels from the PLC."""
        requested_points = tuple(points)
        request = _operations.build_read_array_labels_request(requested_points, abbreviation_labels=abbreviation_labels)
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.parse_array_label_read_response(
                response.data,
                requested_points=requested_points,
            ),
        )

    async def write_array_labels(
        self, points: Sequence[LabelArrayWritePoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> None:
        """Write array labels to the PLC."""
        request = _operations.build_write_array_labels_request(points, abbreviation_labels=abbreviation_labels)
        await self._request(request.command, request.subcommand, request.payload)

    async def read_random_labels(
        self, labels: Sequence[str], *, abbreviation_labels: Sequence[str] = ()
    ) -> list[LabelRandomReadResult]:
        """Read random labels from the PLC."""
        requested_labels = tuple(labels)
        request = _operations.build_read_random_labels_request(
            requested_labels, abbreviation_labels=abbreviation_labels
        )
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.parse_label_read_random_response(
                response.data,
                expected_points=len(requested_labels),
            ),
        )

    async def write_random_labels(
        self, points: Sequence[LabelRandomWritePoint], *, abbreviation_labels: Sequence[str] = ()
    ) -> None:
        """Write random labels to the PLC."""
        request = _operations.build_write_random_labels_request(points, abbreviation_labels=abbreviation_labels)
        await self._request(request.command, request.subcommand, request.payload)

    # --------------------
    # Memory
    # --------------------

    async def memory_read_words(self, head_address: int, word_length: int) -> list[int]:
        """Read memory words from the PLC."""
        request = _operations.build_memory_read_words_request(head_address, word_length)
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_memory_read_words_response(response, word_length=word_length),
        )

    async def memory_write_words(self, head_address: int, values: Sequence[int]) -> None:
        """Write memory words to the PLC."""
        request = _operations.build_memory_write_words_request(head_address, values)
        await self._request(request.command, request.subcommand, request.payload)

    async def extend_unit_read_words(self, head_address: int, word_length: int, module_no: int) -> list[int]:
        """Read words from an extend unit."""
        request = _operations.build_extend_unit_read_words_request(head_address, word_length, module_no)
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_extend_unit_read_words_response(
                response,
                word_length=word_length,
            ),
        )

    async def extend_unit_write_words(self, head_address: int, module_no: int, values: Sequence[int]) -> None:
        """Write words to an extend unit."""
        request = _operations.build_extend_unit_write_words_request(head_address, module_no, values)
        await self._request(request.command, request.subcommand, request.payload)

    async def read_long_timer(self, *, head_no: int, points: int) -> list[LongTimerResult]:
        """Read long timers from the PLC."""
        head_no, word_points = _operations._validate_long_timer_range(head_no, points, self.plc_profile)
        words_raw = await self.read_devices(f"LTN{head_no}", word_points, bit_unit=False)
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

    async def read_long_retentive_timer(self, *, head_no: int, points: int) -> list[LongTimerResult]:
        """Read long retentive timers from the PLC."""
        head_no, word_points = _operations._validate_long_timer_range(head_no, points, self.plc_profile)
        words_raw = await self.read_devices(f"LSTN{head_no}", word_points, bit_unit=False)
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

    async def read_ltc_states(self, *, head_no: int, points: int) -> list[bool]:
        """Read long timer coil states."""
        return [item.coil for item in await self.read_long_timer(head_no=head_no, points=points)]

    async def read_lts_states(self, *, head_no: int, points: int) -> list[bool]:
        """Read long timer contact states."""
        return [item.contact for item in await self.read_long_timer(head_no=head_no, points=points)]

    async def read_lstc_states(self, *, head_no: int, points: int) -> list[bool]:
        """Read long retentive timer coil states."""
        items = await self.read_long_retentive_timer(head_no=head_no, points=points)
        return [item.coil for item in items]

    async def read_lsts_states(self, *, head_no: int, points: int) -> list[bool]:
        """Read long retentive timer contact states."""
        items = await self.read_long_retentive_timer(head_no=head_no, points=points)
        return [item.contact for item in items]

    async def extend_unit_read_bytes(self, head_address: int, byte_length: int, module_no: int) -> bytes:
        """Read bytes from an extend unit."""
        request = _operations.build_extend_unit_read_bytes_request(head_address, byte_length, module_no)
        return await self._request_decoded(
            request.command,
            request.subcommand,
            request.payload,
            lambda response: _operations.decode_extend_unit_read_bytes_response(
                response,
                byte_length=byte_length,
            ),
        )

    async def extend_unit_read_word(self, head_address: int, module_no: int) -> int:
        """Read a single word from an extend unit."""
        return (await self.extend_unit_read_words(head_address, 1, module_no))[0]

    async def extend_unit_read_dword(self, head_address: int, module_no: int) -> int:
        """Read a double word from an extend unit."""
        return int.from_bytes(await self.extend_unit_read_bytes(head_address, 4, module_no), "little", signed=False)

    async def extend_unit_write_bytes(self, head_address: int, module_no: int, data: bytes) -> None:
        """Write bytes to an extend unit."""
        request = _operations.build_extend_unit_write_bytes_request(head_address, module_no, data)
        await self._request(request.command, request.subcommand, request.payload)

    async def extend_unit_write_word(self, head_address: int, module_no: int, value: int) -> None:
        """Write a single word to an extend unit."""
        request = _operations.build_extend_unit_write_word_request(head_address, module_no, value)
        await self._request(request.command, request.subcommand, request.payload)

    async def extend_unit_write_dword(self, head_address: int, module_no: int, value: int) -> None:
        """Write a double word to an extend unit."""
        request = _operations.build_extend_unit_write_dword_request(head_address, module_no, value)
        await self._request(request.command, request.subcommand, request.payload)

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
        if monitoring_timer is not None and (
            isinstance(monitoring_timer, bool)
            or not isinstance(monitoring_timer, int)
            or not 0 <= monitoring_timer <= 0xFFFF
        ):
            raise ValueError("monitoring_timer must be an integer in range 0..65535 when provided")
        _validate_request_payload_length(len(data), _request_payload_limit(self.transport_type, self.frame_type))
        async with self._operation_queue.turn():
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
            attempted_send = False
            try:
                loop = asyncio.get_running_loop()
                deadline = loop.time() + self.timeout
                await self._connect_unlocked(deadline=deadline)
                self._operation_queue.ensure_current()
                if self.transport_type == "tcp":
                    if self._writer is None:
                        raise SlmpNotConnectedError("TCP connection is not open")
                    attempted_send = True
                    self._writer.write(frame)
                    await asyncio.wait_for(self._writer.drain(), timeout=_remaining_timeout(deadline, loop=loop))
                else:
                    if self._udp_transport is None:
                        raise SlmpNotConnectedError("UDP endpoint is not open")
                    attempted_send = True
                    self._udp_transport.sendto(frame)
                self._record_send(len(frame))
                self._operation_queue.ensure_current()
            except BaseException as err:
                failure: BaseException = err
                try:
                    self._operation_queue.ensure_current()
                except SlmpClosedError as closed:
                    failure = closed
                classified = _classify_exchange_failure(failure, state_changing=True, attempted_send=attempted_send)
                if classified is err:
                    raise
                raise classified from failure
            finally:
                if self.transport_type == "tcp":
                    await self._close_tcp_unlocked()
                else:
                    self._close_udp_unlocked()
            try:
                await self._emit_trace(
                    _SlmpTraceFrame(
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
                self._operation_queue.ensure_current()
            except BaseException as err:
                failure = err
                try:
                    self._operation_queue.ensure_current()
                except SlmpClosedError as closed:
                    failure = closed
                classified = _classify_exchange_failure(failure, state_changing=True, attempted_send=attempted_send)
                if classified is err:
                    raise
                raise classified from failure
        # A send-only command can still produce an NG response. 3E has no
        # serial field, so retaining this transport could assign that response
        # to the next request. Reconnection is therefore mandatory.

    async def _send_and_receive(self, frame: bytes) -> bytes:
        """Send a frame and receive the response."""
        loop = asyncio.get_running_loop()
        expected_identity = _request_identity(frame, frame_type=self.frame_type)
        async with self._operation_queue.turn():
            attempted_send = False
            try:
                deadline = loop.time() + self.timeout
                await self._connect_unlocked(deadline=deadline)
                self._operation_queue.ensure_current()
                if self.transport_type == "tcp":
                    if self._writer is None:
                        raise SlmpNotConnectedError("TCP connection is not open")
                    attempted_send = True
                    self._writer.write(frame)
                    remaining = _remaining_timeout(deadline, loop=loop)
                    await asyncio.wait_for(self._writer.drain(), timeout=remaining)
                    self._record_send(len(frame))
                    while True:
                        raw = await self._receive_frame(deadline=deadline)
                        if _response_matches_request(
                            raw, frame_type=self.frame_type, expected_identity=expected_identity
                        ):
                            self._operation_queue.ensure_current()
                            return raw
                else:
                    if self._udp_transport is None or self._udp_protocol is None:
                        raise SlmpNotConnectedError("UDP endpoint is not open")
                    protocol = self._udp_protocol
                    protocol.set_datagram_accounting(self._record_receive)
                    waiter = protocol.begin_response_wait(expected_identity)
                    attempted_send = True
                    try:
                        self._udp_transport.sendto(frame)
                        self._record_send(len(frame))
                        remaining = _remaining_timeout(deadline, loop=loop)
                        raw = await asyncio.wait_for(waiter, timeout=remaining)
                        self._operation_queue.ensure_current()
                        return raw
                    finally:
                        protocol.forget_response_wait(waiter)
            except BaseException as err:
                failure = err
                try:
                    self._operation_queue.ensure_current()
                except SlmpClosedError as closed:
                    failure = closed
                if self.transport_type == "tcp":
                    await self._close_tcp_unlocked()
                else:
                    self._close_udp_unlocked()
                classified = _classify_exchange_failure(
                    failure,
                    state_changing=self._active_state_changing,
                    attempted_send=attempted_send,
                )
                if classified is err:
                    raise
                raise classified from failure

    async def _receive_frame(self, *, deadline: float) -> bytes:
        """Receive a single SLMP frame."""
        assert self._reader is not None
        head_size = 13 if self.frame_type == FrameType.FRAME_4E else 9
        loop = asyncio.get_running_loop()
        try:
            head_timeout = _remaining_timeout(deadline, loop=loop)
            head = await asyncio.wait_for(self._reader.readexactly(head_size), timeout=head_timeout)
            expected_subheader = b"\xd4\x00" if self.frame_type == FrameType.FRAME_4E else b"\xd0\x00"
            if head[:2] != expected_subheader:
                raise SlmpError("unexpected response frame type")
            response_data_length = int.from_bytes(head[-2:], "little")
            tail_timeout = _remaining_timeout(deadline, loop=loop)
            tail = await asyncio.wait_for(self._reader.readexactly(response_data_length), timeout=tail_timeout)
            frame = head + tail
            self._record_receive(len(frame))
            return frame
        except asyncio.IncompleteReadError as err:
            raise SlmpTransportError("connection closed while receiving data") from err

    async def _emit_trace(self, trace: _SlmpTraceFrame) -> None:
        """Emit a trace event if a trace hook is registered."""
        if self._trace_hook:
            try:
                if asyncio.iscoroutinefunction(self._trace_hook):
                    await self._trace_hook(trace)
                else:
                    self._trace_hook(trace)
            except Exception:
                pass


def _response_matches_request(
    raw: bytes,
    *,
    frame_type: FrameType,
    expected_identity: tuple[int | None, SlmpTarget],
) -> bool:
    """Validate one complete response and match its request identity."""
    response = decode_response(raw, frame_type=frame_type)
    expected_serial, expected_target = expected_identity
    if (
        response.target.network != expected_target.network
        or response.target.station != expected_target.station
        or response.target.module_io != expected_target.module_io
        or response.target.multidrop != expected_target.multidrop
    ):
        return False
    return expected_serial is None or response.serial == expected_serial


def _request_identity(frame: bytes, *, frame_type: FrameType) -> tuple[int | None, SlmpTarget]:
    """Extract the required response identity from one encoded request frame."""
    if frame_type == FrameType.FRAME_4E:
        if len(frame) < 11 or frame[:2] != b"\x54\x00":
            raise SlmpError("invalid 4E request frame")
        serial: int | None = int.from_bytes(frame[2:4], "little")
        offset = 6
    else:
        if len(frame) < 7 or frame[:2] != b"\x50\x00":
            raise SlmpError("invalid 3E request frame")
        serial = None
        offset = 2
    return serial, SlmpTarget(
        network=frame[offset],
        station=frame[offset + 1],
        module_io=int.from_bytes(frame[offset + 2 : offset + 4], "little"),
        multidrop=frame[offset + 4],
    )


def _remaining_timeout(deadline: float, *, loop: asyncio.AbstractEventLoop) -> float:
    remaining = deadline - loop.time()
    if remaining <= 0:
        raise TimeoutError(_COMMUNICATION_TIMEOUT_MESSAGE)
    return remaining


def _connection_remaining_timeout(deadline: float, *, loop: asyncio.AbstractEventLoop) -> float:
    remaining = deadline - loop.time()
    if remaining <= 0:
        raise SlmpTimeoutError("SLMP connection timeout")
    return remaining


def _raise_connection_timeout_or_transport(
    error: asyncio.TimeoutError | TimeoutError,
    *,
    deadline: float,
    loop: asyncio.AbstractEventLoop,
) -> NoReturn:
    # ``asyncio.wait_for`` reports its own deadline by chaining the
    # TimeoutError from the cancellation it injected.  On Windows the event
    # loop clock can still appear a few milliseconds before ``deadline`` at
    # that point, so the clock comparison alone misclassifies a real timeout
    # as a transport failure.
    if isinstance(error.__cause__, asyncio.CancelledError) or deadline - loop.time() <= 0:
        raise SlmpTimeoutError("SLMP connection timeout") from error
    raise SlmpTransportError(f"SLMP connection failed before its deadline: {error}") from error


def _classify_exchange_failure(
    error: BaseException,
    *,
    state_changing: bool,
    attempted_send: bool,
) -> BaseException:
    if isinstance(error, SlmpOutcomeUnknownError):
        return error
    if isinstance(error, SlmpClosedError):
        reason = SlmpOutcomeUnknownReason.CLOSED
        definite: BaseException = error
    elif isinstance(error, SlmpTimeoutError):
        reason = SlmpOutcomeUnknownReason.TIMEOUT
        definite = error
    elif isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        reason = SlmpOutcomeUnknownReason.TIMEOUT
        definite = SlmpTimeoutError(_COMMUNICATION_TIMEOUT_MESSAGE)
    elif isinstance(error, asyncio.CancelledError):
        reason = SlmpOutcomeUnknownReason.CANCELLED
        definite = error
    elif isinstance(error, SlmpTransportError):
        reason = SlmpOutcomeUnknownReason.TRANSPORT
        definite = error
    elif isinstance(error, SlmpError):
        reason = SlmpOutcomeUnknownReason.PROTOCOL
        definite = error
    elif isinstance(error, (OSError, ConnectionError)):
        reason = SlmpOutcomeUnknownReason.TRANSPORT
        definite = SlmpTransportError(f"SLMP transport failure: {error}")
    else:
        return error
    if state_changing and attempted_send:
        return SlmpOutcomeUnknownError(
            f"SLMP state-changing operation outcome is unknown ({reason.value})",
            reason=reason,
            cause=error,
        )
    return definite
