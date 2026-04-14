"""SLMP binary client."""

from __future__ import annotations

import socket
import struct
import warnings
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

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
    _check_label_unit_specification,
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
    _normalize_device_family_hint,
    _normalize_items,
    _raise_response_error,
    _require_explicit_device_family_for_xy,
    _validate_block_read_devices,
    _validate_block_write_devices,
    _validate_direct_read_device,
    _validate_monitor_register_devices,
    _validate_random_read_devices,
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
from .errors import SlmpError, SlmpPracticalPathWarning

if TYPE_CHECKING:
    from .device_ranges import SlmpDeviceRangeCatalog, SlmpDeviceRangeFamily


class SlmpClient:
    """Synchronous SLMP client supporting 3E and 4E frames (binary).

    This client provides high-level typed APIs for interacting with Mitsubishi
    and compatible PLCs using the SLMP protocol.

    Examples:
        >>> from slmp.client import SlmpClient
        >>> with SlmpClient("192.168.250.100", 1025) as client:
        ...     values = client.read_devices("D100", 5)
        ...     print(values)
        [0, 0, 0, 0, 0]
    """

    def __init__(
        self,
        host: str,
        port: int = 5000,
        *,
        transport: str = "tcp",
        timeout: float = 3.0,
        plc_series: PLCSeries | str = PLCSeries.QL,
        frame_type: FrameType | str = FrameType.FRAME_4E,
        default_target: SlmpTarget | None = None,
        monitoring_timer: int = 0x0010,
        raise_on_error: bool = True,
        trace_hook: Callable[[SlmpTraceFrame], None] | None = None,
        device_family: object | None = None,
    ) -> None:
        """Initialize the SLMP client.

        Args:
            host: PLC IP address.
            port: PLC port number. Defaults to 5000.
            transport: Transport protocol ('tcp' or 'udp'). Defaults to 'tcp'.
            timeout: Socket timeout in seconds. Defaults to 3.0.
            plc_series: Target PLC series. Defaults to QL.
            frame_type: SLMP frame type. Defaults to 4E.
            device_family: Canonical address family used for string device parsing,
                such as ``"iq-f"``, ``"qcpu"``, or ``"qnudv"``.
            default_target: Default target station routing information.
            monitoring_timer: Default monitoring timer value (multiples of 250ms). Defaults to 0x0010 (4s).
            raise_on_error: Whether to raise SlmpError on non-zero end codes. Defaults to True.
            trace_hook: Optional callback for tracing requests and responses.
        """
        self.host = host
        self.port = port
        self.transport = transport.lower()
        if self.transport not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.timeout = timeout
        self.plc_series = PLCSeries(plc_series)
        self.frame_type = FrameType(frame_type)
        self.default_target = default_target or SlmpTarget()
        self.monitoring_timer = monitoring_timer
        self.raise_on_error = raise_on_error
        self.trace_hook = trace_hook
        self.device_family = _normalize_device_family_hint(device_family)

        self._serial = 0
        self._sock: socket.socket | None = None

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
        _check_points_u16(points, "points")
        s = PLCSeries(series) if series is not None else self.plc_series
        ref = self._parse_device(device)
        _validate_direct_read_device(ref, points=points, bit_unit=bit_unit)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=s, access_kind="direct")
        _warn_boundary_behavior(
            ref,
            series=s,
            points=points,
            write=False,
            bit_unit=bit_unit,
            access_kind="direct",
        )
        sub = resolve_device_subcommand(bit_unit=bit_unit, series=s, extension=False)
        payload = encode_device_spec(ref, series=s) + points.to_bytes(2, "little")
        resp = self.request(Command.DEVICE_READ, subcommand=sub, data=payload)
        if bit_unit:
            return unpack_bit_values(resp.data, points)
        words = decode_device_words(resp.data)
        if len(words) != points:
            raise SlmpError(f"word count mismatch: expected={points}, actual={len(words)}")
        return words

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
        if not values:
            raise ValueError("values must not be empty")
        s = PLCSeries(series) if series is not None else self.plc_series
        ref = self._parse_device(device)
        _check_temporarily_unsupported_device(ref)
        _warn_practical_device_path(ref, series=s, access_kind="direct")
        _warn_boundary_behavior(
            ref,
            series=s,
            points=len(values),
            write=True,
            bit_unit=bit_unit,
            access_kind="direct",
        )
        sub = resolve_device_subcommand(bit_unit=bit_unit, series=s, extension=False)

        payload = bytearray()
        payload += encode_device_spec(ref, series=s)
        payload += len(values).to_bytes(2, "little")
        if bit_unit:
            payload += pack_bit_values(values)
        else:
            for value in values:
                payload += int(value).to_bytes(2, "little", signed=False)
        self.request(Command.DEVICE_WRITE, subcommand=sub, data=bytes(payload))

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
        if count < 1:
            raise ValueError("count must be >= 1")
        words = [int(value) for value in self.read_devices(device, count * 2, series=series)]
        values: list[int] = []
        for offset in range(0, len(words), 2):
            values.append(words[offset] | (words[offset + 1] << 16))
        return values

    def write_dwords(
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
        self.write_devices(device, words, series=series)

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
        values: list[float] = []
        for bits in self.read_dwords(device, count, series=series):
            values.append(struct.unpack("<f", struct.pack("<I", bits))[0])
        return values

    def write_float32s(
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
        self.write_dwords(device, dwords, series=series)

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
        _check_points_u16(points, "points")
        s = PLCSeries(series) if series is not None else self.plc_series
        ref, effective_extension = self._resolve_extended_device_and_extension(device, extension)
        _check_temporarily_unsupported_device(ref, access_kind="extended_device")
        _warn_practical_device_path(ref, series=s, access_kind="extended_device")
        if effective_extension.direct_memory_specification == DIRECT_MEMORY_LINK_DIRECT:
            s = PLCSeries.QL
        sub = resolve_device_subcommand(bit_unit=bit_unit, series=s, extension=True)
        payload = bytearray()
        payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        payload += points.to_bytes(2, "little")
        resp = self.request(Command.DEVICE_READ, subcommand=sub, data=bytes(payload))
        if bit_unit:
            return unpack_bit_values(resp.data, points)
        words = decode_device_words(resp.data)
        if len(words) != points:
            raise SlmpError(f"word count mismatch: expected={points}, actual={len(words)}")
        return words

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
        if not values:
            raise ValueError("values must not be empty")
        s = PLCSeries(series) if series is not None else self.plc_series
        ref, effective_extension = self._resolve_extended_device_and_extension(device, extension)
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
        self.request(Command.DEVICE_WRITE, subcommand=sub, data=bytes(payload))

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
        if not word_devices and not dword_devices:
            raise ValueError("word_devices and dword_devices must not both be empty")
        if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
            raise ValueError("word_devices and dword_devices must be <= 255 each")
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

        resp = self.request(Command.DEVICE_READ_RANDOM, subcommand=sub, data=bytes(payload))
        expected = len(words) * 2 + len(dwords) * 4
        if len(resp.data) != expected:
            raise SlmpError(f"random read response size mismatch: expected={expected}, actual={len(resp.data)}")

        offset = 0
        word_values = decode_device_words(resp.data[offset : offset + (len(words) * 2)])
        offset += len(words) * 2
        dword_values = decode_device_dwords(resp.data[offset:])
        return RandomReadResult(
            word={str(dev): value for dev, value in zip(words, word_values, strict=True)},
            dword={str(dev): value for dev, value in zip(dwords, dword_values, strict=True)},
        )

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

        resp = self.request(Command.DEVICE_READ_RANDOM, subcommand=sub, data=bytes(payload))
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
        word_items = _normalize_items(word_values)
        dword_items = _normalize_items(dword_values)
        if not word_items and not dword_items:
            raise ValueError("word_values and dword_values must not both be empty")
        if len(word_items) > 0xFF or len(dword_items) > 0xFF:
            raise ValueError("word_values and dword_values must be <= 255 each")

        s = PLCSeries(series) if series is not None else self.plc_series
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=False)
        payload = bytearray([len(word_items), len(dword_items)])
        for device, value in word_items:
            _check_temporarily_unsupported_device(device)
            payload += encode_device_spec(device, series=s)
            payload += int(value).to_bytes(2, "little", signed=False)
        for device, value in dword_items:
            _check_temporarily_unsupported_device(device)
            payload += encode_device_spec(device, series=s)
            payload += int(value).to_bytes(4, "little", signed=False)
        self.request(Command.DEVICE_WRITE_RANDOM, subcommand=sub, data=bytes(payload))

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
        if not word_values and not dword_values:
            raise ValueError("word_values and dword_values must not both be empty")
        if len(word_values) > 0xFF or len(dword_values) > 0xFF:
            raise ValueError("word_values and dword_values must be <= 255 each")
        s = PLCSeries(series) if series is not None else self.plc_series
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=True)
        payload = bytearray([len(word_values), len(dword_values)])
        for device, value, ext in word_values:
            ref, effective_extension = self._resolve_extended_device_and_extension(device, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
            payload += int(value).to_bytes(2, "little", signed=False)
        for device, value, ext in dword_values:
            ref, effective_extension = self._resolve_extended_device_and_extension(device, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
            payload += int(value).to_bytes(4, "little", signed=False)
        self.request(Command.DEVICE_WRITE_RANDOM, subcommand=sub, data=bytes(payload))

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
        items = _normalize_items(bit_values)
        if not items:
            raise ValueError("bit_values must not be empty")
        if len(items) > 0xFF:
            raise ValueError("bit_values must be <= 255")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_bit_write_count(len(items), series=s, name="write_random_bits")
        sub = resolve_device_subcommand(bit_unit=True, series=s, extension=False)
        payload = bytearray([len(items)])
        for device, state in items:
            _check_temporarily_unsupported_device(device)
            payload += encode_device_spec(device, series=s)
            if s == PLCSeries.IQR:
                # iQ-R/iQ-L random bit write uses 2-byte set/reset field.
                # ON must be encoded as 0x0001 (01 00 in little-endian).
                payload += b"\x01\x00" if bool(state) else b"\x00\x00"
            else:
                payload += b"\x01" if bool(state) else b"\x00"
        self.request(Command.DEVICE_WRITE_RANDOM, subcommand=sub, data=bytes(payload))

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
        self.request(Command.DEVICE_WRITE_RANDOM, subcommand=sub, data=bytes(payload))

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
        if not word_devices and not dword_devices:
            raise ValueError("word_devices and dword_devices must not both be empty")
        if len(word_devices) > 0xFF or len(dword_devices) > 0xFF:
            raise ValueError("word_devices and dword_devices must be <= 255 each")
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_random_read_like_counts(
            len(word_devices),
            len(dword_devices),
            series=s,
            name="register_monitor_devices",
        )
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
        self.request(Command.DEVICE_ENTRY_MONITOR, subcommand=sub, data=bytes(payload))

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
        for dev, ext in word_devices:
            ref, effective_extension = self._resolve_extended_device_and_extension(dev, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        for dev, ext in dword_devices:
            ref, effective_extension = self._resolve_extended_device_and_extension(dev, ext)
            _check_temporarily_unsupported_device(ref, access_kind="extended_device")
            payload += encode_extended_device_spec(ref, series=s, extension=effective_extension)
        self.request(Command.DEVICE_ENTRY_MONITOR, subcommand=sub, data=bytes(payload))

    def run_monitor_cycle(self, *, word_points: int, dword_points: int) -> MonitorResult:
        """Execute a monitoring cycle for previously registered devices.

        Args:
            word_points: Number of registered word points.
            dword_points: Number of registered double-word points.

        Returns:
            MonitorResult containing the read values.

        """
        if word_points < 0 or dword_points < 0:
            raise ValueError("word_points and dword_points must be >= 0")
        resp = self.request(Command.DEVICE_EXECUTE_MONITOR, subcommand=0x0000, data=b"")
        expected = word_points * 2 + dword_points * 4
        if len(resp.data) != expected:
            raise SlmpError(f"monitor response size mismatch: expected={expected}, actual={len(resp.data)}")
        offset = 0
        words = decode_device_words(resp.data[offset : offset + word_points * 2])
        offset += word_points * 2
        dwords = decode_device_dwords(resp.data[offset:])
        return MonitorResult(word=words, dword=dwords)

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
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_block_request_limits(word_blocks, bit_blocks, series=s, name="read_block")
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=False)

        payload = bytearray([len(word_blocks), len(bit_blocks)])
        norm_word: list[tuple[DeviceRef, int]] = []
        norm_bit: list[tuple[DeviceRef, int]] = []

        for dev, points in word_blocks:
            _check_points_u16(points, "word_block points")
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            _warn_practical_device_path(ref, series=s, access_kind="direct")
            norm_word.append((ref, points))
            payload += encode_device_spec(ref, series=s)
            payload += points.to_bytes(2, "little")
        for dev, points in bit_blocks:
            _check_points_u16(points, "bit_block points")
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            _warn_practical_device_path(ref, series=s, access_kind="direct")
            norm_bit.append((ref, points))
            payload += encode_device_spec(ref, series=s)
            payload += points.to_bytes(2, "little")
        _validate_block_read_devices([ref for ref, _ in norm_word], [ref for ref, _ in norm_bit])

        resp = self.request(Command.DEVICE_READ_BLOCK, subcommand=sub, data=bytes(payload))

        offset = 0
        word_result: list[DeviceBlockResult] = []
        for ref, points in norm_word:
            size = points * 2
            words = decode_device_words(resp.data[offset : offset + size])
            if len(words) != points:
                raise SlmpError(f"word block response mismatch for {ref}")
            word_result.append(DeviceBlockResult(device=str(ref), values=words))
            offset += size

        bit_result: list[DeviceBlockResult] = []
        for ref, points in norm_bit:
            size = points * 2
            words = decode_device_words(resp.data[offset : offset + size])
            if len(words) != points:
                raise SlmpError(f"bit block response mismatch for {ref}")
            bit_result.append(DeviceBlockResult(device=str(ref), values=words))
            offset += size

        if offset != len(resp.data):
            raise SlmpError(f"read block response trailing data: {len(resp.data) - offset} bytes")
        return BlockReadResult(word_blocks=word_result, bit_blocks=bit_result)

    def write_block(
        self,
        *,
        word_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
        bit_blocks: Sequence[tuple[str | DeviceRef, Sequence[int]]] = (),
        series: PLCSeries | str | None = None,
        split_mixed_blocks: bool = False,
        retry_mixed_on_error: bool = False,
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
                retry_mixed_on_error=False,
            )
            self.write_block(
                word_blocks=(),
                bit_blocks=bit_blocks,
                series=series,
                split_mixed_blocks=False,
                retry_mixed_on_error=False,
            )
            return
        s = PLCSeries(series) if series is not None else self.plc_series
        _check_block_request_limits(word_blocks, bit_blocks, series=s, name="write_block")
        sub = resolve_device_subcommand(bit_unit=False, series=s, extension=False)

        payload = bytearray([len(word_blocks), len(bit_blocks)])
        word_refs: list[DeviceRef] = []
        bit_refs: list[DeviceRef] = []
        for dev, values in word_blocks:
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            _warn_practical_device_path(ref, series=s, access_kind="direct")
            _check_points_u16(len(values), "word block size")
            payload += encode_device_spec(ref, series=s)
            payload += len(values).to_bytes(2, "little")
            word_refs.append(ref)
        for dev, values in bit_blocks:
            ref = self._parse_device(dev)
            _check_temporarily_unsupported_device(ref)
            _warn_practical_device_path(ref, series=s, access_kind="direct")
            _check_points_u16(len(values), "bit block size")
            payload += encode_device_spec(ref, series=s)
            payload += len(values).to_bytes(2, "little")
            bit_refs.append(ref)
        _validate_block_write_devices(word_refs, bit_refs)

        for _, values in word_blocks:
            for value in values:
                payload += int(value).to_bytes(2, "little", signed=False)
        for _, values in bit_blocks:
            for value in values:
                payload += int(value).to_bytes(2, "little", signed=False)
        resp = self.request(
            Command.DEVICE_WRITE_BLOCK,
            subcommand=sub,
            data=bytes(payload),
            raise_on_error=False,
        )
        if resp.end_code == 0:
            return
        if retry_mixed_on_error and word_blocks and bit_blocks and resp.end_code in _MIXED_BLOCK_RETRY_END_CODES:
            warnings.warn(
                (
                    f"mixed block write was rejected with 0x{resp.end_code:04X}; "
                    "retrying as separate word-only and bit-only block writes"
                ),
                SlmpPracticalPathWarning,
                stacklevel=2,
            )
            self.write_block(
                word_blocks=word_blocks,
                bit_blocks=(),
                series=series,
                split_mixed_blocks=False,
                retry_mixed_on_error=False,
            )
            self.write_block(
                word_blocks=(),
                bit_blocks=bit_blocks,
                series=series,
                split_mixed_blocks=False,
                retry_mixed_on_error=False,
            )
            return
        if self.raise_on_error:
            _raise_response_error(resp, command=Command.DEVICE_WRITE_BLOCK, subcommand=sub)

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
        _check_u32(head_address, "head_address")
        if word_length < 1 or word_length > 0x01E0:
            raise ValueError(f"word_length out of range (1..480): {word_length}")
        payload = head_address.to_bytes(4, "little") + word_length.to_bytes(2, "little")
        data = self.request(Command.MEMORY_READ, 0x0000, payload).data
        words = decode_device_words(data)
        if len(words) != word_length:
            raise SlmpError(f"memory read size mismatch: expected={word_length}, actual={len(words)}")
        return words

    def memory_write_words(self, head_address: int, values: Sequence[int]) -> None:
        """Write 16-bit words to intelligent function module/special function module buffer memory.

        Args:
            head_address: Start address.
            values: Sequence of 16-bit word values to write.

        """
        _check_u32(head_address, "head_address")
        if not values:
            raise ValueError("values must not be empty")
        if len(values) > 0x01E0:
            raise ValueError(f"word length out of range (1..480): {len(values)}")
        payload = bytearray()
        payload += head_address.to_bytes(4, "little")
        payload += len(values).to_bytes(2, "little")
        for value in values:
            payload += int(value).to_bytes(2, "little", signed=False)
        self.request(Command.MEMORY_WRITE, 0x0000, bytes(payload))

    def extend_unit_read_bytes(self, head_address: int, byte_length: int, module_no: int) -> bytes:
        """Read bytes from multiple-CPU shared memory or other extended units.

        Args:
            head_address: Start address.
            byte_length: Number of bytes to read.
            module_no: Module number or unit identification.

        Returns:
            Read data as bytes.

        """
        _check_u32(head_address, "head_address")
        _check_u16(module_no, "module_no")
        if byte_length < 2 or byte_length > 0x0780:
            raise ValueError(f"byte_length out of range (2..1920): {byte_length}")
        payload = (
            head_address.to_bytes(4, "little") + byte_length.to_bytes(2, "little") + module_no.to_bytes(2, "little")
        )
        data = self.request(Command.EXTEND_UNIT_READ, 0x0000, payload).data
        if len(data) != byte_length:
            raise SlmpError(f"extend unit read size mismatch: expected={byte_length}, actual={len(data)}")
        return data

    def extend_unit_read_words(self, head_address: int, word_length: int, module_no: int) -> list[int]:
        """Read 16-bit words from multiple-CPU shared memory or other extended units.

        Args:
            head_address: Start address.
            word_length: Number of words to read.
            module_no: Module number or unit identification.

        Returns:
            List of 16-bit word values.

        """
        _check_u32(head_address, "head_address")
        if word_length < 1 or word_length > 0x03C0:
            raise ValueError(f"word_length out of range (1..960): {word_length}")
        data = self.extend_unit_read_bytes(head_address, word_length * 2, module_no)
        words = decode_device_words(data)
        if len(words) != word_length:
            raise SlmpError(f"extend unit read word size mismatch: expected={word_length}, actual={len(words)}")
        return words

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
        _check_u32(head_address, "head_address")
        _check_u16(module_no, "module_no")
        if len(data) < 2 or len(data) > 0x0780:
            raise ValueError(f"data length out of range (2..1920): {len(data)}")
        payload = (
            head_address.to_bytes(4, "little")
            + len(data).to_bytes(2, "little")
            + module_no.to_bytes(2, "little")
            + data
        )
        self.request(Command.EXTEND_UNIT_WRITE, 0x0000, payload)

    def extend_unit_write_words(self, head_address: int, module_no: int, values: Sequence[int]) -> None:
        """Write 16-bit words to multiple-CPU shared memory or other extended units.

        Args:
            head_address: Start address.
            module_no: Module number or unit identification.
            values: Sequence of 16-bit word values to write.

        """
        _check_u32(head_address, "head_address")
        if not values:
            raise ValueError("values must not be empty")
        if len(values) > 0x03C0:
            raise ValueError(f"word_length out of range (1..960): {len(values)}")
        payload = bytearray()
        for value in values:
            payload += int(value).to_bytes(2, "little", signed=False)
        self.extend_unit_write_bytes(head_address, module_no, bytes(payload))

    def extend_unit_write_word(self, head_address: int, module_no: int, value: int) -> None:
        """Write one 16-bit word to an extend-unit buffer."""
        _check_u16(value, "value")
        self.extend_unit_write_words(head_address, module_no, [value])

    def extend_unit_write_dword(self, head_address: int, module_no: int, value: int) -> None:
        """Write one 32-bit value to an extend-unit buffer."""
        _check_u32(value, "value")
        self.extend_unit_write_bytes(head_address, module_no, int(value).to_bytes(4, "little", signed=False))

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

    def remote_run(self, *, force: bool = False, clear_mode: int = 2) -> None:
        """Remote RUN.

        Args:
            force: Force RUN even if the RUN/STOP switch is at STOP.
            clear_mode: Clear mode (0: No clear, 1: Clear except latch, 2: Clear all).

        """
        if clear_mode not in {0, 1, 2}:
            raise ValueError(f"clear_mode must be one of 0,1,2: {clear_mode}")
        mode = 0x0003 if force else 0x0001
        payload = mode.to_bytes(2, "little") + clear_mode.to_bytes(2, "little")
        self.request(Command.REMOTE_RUN, 0x0000, payload)

    def remote_stop(self) -> None:
        """Remote STOP."""
        self.request(Command.REMOTE_STOP, 0x0000, b"\x01\x00")

    def remote_pause(self, *, force: bool = False) -> None:
        """Remote PAUSE.

        Args:
            force: Force PAUSE.

        """
        mode = 0x0003 if force else 0x0001
        self.request(Command.REMOTE_PAUSE, 0x0000, mode.to_bytes(2, "little"))

    def remote_latch_clear(self) -> None:
        """Remote latch clear."""
        self.request(Command.REMOTE_LATCH_CLEAR, 0x0000, b"\x01\x00")

    def remote_reset(self, *, subcommand: int = 0x0000, expect_response: bool | None = None) -> None:
        """Remote RESET.

        Args:
            subcommand: Subcommand (0x0000: RESET, 0x0001: RESET and wait).
            expect_response: Whether to wait for a response.

        """
        if subcommand not in {0x0000, 0x0001}:
            raise ValueError(f"remote reset subcommand must be 0x0000 or 0x0001: 0x{subcommand:04X}")
        should_wait = (subcommand != 0x0000) if expect_response is None else expect_response
        if should_wait:
            self.request(Command.REMOTE_RESET, subcommand, b"")
            return
        self._send_no_response(Command.REMOTE_RESET, subcommand, b"")

    def remote_password_lock(self, password: str, *, series: PLCSeries | str | None = None) -> None:
        """Remote password lock.

        Args:
            password: Password string.
            series: Optional PLC series override.

        """
        s = PLCSeries(series) if series is not None else self.plc_series
        payload = _encode_remote_password_payload(password, series=s)
        self.request(Command.REMOTE_PASSWORD_LOCK, 0x0000, payload)

    def remote_password_unlock(self, password: str, *, series: PLCSeries | str | None = None) -> None:
        """Remote password unlock.

        Args:
            password: Password string.
            series: Optional PLC series override.

        """
        s = PLCSeries(series) if series is not None else self.plc_series
        payload = _encode_remote_password_payload(password, series=s)
        self.request(Command.REMOTE_PASSWORD_UNLOCK, 0x0000, payload)

    def self_test_loopback(self, data: bytes | str) -> bytes:
        """Self-test (loopback).

        Args:
            data: Data to send for loopback test.

        Returns:
            Received loopback data.

        """
        loopback = data.encode("ascii") if isinstance(data, str) else bytes(data)
        if len(loopback) < 1 or len(loopback) > 960:
            raise ValueError(f"loopback data size out of range (1..960): {len(loopback)}")
        payload = len(loopback).to_bytes(2, "little") + loopback
        resp = self.request(Command.SELF_TEST, 0x0000, payload).data
        if len(resp) < 2:
            raise SlmpError(f"self test response too short: {len(resp)}")
        size = int.from_bytes(resp[:2], "little")
        body = resp[2:]
        if size != len(body):
            raise SlmpError(f"self test response size mismatch: size={size}, actual={len(body)}")
        return body

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
        payload = self.build_array_label_read_payload(points, abbreviation_labels=abbreviation_labels)
        data = self.request(Command.LABEL_ARRAY_READ, 0x0000, payload).data
        return self.parse_array_label_read_response(data, expected_points=len(points))

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
        payload = self.build_array_label_write_payload(points, abbreviation_labels=abbreviation_labels)
        self.request(Command.LABEL_ARRAY_WRITE, 0x0000, payload)

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
        payload = self.build_label_read_random_payload(labels, abbreviation_labels=abbreviation_labels)
        data = self.request(Command.LABEL_READ_RANDOM, 0x0000, payload).data
        return self.parse_label_read_random_response(data, expected_points=len(labels))

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
        payload = self.build_label_write_random_payload(points, abbreviation_labels=abbreviation_labels)
        self.request(Command.LABEL_WRITE_RANDOM, 0x0000, payload)

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
        if not points:
            raise ValueError("points must not be empty")
        _check_u16(len(points), "number of array points")
        _check_u16(len(abbreviation_labels), "number of abbreviation points")
        payload = bytearray()
        payload += len(points).to_bytes(2, "little")
        payload += len(abbreviation_labels).to_bytes(2, "little")
        for name in abbreviation_labels:
            payload += _encode_label_name(name)
        for point in points:
            _check_label_unit_specification(point.unit_specification, "unit_specification")
            _check_u16(point.array_data_length, "array_data_length")
            payload += _encode_label_name(point.label)
            payload += point.unit_specification.to_bytes(1, "little")
            payload += b"\x00"
            payload += point.array_data_length.to_bytes(2, "little")
        return bytes(payload)

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
        if not points:
            raise ValueError("points must not be empty")
        _check_u16(len(points), "number of array points")
        _check_u16(len(abbreviation_labels), "number of abbreviation points")
        payload = bytearray()
        payload += len(points).to_bytes(2, "little")
        payload += len(abbreviation_labels).to_bytes(2, "little")
        for name in abbreviation_labels:
            payload += _encode_label_name(name)
        for point in points:
            _check_label_unit_specification(point.unit_specification, "unit_specification")
            _check_u16(point.array_data_length, "array_data_length")
            raw = bytes(point.data)
            expected = _label_array_data_bytes(point.unit_specification, point.array_data_length)
            if len(raw) != expected:
                raise ValueError(
                    "array label write data size mismatch: "
                    f"expected={expected}, actual={len(raw)}, unit_specification={point.unit_specification}, "
                    f"array_data_length={point.array_data_length}"
                )
            payload += _encode_label_name(point.label)
            payload += point.unit_specification.to_bytes(1, "little")
            payload += b"\x00"
            payload += point.array_data_length.to_bytes(2, "little")
            payload += raw
        return bytes(payload)

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
        if not labels:
            raise ValueError("labels must not be empty")
        _check_u16(len(labels), "number of read data points")
        _check_u16(len(abbreviation_labels), "number of abbreviation points")
        payload = bytearray()
        payload += len(labels).to_bytes(2, "little")
        payload += len(abbreviation_labels).to_bytes(2, "little")
        for name in abbreviation_labels:
            payload += _encode_label_name(name)
        for label in labels:
            payload += _encode_label_name(label)
        return bytes(payload)

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
        if not points:
            raise ValueError("points must not be empty")
        _check_u16(len(points), "number of write data points")
        _check_u16(len(abbreviation_labels), "number of abbreviation points")
        payload = bytearray()
        payload += len(points).to_bytes(2, "little")
        payload += len(abbreviation_labels).to_bytes(2, "little")
        for name in abbreviation_labels:
            payload += _encode_label_name(name)
        for point in points:
            raw = bytes(point.data)
            _check_u16(len(raw), "write data length")
            payload += _encode_label_name(point.label)
            payload += len(raw).to_bytes(2, "little")
            payload += raw
        return bytes(payload)

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
        if len(data) < 2:
            raise SlmpError(f"array label read response too short: {len(data)}")
        points = int.from_bytes(data[:2], "little")
        if expected_points is not None and points != expected_points:
            raise SlmpError(f"array label read point count mismatch: expected={expected_points}, actual={points}")
        offset = 2
        out: list[LabelArrayReadResult] = []
        for _ in range(points):
            if offset + 4 > len(data):
                raise SlmpError("array label read response truncated before metadata")
            data_type_id = data[offset]
            unit_specification = data[offset + 1]
            _check_label_unit_specification(unit_specification, "response unit_specification")
            array_data_length = int.from_bytes(data[offset + 2 : offset + 4], "little")
            offset += 4
            data_size = _label_array_data_bytes(unit_specification, array_data_length)
            if offset + data_size > len(data):
                raise SlmpError(
                    "array label read response truncated in data payload: "
                    f"needed={data_size}, remaining={len(data) - offset}"
                )
            raw = data[offset : offset + data_size]
            offset += data_size
            out.append(
                LabelArrayReadResult(
                    data_type_id=data_type_id,
                    unit_specification=unit_specification,
                    array_data_length=array_data_length,
                    data=raw,
                )
            )
        if offset != len(data):
            raise SlmpError(f"array label read response has trailing bytes: {len(data) - offset}")
        return out

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
        if len(data) < 2:
            raise SlmpError(f"label random read response too short: {len(data)}")
        points = int.from_bytes(data[:2], "little")
        if expected_points is not None and points != expected_points:
            raise SlmpError(f"label random read point count mismatch: expected={expected_points}, actual={points}")
        offset = 2
        out: list[LabelRandomReadResult] = []
        for _ in range(points):
            if offset + 4 > len(data):
                raise SlmpError("label random read response truncated before metadata")
            data_type_id = data[offset]
            spare = data[offset + 1]
            read_data_length = int.from_bytes(data[offset + 2 : offset + 4], "little")
            offset += 4
            if offset + read_data_length > len(data):
                raise SlmpError(
                    "label random read response truncated in data payload: "
                    f"needed={read_data_length}, remaining={len(data) - offset}"
                )
            raw = data[offset : offset + read_data_length]
            offset += read_data_length
            out.append(
                LabelRandomReadResult(
                    data_type_id=data_type_id,
                    spare=spare,
                    read_data_length=read_data_length,
                    data=raw,
                )
            )
        if offset != len(data):
            raise SlmpError(f"label random read response has trailing bytes: {len(data) - offset}")
        return out

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

    def remote_reset_raw(self, payload: bytes = b"") -> None:
        """Low-level wrapper for REMOTE_RESET command (no response)."""
        if payload:
            raise ValueError("remote reset does not use request data")
        self._send_no_response(Command.REMOTE_RESET, 0x0000, b"")

    def read_type_name(self) -> TypeNameInfo:
        """Read the PLC model name and code."""
        data = self.request(Command.READ_TYPE_NAME, 0x0000, b"").data
        model = ""
        model_code = None
        if len(data) >= 16:
            model = data[:16].split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        if len(data) >= 18:
            model_code = int.from_bytes(data[16:18], "little")
        return TypeNameInfo(raw=data, model=model, model_code=model_code)

    def read_device_range_catalog_for_family(
        self,
        family: SlmpDeviceRangeFamily | str,
    ) -> SlmpDeviceRangeCatalog:
        """Read the configured device-range catalog for one canonical explicit PLC family."""
        from .device_ranges import read_device_range_catalog_for_family_sync

        return read_device_range_catalog_for_family_sync(self, family)

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
