"""SLMP binary client."""

from __future__ import annotations

import math
import socket
import threading
from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from typing import TYPE_CHECKING

from . import _operations
from ._socket_options import configure_tcp_keepalive
from .capability_profiles import ensure_extended_profile_feature_allowed, ensure_profile_feature_allowed
from .constants import Command, FrameType, PLCSeries, RemoteClearMode
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
    _build_device_modification_flags,
    _ExtensionSpec,
    _format_semantic_extended_device_key,
    _parse_extended_device,
    _raise_response_error,
    _require_explicit_plc_profile_for_xy,
    _resolve_connection_profile,
    _resolve_extended_device_and_extension,
    _resolve_port,
    _SlmpTraceFrame,
    decode_cpu_operation_state,
    decode_response,
    encode_request,
    parse_device,
)
from .errors import SlmpError

_EXPECTED_RESPONSE_SERIAL: ContextVar[int | None] = ContextVar("slmp_expected_response_serial", default=None)

if TYPE_CHECKING:
    from .core import SlmpPlcProfile
    from .device_ranges import SlmpDeviceRangeCatalog


class SlmpClient:
    """Synchronous SLMP client supporting 3E and 4E frames (binary).

    This client provides high-level typed APIs for interacting with MELSEC
    and compatible PLCs using the SLMP protocol.

    Examples:
        >>> from slmp.client import SlmpClient
        >>> with SlmpClient("192.168.250.100", 1025, plc_profile="melsec:iq-r") as client:
        ...     values = client.read_devices("D100", 5, bit_unit=False)
        ...     print(values)
        [0, 0, 0, 0, 0]
    """

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
        _maintainer_trace_hook: Callable[[_SlmpTraceFrame], None] | None = None,
        _maintainer_strict_profile: bool = True,
    ) -> None:
        """Initialize the SLMP client.

        Args:
            host: PLC IP address.
            port: Required PLC port number in range 1..65535.
            transport: Required transport protocol (``"tcp"`` or ``"udp"``).
            timeout: Socket timeout in seconds. Defaults to 3.0.
            plc_profile: Canonical high-level PLC profile. The standard client
                route requires this and derives frame type, access profile,
                and address/range handling from it.
            default_target: Default target station routing information.
            monitoring_timer: Default monitoring timer value (multiples of 250ms). Defaults to 0x0010 (4s).
            raise_on_error: Whether to raise SlmpError on non-zero end codes. Defaults to True.
        """
        self.host = host
        if not isinstance(transport, str):
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.transport = transport.strip().lower()
        if self.transport not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.port = _resolve_port(port, self.transport)
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a finite number greater than zero")
        self.timeout = float(timeout)
        if plc_profile is None:
            raise ValueError("plc_profile is required for SlmpClient")
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
        self._request_lock = threading.RLock()
        self._sock: socket.socket | None = None
        self._request_count = 0
        self._tx_bytes = 0
        self._rx_bytes = 0

    def traffic_stats(self) -> SlmpTrafficStats:
        """Return a read-only snapshot of cumulative traffic for this client lifetime."""
        with self._request_lock:
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

    def connect(self) -> None:
        """Open the connection to the PLC.

        Raises:
            socket.error: If the connection fails.
        """
        if self._sock is not None:
            return
        sock_type = socket.SOCK_STREAM if self.transport == "tcp" else socket.SOCK_DGRAM
        sock = socket.socket(socket.AF_INET, sock_type)
        try:
            sock.settimeout(self.timeout)
            if self.transport == "tcp":
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                configure_tcp_keepalive(sock, idle_seconds=30)
            sock.connect((self.host, self.port))
        except BaseException:
            try:
                sock.close()
            except Exception:
                pass
            raise
        self._sock = sock

    def close(self) -> None:
        """Close the connection to the PLC."""
        if self._sock is None:
            return
        self._sock.close()
        self._sock = None

    def __enter__(self) -> SlmpClient:
        """Enter the context manager and open the connection."""
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        """Exit the context manager and close the connection."""
        self.close()

    def _request(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
    ) -> SlmpResponse:
        """Serialize one request on this client connection."""
        if monitoring_timer is not None and (
            isinstance(monitoring_timer, bool)
            or not isinstance(monitoring_timer, int)
            or not 0 <= monitoring_timer <= 0xFFFF
        ):
            raise ValueError("monitoring_timer must be an integer in range 0..65535 when provided")
        if raise_on_error is not None and type(raise_on_error) is not bool:
            raise ValueError("raise_on_error must be a boolean when provided")
        effective_raise_on_error = self.raise_on_error if raise_on_error is None else raise_on_error
        with self._request_lock:
            return self._request_unlocked(
                command,
                subcommand,
                data,
                serial=serial,
                target=target,
                monitoring_timer=monitoring_timer,
                raise_on_error=effective_raise_on_error,
            )

    def _request_unlocked(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
    ) -> SlmpResponse:
        """Send an internal SLMP request and return the response.

        Args:
            command: SLMP command code (e.g. 0x0401).
            subcommand: SLMP subcommand code (e.g. 0x0002).
            data: Binary payload for the command.
            serial: Serial number for the request. Auto-generated if None.
            target: Target station information. Defaults to `default_target`.
            monitoring_timer: Monitoring timer value for this request.
            raise_on_error: Override the default `raise_on_error` setting.

        Returns:
            Decoded response from the PLC.

        Raises:
            SlmpError: If the PLC returns a non-zero end code and error raising is enabled.
            socket.error: If a communication error occurs.
        """
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
        expected_serial = serial_no if self.frame_type == FrameType.FRAME_4E else None
        token = _EXPECTED_RESPONSE_SERIAL.set(expected_serial)
        try:
            raw = self._send_and_receive(frame)
        finally:
            _EXPECTED_RESPONSE_SERIAL.reset(token)
        resp = decode_response(raw, frame_type=self.frame_type)
        self._emit_trace(
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

        do_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        if do_raise and resp.end_code != 0:
            raise SlmpError(
                f"SLMP error end_code=0x{resp.end_code:04X} command=0x{cmd:04X} subcommand=0x{subcommand:04X}",
                end_code=resp.end_code,
                data=resp.data,
                error_info=resp.error_info,
            )
        return resp

    def raw_command(
        self,
        command: int | Command,
        *,
        subcommand: int,
        payload: bytes,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
    ) -> SlmpResponse:
        """Send one maintainer-level raw SLMP command.

        The frame serial is always allocated by the client so response
        correlation cannot be bypassed by public callers.
        """
        return self._request(
            command=command,
            subcommand=subcommand,
            data=payload,
            target=target,
            monitoring_timer=monitoring_timer,
            raise_on_error=raise_on_error,
        )

    @staticmethod
    def _make_extension_spec(
        *,
        extension_specification: int,
        extension_specification_modification: int,
        device_modification_index: int,
        use_indirect_specification: bool,
        register_mode: str,
        direct_memory_specification: int,
        series: PLCSeries | str,
    ) -> _ExtensionSpec:
        """Build a raw extension specification for maintainer probe commands."""
        resolved_series = PLCSeries(series)
        return _ExtensionSpec(
            extension_specification=extension_specification,
            extension_specification_modification=extension_specification_modification,
            device_modification_index=device_modification_index,
            device_modification_flags=_build_device_modification_flags(
                series=resolved_series,
                use_indirect_specification=use_indirect_specification,
                register_mode=register_mode,
            ),
            direct_memory_specification=direct_memory_specification,
        )

    # --------------------
    # Device commands (typed)
    # --------------------

    def read_devices(
        self,
        device: str | DeviceRef,
        points: int,
        *,
        bit_unit: bool,
    ) -> list[int] | list[bool]:
        """Read device values from the PLC.

        Args:
            device: Device reference string (e.g. 'D100', 'X0') or `DeviceRef`.
            points: Number of consecutive points to read.
            bit_unit: If True, read in bit units (returns list of bool);
                otherwise read in word units (returns list of int).

        Returns:
            A list of integers (for word units) or booleans (for bit units).

        Raises:
            SlmpError: If the PLC returns an error code.
            ValueError: If `points` is out of valid range (0-65535).
        """
        self._ensure_profile_feature_allowed("direct")
        request = _operations.build_read_devices_request(
            device,
            points,
            bit_unit=bit_unit,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        resp = self._request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_devices_response(resp, points=points, bit_unit=bit_unit)

    def write_devices(
        self,
        device: str | DeviceRef,
        values: Sequence[int | bool],
        *,
        bit_unit: bool,
    ) -> None:
        """Write values to PLC devices.

        Args:
            device: Starting device reference (e.g. 'D100', 'Y0') or `DeviceRef`.
            values: Sequence of values to write.
            bit_unit: If True, write in bit units (expects Sequence[bool]);
                otherwise write in word units (expects Sequence[int]).

        Raises:
            SlmpError: If the PLC returns an error code.
            ValueError: If `values` is empty or exceeds valid protocol limits.
        """
        self._ensure_profile_feature_allowed("direct")
        request = _operations.build_write_devices_request(
            device,
            values,
            bit_unit=bit_unit,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def read_dword(
        self,
        device: str | DeviceRef,
    ) -> int:
        """Read one 32-bit value from two consecutive word devices."""
        return self.read_dwords(device, 1)[0]

    def write_dword(
        self,
        device: str | DeviceRef,
        value: int,
    ) -> None:
        """Write one 32-bit value to two consecutive word devices."""
        self.write_dwords(device, [value])

    def read_dwords(
        self,
        device: str | DeviceRef,
        count: int,
    ) -> list[int]:
        """Read one or more 32-bit values from consecutive word devices."""
        request = _operations.build_read_dwords_request(
            device,
            count,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        resp = self._request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_dwords_response(resp, count=count)

    def write_dwords(
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
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def read_float32(
        self,
        device: str | DeviceRef,
    ) -> float:
        """Read one IEEE-754 float32 from two consecutive word devices."""
        return self.read_float32s(device, 1)[0]

    def write_float32(
        self,
        device: str | DeviceRef,
        value: float,
    ) -> None:
        """Write one IEEE-754 float32 to two consecutive word devices."""
        self.write_float32s(device, [value])

    def read_float32s(
        self,
        device: str | DeviceRef,
        count: int,
    ) -> list[float]:
        """Read one or more IEEE-754 float32 values from consecutive word devices."""
        request = _operations.build_read_dwords_request(
            device,
            count,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        resp = self._request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_float32s_response(resp, count=count)

    def write_float32s(
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
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def read_devices_ext(
        self,
        device: str | SlmpExtendedDevice,
        points: int,
        *,
        bit_unit: bool,
    ) -> list[int] | list[bool]:
        """Read a qualified Extended Device address with fields derived from the address."""
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
        resp = self._request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_devices_response(resp, points=points, bit_unit=bit_unit)

    def _read_devices_ext_raw(
        self,
        device: str | DeviceRef,
        points: int,
        *,
        extension: _ExtensionSpec,
        bit_unit: bool,
        series: PLCSeries | str | None = None,
    ) -> list[int] | list[bool]:
        """Execute a raw Extended Device read for maintainer probes."""
        self._ensure_profile_feature_allowed("direct")
        ref, effective_extension = _resolve_extended_device_and_extension(
            device,
            extension,
            plc_profile=self.plc_profile,
        )
        ensure_extended_profile_feature_allowed(
            self.plc_profile,
            ref,
            effective_extension,
            strict_profile=self._strict_profile,
        )
        request = _operations.build_read_devices_ext_request(
            device,
            points,
            extension=extension,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        resp = self._request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_devices_response(resp, points=points, bit_unit=bit_unit)

    def write_devices_ext(
        self,
        device: str | SlmpExtendedDevice,
        values: Sequence[int | bool],
        *,
        bit_unit: bool,
    ) -> None:
        """Write a qualified Extended Device address with fields derived from the address."""
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
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def _write_devices_ext_raw(
        self,
        device: str | DeviceRef,
        values: Sequence[int | bool],
        *,
        extension: _ExtensionSpec,
        bit_unit: bool,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Execute a raw Extended Device write for maintainer probes."""
        self._ensure_profile_feature_allowed("direct")
        ref, effective_extension = _resolve_extended_device_and_extension(
            device,
            extension,
            plc_profile=self.plc_profile,
        )
        ensure_extended_profile_feature_allowed(
            self.plc_profile,
            ref,
            effective_extension,
            strict_profile=self._strict_profile,
        )
        request = _operations.build_write_devices_ext_request(
            device,
            values,
            extension=extension,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def read_random(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
    ) -> RandomReadResult:
        """Read multiple word and double-word devices at random.

        Args:
            word_devices: List of word devices to read.
            dword_devices: List of double-word devices to read.

        """
        self._ensure_profile_feature_allowed("random")
        operation = _operations.build_read_random_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        resp = self._request(
            operation.request.command,
            subcommand=operation.request.subcommand,
            data=operation.request.payload,
        )
        return _operations.decode_read_random_response(resp, operation)

    def read_random_ext(
        self,
        *,
        word_devices: Sequence[str | SlmpExtendedDevice] = (),
        dword_devices: Sequence[str | SlmpExtendedDevice] = (),
    ) -> RandomReadResult:
        """Read multiple word and double-word devices at random using Extended Device extensions.

        Args:
            word_devices: Qualified word-device addresses.
            dword_devices: Qualified double-word-device addresses.

        """
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
        resp = self._request(
            operation.request.command,
            subcommand=operation.request.subcommand,
            data=operation.request.payload,
        )
        return _operations.decode_read_random_response(resp, operation)

    def write_random_words(
        self,
        *,
        word_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]] = (),
        dword_values: Mapping[str | DeviceRef, int] | Sequence[tuple[str | DeviceRef, int]] = (),
    ) -> None:
        """Write multiple word and double-word values at random.

        Args:
            word_values: Mapping or sequence of (device, value) for word devices.
            dword_values: Mapping or sequence of (device, value) for double-word devices.

        """
        self._ensure_profile_feature_allowed("random")
        request = _operations.build_write_random_words_request(
            word_values=word_values,
            dword_values=dword_values,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def write_random_words_ext(
        self,
        *,
        word_values: Sequence[tuple[str | SlmpExtendedDevice, int]] = (),
        dword_values: Sequence[tuple[str | SlmpExtendedDevice, int]] = (),
    ) -> None:
        """Write multiple word and double-word values at random using Extended Device extensions.

        Args:
            word_values: Qualified (device, value) pairs for word devices.
            dword_values: Qualified (device, value) pairs for double-word devices.

        """
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
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def write_random_bits(
        self,
        bit_values: Mapping[str | DeviceRef, bool | int] | Sequence[tuple[str | DeviceRef, bool | int]],
    ) -> None:
        """Write multiple bit values at random.

        Args:
            bit_values: Mapping or sequence of (device, value) for bit devices.

        """
        self._ensure_profile_feature_allowed("random")
        request = _operations.build_write_random_bits_request(
            bit_values,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def write_random_bits_ext(
        self,
        bit_values: Sequence[tuple[str | SlmpExtendedDevice, bool | int]],
    ) -> None:
        """Write multiple bit values at random using Extended Device extensions.

        Args:
            bit_values: Qualified (device, value) pairs for bit devices.

        """
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
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def register_monitor_devices(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
    ) -> None:
        """Register word and double-word devices for monitoring.

        Args:
            word_devices: List of word devices to monitor.
            dword_devices: List of double-word devices to monitor.

        """
        self._ensure_profile_feature_allowed("monitor")
        request = _operations.build_register_monitor_devices_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=None,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def register_monitor_devices_ext(
        self,
        *,
        word_devices: Sequence[str | SlmpExtendedDevice] = (),
        dword_devices: Sequence[str | SlmpExtendedDevice] = (),
    ) -> None:
        """Register devices for monitoring using Extended Device extensions.

        Args:
            word_devices: Qualified word-device addresses.
            dword_devices: Qualified double-word-device addresses.

        """
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
        self._request(request.command, subcommand=request.subcommand, data=request.payload)

    def run_monitor_cycle(self, *, word_points: int, dword_points: int) -> MonitorResult:
        """Execute a monitoring cycle for previously registered devices.

        Args:
            word_points: Number of registered word points. Combined count must
                be within the active profile's monitor-registration limit.
            dword_points: Number of registered double-word points. Both counts
                cannot be zero.

        Returns:
            MonitorResult containing the read values.

        """
        self._ensure_profile_feature_allowed("monitor")
        request = _operations.build_run_monitor_cycle_request(
            word_points=word_points,
            dword_points=dword_points,
            default_series=self.plc_series,
            address_profile=self.plc_profile,
        )
        resp = self._request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_run_monitor_cycle_response(resp, word_points=word_points, dword_points=dword_points)

    def read_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, int]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, int]] = (),
    ) -> BlockReadResult:
        """Read word blocks and bit-device word blocks."""
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
        resp = self._request(
            operation.request.command,
            subcommand=operation.request.subcommand,
            data=operation.request.payload,
        )
        return _operations.decode_read_block_response(resp, operation)

    def write_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
    ) -> None:
        """Write word blocks and bit-device word blocks."""
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
        resp = self._request(
            request.command,
            subcommand=request.subcommand,
            data=request.payload,
            raise_on_error=False,
        )
        if resp.end_code == 0:
            return
        if effective_raise_on_error:
            _raise_response_error(resp, command=request.command, subcommand=request.subcommand)

    def read_long_timer(
        self,
        *,
        head_no: int,
        points: int,
    ) -> list[LongTimerResult]:
        """Read long timer (LT) by LTN in 4-word units and decode status bits."""
        return self._read_long_timer_like(device_prefix="LTN", head_no=head_no, points=points, series=None)

    def read_long_retentive_timer(
        self,
        *,
        head_no: int,
        points: int,
    ) -> list[LongTimerResult]:
        """Read long retentive timer (LST) by LSTN in 4-word units and decode status bits."""
        return self._read_long_timer_like(device_prefix="LSTN", head_no=head_no, points=points, series=None)

    def read_ltc_states(
        self,
        *,
        head_no: int,
        points: int,
    ) -> list[bool]:
        """Read LT coil states by decoding LTN 4-word units."""
        return [item.coil for item in self.read_long_timer(head_no=head_no, points=points)]

    def read_lts_states(
        self,
        *,
        head_no: int,
        points: int,
    ) -> list[bool]:
        """Read LT contact states by decoding LTN 4-word units."""
        return [item.contact for item in self.read_long_timer(head_no=head_no, points=points)]

    def read_lstc_states(
        self,
        *,
        head_no: int,
        points: int,
    ) -> list[bool]:
        """Read LST coil states by decoding LSTN 4-word units."""
        return [item.coil for item in self.read_long_retentive_timer(head_no=head_no, points=points)]

    def read_lsts_states(
        self,
        *,
        head_no: int,
        points: int,
    ) -> list[bool]:
        """Read LST contact states by decoding LSTN 4-word units."""
        return [item.contact for item in self.read_long_retentive_timer(head_no=head_no, points=points)]

    def _read_long_timer_like(
        self,
        *,
        device_prefix: str,
        head_no: int,
        points: int,
        series: PLCSeries | str | None,
    ) -> list[LongTimerResult]:
        head_no, word_points = _operations._validate_long_timer_range(head_no, points, self.plc_profile)

        words_raw = self.read_devices(
            f"{device_prefix}{head_no}",
            word_points,
            bit_unit=False,
        )
        words = [int(v) for v in words_raw]
        if len(words) != word_points:
            raise SlmpError(f"long timer read size mismatch: expected={word_points}, actual={len(words)}")

        result: list[LongTimerResult] = []
        for offset in range(points):
            base = offset * 4
            block = words[base : base + 4]
            status_word = block[2]
            result.append(
                LongTimerResult(
                    index=head_no + offset,
                    device=f"{device_prefix}{head_no + offset}",
                    current_value=(block[1] << 16) | block[0],
                    contact=bool(status_word & 0x0002),
                    coil=bool(status_word & 0x0001),
                    status_word=status_word,
                    raw_words=block,
                )
            )
        return result

    # --------------------
    # Additional typed command APIs
    # --------------------

    def memory_read_words(self, head_address: int, word_length: int) -> list[int]:
        """Read 16-bit words from intelligent function module/special function module buffer memory.

        Args:
            head_address: Start address.
            word_length: Number of words to read.

        Returns:
            List of 16-bit word values.

        """
        request = _operations.build_memory_read_words_request(head_address, word_length)
        resp = self._request(request.command, request.subcommand, request.payload)
        return _operations.decode_memory_read_words_response(resp, word_length=word_length)

    def memory_write_words(self, head_address: int, values: Sequence[int]) -> None:
        """Write 16-bit words to intelligent function module/special function module buffer memory.

        Args:
            head_address: Start address.
            values: Sequence of 16-bit word values to write.

        """
        request = _operations.build_memory_write_words_request(head_address, values)
        self._request(request.command, request.subcommand, request.payload)

    def extend_unit_read_bytes(self, head_address: int, byte_length: int, module_no: int) -> bytes:
        """Read bytes from multiple-CPU shared memory or other extended units.

        Args:
            head_address: Start address.
            byte_length: Number of bytes to read.
            module_no: Module number or unit identification.

        Returns:
            Read data as bytes.

        """
        request = _operations.build_extend_unit_read_bytes_request(head_address, byte_length, module_no)
        resp = self._request(request.command, request.subcommand, request.payload)
        return _operations.decode_extend_unit_read_bytes_response(resp, byte_length=byte_length)

    def extend_unit_read_words(self, head_address: int, word_length: int, module_no: int) -> list[int]:
        """Read 16-bit words from multiple-CPU shared memory or other extended units.

        Args:
            head_address: Start address.
            word_length: Number of words to read.
            module_no: Module number or unit identification.

        Returns:
            List of 16-bit word values.

        """
        request = _operations.build_extend_unit_read_words_request(head_address, word_length, module_no)
        resp = self._request(request.command, request.subcommand, request.payload)
        return _operations.decode_extend_unit_read_words_response(resp, word_length=word_length)

    def extend_unit_read_word(self, head_address: int, module_no: int) -> int:
        """Read one 16-bit word from an extend-unit buffer."""
        return self.extend_unit_read_words(head_address, 1, module_no)[0]

    def extend_unit_read_dword(self, head_address: int, module_no: int) -> int:
        """Read one 32-bit value from an extend-unit buffer."""
        return int.from_bytes(self.extend_unit_read_bytes(head_address, 4, module_no), "little", signed=False)

    def extend_unit_write_bytes(self, head_address: int, module_no: int, data: bytes) -> None:
        """Write bytes to multiple-CPU shared memory or other extended units.

        Args:
            head_address: Start address.
            module_no: Module number or unit identification.
            data: Bytes to write.

        """
        request = _operations.build_extend_unit_write_bytes_request(head_address, module_no, data)
        self._request(request.command, request.subcommand, request.payload)

    def extend_unit_write_words(self, head_address: int, module_no: int, values: Sequence[int]) -> None:
        """Write 16-bit words to multiple-CPU shared memory or other extended units.

        Args:
            head_address: Start address.
            module_no: Module number or unit identification.
            values: Sequence of 16-bit word values to write.

        """
        request = _operations.build_extend_unit_write_words_request(head_address, module_no, values)
        self._request(request.command, request.subcommand, request.payload)

    def extend_unit_write_word(self, head_address: int, module_no: int, value: int) -> None:
        """Write one 16-bit word to an extend-unit buffer."""
        request = _operations.build_extend_unit_write_word_request(head_address, module_no, value)
        self._request(request.command, request.subcommand, request.payload)

    def extend_unit_write_dword(self, head_address: int, module_no: int, value: int) -> None:
        """Write one 32-bit value to an extend-unit buffer."""
        request = _operations.build_extend_unit_write_dword_request(head_address, module_no, value)
        self._request(request.command, request.subcommand, request.payload)

    def remote_run(self, *, force: bool, clear_mode: RemoteClearMode) -> None:
        """Remote RUN.

        Args:
            force: Force RUN even if the RUN/STOP switch is at STOP.
            clear_mode: Clear mode (0: No clear, 1: Clear except latch, 2: Clear all).

        """
        if type(force) is not bool:
            raise ValueError("force must be a boolean")
        if not isinstance(clear_mode, RemoteClearMode):
            raise ValueError("clear_mode must be a RemoteClearMode")
        request = _operations.build_remote_run_request(force=force, clear_mode=int(clear_mode))
        self._request(request.command, request.subcommand, request.payload)

    def remote_stop(self) -> None:
        """Remote STOP."""
        request = _operations.build_remote_stop_request()
        self._request(request.command, request.subcommand, request.payload)

    def remote_pause(self, *, force: bool) -> None:
        """Remote PAUSE.

        Args:
            force: Force PAUSE.

        """
        if type(force) is not bool:
            raise ValueError("force must be a boolean")
        request = _operations.build_remote_pause_request(force=force)
        self._request(request.command, request.subcommand, request.payload)

    def remote_latch_clear(self) -> None:
        """Remote latch clear."""
        request = _operations.build_remote_latch_clear_request()
        self._request(request.command, request.subcommand, request.payload)

    def clear_error(self) -> None:
        """Clear the current PLC error using the fixed semantic command."""
        request = _operations.build_clear_error_request()
        self._request(request.command, request.subcommand, request.payload)

    def remote_reset(self) -> None:
        """Remote RESET without waiting for a response, as required by the protocol contract."""
        request = _operations.build_remote_reset_request(subcommand=0x0000)
        self._send_no_response(request.command, request.subcommand, request.payload)

    def remote_password_lock(self, password: str) -> None:
        """Remote password lock.

        Args:
            password: Password string.

        """
        request = _operations.build_remote_password_lock_request(
            password,
            series=None,
            default_series=self.plc_series,
        )
        self._request(request.command, request.subcommand, request.payload)

    def remote_password_unlock(self, password: str) -> None:
        """Remote password unlock.

        Args:
            password: Password string.

        """
        request = _operations.build_remote_password_unlock_request(
            password,
            series=None,
            default_series=self.plc_series,
        )
        self._request(request.command, request.subcommand, request.payload)

    def self_test_loopback(self, data: bytes | str) -> bytes:
        """Self-test (loopback).

        Args:
            data: Data to send for loopback test.

        Returns:
            Received loopback data.

        """
        request = _operations.build_self_test_loopback_request(data)
        resp = self._request(request.command, request.subcommand, request.payload)
        return _operations.decode_self_test_loopback_response(resp, expected=request.payload[2:])

    # --------------------
    # Label command helpers (typed)
    # --------------------

    def read_array_labels(
        self,
        points: Sequence[LabelArrayReadPoint],
        *,
        abbreviation_labels: Sequence[str] = (),
    ) -> list[LabelArrayReadResult]:
        """Read multiple array labels.

        Args:
            points: List of array labels and points to read.
            abbreviation_labels: Optional list of abbreviation labels.

        Returns:
            List of LabelArrayReadResult.

        """
        request = _operations.build_read_array_labels_request(points, abbreviation_labels=abbreviation_labels)
        data = self._request(request.command, request.subcommand, request.payload).data
        return _operations.parse_array_label_read_response(data, expected_points=len(points))

    def write_array_labels(
        self,
        points: Sequence[LabelArrayWritePoint],
        *,
        abbreviation_labels: Sequence[str] = (),
    ) -> None:
        """Write multiple array labels.

        Args:
            points: List of array labels and data to write.
            abbreviation_labels: Optional list of abbreviation labels.

        """
        request = _operations.build_write_array_labels_request(points, abbreviation_labels=abbreviation_labels)
        self._request(request.command, request.subcommand, request.payload)

    def read_random_labels(
        self,
        labels: Sequence[str],
        *,
        abbreviation_labels: Sequence[str] = (),
    ) -> list[LabelRandomReadResult]:
        """Read multiple labels at random.

        Args:
            labels: List of label names to read.
            abbreviation_labels: Optional list of abbreviation labels.

        Returns:
            List of LabelRandomReadResult.

        """
        request = _operations.build_read_random_labels_request(labels, abbreviation_labels=abbreviation_labels)
        data = self._request(request.command, request.subcommand, request.payload).data
        return _operations.parse_label_read_random_response(data, expected_points=len(labels))

    def write_random_labels(
        self,
        points: Sequence[LabelRandomWritePoint],
        *,
        abbreviation_labels: Sequence[str] = (),
    ) -> None:
        """Write multiple labels at random.

        Args:
            points: List of labels and data to write.
            abbreviation_labels: Optional list of abbreviation labels.

        """
        request = _operations.build_write_random_labels_request(points, abbreviation_labels=abbreviation_labels)
        self._request(request.command, request.subcommand, request.payload)

    def read_type_name(self) -> TypeNameInfo:
        """Read the PLC model name and code."""
        self._ensure_profile_feature_allowed("type_name")
        request = _operations.build_read_type_name_request()
        resp = self._request(request.command, request.subcommand, request.payload)
        return _operations.decode_read_type_name_response(resp)

    def read_device_range_catalog_for_plc_profile(
        self,
        plc_profile: SlmpPlcProfile | str,
    ) -> SlmpDeviceRangeCatalog:
        """Read the configured device-range catalog for one canonical explicit PLC profile."""
        from .device_ranges import read_device_range_catalog_for_plc_profile_sync

        return read_device_range_catalog_for_plc_profile_sync(self, plc_profile)

    def read_device_range_catalog(self) -> SlmpDeviceRangeCatalog:
        """Read the configured device-range catalog for this client's explicit PLC profile."""
        if self.range_profile is None:
            raise ValueError("read_device_range_catalog() requires explicit plc_profile on the client.")
        return self.read_device_range_catalog_for_plc_profile(self.range_profile)

    def read_cpu_operation_state(self) -> CpuOperationState:
        """Read SD203 and decode the CPU operation state from the lower 4 bits."""
        return decode_cpu_operation_state(self.read_devices("SD203", 1, bit_unit=False)[0])

    # --------------------
    # Internal I/O
    # --------------------

    def _send_no_response(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
    ) -> None:
        """Serialize one no-response request on this client connection."""
        if monitoring_timer is not None and (
            isinstance(monitoring_timer, bool)
            or not isinstance(monitoring_timer, int)
            or not 0 <= monitoring_timer <= 0xFFFF
        ):
            raise ValueError("monitoring_timer must be an integer in range 0..65535 when provided")
        with self._request_lock:
            self._send_no_response_unlocked(
                command,
                subcommand,
                data,
                serial=serial,
                target=target,
                monitoring_timer=monitoring_timer,
            )

    def _send_no_response_unlocked(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
    ) -> None:
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
        self.connect()
        assert self._sock is not None
        if self.transport == "tcp":
            self._sock.sendall(frame)
            self._record_send(len(frame))
            self._emit_trace(
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
        else:
            if self._sock.send(frame) != len(frame):
                raise OSError("UDP send did not accept the complete SLMP datagram")
            self._record_send(len(frame))
            self._emit_trace(
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
        # A send-only command can still produce an NG response. 3E has no
        # serial field, so retaining this transport could assign that response
        # to the next request. Reconnection is therefore mandatory.
        self.close()

    def _next_serial(self) -> int:
        serial = self._serial & 0xFFFF
        self._serial = (self._serial + 1) & 0xFFFF
        return serial

    def _send_and_receive(self, frame: bytes) -> bytes:
        self.connect()
        assert self._sock is not None
        expected_serial = _EXPECTED_RESPONSE_SERIAL.get()

        if self.transport == "tcp":
            try:
                self._sock.sendall(frame)
                self._record_send(len(frame))
                while True:
                    raw = self._receive_frame()
                    if _response_matches_serial(raw, expected_serial):
                        return raw
            except BaseException:
                self.close()
                raise

        try:
            if self._sock.send(frame) != len(frame):
                raise OSError("UDP send did not accept the complete SLMP datagram")
            self._record_send(len(frame))
            while True:
                raw = self._receive_frame()
                if _response_matches_serial(raw, expected_serial):
                    return raw
        except BaseException:
            self.close()
            raise

    def _receive_frame(self, *, timeout: float | None = None) -> bytes:
        self.connect()
        assert self._sock is not None
        previous_timeout = self._sock.gettimeout()
        if timeout is not None:
            self._sock.settimeout(timeout)
        sock = self._sock
        try:
            if self.transport == "tcp":
                frame = _recv_tcp_frame(sock, frame_type=self.frame_type)
            else:
                frame = sock.recv(65535)
            self._record_receive(len(frame))
            return frame
        except (OSError, SlmpError):
            self.close()
            raise
        finally:
            if timeout is not None and self._sock is sock:
                sock.settimeout(previous_timeout)

    def _emit_trace(self, trace: _SlmpTraceFrame) -> None:
        if self._trace_hook is None:
            return
        try:
            self._trace_hook(trace)
        except Exception:
            # Trace callback failures must not affect protocol behavior.
            pass


def _recv_tcp_frame(sock: socket.socket, *, frame_type: FrameType) -> bytes:
    # 4E response header up to data length: Subheader(2) + Serial(2) + Reserved(2) + Target(5) + Len(2) = 13 bytes.
    # 3E response header up to data length: Subheader(2) + Target(5) + Len(2) = 9 bytes.
    head_size = 13 if frame_type == FrameType.FRAME_4E else 9
    head = bytearray(head_size)
    _recv_exact_into(sock, memoryview(head))
    expected_subheader = b"\xd4\x00" if frame_type == FrameType.FRAME_4E else b"\xd0\x00"
    if head[:2] != expected_subheader:
        raise SlmpError("unexpected response frame type")
    response_data_length = int.from_bytes(head[-2:], "little")
    frame = bytearray(head_size + response_data_length)
    frame[:head_size] = head
    _recv_exact_into(sock, memoryview(frame)[head_size:])
    return bytes(frame)


def _response_matches_serial(raw: bytes, expected_serial: int | None) -> bool:
    if expected_serial is None:
        return True
    if len(raw) < 4 or raw[:2] != b"\xd4\x00":
        raise SlmpError("unexpected response frame type")
    return int.from_bytes(raw[2:4], "little") == expected_serial


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    buf = bytearray(size)
    _recv_exact_into(sock, memoryview(buf))
    return bytes(buf)


def _recv_exact_into(sock: socket.socket, view: memoryview) -> None:
    recv_into = getattr(sock, "recv_into", None)
    if callable(recv_into):
        while len(view) > 0:
            read = recv_into(view)
            if read == 0:
                raise SlmpError("connection closed while receiving data")
            view = view[read:]
        return

    offset = 0
    total = len(view)
    while offset < total:
        chunk = sock.recv(total - offset)
        if not chunk:
            raise SlmpError("connection closed while receiving data")
        end = offset + len(chunk)
        view[offset:end] = chunk
        offset = end
