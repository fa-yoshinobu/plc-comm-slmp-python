"""Unit tests for AsyncSlmpClient using a mock SLMP server."""

import asyncio
import re
from contextlib import AbstractContextManager
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - lets unittest discovery import this module without pytest

    class _RaisesContext(AbstractContextManager):
        def __init__(self, expected_exception: type[BaseException], match: str | None = None) -> None:
            self._expected_exception = expected_exception
            self._match = match

        def __exit__(self, exc_type, exc, tb) -> bool:
            if exc_type is None:
                raise AssertionError(f"{self._expected_exception.__name__} was not raised")
            if not issubclass(exc_type, self._expected_exception):
                return False
            if self._match and not re.search(self._match, str(exc)):
                raise AssertionError(f"{self._match!r} did not match {exc!r}")
            return True

    class _PytestFallback:
        class mark:
            @staticmethod
            def asyncio(func):
                return func

        @staticmethod
        def raises(expected_exception: type[BaseException], match: str | None = None) -> _RaisesContext:
            return _RaisesContext(expected_exception, match)

    pytest = _PytestFallback()

from slmp.async_client import AsyncSlmpClient
from slmp.constants import Command, CpuModule, PLCSeries, RemoteClearMode
from slmp.core import DeviceRef, SlmpError, SlmpResponse, SlmpTarget
from slmp.errors import SlmpProfileFeatureError


def _build_4e_response(serial: int, data: bytes, *, end_code: int = 0) -> bytes:
    payload = end_code.to_bytes(2, "little") + data
    return (
        b"\xd4\x00"
        + serial.to_bytes(2, "little")
        + b"\x00\x00"
        + b"\x00\xff\xff\x03\x00"
        + len(payload).to_bytes(2, "little")
        + payload
    )


# --- Mock SLMP Server for Testing ---


@pytest.mark.asyncio
async def test_async_tcp_connect_closes_writer_when_required_keepalive_setup_fails() -> None:
    target = SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0)
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=target,
        plc_profile="melsec:iq-r",
    )
    reader = MagicMock()
    writer = MagicMock()
    writer.get_extra_info.return_value = MagicMock()
    writer.wait_closed = AsyncMock()

    with (
        patch("slmp.async_client.asyncio.open_connection", new=AsyncMock(return_value=(reader, writer))),
        patch("slmp.async_client.configure_tcp_keepalive", side_effect=OSError("keepalive unavailable")),
    ):
        with pytest.raises(OSError, match="keepalive unavailable"):
            await client.connect()

    writer.close.assert_called_once_with()
    writer.wait_closed.assert_awaited_once_with()
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_async_raise_on_error_requires_real_booleans_before_transport() -> None:
    target = SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0)
    with pytest.raises(ValueError, match="raise_on_error must be a boolean"):
        AsyncSlmpClient(  # type: ignore[arg-type]
            "127.0.0.1",
            1025,
            transport="tcp",
            default_target=target,
            plc_profile="melsec:iq-r",
            raise_on_error="false",
        )

    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=target,
        plc_profile="melsec:iq-r",
    )
    with pytest.raises(ValueError, match="raise_on_error must be a boolean"):
        await client._request(  # type: ignore[arg-type]
            Command.SELF_TEST,
            0,
            b"",
            raise_on_error="false",
        )
    assert client._reader is None

    async def respond(frame: bytes) -> bytes:
        client.raise_on_error = False
        return _build_4e_response(int.from_bytes(frame[2:4], "little"), b"ng", end_code=0xC051)

    client.raise_on_error = True
    with patch.object(client, "_send_and_receive", side_effect=respond):
        with pytest.raises(SlmpError):
            await client.raw_command(Command.CLEAR_ERROR, subcommand=0, payload=b"")
        client.raise_on_error = True
        response = await client.raw_command(
            Command.CLEAR_ERROR,
            subcommand=0,
            payload=b"",
            raise_on_error=False,
        )
        assert response.end_code == 0xC051
        client.raise_on_error = False
        response = await client.raw_command(Command.CLEAR_ERROR, subcommand=0, payload=b"")
        assert response.end_code == 0xC051


