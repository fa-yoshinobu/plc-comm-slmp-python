"""Focused contracts for the approved next-release public API changes."""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import tomllib

import slmp
from slmp import AsyncSlmpClient, SlmpClient
from slmp import cli as slmp_cli

ROOT = Path(__file__).resolve().parents[1]

REMOVED_MEMORY_EXTEND_METHODS = (
    "memory_read_words",
    "memory_write_words",
    "extend_unit_read_bytes",
    "extend_unit_read_words",
    "extend_unit_read_word",
    "extend_unit_read_dword",
    "extend_unit_write_bytes",
    "extend_unit_write_words",
    "extend_unit_write_word",
    "extend_unit_write_dword",
)

EXTENDED_NAME_PAIRS = (
    ("read_devices_ext", "read_devices_extended"),
    ("write_devices_ext", "write_devices_extended"),
    ("read_random_ext", "read_random_extended"),
    ("write_random_words_ext", "write_random_words_extended"),
    ("write_random_bits_ext", "write_random_bits_extended"),
    ("register_monitor_devices_ext", "register_monitor_devices_extended"),
)


def test_removed_memory_extend_surface_and_open_items_console_are_absent() -> None:
    for client_type in (SlmpClient, AsyncSlmpClient):
        for name in REMOVED_MEMORY_EXTEND_METHODS:
            assert not hasattr(client_type, name), f"unexpected public method: {client_type.__name__}.{name}"

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = project["project"]["scripts"]
    assert "slmp-open-items-recheck" not in scripts
    assert not hasattr(slmp_cli, "open_items_recheck_main")
    assert not (ROOT / "scripts" / "slmp_open_items_recheck.py").exists()


def test_address_naming_reuses_existing_public_components_without_duplicate_aliases() -> None:
    for name in (
        "DeviceAddress",
        "AddressSpec",
        "parse_device_address",
        "format_device_address",
        "normalize_device_address",
        "parse_address_spec",
        "format_address_spec",
        "normalize_address_spec",
    ):
        assert not hasattr(slmp, name), f"unexpected duplicate address API: {name}"


def test_extended_canonical_and_compatibility_signatures_match() -> None:
    for client_type in (SlmpClient, AsyncSlmpClient):
        for old_name, canonical_name in EXTENDED_NAME_PAIRS:
            old = getattr(client_type, old_name)
            canonical = getattr(client_type, canonical_name)
            assert inspect.signature(old) == inspect.signature(canonical)


def test_sync_extended_old_names_delegate_directly_to_canonical_methods() -> None:
    client = MagicMock()

    SlmpClient.read_devices_ext(client, r"U3E0\G0", 1, bit_unit=False)
    client.read_devices_extended.assert_called_once_with(r"U3E0\G0", 1, bit_unit=False)

    SlmpClient.write_devices_ext(client, r"U3E0\G0", [1], bit_unit=False)
    client.write_devices_extended.assert_called_once_with(r"U3E0\G0", [1], bit_unit=False)

    SlmpClient.read_random_ext(client, word_devices=[r"U3E0\G0"], dword_devices=[r"J1\W0"])
    client.read_random_extended.assert_called_once_with(
        word_devices=[r"U3E0\G0"],
        dword_devices=[r"J1\W0"],
    )

    SlmpClient.write_random_words_ext(client, word_values=[(r"U3E0\G0", 1)])
    client.write_random_words_extended.assert_called_once_with(
        word_values=[(r"U3E0\G0", 1)],
        dword_values=(),
    )

    SlmpClient.write_random_bits_ext(client, [(r"J1\B0", True)])
    client.write_random_bits_extended.assert_called_once_with([(r"J1\B0", True)])

    SlmpClient.register_monitor_devices_ext(client, word_devices=[r"U3E0\G0"])
    client.register_monitor_devices_extended.assert_called_once_with(
        word_devices=[r"U3E0\G0"],
        dword_devices=(),
    )


class AsyncCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_extended_old_names_delegate_directly_to_canonical_methods(self) -> None:
        client = MagicMock()
        client.read_devices_extended = AsyncMock(return_value=[1])
        client.write_devices_extended = AsyncMock()
        client.read_random_extended = AsyncMock()
        client.write_random_words_extended = AsyncMock()
        client.write_random_bits_extended = AsyncMock()
        client.register_monitor_devices_extended = AsyncMock()

        await AsyncSlmpClient.read_devices_ext(client, r"U3E0\G0", 1, bit_unit=False)
        client.read_devices_extended.assert_awaited_once_with(r"U3E0\G0", 1, bit_unit=False)

        await AsyncSlmpClient.write_devices_ext(client, r"U3E0\G0", [1], bit_unit=False)
        client.write_devices_extended.assert_awaited_once_with(r"U3E0\G0", [1], bit_unit=False)

        await AsyncSlmpClient.read_random_ext(client, word_devices=[r"U3E0\G0"])
        client.read_random_extended.assert_awaited_once_with(
            word_devices=[r"U3E0\G0"],
            dword_devices=(),
        )

        await AsyncSlmpClient.write_random_words_ext(client, dword_values=[(r"J1\W0", 1)])
        client.write_random_words_extended.assert_awaited_once_with(
            word_values=(),
            dword_values=[(r"J1\W0", 1)],
        )

        await AsyncSlmpClient.write_random_bits_ext(client, [(r"J1\B0", True)])
        client.write_random_bits_extended.assert_awaited_once_with([(r"J1\B0", True)])

        await AsyncSlmpClient.register_monitor_devices_ext(client, dword_devices=[r"J1\W0"])
        client.register_monitor_devices_extended.assert_awaited_once_with(
            word_devices=(),
            dword_devices=[r"J1\W0"],
        )

    async def test_async_latest_self_diagnosis_reads_sd0_once_and_propagates_errors(self) -> None:
        client = MagicMock()
        client.read_devices = AsyncMock(return_value=[0xC123])

        assert await AsyncSlmpClient.read_latest_self_diagnosis_error_code(client) == 0xC123
        client.read_devices.assert_awaited_once_with("SD0", 1, bit_unit=False)

        client.read_devices.reset_mock()
        client.read_devices.side_effect = RuntimeError("PLC error")
        with self.assertRaisesRegex(RuntimeError, "PLC error"):
            await AsyncSlmpClient.read_latest_self_diagnosis_error_code(client)
        client.read_devices.assert_awaited_once_with("SD0", 1, bit_unit=False)


def test_sync_latest_self_diagnosis_reads_sd0_once_and_propagates_errors() -> None:
    client = MagicMock()
    client.read_devices.return_value = [0xC123]

    assert SlmpClient.read_latest_self_diagnosis_error_code(client) == 0xC123
    client.read_devices.assert_called_once_with("SD0", 1, bit_unit=False)

    client.read_devices.reset_mock()
    client.read_devices.side_effect = RuntimeError("PLC error")
    with unittest.TestCase().assertRaisesRegex(RuntimeError, "PLC error"):
        SlmpClient.read_latest_self_diagnosis_error_code(client)
    client.read_devices.assert_called_once_with("SD0", 1, bit_unit=False)


def test_plc_profile_display_name_is_canonical_and_legacy_name_delegates() -> None:
    assert "plc_profile_display_name" in slmp.__all__
    expected = slmp.plc_profile_display_name("melsec:iq-r")
    assert slmp.display_name("melsec:iq-r") == expected

    with patch("slmp.capability_profiles.plc_profile_display_name", return_value="profile") as canonical:
        assert slmp.display_name("melsec:iq-r") == "profile"
    canonical.assert_called_once_with("melsec:iq-r")

    for invalid in (None, "unknown"):
        with unittest.TestCase().assertRaises(ValueError):
            slmp.plc_profile_display_name(invalid)
        with unittest.TestCase().assertRaises(ValueError):
            slmp.display_name(invalid)


def test_client_read_dwords_methods_remain_non_deprecated_client_members() -> None:
    for client_type in (SlmpClient, AsyncSlmpClient):
        parameters = list(inspect.signature(client_type.read_dwords).parameters)
        assert parameters == ["self", "device", "count"]
        assert "Deprecated" not in (client_type.read_dwords.__doc__ or "")
