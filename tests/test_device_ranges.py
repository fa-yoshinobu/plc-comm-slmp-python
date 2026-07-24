"""Tests for explicit-profile device-range catalog helpers."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from slmp.async_client import AsyncSlmpClient
from slmp.client import SlmpClient
from slmp.constants import Command, PLCSeries
from slmp.core import (
    SlmpPlcProfile,
    SlmpResponse,
    SlmpTarget,
    SlmpUnsupportedDeviceError,
    encode_device_spec,
    parse_device,
)
from slmp.device_ranges import (
    SlmpDeviceRangeNotation,
    _can_read_one_word_async,
    _can_read_one_word_sync,
    build_device_range_catalog_for_plc_profile,
    normalize_plc_profile,
)
from slmp.errors import SlmpError, SlmpTimeoutError


class _TimeoutRangeClient:
    def read_devices(self, address, points, *, bit_unit):
        raise SlmpTimeoutError("injected timeout")


class _AsyncTimeoutRangeClient:
    async def read_devices(self, address, points, *, bit_unit):
        raise SlmpTimeoutError("injected timeout")


def test_runtime_range_probe_does_not_classify_sync_timeout_as_out_of_range() -> None:
    with unittest.TestCase().assertRaises(SlmpTimeoutError):
        _can_read_one_word_sync(_TimeoutRangeClient(), "ZR0")


def test_runtime_range_probe_does_not_classify_async_timeout_as_out_of_range() -> None:
    with unittest.TestCase().assertRaises(SlmpTimeoutError):
        asyncio.run(_can_read_one_word_async(_AsyncTimeoutRangeClient(), "ZR0"))


def _pack_words(values: list[int]) -> bytes:
    payload = bytearray()
    for value in values:
        payload += int(value & 0xFFFF).to_bytes(2, "little")
    return bytes(payload)


def _build_word_block(start: int, count: int, values: dict[int, int]) -> bytes:
    return _pack_words([values.get(start + index, 0) for index in range(count)])


def _load_canonical_device_range_rules() -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / "slmp_device_range_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_rule_value(rule: dict[str, object]) -> int:
    kind = str(rule["kind"])
    if kind.endswith("clipped"):
        return int(rule["clip_value"]) + 5
    return 123


def _canonical_register_snapshot(profile: dict[str, object], only_item: str | None = None) -> dict[int, int]:
    start = int(profile["register_start"])
    count = int(profile["register_count"])
    registers = {start + offset: 0 for offset in range(count)}
    rules = profile["rules"]
    assert isinstance(rules, dict)
    rule_values = [rules[only_item]] if only_item is not None else rules.values()
    for rule_value in rule_values:
        rule = rule_value
        assert isinstance(rule, dict)
        kind = str(rule["kind"])
        register = rule.get("register")
        if register is None:
            continue
        reg = int(register)
        value = _canonical_rule_value(rule)
        if kind.startswith("dword-register"):
            registers[reg] = value & 0xFFFF
            registers[reg + 1] = (value >> 16) & 0xFFFF
        elif kind.startswith("word-register"):
            registers[reg] = value & 0xFFFF
    return registers


def _canonical_expected_point_count(rule: dict[str, object]) -> int | None:
    kind = str(rule["kind"])
    if kind in {"unsupported", "undefined"}:
        return None
    if kind == "fixed":
        return int(rule["fixed_value"])
    value = _canonical_rule_value(rule)
    if kind.endswith("clipped"):
        return min(value, int(rule["clip_value"]))
    return value


class _FakeSyncClient(SlmpClient):
    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("plc_profile", "melsec:iq-r")
        kwargs.setdefault("port", 1025)
        kwargs.setdefault("transport", "tcp")
        kwargs.setdefault("default_target", SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
        super().__init__("127.0.0.1", **kwargs)
        self.last_request: tuple[int, int, bytes] | None = None
        self.next_response_data = b""
        self.rejected_prefixes: tuple[str, ...] = ()

    def _request(
        self, command: int | Command, subcommand: int = 0x0000, data: bytes = b"", **_: object
    ) -> SlmpResponse:
        self.last_request = (int(command), subcommand, data)
        return SlmpResponse(
            serial=0,
            target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            end_code=0,
            data=self.next_response_data,
            raw=b"",
        )

    def read_devices(self, device, points: int, *, bit_unit: bool = False, series=None):  # type: ignore[no-untyped-def]
        text = f"{device.code}{device.number}" if hasattr(device, "code") else str(device)
        if text.startswith(self.rejected_prefixes):
            raise SlmpError("rejected by test")
        return super().read_devices(device, points, bit_unit=bit_unit)


class _FakeAsyncClient(AsyncSlmpClient):
    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("plc_profile", "melsec:iq-r")
        kwargs.setdefault("port", 1025)
        kwargs.setdefault("transport", "tcp")
        kwargs.setdefault("default_target", SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0))
        super().__init__("127.0.0.1", **kwargs)
        self.last_request: tuple[int, int, bytes] | None = None
        self.next_response_data = b""
        self.rejected_prefixes: tuple[str, ...] = ()

    async def _request(
        self,
        command: int | Command,
        subcommand: int = 0x0000,
        data: bytes = b"",
        **_: object,
    ) -> SlmpResponse:
        self.last_request = (int(command), subcommand, data)
        return SlmpResponse(
            serial=0,
            target=SlmpTarget(network=0, station=0xFF, module_io=0x03FF, multidrop=0),
            end_code=0,
            data=self.next_response_data,
            raw=b"",
        )

    async def read_devices(self, device, points: int, *, bit_unit: bool = False, series=None):  # type: ignore[no-untyped-def]
        text = f"{device.code}{device.number}" if hasattr(device, "code") else str(device)
        if text.startswith(self.rejected_prefixes):
            raise SlmpError("rejected by test")
        return await super().read_devices(device, points, bit_unit=bit_unit)


class TestSyncDeviceRanges(unittest.TestCase):
    def test_family_alias_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported PLC profile"):
            normalize_plc_profile("iqf")

    def test_iqf_reads_one_sd_block_and_formats_xy_in_octal(self) -> None:
        client = _FakeSyncClient(plc_profile="melsec:iq-f")
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
                276: 256,
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

        catalog = client.read_device_range_catalog_for_plc_profile("melsec:iq-f")

        self.assertEqual(catalog.plc_profile, SlmpPlcProfile.IqF)
        self.assertEqual(catalog.model, "IQ-F")
        self.assertFalse(catalog.has_model_code)
        self.assertEqual(
            client.last_request,
            (
                int(Command.DEVICE_READ),
                0x0000,
                encode_device_spec("SD260", series=PLCSeries.QL, plc_profile="melsec:iq-f")
                + (46).to_bytes(2, "little"),
            ),
        )

        entries = {entry.device: entry for entry in catalog.entries}
        self.assertEqual(entries["X"].point_count, 1024)
        self.assertEqual(entries["X"].address_range, "X0000-X1777")
        self.assertEqual(entries["X"].notation, SlmpDeviceRangeNotation.Base8)
        self.assertEqual(entries["Y"].address_range, "Y0000-Y1777")
        self.assertTrue(entries["S"].supported)
        self.assertEqual(entries["S"].point_count, 256)
        self.assertEqual(entries["S"].address_range, "S0-S255")
        self.assertEqual(entries["R"].point_count, 32768)
        self.assertEqual(entries["R"].address_range, "R0-R32767")
        self.assertFalse(entries["V"].supported)
        self.assertIsNone(entries["V"].point_count)
        self.assertEqual(entries["LCS"].point_count, 64)
        self.assertEqual(entries["LCS"].address_range, "LCS0-LCS63")

    def test_qcpu_unit_uses_base_rules_but_reports_unit_profile(self) -> None:
        registers = {register: 0 for register in range(290, 305)}
        registers[290] = 123

        catalog = build_device_range_catalog_for_plc_profile(
            SlmpPlcProfile.QCpuQj71E71100,
            registers,
        )

        self.assertEqual(catalog.plc_profile, SlmpPlcProfile.QCpuQj71E71100)
        self.assertEqual(catalog.model, "QCPU via QJ71E71-100")
        entries = {entry.device: entry for entry in catalog.entries}
        self.assertEqual(entries["X"].point_count, 123)
        self.assertEqual(entries["X"].address_range, "X000-X07A")

    def test_iqr_unit_uses_iqr_rules_but_reports_unit_profile(self) -> None:
        registers = {register: 0 for register in range(260, 310)}
        registers[280] = 0x0034
        registers[281] = 0x0001

        catalog = build_device_range_catalog_for_plc_profile(
            SlmpPlcProfile.IqRRj71En71,
            registers,
        )

        self.assertEqual(catalog.plc_profile, SlmpPlcProfile.IqRRj71En71)
        self.assertEqual(catalog.model, "iQ-R via RJ71EN71")
        entries = {entry.device: entry for entry in catalog.entries}
        self.assertEqual(entries["D"].point_count, 0x00010034)
        self.assertEqual(entries["D"].address_range, "D0-D65587")

    def test_mxr_unit_uses_mxr_rules_but_reports_unit_profile(self) -> None:
        registers = {register: 0 for register in range(260, 310)}
        registers[280] = 0x0034
        registers[281] = 0x0001

        catalog = build_device_range_catalog_for_plc_profile(
            SlmpPlcProfile.MxRRj71En71,
            registers,
        )

        self.assertEqual(catalog.plc_profile, SlmpPlcProfile.MxRRj71En71)
        self.assertEqual(catalog.model, "MX-R via RJ71EN71")
        entries = {entry.device: entry for entry in catalog.entries}
        self.assertEqual(entries["D"].point_count, 0x00010034)
        self.assertEqual(entries["D"].address_range, "D0-D65587")

    def test_mx_profiles_keep_s_supported_from_sd276(self) -> None:
        for plc_profile in (SlmpPlcProfile.MxF, SlmpPlcProfile.MxR, SlmpPlcProfile.MxRRj71En71):
            with self.subTest(plc_profile=plc_profile):
                registers = {register: 0 for register in range(260, 310)}
                registers[276] = 123
                catalog = build_device_range_catalog_for_plc_profile(
                    plc_profile,
                    registers,
                )

                entries = {entry.device: entry for entry in catalog.entries}
                self.assertTrue(entries["S"].supported)
                self.assertEqual(entries["S"].source, "SD276-SD277 (32-bit)")
                self.assertEqual(entries["S"].point_count, 123)
                self.assertEqual(entries["S"].address_range, "S0-S122")

    def test_catalog_matches_canonical_device_range_rules_fixture(self) -> None:
        payload = _load_canonical_device_range_rules()
        rows = payload["rows"]
        profiles = payload["profiles"]
        notation_overrides = payload.get("notation_overrides", {})
        assert isinstance(rows, dict)
        assert isinstance(profiles, dict)
        assert isinstance(notation_overrides, dict)

        for profile_name, profile_payload in profiles.items():
            assert isinstance(profile_payload, dict)
            with self.subTest(profile=profile_name):
                rules = profile_payload["rules"]
                assert isinstance(rules, dict)
                profile_notation_overrides = notation_overrides.get(profile_name, {})
                assert isinstance(profile_notation_overrides, dict)

                for item, rule_payload in rules.items():
                    row = rows[item]
                    assert isinstance(row, dict)
                    assert isinstance(rule_payload, dict)
                    catalog = build_device_range_catalog_for_plc_profile(
                        normalize_plc_profile(profile_name),
                        _canonical_register_snapshot(profile_payload, item),
                    )
                    entries = {entry.device: entry for entry in catalog.entries}
                    expected_supported = rule_payload["kind"] != "unsupported"
                    expected_point_count = _canonical_expected_point_count(rule_payload)
                    expected_notation = profile_notation_overrides.get(item, row["notation"])
                    for device_payload in row["devices"]:
                        assert isinstance(device_payload, dict)
                        device = str(device_payload["device"])
                        entry = entries[device]
                        self.assertEqual(entry.supported, expected_supported, f"{profile_name} {device}")
                        self.assertEqual(entry.point_count, expected_point_count, f"{profile_name} {device}")
                        self.assertEqual(
                            entry.notation,
                            SlmpDeviceRangeNotation(str(expected_notation)),
                            f"{profile_name} {device}",
                        )

    def test_profile_unsupported_device_codes_match_canonical_fixture(self) -> None:
        payload = _load_canonical_device_range_rules()
        rows = payload["rows"]
        profiles = payload["profiles"]
        assert isinstance(rows, dict)
        assert isinstance(profiles, dict)

        for profile_name, profile_payload in profiles.items():
            semantic_profile = "melsec:qcpu:qj71e71-100" if profile_name == "melsec:qcpu" else profile_name
            assert isinstance(profile_payload, dict)
            rules = profile_payload["rules"]
            assert isinstance(rules, dict)
            for item, rule_payload in rules.items():
                assert isinstance(rule_payload, dict)
                row = rows[item]
                assert isinstance(row, dict)
                expected_supported = rule_payload["kind"] != "unsupported"
                for device_payload in row["devices"]:
                    assert isinstance(device_payload, dict)
                    device = str(device_payload["device"])
                    address = f"{device}10"
                    if expected_supported:
                        self.assertEqual(parse_device(address, plc_profile=semantic_profile).code, device)
                    else:
                        with self.assertRaises(SlmpUnsupportedDeviceError, msg=f"{profile_name} {device}"):
                            parse_device(address, plc_profile=semantic_profile)

        with self.assertRaises(SlmpUnsupportedDeviceError):
            parse_device("DX10", plc_profile="melsec:iq-f")
        with self.assertRaises(SlmpUnsupportedDeviceError):
            parse_device("DY10", plc_profile="melsec:iq-f")

    def test_read_device_range_catalog_uses_client_plc_profile_defaults(self) -> None:
        client = _FakeSyncClient(plc_profile="melsec:iq-l")
        client.next_response_data = _build_word_block(
            260,
            50,
            {
                260: 4096,
                262: 4096,
                280: 8192,
                282: 1024,
            },
        )

        catalog = client.read_device_range_catalog()

        self.assertEqual(catalog.plc_profile, SlmpPlcProfile.IqL)
        self.assertEqual(client.plc_profile, "melsec:iq-l")
        self.assertEqual(
            client.last_request,
            (
                int(Command.DEVICE_READ),
                0x0002,
                encode_device_spec("SD260", series=PLCSeries.IQR, plc_profile="melsec:iq-l")
                + (50).to_bytes(2, "little"),
            ),
        )


class TestAsyncDeviceRanges(unittest.IsolatedAsyncioTestCase):
    async def test_qnu_uses_sd300_for_st_and_fixed_z_range(self) -> None:
        client = _FakeAsyncClient(plc_profile="melsec:qnu")
        client.rejected_prefixes = ("ZR",)
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
                305: 65535,
                308: 12288,
                310: 8192,
            },
        )

        catalog = await client.read_device_range_catalog_for_plc_profile(SlmpPlcProfile.QnU)

        self.assertEqual(catalog.plc_profile, SlmpPlcProfile.QnU)
        self.assertEqual(
            client.last_request,
            (
                int(Command.DEVICE_READ),
                0x0000,
                encode_device_spec("SD286", series=PLCSeries.QL, plc_profile="melsec:qnu") + (26).to_bytes(2, "little"),
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