@pytest.mark.asyncio
async def test_async_request_monitoring_timer_rejects_invalid_override_before_transport() -> None:
    target = SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0)
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=target,
        plc_profile="melsec:iq-r",
    )
    for invalid in (False, True, -1, 0x10000, 1.5, "16", [], {}):
        with pytest.raises(ValueError, match="monitoring_timer must be an integer"):
            await client.raw_command(  # type: ignore[arg-type]
                Command.CLEAR_ERROR,
                subcommand=0,
                payload=b"",
                monitoring_timer=invalid,
            )
    assert client._reader is None


@pytest.mark.asyncio
async def test_async_generic_device_bit_unit_is_required_and_must_be_boolean() -> None:
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
    )
    with pytest.raises(TypeError):
        await client.read_devices("D0", 1)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await client.write_devices("D0", [1])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await client.read_devices_ext(r"U3E0\G0", 1)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await client.write_devices_ext(r"U3E0\G0", [1])  # type: ignore[call-arg]

    for invalid in (None, 0, 1, "false", "", [], {}):
        with pytest.raises(ValueError, match="bit_unit is required and must be a boolean"):
            await client.read_devices("D0", 1, bit_unit=invalid)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="bit_unit is required and must be a boolean"):
            await client.write_devices("D0", [1], bit_unit=invalid)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="bit_unit is required and must be a boolean"):
            await client.read_devices_ext(r"U3E0\G0", 1, bit_unit=invalid)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="bit_unit is required and must be a boolean"):
            await client.write_devices_ext(r"U3E0\G0", [1], bit_unit=invalid)  # type: ignore[arg-type]
    assert client._reader is None
    assert client._writer is None


def test_async_maintainer_trace_hook_defaults_off_and_requires_callable() -> None:
    target = SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0)
    client = AsyncSlmpClient(
        "127.0.0.1",
        1025,
        transport="tcp",
        default_target=target,
        plc_profile="melsec:iq-r",
    )
    assert client._trace_hook is None
    with pytest.raises(ValueError, match="_maintainer_trace_hook must be callable or None"):
        AsyncSlmpClient(  # type: ignore[arg-type]
            "127.0.0.1",
            1025,
            transport="tcp",
            default_target=target,
            plc_profile="melsec:iq-r",
            _maintainer_trace_hook="stdout",
        )


