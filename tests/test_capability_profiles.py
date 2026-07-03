"""Tests for canonical SLMP capability profiles."""

from __future__ import annotations

import json
from pathlib import Path

from slmp.capability_profiles import BUILTIN_CAPABILITY_PROFILES


def test_builtin_capability_profiles_match_canonical_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "slmp_builtin_ethernet_profiles.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))["profiles"]

    assert sorted(expected) == sorted(BUILTIN_CAPABILITY_PROFILES)
    for profile_id, expected_profile in expected.items():
        actual = BUILTIN_CAPABILITY_PROFILES[profile_id]
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
