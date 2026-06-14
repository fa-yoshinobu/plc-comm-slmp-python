"""SLMP binary client."""

from __future__ import annotations

import socket
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

from . import _operations
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
    _check_points_u16,
    _raise_response_error,
    _require_explicit_plc_profile_for_xy,
    _resolve_connection_profile,
    _resolve_port,
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


class SlmpClient:
    """Synchronous SLMP client supporting 3E and 4E frames (binary).

    This client provides high-level typed APIs for interacting with MELSEC
    and compatible PLCs using the SLMP protocol.

    Examples:
        >>> from slmp.client import SlmpClient
        >>> with SlmpClient("192.168.250.100", 1025, plc_profile="melsec:iq-r") as client:
        ...     values = client.read_devices("D100", 5)
        ...     print(values)
        [0, 0, 0, 0, 0]
    """

    def __init__(
        self,
        host: str,
        port: int | None = None,
        *,
        transport: str = "tcp",
        timeout: float = 3.0,
        plc_profile: object | None = None,
        plc_series: PLCSeries | str | None = None,
        frame_type: FrameType | str | None = None,
        default_target: SlmpTarget | None = None,
        monitoring_timer: int = 0x0010,
        raise_on_error: bool = True,
        trace_hook: Callable[[SlmpTraceFrame], None] | None = None,
        address_profile: object | None = None,
        _allow_manual_profile: bool = False,
    ) -> None:
        """Initialize the SLMP client.

        Args:
            host: PLC IP address.
            port: PLC port number. Defaults to 1025 for TCP and 1035 for UDP.
            transport: Transport protocol ('tcp' or 'udp'). Defaults to 'tcp'.
            timeout: Socket timeout in seconds. Defaults to 3.0.
            plc_profile: Canonical high-level PLC profile. The standard client
                route requires this and derives frame type, access profile,
                and address/range handling from it.
            default_target: Default target station routing information.
            monitoring_timer: Default monitoring timer value (multiples of 250ms). Defaults to 0x0010 (4s).
            raise_on_error: Whether to raise SlmpError on non-zero end codes. Defaults to True.
            trace_hook: Optional callback for tracing requests and responses.
        """
        self.host = host
        self.transport = transport.lower()
        if self.transport not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.port = _resolve_port(port, self.transport)
        self.timeout = timeout
        if not _allow_manual_profile:
            if plc_profile is None:
                raise ValueError(
                    "plc_profile is required for the standard SlmpClient route "
                    "unless you explicitly opt into a low-level frame/profile path."
                )
            if plc_profile is not None and any(
                value is not None for value in (plc_series, frame_type, address_profile)
            ):
                raise ValueError("plc_profile is the only supported PLC selector for the standard SlmpClient route.")
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
        self._sock: socket.socket | None = None

    def _parse_device(self, device: str | DeviceRef) -> DeviceRef:
        ref = parse_device(device, plc_profile=self.address_profile)
        return _require_explicit_plc_profile_for_xy(device, self.address_profile, ref)

    def _resolve_extended_device_and_extension(
        self,
        device: str | DeviceRef,
        extension: ExtensionSpec,
    ) -> tuple[DeviceRef, ExtensionSpec]:
        ref, effective_extension = resolve_extended_device_and_extension(
            device,
            extension,
            plc_profile=self.address_profile,
        )
        return _require_explicit_plc_profile_for_xy(device, self.address_profile, ref), effective_extension

    def connect(self) -> None:
        """Open the connection to the PLC.

        Raises:
            socket.error: If the connection fails.
        """
        if self._sock is not None:
            return
        sock_type = socket.SOCK_STREAM if self.transport == "tcp" else socket.SOCK_DGRAM
        sock = socket.socket(socket.AF_INET, sock_type)
        sock.settimeout(self.timeout)
        if self.transport == "tcp":
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.connect((self.host, self.port))
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

    def request(
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
        """Send an SLMP request and return the response.

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
        raw = self._send_and_receive(frame)
        resp = decode_response(raw, frame_type=self.frame_type)
        self._emit_trace(
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

    def raw_command(
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
        return self.request(
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
        """Create an ExtensionSpec for Extended Device commands.

        Args:
            extension_specification: Extension specification (16-bit).
            extension_specification_modification: Extension specification modification (8-bit).
            device_modification_index: Device modification index (8-bit).
            use_indirect_specification: Whether to use indirect specification.
            register_mode: Register mode ('none', 'index', 'long_index').
            direct_memory_specification: Direct memory specification (8-bit).
            series: PLC series for flag calculation.

        """
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

    def read_devices(
        self,
        device: str | DeviceRef,
        points: int,
        *,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> list[int] | list[bool]:
        """Read device values from the PLC.

        Args:
            device: Device reference string (e.g. 'D100', 'X0') or `DeviceRef`.
            points: Number of consecutive points to read.
            bit_unit: If True, read in bit units (returns list of bool);
                otherwise read in word units (returns list of int).
            series: Optional PLC series override for this specific request.

        Returns:
            A list of integers (for word units) or booleans (for bit units).

        Raises:
            SlmpError: If the PLC returns an error code.
            ValueError: If `points` is out of valid range (0-65535).
        """
        request = _operations.build_read_devices_request(
            device,
            points,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_devices_response(resp, points=points, bit_unit=bit_unit)

    def write_devices(
        self,
        device: str | DeviceRef,
        values: Sequence[int | bool],
        *,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write values to PLC devices.

        Args:
            device: Starting device reference (e.g. 'D100', 'Y0') or `DeviceRef`.
            values: Sequence of values to write.
            bit_unit: If True, write in bit units (expects Sequence[bool]);
                otherwise write in word units (expects Sequence[int]).
            series: Optional PLC series override for this specific request.

        Raises:
            SlmpError: If the PLC returns an error code.
            ValueError: If `values` is empty or exceeds valid protocol limits.
        """
        request = _operations.build_write_devices_request(
            device,
            values,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def read_dword(
        self,
        device: str | DeviceRef,
        *,
        series: PLCSeries | str | None = None,
    ) -> int:
        """Read one 32-bit value from two consecutive word devices."""
        return self.read_dwords(device, 1, series=series)[0]

    def write_dword(
        self,
        device: str | DeviceRef,
        value: int,
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write one 32-bit value to two consecutive word devices."""
        self.write_dwords(device, [value], series=series)

    def read_dwords(
        self,
        device: str | DeviceRef,
        count: int,
        *,
        series: PLCSeries | str | None = None,
    ) -> list[int]:
        """Read one or more 32-bit values from consecutive word devices."""
        request = _operations.build_read_dwords_request(
            device,
            count,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_dwords_response(resp, count=count)

    def write_dwords(
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
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def read_float32(
        self,
        device: str | DeviceRef,
        *,
        series: PLCSeries | str | None = None,
    ) -> float:
        """Read one IEEE-754 float32 from two consecutive word devices."""
        return self.read_float32s(device, 1, series=series)[0]

    def write_float32(
        self,
        device: str | DeviceRef,
        value: float,
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write one IEEE-754 float32 to two consecutive word devices."""
        self.write_float32s(device, [value], series=series)

    def read_float32s(
        self,
        device: str | DeviceRef,
        count: int,
        *,
        series: PLCSeries | str | None = None,
    ) -> list[float]:
        """Read one or more IEEE-754 float32 values from consecutive word devices."""
        request = _operations.build_read_dwords_request(
            device,
            count,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_float32s_response(resp, count=count)

    def write_float32s(
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
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def read_devices_ext(
        self,
        device: str | DeviceRef,
        points: int,
        *,
        extension: ExtensionSpec,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> list[int] | list[bool]:
        """Extended Device extension read (subcommand 0081/0080 or 0083/0082)."""
        request = _operations.build_read_devices_ext_request(
            device,
            points,
            extension=extension,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_read_devices_response(resp, points=points, bit_unit=bit_unit)

    def write_devices_ext(
        self,
        device: str | DeviceRef,
        values: Sequence[int | bool],
        *,
        extension: ExtensionSpec,
        bit_unit: bool = False,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Extended Device extension write (subcommand 0081/0080 or 0083/0082)."""
        request = _operations.build_write_devices_ext_request(
            device,
            values,
            extension=extension,
            bit_unit=bit_unit,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def read_random(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
        series: PLCSeries | str | None = None,
    ) -> RandomReadResult:
        """Read multiple word and double-word devices at random.

        Args:
            word_devices: List of word devices to read.
            dword_devices: List of double-word devices to read.
            series: Optional PLC series override.

        """
        operation = _operations.build_read_random_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = self.request(
            operation.request.command,
            subcommand=operation.request.subcommand,
            data=operation.request.payload,
        )
        return _operations.decode_read_random_response(resp, operation)

    def read_random_ext(
        self,
        *,
        word_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        dword_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> RandomReadResult:
        """Read multiple word and double-word devices at random using Extended Device extensions.

        Args:
            word_devices: List of (device, extension) tuples for word devices.
            dword_devices: List of (device, extension) tuples for double-word devices.
            series: Optional PLC series override.

        """
        operation = _operations.build_read_random_ext_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        resp = self.request(
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
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple word and double-word values at random.

        Args:
            word_values: Mapping or sequence of (device, value) for word devices.
            dword_values: Mapping or sequence of (device, value) for double-word devices.
            series: Optional PLC series override.

        """
        request = _operations.build_write_random_words_request(
            word_values=word_values,
            dword_values=dword_values,
            series=series,
            default_series=self.plc_series,
        )
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def write_random_words_ext(
        self,
        *,
        word_values: Sequence[tuple[str | DeviceRef, int, ExtensionSpec]] = (),
        dword_values: Sequence[tuple[str | DeviceRef, int, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple word and double-word values at random using Extended Device extensions.

        Args:
            word_values: List of (device, value, extension) for word devices.
            dword_values: List of (device, value, extension) for double-word devices.
            series: Optional PLC series override.

        """
        request = _operations.build_write_random_words_ext_request(
            word_values=word_values,
            dword_values=dword_values,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def write_random_bits(
        self,
        bit_values: Mapping[str | DeviceRef, bool | int] | Sequence[tuple[str | DeviceRef, bool | int]],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple bit values at random.

        Args:
            bit_values: Mapping or sequence of (device, value) for bit devices.
            series: Optional PLC series override.

        """
        request = _operations.build_write_random_bits_request(
            bit_values,
            series=series,
            default_series=self.plc_series,
        )
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def write_random_bits_ext(
        self,
        bit_values: Sequence[tuple[str | DeviceRef, bool | int, ExtensionSpec]],
        *,
        series: PLCSeries | str | None = None,
    ) -> None:
        """Write multiple bit values at random using Extended Device extensions.

        Args:
            bit_values: List of (device, value, extension) for bit devices.
            series: Optional PLC series override.

        """
        request = _operations.build_write_random_bits_ext_request(
            bit_values,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def register_monitor_devices(
        self,
        *,
        word_devices: Sequence[str | DeviceRef] = (),
        dword_devices: Sequence[str | DeviceRef] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Register word and double-word devices for monitoring.

        Args:
            word_devices: List of word devices to monitor.
            dword_devices: List of double-word devices to monitor.
            series: Optional PLC series override.

        """
        request = _operations.build_register_monitor_devices_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def register_monitor_devices_ext(
        self,
        *,
        word_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        dword_devices: Sequence[tuple[str | DeviceRef, ExtensionSpec]] = (),
        series: PLCSeries | str | None = None,
    ) -> None:
        """Register devices for monitoring using Extended Device extensions.

        Args:
            word_devices: List of (device, extension) for word devices.
            dword_devices: List of (device, extension) for double-word devices.
            series: Optional PLC series override.

        """
        request = _operations.build_register_monitor_devices_ext_request(
            word_devices=word_devices,
            dword_devices=dword_devices,
            series=series,
            default_series=self.plc_series,
            address_profile=self.address_profile,
        )
        self.request(request.command, subcommand=request.subcommand, data=request.payload)

    def run_monitor_cycle(self, *, word_points: int, dword_points: int) -> MonitorResult:
        """Execute a monitoring cycle for previously registered devices.

        Args:
            word_points: Number of registered word points.
            dword_points: Number of registered double-word points.

        Returns:
            MonitorResult containing the read values.

        """
        request = _operations.build_run_monitor_cycle_request(word_points=word_points, dword_points=dword_points)
        resp = self.request(request.command, subcommand=request.subcommand, data=request.payload)
        return _operations.decode_run_monitor_cycle_response(resp, word_points=word_points, dword_points=dword_points)

    def read_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, int]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, int]] = (),
        series: PLCSeries | str | None = None,
        split_mixed_blocks: bool = False,
    ) -> BlockReadResult:
        """Read word blocks and bit-device word blocks."""
        if not word_blocks and not bit_blocks:
            raise ValueError("word_blocks and bit_blocks must not both be empty")
        if len(word_blocks) > 0xFF or len(bit_blocks) > 0xFF:
            raise ValueError("word_blocks and bit_blocks must be <= 255 each")
        if split_mixed_blocks and word_blocks and bit_blocks:
            w = self.read_block(
                word_blocks=word_blocks,
                bit_blocks=(),
                series=series,
                split_mixed_blocks=False,
            )
            b = self.read_block(
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
        resp = self.request(
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
        series: PLCSeries | str | None = None,
        split_mixed_blocks: bool = False,
    ) -> None:
        """Write word blocks and bit-device word blocks."""
        if not word_blocks and not bit_blocks:
            raise ValueError("word_blocks and bit_blocks must not both be empty")
        if len(word_blocks) > 0xFF or len(bit_blocks) > 0xFF:
            raise ValueError("word_blocks and bit_blocks must be <= 255 each")
        if split_mixed_blocks and word_blocks and bit_blocks:
            self.write_block(
                word_blocks=word_blocks,
                bit_blocks=(),
                series=series,
                split_mixed_blocks=False,
            )
            self.write_block(
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
        resp = self.request(
            request.command,
            subcommand=request.subcommand,
            data=request.payload,
            raise_on_error=False,
        )
        if resp.end_code == 0:
            return
        if self.raise_on_error:
            _raise_response_error(resp, command=request.command, subcommand=request.subcommand)

    def read_long_timer(
        self,
        *,
        head_no: int = 0,
        points: int = 1,
        series: PLCSeries | str | None = None,
    ) -> list[LongTimerResult]:
        """Read long timer (LT) by LTN in 4-word units and decode status bits."""
        return self._read_long_timer_like(device_prefix="LTN", head_no=head_no, points=points, series=series)

    def read_long_retentive_timer(
        self,
        *,
        head_no: int = 0,
        points: int = 1,
        series: PLCSeries | str | None = None,
    ) -> list[LongTimerResult]:
        """Read long retentive timer (LST) by LSTN in 4-word units and decode status bits."""
        return self._read_long_timer_like(device_prefix="LSTN", head_no=head_no, points=points, series=series)

    def read_ltc_states(
        self,
        *,
        head_no: int = 0,
        points: int = 1,
        series: PLCSeries | str | None = None,
    ) -> list[bool]:
        """Read LT coil states by decoding LTN 4-word units."""
        return [item.coil for item in self.read_long_timer(head_no=head_no, points=points, series=series)]

    def read_lts_states(
        self,
        *,
        head_no: int = 0,
        points: int = 1,
        series: PLCSeries | str | None = None,
    ) -> list[bool]:
        """Read LT contact states by decoding LTN 4-word units."""
        return [item.contact for item in self.read_long_timer(head_no=head_no, points=points, series=series)]

    def read_lstc_states(
        self,
        *,
        head_no: int = 0,
        points: int = 1,
        series: PLCSeries | str | None = None,
    ) -> list[bool]:
        """Read LST coil states by decoding LSTN 4-word units."""
        return [item.coil for item in self.read_long_retentive_timer(head_no=head_no, points=points, series=series)]

    def read_lsts_states(
        self,
        *,
        head_no: int = 0,
        points: int = 1,
        series: PLCSeries | str | None = None,
    ) -> list[bool]:
        """Read LST contact states by decoding LSTN 4-word units."""
        return [item.contact for item in self.read_long_retentive_timer(head_no=head_no, points=points, series=series)]

    def _read_long_timer_like(
        self,
        *,
        device_prefix: str,
        head_no: int,
        points: int,
        series: PLCSeries | str | None,
    ) -> list[LongTimerResult]:
        if head_no < 0:
            raise ValueError(f"head_no must be >= 0: {head_no}")
        if points < 1:
            raise ValueError(f"points must be >= 1: {points}")
        word_points = points * 4
        _check_points_u16(word_points, "long timer word points")

        words_raw = self.read_devices(
            f"{device_prefix}{head_no}",
            word_points,
            bit_unit=False,
            series=series,
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
        resp = self.request(request.command, request.subcommand, request.payload)
        return _operations.decode_memory_read_words_response(resp, word_length=word_length)

    def memory_write_words(self, head_address: int, values: Sequence[int]) -> None:
        """Write 16-bit words to intelligent function module/special function module buffer memory.

        Args:
            head_address: Start address.
            values: Sequence of 16-bit word values to write.

        """
        request = _operations.build_memory_write_words_request(head_address, values)
        self.request(request.command, request.subcommand, request.payload)

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
        resp = self.request(request.command, request.subcommand, request.payload)
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
        resp = self.request(request.command, request.subcommand, request.payload)
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
        self.request(request.command, request.subcommand, request.payload)

    def extend_unit_write_words(self, head_address: int, module_no: int, values: Sequence[int]) -> None:
        """Write 16-bit words to multiple-CPU shared memory or other extended units.

        Args:
            head_address: Start address.
            module_no: Module number or unit identification.
            values: Sequence of 16-bit word values to write.

        """
        request = _operations.build_extend_unit_write_words_request(head_address, module_no, values)
        self.request(request.command, request.subcommand, request.payload)

    def extend_unit_write_word(self, head_address: int, module_no: int, value: int) -> None:
        """Write one 16-bit word to an extend-unit buffer."""
        request = _operations.build_extend_unit_write_word_request(head_address, module_no, value)
        self.request(request.command, request.subcommand, request.payload)

    def extend_unit_write_dword(self, head_address: int, module_no: int, value: int) -> None:
        """Write one 32-bit value to an extend-unit buffer."""
        request = _operations.build_extend_unit_write_dword_request(head_address, module_no, value)
        self.request(request.command, request.subcommand, request.payload)

    def cpu_buffer_read_bytes(self, head_address: int, byte_length: int, *, module_no: int = 0x03E0) -> bytes:
        """Read CPU buffer memory by extend-unit command using the CPU start I/O number."""
        return self.extend_unit_read_bytes(head_address, byte_length, module_no)

    def cpu_buffer_read_words(self, head_address: int, word_length: int, *, module_no: int = 0x03E0) -> list[int]:
        """Read CPU buffer memory words by extend-unit command using the CPU start I/O number."""
        return self.extend_unit_read_words(head_address, word_length, module_no)

    def cpu_buffer_read_word(self, head_address: int, *, module_no: int = 0x03E0) -> int:
        """Read one 16-bit CPU buffer word via the verified extend-unit path."""
        return self.extend_unit_read_word(head_address, module_no)

    def cpu_buffer_read_dword(self, head_address: int, *, module_no: int = 0x03E0) -> int:
        """Read one 32-bit CPU buffer value via the verified extend-unit path."""
        return self.extend_unit_read_dword(head_address, module_no)

    def cpu_buffer_write_bytes(self, head_address: int, data: bytes, *, module_no: int = 0x03E0) -> None:
        """Write CPU buffer memory by extend-unit command using the CPU start I/O number."""
        self.extend_unit_write_bytes(head_address, module_no, data)

    def cpu_buffer_write_words(self, head_address: int, values: Sequence[int], *, module_no: int = 0x03E0) -> None:
        """Write CPU buffer memory words by extend-unit command using the CPU start I/O number."""
        self.extend_unit_write_words(head_address, module_no, values)

    def cpu_buffer_write_word(self, head_address: int, value: int, *, module_no: int = 0x03E0) -> None:
        """Write one 16-bit CPU buffer word via the verified extend-unit path."""
        self.extend_unit_write_word(head_address, module_no, value)

    def cpu_buffer_write_dword(self, head_address: int, value: int, *, module_no: int = 0x03E0) -> None:
        """Write one 32-bit CPU buffer value via the verified extend-unit path."""
        self.extend_unit_write_dword(head_address, module_no, value)

    def remote_run(self, *, force: bool = False, clear_mode: int = 0) -> None:
        """Remote RUN.

        Args:
            force: Force RUN even if the RUN/STOP switch is at STOP.
            clear_mode: Clear mode (0: No clear, 1: Clear except latch, 2: Clear all).

        """
        request = _operations.build_remote_run_request(force=force, clear_mode=clear_mode)
        self.request(request.command, request.subcommand, request.payload)

    def remote_stop(self) -> None:
        """Remote STOP."""
        request = _operations.build_remote_stop_request()
        self.request(request.command, request.subcommand, request.payload)

    def remote_pause(self, *, force: bool = False) -> None:
        """Remote PAUSE.

        Args:
            force: Force PAUSE.

        """
        request = _operations.build_remote_pause_request(force=force)
        self.request(request.command, request.subcommand, request.payload)

    def remote_latch_clear(self) -> None:
        """Remote latch clear."""
        request = _operations.build_remote_latch_clear_request()
        self.request(request.command, request.subcommand, request.payload)

    def remote_reset(self, *, subcommand: int = 0x0000, expect_response: bool | None = None) -> None:
        """Remote RESET.

        Args:
            subcommand: Subcommand (0x0000: RESET).
            expect_response: Whether to wait for a response.

        """
        request = _operations.build_remote_reset_request(subcommand=subcommand)
        should_wait = False if expect_response is None else expect_response
        if should_wait:
            self.request(request.command, request.subcommand, request.payload)
            return
        self._send_no_response(request.command, request.subcommand, request.payload)

    def remote_password_lock(self, password: str, *, series: PLCSeries | str | None = None) -> None:
        """Remote password lock.

        Args:
            password: Password string.
            series: Optional PLC series override.

        """
        request = _operations.build_remote_password_lock_request(
            password,
            series=series,
            default_series=self.plc_series,
        )
        self.request(request.command, request.subcommand, request.payload)

    def remote_password_unlock(self, password: str, *, series: PLCSeries | str | None = None) -> None:
        """Remote password unlock.

        Args:
            password: Password string.
            series: Optional PLC series override.

        """
        request = _operations.build_remote_password_unlock_request(
            password,
            series=series,
            default_series=self.plc_series,
        )
        self.request(request.command, request.subcommand, request.payload)

    def self_test_loopback(self, data: bytes | str) -> bytes:
        """Self-test (loopback).

        Args:
            data: Data to send for loopback test.

        Returns:
            Received loopback data.

        """
        request = _operations.build_self_test_loopback_request(data)
        resp = self.request(request.command, request.subcommand, request.payload)
        return _operations.decode_self_test_loopback_response(resp)

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
        data = self.request(request.command, request.subcommand, request.payload).data
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
        self.request(request.command, request.subcommand, request.payload)

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
        data = self.request(request.command, request.subcommand, request.payload).data
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
        self.request(request.command, request.subcommand, request.payload)

    @staticmethod
    def build_array_label_read_payload(
        points: Sequence[LabelArrayReadPoint],
        *,
        abbreviation_labels: Sequence[str] = (),
    ) -> bytes:
        """Build the binary payload for array label read command.

        Args:
            points: List of points to read.
            abbreviation_labels: Optional abbreviation labels.

        Returns:
            Binary payload.

        """
        return _operations.build_array_label_read_payload(points, abbreviation_labels=abbreviation_labels)

    @staticmethod
    def build_array_label_write_payload(
        points: Sequence[LabelArrayWritePoint],
        *,
        abbreviation_labels: Sequence[str] = (),
    ) -> bytes:
        """Build the binary payload for array label write command.

        Args:
            points: List of points and data to write.
            abbreviation_labels: Optional abbreviation labels.

        Returns:
            Binary payload.

        """
        return _operations.build_array_label_write_payload(points, abbreviation_labels=abbreviation_labels)

    @staticmethod
    def build_label_read_random_payload(
        labels: Sequence[str],
        *,
        abbreviation_labels: Sequence[str] = (),
    ) -> bytes:
        """Build the binary payload for label random read command.

        Args:
            labels: List of label names to read.
            abbreviation_labels: Optional abbreviation labels.

        Returns:
            Binary payload.

        """
        return _operations.build_label_read_random_payload(labels, abbreviation_labels=abbreviation_labels)

    @staticmethod
    def build_label_write_random_payload(
        points: Sequence[LabelRandomWritePoint],
        *,
        abbreviation_labels: Sequence[str] = (),
    ) -> bytes:
        """Build the binary payload for label random write command.

        Args:
            points: List of labels and data to write.
            abbreviation_labels: Optional abbreviation labels.

        Returns:
            Binary payload.

        """
        return _operations.build_label_write_random_payload(points, abbreviation_labels=abbreviation_labels)

    @staticmethod
    def parse_array_label_read_response(
        data: bytes,
        *,
        expected_points: int | None = None,
    ) -> list[LabelArrayReadResult]:
        """Parse binary response data from array label read command.

        Args:
            data: Binary response data.
            expected_points: Optional expected point count.

        Returns:
            List of LabelArrayReadResult.

        """
        return _operations.parse_array_label_read_response(data, expected_points=expected_points)

    @staticmethod
    def parse_label_read_random_response(
        data: bytes,
        *,
        expected_points: int | None = None,
    ) -> list[LabelRandomReadResult]:
        """Parse binary response data from label random read command.

        Args:
            data: Binary response data.
            expected_points: Optional expected point count.

        Returns:
            List of LabelRandomReadResult.

        """
        return _operations.parse_label_read_random_response(data, expected_points=expected_points)

    # --------------------
    # Full command wrappers (raw payload)
    # --------------------

    def array_label_read(self, payload: bytes = b"") -> bytes:
        """Low-level wrapper for LABEL_ARRAY_READ command."""
        return self.request(Command.LABEL_ARRAY_READ, 0x0000, payload).data

    def array_label_write(self, payload: bytes = b"") -> None:
        """Low-level wrapper for LABEL_ARRAY_WRITE command."""
        self.request(Command.LABEL_ARRAY_WRITE, 0x0000, payload)

    def label_read_random(self, payload: bytes = b"") -> bytes:
        """Low-level wrapper for LABEL_READ_RANDOM command."""
        return self.request(Command.LABEL_READ_RANDOM, 0x0000, payload).data

    def label_write_random(self, payload: bytes = b"") -> None:
        """Low-level wrapper for LABEL_WRITE_RANDOM command."""
        self.request(Command.LABEL_WRITE_RANDOM, 0x0000, payload)

    def memory_read(self, payload: bytes = b"") -> bytes:
        """Low-level wrapper for MEMORY_READ command."""
        return self.request(Command.MEMORY_READ, 0x0000, payload).data

    def memory_write(self, payload: bytes = b"") -> None:
        """Low-level wrapper for MEMORY_WRITE command."""
        self.request(Command.MEMORY_WRITE, 0x0000, payload)

    def extend_unit_read(self, payload: bytes = b"") -> bytes:
        """Low-level wrapper for EXTEND_UNIT_READ command."""
        return self.request(Command.EXTEND_UNIT_READ, 0x0000, payload).data

    def extend_unit_write(self, payload: bytes = b"") -> None:
        """Low-level wrapper for EXTEND_UNIT_WRITE command."""
        self.request(Command.EXTEND_UNIT_WRITE, 0x0000, payload)

    def remote_run_raw(self, payload: bytes = b"") -> None:
        """Low-level wrapper for REMOTE_RUN command."""
        self.request(Command.REMOTE_RUN, 0x0000, payload)

    def remote_stop_raw(self, payload: bytes = b"") -> None:
        """Low-level wrapper for REMOTE_STOP command."""
        self.request(Command.REMOTE_STOP, 0x0000, payload)

    def remote_pause_raw(self, payload: bytes = b"") -> None:
        """Low-level wrapper for REMOTE_PAUSE command."""
        self.request(Command.REMOTE_PAUSE, 0x0000, payload)

    def remote_latch_clear_raw(self, payload: bytes = b"") -> None:
        """Low-level wrapper for REMOTE_LATCH_CLEAR command."""
        self.request(Command.REMOTE_LATCH_CLEAR, 0x0000, payload)

    def remote_reset_raw(self, payload: bytes = b"\x01\x00") -> None:
        """Low-level wrapper for REMOTE_RESET command (no response)."""
        self._send_no_response(Command.REMOTE_RESET, 0x0000, payload)

    def read_type_name(self) -> TypeNameInfo:
        """Read the PLC model name and code."""
        request = _operations.build_read_type_name_request()
        resp = self.request(request.command, request.subcommand, request.payload)
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

    def remote_password_lock_raw(self, payload: bytes = b"") -> None:
        """Low-level wrapper for REMOTE_PASSWORD_LOCK command."""
        self.request(Command.REMOTE_PASSWORD_LOCK, 0x0000, payload)

    def remote_password_unlock_raw(self, payload: bytes = b"") -> None:
        """Low-level wrapper for REMOTE_PASSWORD_UNLOCK command."""
        self.request(Command.REMOTE_PASSWORD_UNLOCK, 0x0000, payload)

    def self_test(self, payload: bytes = b"") -> bytes:
        """Low-level wrapper for SELF_TEST command."""
        return self.request(Command.SELF_TEST, 0x0000, payload).data

    def clear_error(self, payload: bytes = b"") -> None:
        """Low-level wrapper for CLEAR_ERROR command."""
        self.request(Command.CLEAR_ERROR, 0x0000, payload)

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
            self._emit_trace(
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
            return
        self._sock.sendto(frame, (self.host, self.port))
        self._emit_trace(
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

    def _next_serial(self) -> int:
        serial = self._serial & 0xFFFF
        self._serial = (self._serial + 1) & 0xFFFF
        return serial

    def _send_and_receive(self, frame: bytes) -> bytes:
        self.connect()
        assert self._sock is not None

        if self.transport == "tcp":
            self._sock.sendall(frame)
            return self._receive_frame()

        self._sock.sendto(frame, (self.host, self.port))
        return self._receive_frame()

    def _receive_frame(self, *, timeout: float | None = None) -> bytes:
        self.connect()
        assert self._sock is not None
        previous_timeout = self._sock.gettimeout()
        if timeout is not None:
            self._sock.settimeout(timeout)
        try:
            if self.transport == "tcp":
                return _recv_tcp_frame(self._sock, frame_type=self.frame_type)
            data, _ = self._sock.recvfrom(65535)
            return data
        finally:
            if timeout is not None:
                self._sock.settimeout(previous_timeout)

    def _emit_trace(self, trace: SlmpTraceFrame) -> None:
        if self.trace_hook is None:
            return
        try:
            self.trace_hook(trace)
        except Exception:
            # Trace callback failures must not affect protocol behavior.
            pass


def _recv_tcp_frame(sock: socket.socket, *, frame_type: FrameType) -> bytes:
    # 4E response header up to data length: Subheader(2) + Serial(2) + Reserved(2) + Target(5) + Len(2) = 13 bytes.
    # 3E response header up to data length: Subheader(2) + Target(5) + Len(2) = 9 bytes.
    head_size = 13 if frame_type == FrameType.FRAME_4E else 9
    head = bytearray(head_size)
    _recv_exact_into(sock, memoryview(head))
    response_data_length = int.from_bytes(head[-2:], "little")
    frame = bytearray(head_size + response_data_length)
    frame[:head_size] = head
    _recv_exact_into(sock, memoryview(frame)[head_size:])
    return bytes(frame)


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