class MockSLMPServer:
    """Mock SLMP server for testing."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        """Initialize mock server."""
        self.host = host
        self.port = port
        self.server: asyncio.AbstractServer | None = None

    async def start(self) -> "MockSLMPServer":
        """Start the mock server."""
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        """Stop the mock server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle client connection."""
        try:
            while True:
                # Read Header (4E: 13 bytes)
                head = await reader.readexactly(13)
                if not head:
                    break

                data_len = int.from_bytes(head[11:13], "little")
                body = await reader.readexactly(data_len)

                command = int.from_bytes(body[2:4], "little")

                # Default Success Response (EndCode: 00 00)
                # Subheader(D4 00), Serial(copy), Reserved(00 00), Target(copy), Len, EndCode(00 00)
                response_body = b"\x00\x00"  # EndCode

                if command == Command.READ_TYPE_NAME:
                    # Model: "MOCK-PLC", ModelCode: 0x1234
                    response_body += b"MOCK-PLC".ljust(16, b"\x00") + b"\x34\x12"
                elif command == Command.DEVICE_READ:
                    # Return 0x0001 for any word read
                    response_body += b"\x01\x00"

                resp_len = len(response_body)
                header = b"\xd4\x00" + head[2:4] + b"\x00\x00" + head[6:11] + resp_len.to_bytes(2, "little")

                writer.write(header + response_body)
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class SerialSkewSLMPServer(MockSLMPServer):
    """Server that sends one stale 4E response before the matching response."""

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readexactly(13)
            data_len = int.from_bytes(head[11:13], "little")
            await reader.readexactly(data_len)

            serial = int.from_bytes(head[2:4], "little")
            stale = self._response(head, (serial + 1) & 0xFFFF, b"\x11\x11")
            matching = self._response(head, serial, b"\x22\x22")
            writer.write(stale + matching)
            await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    @staticmethod
    def _response(request_head: bytes, serial: int, data: bytes) -> bytes:
        body = b"\x00\x00" + data
        header = (
            b"\xd4\x00"
            + serial.to_bytes(2, "little")
            + b"\x00\x00"
            + request_head[6:11]
            + len(body).to_bytes(2, "little")
        )
        return header + body


class FakeAsyncClient(AsyncSlmpClient):
    """Fake async client for testing."""

    def __init__(self, **kwargs) -> None:
        """Initialize fake client."""
        if not any(name in kwargs for name in ("plc_profile", "plc_series", "frame_type", "address_profile")):
            kwargs["plc_profile"] = "melsec:iq-r"
        kwargs.setdefault("port", 1025)
        kwargs.setdefault("transport", "tcp")
        kwargs.setdefault("default_target", SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
        super().__init__("127.0.0.1", **kwargs)
        self.last_request = None
        self.next_response_data = b""
        self.next_response_end_code = 0

    async def _request(
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
        """Mock request method."""
        self.last_request = (int(command), subcommand, data, serial, target, monitoring_timer, raise_on_error)
        end_code = self.next_response_end_code
        response_data = self.next_response_data
        do_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        if do_raise and end_code != 0:
            raise SlmpError(
                f"SLMP error end_code=0x{end_code:04X} command=0x{int(command):04X} subcommand=0x{subcommand:04X}",
                end_code=end_code,
                data=response_data,
            )
        return SlmpResponse(
            serial=0,
            target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            end_code=end_code,
            data=response_data,
            raw=b"",
        )


# --- Test Cases ---


@pytest.mark.asyncio
async def test_async_cpu_buffer_helpers_require_explicit_typed_module() -> None:
    client = FakeAsyncClient()
    with pytest.raises(TypeError):
        await client.cpu_buffer_read_words(0, 1)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await client.cpu_buffer_write_words(0, [1])  # type: ignore[call-arg]
    for invalid in (None, 0x03E0, "CPU1", "", 0x03E4):
        with pytest.raises(ValueError, match="CpuModule.CPU1"):
            await client.cpu_buffer_read_words(0, 1, module=invalid)  # type: ignore[arg-type]
    assert client.last_request is None

    for module in CpuModule:
        client.next_response_data = b"\x34\x12"
        assert await client.cpu_buffer_read_words(0, 1, module=module) == [0x1234]
        assert int.from_bytes(client.last_request[2][6:8], "little") == int(module)
        await client.cpu_buffer_write_words(0, [0x1234], module=module)
        assert int.from_bytes(client.last_request[2][6:8], "little") == int(module)


@pytest.mark.asyncio
async def test_async_connect_and_read_model() -> None:
    """Test connection and basic read_type_name."""
    mock = MockSLMPServer()
    await mock.start()

    try:
        async with AsyncSlmpClient(
            mock.host,
            mock.port,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
        ) as cli:
            info = await cli.read_type_name()
            assert info.model == "MOCK-PLC"
            assert info.model_code == 0x1234
    finally:
        await mock.stop()


@pytest.mark.asyncio
async def test_async_read_devices() -> None:
    """Test device reading."""
    mock = MockSLMPServer()
    await mock.start()

    try:
        async with AsyncSlmpClient(
            mock.host,
            mock.port,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
        ) as cli:
            val = await cli.read_devices("D100", 1, bit_unit=False)
            assert val == [1]
    finally:
        await mock.stop()


@pytest.mark.asyncio
async def test_async_4e_request_ignores_mismatched_serial_response() -> None:
    mock = SerialSkewSLMPServer()
    await mock.start()

    try:
        async with AsyncSlmpClient(
            mock.host,
            mock.port,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
        ) as cli:
            val = await cli.read_devices("D100", 1, bit_unit=False)
            assert val == [0x2222]
    finally:
        await mock.stop()


@pytest.mark.asyncio
async def test_async_read_devices_rejects_deviceref_from_different_profile() -> None:
    cli = FakeAsyncClient()
    with pytest.raises(ValueError, match="does not match"):
        await cli.read_devices(DeviceRef("X", 0x10, "melsec:iq-f"), 8, bit_unit=True)
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_remote_run_requires_explicit_force_and_clear_mode() -> None:
    cli = FakeAsyncClient()

    with pytest.raises(TypeError):
        await cli.remote_run()  # type: ignore[call-arg]
    await cli.remote_run(force=False, clear_mode=RemoteClearMode.NO_CLEAR)

    assert cli.last_request is not None
    assert cli.last_request[0] == int(Command.REMOTE_RUN)
    assert cli.last_request[1] == 0x0000
    assert cli.last_request[2] == b"\x01\x00\x00\x00"


@pytest.mark.asyncio
async def test_async_remote_stop_uses_manual_fixed_mode() -> None:
    cli = FakeAsyncClient()

    await cli.remote_stop()

    assert cli.last_request is not None
    assert cli.last_request[0] == int(Command.REMOTE_STOP)
    assert cli.last_request[1] == 0x0000
    assert cli.last_request[2] == b"\x01\x00"


def test_async_client_rejects_invalid_address_profile() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument 'address_profile'"):
        FakeAsyncClient(address_profile="auto")


def test_async_client_rejects_address_profile_alias() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument 'address_profile'"):
        FakeAsyncClient(address_profile="iqf")


@pytest.mark.asyncio
async def test_async_read_devices_iqf_xy_uses_octal_start_address() -> None:
    cli = FakeAsyncClient(plc_profile="melsec:iq-f")
    cli.next_response_data = b"\x10"

    values = await cli.read_devices("Y217", 2, bit_unit=True)

    assert values == [True, False]
    assert cli.last_request is not None
    assert cli.last_request[0] == int(Command.DEVICE_READ)
    assert cli.last_request[1] == 0x0001
    assert cli.last_request[2] == b"\x8f\x00\x00\x9d\x02\x00"


def test_async_client_rejects_invalid_plc_profile() -> None:
    with pytest.raises(ValueError, match="Unsupported plc_profile"):
        FakeAsyncClient(plc_profile="bad-profile")


def test_async_client_rejects_base_qcpu_profile() -> None:
    with pytest.raises(ValueError, match="melsec:qcpu is a base profile.*melsec:qcpu:qj71e71-100"):
        FakeAsyncClient(plc_profile="melsec:qcpu")


def test_async_client_plc_profile_derives_fixed_profile_defaults() -> None:
    cli = FakeAsyncClient(plc_profile="melsec:iq-l")

    assert cli.plc_profile == "melsec:iq-l"
    assert cli.plc_series == PLCSeries.IQR
    assert cli.frame_type.value == "4e"
    assert cli.address_profile == "melsec:iq-l"
    assert cli.range_profile == "melsec:iq-l"


@pytest.mark.asyncio
async def test_async_removed_overrides_and_raw_serial_are_rejected_before_transport() -> None:
    cli = FakeAsyncClient()
    assert not hasattr(cli, "request")
    assert not hasattr(cli, "memory_read")
    assert not hasattr(cli, "remote_reset_raw")

    with pytest.raises(TypeError, match="unexpected keyword argument 'serial'"):
        await cli.raw_command(Command.CLEAR_ERROR, subcommand=0, payload=b"", serial=1)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="required keyword-only argument: 'subcommand'"):
        await cli.raw_command(Command.CLEAR_ERROR, payload=b"")  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="required keyword-only argument: 'payload'"):
        await cli.raw_command(Command.CLEAR_ERROR, subcommand=0)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="unexpected keyword argument 'series'"):
        await cli.read_devices("D0", 1, bit_unit=False, series=PLCSeries.QL)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="unexpected keyword argument 'series'"):
        await cli.remote_password_lock("secret1", series=PLCSeries.QL)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="missing 2 required keyword-only arguments"):
        await cli.read_long_timer()  # type: ignore[call-arg]
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_long_timer_head_and_points_are_required_and_validated_before_transport() -> None:
    cli = FakeAsyncClient()

    with pytest.raises(TypeError, match="missing 2 required keyword-only arguments"):
        await cli.read_long_retentive_timer()  # type: ignore[call-arg]
    for head_no in (None, False, "0", -1, 0x1_0000_0000):
        with pytest.raises((TypeError, ValueError)):
            await cli.read_long_timer(head_no=head_no, points=1)  # type: ignore[arg-type]
    for points in (None, False, "1", 0, -1, 241, 0x4001):
        with pytest.raises((TypeError, ValueError)):
            await cli.read_long_retentive_timer(head_no=0, points=points)  # type: ignore[arg-type]

    assert cli.last_request is None


def test_async_client_unit_profile_keeps_frame_and_series_independent() -> None:
    cli = FakeAsyncClient(plc_profile="melsec:qcpu:qj71e71-100")

    assert cli.plc_profile == "melsec:qcpu:qj71e71-100"
    assert cli.plc_series == PLCSeries.QL
    assert cli.frame_type.value == "4e"
    assert cli.address_profile == "melsec:qcpu"
    assert cli.range_profile == "melsec:qcpu:qj71e71-100"


@pytest.mark.asyncio
async def test_async_concurrency() -> None:
    """Test multiple concurrent requests using gather."""
    mock = MockSLMPServer()
    await mock.start()

    try:
        async with AsyncSlmpClient(
            mock.host,
            mock.port,
            transport="tcp",
            default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            plc_profile="melsec:iq-r",
        ) as cli:
            # Send 5 requests concurrently
            tasks = [cli.read_devices(f"D{i}", 1, bit_unit=False) for i in range(5)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            for r in results:
                assert r == [1]
    finally:
        await mock.stop()


@pytest.mark.asyncio
async def test_async_timeout() -> None:
    """Test timeout behavior."""
    # Specify a port that is not listening
    cli = AsyncSlmpClient(
        "127.0.0.1",
        1,
        transport="tcp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        plc_profile="melsec:iq-r",
        timeout=0.1,
    )
    with pytest.raises(ConnectionError):
        await cli.connect()


@pytest.mark.asyncio
async def test_async_udp_read() -> None:
    """Test device reading over UDP (using a simple mock)."""
    # Note: Mocking UDP server is slightly different, but for simplicity
    # we test the client setup and a simulated timeout to verify the UDP path.
    cli = AsyncSlmpClient(
        "127.0.0.1",
        9999,
        plc_profile="melsec:iq-r",
        transport="udp",
        default_target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
        timeout=0.1,
    )
    await cli.connect()
    try:
        with pytest.raises(SlmpError, match="UDP communication timeout"):
            await cli.read_devices("D100", 1, bit_unit=False)
    finally:
        await cli.close()


@pytest.mark.asyncio
async def test_async_read_word_helper_uses_low_word_first() -> None:
    """Test that read_dword uses low word first."""
    cli = FakeAsyncClient()
    cli.next_response_data = b"\x78\x56\x34\x12"

    value = await cli.read_dword("D100")

    assert value == 0x12345678
    assert cli.last_request is not None
    assert cli.last_request[0] == int(Command.DEVICE_READ)
    assert cli.last_request[2][-2:] == b"\x02\x00"


@pytest.mark.asyncio
async def test_async_direct_bit_read_rejects_long_timer_state_devices() -> None:
    """Async direct bit reads for LT/LST state devices must fail before transport."""
    cli = FakeAsyncClient()

    with pytest.raises(ValueError, match="Direct bit read is not supported for LTC"):
        await cli.read_devices("LTC0", 1, bit_unit=True)

    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_direct_word_read_requires_four_word_long_timer_blocks() -> None:
    """Async LTN/LSTN direct reads must use 4-word units."""
    cli = FakeAsyncClient()

    with pytest.raises(ValueError, match="requires 4-word blocks"):
        await cli.read_devices("LTN0", 2, bit_unit=False)

    assert cli.last_request is None

    cli.next_response_data = b"\x01\x00\x02\x00\x03\x00\x04\x00"
    values = await cli.read_devices("LTN0", 4, bit_unit=False)
    assert values == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_async_read_random_rejects_lcs_lcc() -> None:
    """Async Read Random must reject long counter state devices."""
    cli = FakeAsyncClient()

    with pytest.raises(ValueError, match="Read Random \\(0x0403\\) does not support LCS/LCC"):
        await cli.read_random(word_devices=["LCS10"])

    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_read_block_rejects_lcs_lcc() -> None:
    cli = FakeAsyncClient()
    with pytest.raises(ValueError, match=r"Read Block \(0x0406\) does not support LCS/LCC"):
        await cli.read_block(bit_blocks=[("LCS10", 1)])
    assert cli.last_request is None


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["melsec:lcpu", "melsec:qnu"])
async def test_async_read_block_rejects_q_profiles_before_transport(profile: str) -> None:
    cli = FakeAsyncClient(plc_profile=profile)
    with pytest.raises(SlmpProfileFeatureError, match=rf"block.*{profile}|{profile}.*block"):
        await cli.read_block(word_blocks=[("D100", 1)], bit_blocks=[("M100", 1)])
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_read_block_rejects_qnudv_by_profile_guard() -> None:
    cli = FakeAsyncClient(plc_profile="melsec:qnudv")
    with pytest.raises(SlmpProfileFeatureError, match="block"):
        await cli.read_block(word_blocks=[("D100", 1)], bit_blocks=[("M100", 1)])
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_read_type_name_qnudv_rejects_by_profile_guard() -> None:
    cli = FakeAsyncClient(plc_profile="melsec:qnudv")
    with pytest.raises(SlmpProfileFeatureError, match="type_name.*C059"):
        await cli.read_type_name()
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_write_block_rejects_lcs_lcc() -> None:
    cli = FakeAsyncClient()
    with pytest.raises(ValueError, match=r"Write Block \(0x1406\) does not support LCS/LCC"):
        await cli.write_block(bit_blocks=[("LCC10", [1])])
    assert cli.last_request is None


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["melsec:lcpu", "melsec:qnu"])
async def test_async_write_block_rejects_q_profiles_before_transport(profile: str) -> None:
    cli = FakeAsyncClient(plc_profile=profile)
    with pytest.raises(SlmpProfileFeatureError, match=rf"block.*{profile}|{profile}.*block"):
        await cli.write_block(word_blocks=[("D100", [1])], bit_blocks=[("M100", [1])])
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_register_monitor_devices_rejects_lcs_lcc() -> None:
    """Async monitor register must reject long counter state devices."""
    cli = FakeAsyncClient()

    with pytest.raises(ValueError, match="Entry Monitor Device \\(0x0801\\) does not support LCS/LCC"):
        await cli.register_monitor_devices(word_devices=["LCS10"])

    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_read_devices_ext_rejects_long_counter_current_before_transport() -> None:
    cli = FakeAsyncClient()
    with pytest.raises(ValueError, match="Direct word read is not supported for LCN"):
        await cli.read_devices_ext(r"J1\LCN10", 4, bit_unit=False)
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_read_random_ext_rejects_lcs_lcc_before_transport() -> None:
    cli = FakeAsyncClient()
    with pytest.raises(ValueError, match=r"Read Random \(0x0403\) does not support LCS/LCC"):
        await cli.read_random_ext(dword_devices=[r"J1\LCS10"])
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_register_monitor_devices_ext_rejects_lcs_lcc_before_transport() -> None:
    cli = FakeAsyncClient()
    with pytest.raises(ValueError, match=r"Entry Monitor Device \(0x0801\) does not support LCS/LCC"):
        await cli.register_monitor_devices_ext(word_devices=[r"J1\LCS10"])
    assert cli.last_request is None


@pytest.mark.asyncio
async def test_async_write_float32_helper_uses_low_word_first() -> None:
    """Test that write_float32 uses low word first."""
    cli = FakeAsyncClient()

    await cli.write_float32("D100", 1.5)

    assert cli.last_request is not None
    assert cli.last_request[0] == int(Command.DEVICE_WRITE)
    assert cli.last_request[2][-4:] == b"\x00\x00\xc0\x3f"


@pytest.mark.asyncio
async def test_async_monitor_alias_uses_entry_monitor_command() -> None:
    """Test that register_monitor_devices uses DEVICE_ENTRY_MONITOR command."""
    cli = FakeAsyncClient()

    await cli.register_monitor_devices(word_devices=["D100"], dword_devices=["D200"])

    assert cli.last_request is not None
    assert cli.last_request[0] == int(Command.DEVICE_ENTRY_MONITOR)
