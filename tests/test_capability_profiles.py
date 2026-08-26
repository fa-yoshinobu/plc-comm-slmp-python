"""Tests for canonical SLMP capability profiles."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from slmp import SlmpProfileLimit, SlmpProfileLimitKey, profile_limit
from slmp.capability_profiles import BUILTIN_CAPABILITY_PROFILES, display_name
from slmp.core import SlmpPlcProfile, plc_profile_descriptors


def test_builtin_capability_profiles_match_canonical_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "slmp_ethernet_profiles.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))["profiles"]

    assert sorted(expected) == sorted(BUILTIN_CAPABILITY_PROFILES)
    for profile_id, expected_profile in expected.items():
        actual = BUILTIN_CAPABILITY_PROFILES[profile_id]
        assert display_name(profile_id) == expected_profile["display_name"]
        assert actual.frame == expected_profile["frame"]
        assert actual.compat == expected_profile["compat"]
        assert sorted(actual.features) == sorted(expected_profile["features"])
        for key, expected_feature in expected_profile["features"].items():
            assert actual.features[key].state == expected_feature["state"]
        assert sorted(actual.limits) == sorted(expected_profile["limits"])
        for key, expected_limit in expected_profile["limits"].items():
            actual_limit = actual.limits[key]
            assert actual_limit.max == expected_limit["max"]
            assert actual_limit.weighted_max == expected_limit.get("weighted_max")
        assert actual.write_policy == expected_profile["write_policy"]


def test_public_profile_limit_lookup_exposes_operational_values_only() -> None:
    assert len(SlmpProfileLimitKey) == 12
    assert all(profile_limit("melsec:iq-r", key) is not None for key in SlmpProfileLimitKey)
    assert profile_limit(
        "melsec:iq-r",
        SlmpProfileLimitKey.RANDOM_READ_WORD,
    ) == SlmpProfileLimit(max_points=96)
    assert profile_limit(
        "melsec:qnudv",
        SlmpProfileLimitKey.RANDOM_READ_WORD,
    ) == SlmpProfileLimit(max_points=192)
    assert profile_limit(
        "melsec:iq-r",
        SlmpProfileLimitKey.RANDOM_WRITE_WORD,
    ) == SlmpProfileLimit(max_points=80, weighted_max_points=960)
    assert profile_limit(None, SlmpProfileLimitKey.RANDOM_READ_WORD) is None
    assert [field.name for field in fields(SlmpProfileLimit)] == [
        "max_points",
        "weighted_max_points",
    ]

    with pytest.raises(TypeError, match="SlmpProfileLimitKey"):
        profile_limit("melsec:iq-r", "random_read_word")  # type: ignore[arg-type]


def test_profile_descriptors_match_canonical_profile_metadata() -> None:
    fixture = Path(__file__).parent / "fixtures" / "slmp_ethernet_profiles.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))["profiles"]
    descriptors = plc_profile_descriptors()

    assert [descriptor.canonical_name for descriptor in descriptors] == [profile.value for profile in SlmpPlcProfile]
    assert {descriptor.canonical_name for descriptor in descriptors} == set(expected)
    for descriptor in descriptors:
        profile = expected[descriptor.canonical_name]
        assert descriptor.display_name == profile["display_name"]
        assert descriptor.connectable is (profile.get("role") != "base")
        assert descriptor.base_profile == profile.get("base_profile")
