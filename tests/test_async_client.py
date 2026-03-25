"""Unit tests for AsyncSlmpClient using a mock SLMP server."""

import asyncio

import pytest

from slmp.async_client import AsyncSlmpClient
from slmp.constants import Command
from slmp.core import SlmpError, SlmpResponse, SlmpTarget

# --- Mock SLMP Server for Testing ---


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


class FakeAsyncClient(AsyncSlmpClient):
    """Fake async client for testing."""

    def __init__(self) -> None:
        """Initialize fake client."""
        super().__init__("127.0.0.1")
        self.last_request = None
        self.next_response_data = b""
        self.next_response_end_code = 0

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
        return SlmpResponse(serial=0, target=SlmpTarget(), end_code=end_code, data=response_data, raw=b"")


# --- Test Cases ---


@pytest.mark.asyncio
async def test_async_connect_and_read_model() -> None:
    """Test connection and basic read_type_name."""
    mock = MockSLMPServer()
    await mock.start()

    try:
        async with AsyncSlmpClient(mock.host, mock.port) as cli:
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
        async with AsyncSlmpClient(mock.host, mock.port) as cli:
            val = await cli.read_devices("D100", 1)
            assert val == [1]
    finally:
        await mock.stop()


@pytest.mark.asyncio
async def test_async_concurrency() -> None:
    """Test multiple concurrent requests using gather."""
    mock = MockSLMPServer()
    await mock.start()

    try:
        async with AsyncSlmpClient(mock.host, mock.port) as cli:
            # Send 5 requests concurrently
            tasks = [cli.read_devices(f"D{i}", 1) for i in range(5)]
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
    cli = AsyncSlmpClient("127.0.0.1", 1, timeout=0.1)
    with pytest.raises(ConnectionError):
        await cli.connect()


@pytest.mark.asyncio
async def test_async_udp_read() -> None:
    """Test device reading over UDP (using a simple mock)."""
    # Note: Mocking UDP server is slightly different, but for simplicity
    # we test the client setup and a simulated timeout to verify the UDP path.
    cli = AsyncSlmpClient("127.0.0.1", 9999, transport="udp", timeout=0.1)
    await cli.connect()
    try:
        with pytest.raises(SlmpError, match="UDP communication timeout"):
            await cli.read_devices("D100", 1)
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
