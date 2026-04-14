"""Tests for explicit-family device-range catalog helpers."""

from __future__ import annotations

import unittest

from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.constants import Command, PLCSeries
from slmp.core import SlmpResponse, SlmpTarget, encode_device_spec
from slmp.device_ranges import SlmpDeviceRangeFamily, SlmpDeviceRangeNotation


def _pack_words(values: list[int]) -> bytes:
    payload = bytearray()
    for value in values:
        payload += int(value & 0xFFFF).to_bytes(2, "little")
    return bytes(payload)


def _build_word_block(start: int, count: int, values: dict[int, int]) -> bytes:
    return _pack_words([values.get(start + index, 0) for index in range(count)])


class _FakeSyncClient(SlmpClient):
    def __init__(self) -> None:
        super().__init__("127.0.0.1")
        self.last_request: tuple[int, int, bytes] | None = None
        self.next_response_data = b""

    def request(self, command: int | Command, subcommand: int = 0x0000, data: bytes = b"", **_: object) -> SlmpResponse:
        self.last_request = (int(command), subcommand, data)
        return SlmpResponse(serial=0, target=SlmpTarget(), end_code=0, data=self.next_response_data, raw=b"")


class _FakeAsyncClient(AsyncSlmpClient):
    def __init__(self) -> None:
        super().__init__("127.0.0.1")
        self.last_request: tuple[int, int, bytes] | None = None
        self.next_response_data = b""

    async def request(
        self,
        command: int | Command,
        subcommand: int = 0x0000,
        data: bytes = b"",
        **_: object,
    ) -> SlmpResponse:
        self.last_request = (int(command), subcommand, data)
        return SlmpResponse(serial=0, target=SlmpTarget(), end_code=0, data=self.next_response_data, raw=b"")


class TestSyncDeviceRanges(unittest.TestCase):
    def test_iqf_reads_one_sd_block_and_formats_xy_in_octal(self) -> None:
        client = _FakeSyncClient()
        client.next_response_data = _build_word_block(
            260,
            46,
            {
                260: 1024,
                262: 1024,
                264: 7680,
                266: 256,
                268: 512,
                270: 128,
                274: 7680,
                280: 8000,
                282: 512,
                284: 512,
                288: 512,
                290: 16,
                292: 256,
                298: 64,
                300: 20,
                302: 2,
                304: 32768 & 0xFFFF,
                305: (32768 >> 16) & 0xFFFF,
            },
        )

        catalog = client.read_device_range_catalog_for_family("iq-f")

        self.assertEqual(catalog.family, SlmpDeviceRangeFamily.IqF)
        self.assertEqual(catalog.model, "IQ-F")
        self.assertFalse(catalog.has_model_code)
        self.assertEqual(
            client.last_request,
            (
                int(Command.DEVICE_READ),
                0x0000,
                encode_device_spec("SD260", series=PLCSeries.QL) + (46).to_bytes(2, "little"),
            ),
        )

        entries = {entry.device: entry for entry in catalog.entries}
        self.assertEqual(entries["X"].point_count, 1024)
        self.assertEqual(entries["X"].address_range, "X0000-X1777")
        self.assertEqual(entries["X"].notation, SlmpDeviceRangeNotation.Base8)
        self.assertEqual(entries["Y"].address_range, "Y0000-Y1777")
        self.assertEqual(entries["R"].point_count, 32768)
        self.assertEqual(entries["R"].address_range, "R0-R32767")
        self.assertFalse(entries["V"].supported)
        self.assertIsNone(entries["V"].point_count)
        self.assertEqual(entries["LCS"].point_count, 64)
        self.assertEqual(entries["LCS"].address_range, "LCS0-LCS63")


class TestAsyncDeviceRanges(unittest.IsolatedAsyncioTestCase):
    async def test_qnu_uses_sd300_for_st_and_sd305_for_z(self) -> None:
        client = _FakeAsyncClient()
        client.next_response_data = _build_word_block(
            286,
            26,
            {
                286: 8192,
                288: 8192,
                290: 8192,
                291: 8192,
                293: 8192,
                295: 2048,
                296: 2048,
                297: 2048,
                298: 8192,
                299: 2048,
                300: 16,
                301: 1024,
                304: 2048,
                305: 20,
                308: 12288,
                310: 8192,
            },
        )

        catalog = await client.read_device_range_catalog_for_family(SlmpDeviceRangeFamily.QnU)

        self.assertEqual(catalog.family, SlmpDeviceRangeFamily.QnU)
        self.assertEqual(
            client.last_request,
            (
                int(Command.DEVICE_READ),
                0x0000,
                encode_device_spec("SD286", series=PLCSeries.QL) + (26).to_bytes(2, "little"),
            ),
        )

        entries = {entry.device: entry for entry in catalog.entries}
        self.assertEqual(entries["STS"].point_count, 16)
        self.assertEqual(entries["STS"].address_range, "STS0-STS15")
        self.assertEqual(entries["STC"].point_count, 16)
        self.assertEqual(entries["STN"].point_count, 16)
        self.assertEqual(entries["CS"].point_count, 1024)
        self.assertEqual(entries["CS"].address_range, "CS0-CS1023")
        self.assertEqual(entries["Z"].point_count, 20)
        self.assertEqual(entries["Z"].address_range, "Z0-Z19")
        self.assertEqual(entries["R"].point_count, 0)
        self.assertIsNone(entries["R"].address_range)

