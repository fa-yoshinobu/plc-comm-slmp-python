"""Built-in SLMP capability profiles.

Source: plc-comm-slmp-profiles main
capability/slmp_ethernet_profiles.json
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

CANONICAL_SOURCE = "plc-comm-slmp-profiles main capability/slmp_ethernet_profiles.json"


@dataclass(frozen=True)
class CapabilityFeature:
    """One feature state from the canonical capability table."""

    state: str
    source: str
    note: str | None = None


@dataclass(frozen=True)
class CapabilityLimit:
    """One protocol limit from the canonical capability table."""

    max: int
    over_end_code: str | None
    source: str
    weighted_max: int | None = None
    note: str | None = None


class SlmpProfileLimitKey(str, Enum):
    """Canonical key for one profile-specific SLMP request limit."""

    DIRECT_WORD_READ = "direct_word_read"
    DIRECT_WORD_WRITE = "direct_word_write"
    DIRECT_BIT_READ = "direct_bit_read"
    DIRECT_BIT_WRITE = "direct_bit_write"
    RANDOM_READ_WORD = "random_read_word"
    RANDOM_WRITE_WORD = "random_write_word"
    RANDOM_WRITE_BIT = "random_write_bit"
    MONITOR_REGISTER_WORD = "monitor_register_word"
    RANDOM_READ_WORD_EXT = "random_read_word_ext"
    RANDOM_WRITE_WORD_EXT = "random_write_word_ext"
    RANDOM_WRITE_BIT_EXT = "random_write_bit_ext"
    MONITOR_REGISTER_WORD_EXT = "monitor_register_word_ext"


@dataclass(frozen=True)
class SlmpProfileLimit:
    """Operational limits for one PLC profile and limit key."""

    max_points: int
    weighted_max_points: int | None = None


@dataclass(frozen=True)
class CapabilityProfile:
    """One canonical PLC capability profile."""

    profile_id: str
    frame: str
    compat: str
    features: dict[str, CapabilityFeature]
    limits: dict[str, CapabilityLimit]
    write_policy: dict[str, str]


def _features(*entries: tuple[str, str, str, str | None]) -> dict[str, CapabilityFeature]:
    return {key: CapabilityFeature(state=state, source=source, note=note) for key, state, source, note in entries}


def _limits(*entries: tuple[str, int, str | None, str, int | None, str | None]) -> dict[str, CapabilityLimit]:
    return {
        key: CapabilityLimit(max=max_value, over_end_code=end_code, source=source, weighted_max=weighted, note=note)
        for key, max_value, end_code, source, weighted, note in entries
    }


def _write_policy(*device_codes: str) -> dict[str, str]:
    return {device_code: "read-only" for device_code in device_codes}


def _policy(**entries: str) -> dict[str, str]:
    return dict(entries)


def _iqr_common_features(hg_state: str) -> dict[str, CapabilityFeature]:
    return _features(
        ("type_name", "supported", "live", None),
        ("direct", "supported", "live", None),
        ("random", "supported", "live", None),
        ("block", "supported", "live", None),
        ("monitor", "supported", "live", None),
        ("ext_module_access", "config-dependent", "live", "Module access depends on the installed special module."),
        (
            "ext_link_direct",
            "config-dependent",
            "live",
            "Link-direct access depends on the network/module configuration.",
        ),
        (
            "hg_cpu_buffer",
            hg_state,
            "live" if hg_state == "supported" else "spec",
            "U3E0\\HG direct/random/monitor succeeded."
            if hg_state == "supported"
            else "CPU-buffer HG is an iQ-R-only path.",
        ),
        ("long_device_path", "supported", "live", None),
        ("lz_32bit_path", "supported", "live", None),
    )


def _ql_features(source: str) -> dict[str, CapabilityFeature]:
    return _features(
        ("type_name", "blocked", source, "Read Type Name returned C059."),
        ("direct", "supported", source, None),
        ("random", "supported", source, None),
        ("block", "blocked", source, "Read/Write Block returned C059."),
        ("monitor", "supported", source, None),
        ("ext_module_access", "blocked", source, "U\\G access is not available on the tested built-in CPU port."),
        ("ext_link_direct", "blocked", source, "Link-direct access is not available on the tested built-in CPU port."),
        ("hg_cpu_buffer", "blocked", "spec", "CPU-buffer HG is an iQ-R-only path."),
        ("long_device_path", "delegated", source, "Existing long-device route rules decide this feature."),
        ("lz_32bit_path", "delegated", source, "Existing 32-bit route rules decide this feature."),
    )


def _ql_unit_features() -> dict[str, CapabilityFeature]:
    return _features(
        ("type_name", "supported", "live", None),
        ("direct", "supported", "live", None),
        ("random", "supported", "live", None),
        ("block", "supported", "live", None),
        ("monitor", "supported", "live", None),
        ("ext_module_access", "config-dependent", "live", None),
        ("ext_link_direct", "config-dependent", "live", None),
        ("hg_cpu_buffer", "blocked", "spec", "CPU-buffer HG is an iQ-R-only path."),
        ("long_device_path", "blocked", "live", None),
        ("lz_32bit_path", "blocked", "live", None),
    )


def _iqr_limits() -> dict[str, CapabilityLimit]:
    return _limits(
        ("direct_word_read", 960, "C051", "live", None, None),
        ("direct_word_write", 960, "C051", "live", None, None),
        ("direct_bit_read", 7168, "C052", "live", None, None),
        ("direct_bit_write", 7168, "C052", "live", None, None),
        ("random_read_word", 96, "C054", "live", None, None),
        ("random_write_word", 80, "C054", "live", 960, None),
        ("random_write_bit", 94, "C053", "live", None, None),
        ("monitor_register_word", 96, "C054", "live", None, None),
        ("random_read_word_ext", 96, "C054", "live", None, None),
        ("random_write_word_ext", 80, "C054", "live", 960, None),
        ("random_write_bit_ext", 94, "C053", "live", None, None),
        ("monitor_register_word_ext", 96, "C054", "live", None, None),
    )


def _iqf_limits() -> dict[str, CapabilityLimit]:
    return _limits(
        ("direct_word_read", 960, "C051", "live", None, None),
        ("direct_word_write", 960, "C051", "live", None, None),
        ("direct_bit_read", 3584, "C052", "live", None, None),
        ("direct_bit_write", 3584, "C052", "live", None, None),
        ("random_read_word", 192, "C054", "live", None, None),
        ("random_write_word", 160, "C054", "live", 1920, None),
        ("random_write_bit", 188, "C053", "live", None, None),
        ("monitor_register_word", 192, "C054", "not-adopted", None, None),
        ("random_read_word_ext", 96, "C054", "live", None, None),
        ("random_write_word_ext", 80, "C054", "live", 960, None),
        ("random_write_bit_ext", 94, "C053", "live", None, None),
        ("monitor_register_word_ext", 96, "C054", "not-adopted", None, None),
    )


def _ql_limits(
    source: str,
    *,
    ext_read_max: int = 192,
    ext_read_over_end_code: str = "C054",
) -> dict[str, CapabilityLimit]:
    return _limits(
        ("direct_word_read", 960, "C051", source, None, None),
        ("direct_word_write", 960, "C051", source, None, None),
        ("direct_bit_read", 7168, "C052", source, None, None),
        ("direct_bit_write", 7168, "C052", source, None, None),
        ("random_read_word", 192, "C054", source, None, None),
        ("random_write_word", 160, "C054", source, 1920, None),
        ("random_write_bit", 188, "C053", source, None, None),
        ("monitor_register_word", 192, "C054", source, None, None),
        ("random_read_word_ext", ext_read_max, ext_read_over_end_code, "inferred", None, None),
        ("random_write_word_ext", 160, "4080", "inferred", 1920, None),
        ("random_write_bit_ext", 188, "C053", "inferred", None, None),
        ("monitor_register_word_ext", 192, "C054", "inferred", None, None),
    )


def _ql_unit_limits(
    *,
    ext_read_max: int,
    include_bit_ext: bool,
    bit_ext_source: str = "live",
) -> dict[str, CapabilityLimit]:
    entries: list[tuple[str, int, str | None, str, int | None, str | None]] = [
        ("direct_word_read", 960, "C051", "live", None, None),
        ("direct_word_write", 960, "C051", "live", None, None),
        ("direct_bit_read", 7168, "C052", "live", None, None),
        ("direct_bit_write", 7168, "C052", "live", None, None),
        ("random_read_word", 192, "C054", "live", None, None),
        ("random_write_word", 160, "4080", "live", 1920, None),
        ("random_write_bit", 188, "C053", "live", None, None),
        ("monitor_register_word", 192, "C054", "live", None, None),
        ("random_read_word_ext", ext_read_max, "4080" if ext_read_max == 185 else "C054", "live", None, None),
        ("random_write_word_ext", 160, "4080", "live", 1920, None),
        ("monitor_register_word_ext", 192, "C054", "live", None, None),
    ]
    if include_bit_ext:
        entries.append(("random_write_bit_ext", 188, "C053", bit_ext_source, None, None))
    return _limits(*entries)


BUILTIN_CAPABILITY_PROFILES: dict[str, CapabilityProfile] = {
    "melsec:iq-r": CapabilityProfile(
        profile_id="melsec:iq-r",
        frame="4E",
        compat="iQ-R",
        features=_iqr_common_features("supported"),
        limits=_iqr_limits(),
        write_policy=_write_policy("S"),
    ),
    "melsec:iq-r:rj71en71": CapabilityProfile(
        profile_id="melsec:iq-r:rj71en71",
        frame="4E",
        compat="iQ-R",
        features=_iqr_common_features("supported"),
        limits=_iqr_limits(),
        write_policy=_write_policy("S"),
    ),
    "melsec:iq-l": CapabilityProfile(
        profile_id="melsec:iq-l",
        frame="4E",
        compat="iQ-R",
        features=_iqr_common_features("blocked"),
        limits=_iqr_limits(),
        write_policy=_write_policy("S"),
    ),
    "melsec:mx-r": CapabilityProfile(
        profile_id="melsec:mx-r",
        frame="4E",
        compat="iQ-R",
        features=_iqr_common_features("blocked"),
        limits=_iqr_limits(),
        write_policy=_write_policy("S"),
    ),
    "melsec:mx-r:rj71en71": CapabilityProfile(
        profile_id="melsec:mx-r:rj71en71",
        frame="4E",
        compat="iQ-R",
        features=_iqr_common_features("blocked"),
        limits=_iqr_limits(),
        write_policy=_write_policy("S"),
    ),
    "melsec:mx-f": CapabilityProfile(
        profile_id="melsec:mx-f",
        frame="4E",
        compat="iQ-R",
        features=_iqr_common_features("blocked"),
        limits=_iqr_limits(),
        write_policy=_write_policy("S"),
    ),
    "melsec:iq-f": CapabilityProfile(
        profile_id="melsec:iq-f",
        frame="3E",
        compat="Q/L",
        features=_features(
            ("type_name", "supported", "live", None),
            ("direct", "supported", "live", None),
            ("random", "supported", "live", None),
            ("block", "supported", "live", None),
            ("monitor", "blocked", "live", "0x0801/0x0802 returned C059 on FX5U."),
            ("ext_module_access", "config-dependent", "live", "U1\\G0 depends on the installed special module."),
            ("ext_link_direct", "blocked", "live", "J1 link-direct access returned a PLC error."),
            ("hg_cpu_buffer", "blocked", "spec", "CPU-buffer HG is an iQ-R-only path."),
            ("long_device_path", "supported", "live", None),
            ("lz_32bit_path", "supported", "live", None),
        ),
        limits=_iqf_limits(),
        write_policy=_policy(S="read-write"),
    ),
    "melsec:qcpu": CapabilityProfile(
        profile_id="melsec:qcpu",
        frame="3E",
        compat="Q/L",
        features=_ql_features("policy"),
        limits=_ql_limits("inferred", ext_read_max=185, ext_read_over_end_code="4080"),
        write_policy=_write_policy("S"),
    ),
    "melsec:qcpu:qj71e71-100": CapabilityProfile(
        profile_id="melsec:qcpu:qj71e71-100",
        frame="4E",
        compat="Q/L",
        features=_ql_unit_features(),
        limits=_ql_unit_limits(ext_read_max=185, include_bit_ext=True),
        write_policy=_policy(S="read-write"),
    ),
    "melsec:lcpu": CapabilityProfile(
        profile_id="melsec:lcpu",
        frame="3E",
        compat="Q/L",
        features=_ql_features("live"),
        limits=_ql_limits("live"),
        write_policy=_write_policy("S"),
    ),
    "melsec:lcpu:lj71e71-100": CapabilityProfile(
        profile_id="melsec:lcpu:lj71e71-100",
        frame="4E",
        compat="Q/L",
        features=_ql_unit_features(),
        limits=_ql_unit_limits(ext_read_max=192, include_bit_ext=True, bit_ext_source="inferred"),
        write_policy=_policy(S="read-write"),
    ),
    "melsec:qnu": CapabilityProfile(
        profile_id="melsec:qnu",
        frame="3E",
        compat="Q/L",
        features=_ql_features("live"),
        limits=_ql_limits("live"),
        write_policy=_write_policy("S"),
    ),
    "melsec:qnu:qj71e71-100": CapabilityProfile(
        profile_id="melsec:qnu:qj71e71-100",
        frame="4E",
        compat="Q/L",
        features=_ql_unit_features(),
        limits=_ql_unit_limits(ext_read_max=192, include_bit_ext=True),
        write_policy=_policy(S="read-write"),
    ),
    "melsec:qnudv": CapabilityProfile(
        profile_id="melsec:qnudv",
        frame="3E",
        compat="Q/L",
        features=_ql_features("live"),
        limits=_ql_limits("live"),
        write_policy=_write_policy("S"),
    ),
    "melsec:qnudv:qj71e71-100": CapabilityProfile(
        profile_id="melsec:qnudv:qj71e71-100",
        frame="4E",
        compat="Q/L",
        features=_ql_unit_features(),
        limits=_ql_unit_limits(ext_read_max=192, include_bit_ext=True),
        write_policy=_policy(S="read-write"),
    ),
}

_PROFILE_DISPLAY_NAMES = {
    "melsec:iq-r": "MELSEC iQ-R (built-in)",
    "melsec:iq-r:rj71en71": "MELSEC iQ-R (RJ71EN71)",
    "melsec:iq-l": "MELSEC iQ-L (built-in)",
    "melsec:mx-r": "MELSEC MX-R (built-in)",
    "melsec:mx-r:rj71en71": "MELSEC MX-R (RJ71EN71)",
    "melsec:mx-f": "MELSEC MX-F (built-in)",
    "melsec:iq-f": "MELSEC iQ-F (built-in)",
    "melsec:qcpu": "MELSEC-Q (base profile)",
    "melsec:qcpu:qj71e71-100": "MELSEC-Q (QJ71E71-100)",
    "melsec:lcpu": "MELSEC-L (built-in)",
    "melsec:lcpu:lj71e71-100": "MELSEC-L (LJ71E71-100)",
    "melsec:qnu": "MELSEC QnU (built-in)",
    "melsec:qnu:qj71e71-100": "MELSEC QnU (QJ71E71-100)",
    "melsec:qnudv": "MELSEC QnUDV (built-in)",
    "melsec:qnudv:qj71e71-100": "MELSEC QnUDV (QJ71E71-100)",
}


def normalize_profile_id(plc_profile: object | None) -> str | None:
    """Return a canonical profile id or None when no profile was selected."""
    if plc_profile is None:
        return None
    raw = getattr(plc_profile, "value", plc_profile)
    text = str(raw).strip()
    return text or None


def capability_profile(plc_profile: object | None) -> CapabilityProfile | None:
    """Return the built-in capability profile, if one is defined."""
    profile_id = normalize_profile_id(plc_profile)
    if profile_id is None:
        return None
    return BUILTIN_CAPABILITY_PROFILES.get(profile_id)


def display_name(plc_profile: object | None) -> str:
    """Return the canonical human-readable display name for a PLC profile."""
    profile_id = normalize_profile_id(plc_profile)
    if profile_id is None:
        raise ValueError("plc_profile is required.")
    try:
        return _PROFILE_DISPLAY_NAMES[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported plc_profile: {plc_profile!r}.") from exc


def _capability_limit(plc_profile: object | None, key: str) -> CapabilityLimit | None:
    """Return an internal capability limit, if present."""
    profile = capability_profile(plc_profile)
    if profile is None:
        return None
    return profile.limits.get(key)


def profile_limit(
    plc_profile: object | None,
    key: SlmpProfileLimitKey,
) -> SlmpProfileLimit | None:
    """Return operational request limits without performing PLC communication."""
    if not isinstance(key, SlmpProfileLimitKey):
        raise TypeError("key must be a SlmpProfileLimitKey")
    limit = _capability_limit(plc_profile, key.value)
    if limit is None:
        return None
    return SlmpProfileLimit(
        max_points=limit.max,
        weighted_max_points=limit.weighted_max,
    )


def is_profile_read_only_device(plc_profile: object | None, device_code: str) -> bool:
    """Return True when write_policy marks the device as read-only."""
    profile = capability_profile(plc_profile)
    if profile is None:
        return False
    return profile.write_policy.get(device_code) == "read-only"


def ensure_profile_feature_allowed(plc_profile: object | None, feature_key: str, *, strict_profile: bool) -> None:
    """Raise when strict profile checks block a feature before transport."""
    if not strict_profile:
        return
    profile = capability_profile(plc_profile)
    if profile is None:
        return
    feature = profile.features.get(feature_key)
    if feature is None or feature.state not in {"blocked", "unverified"}:
        return

    from .errors import SlmpProfileFeatureError

    evidence = (
        f"{feature.source}; {CANONICAL_SOURCE}"
        if feature.note is None
        else (f"{feature.source}: {feature.note}; {CANONICAL_SOURCE}")
    )
    raise SlmpProfileFeatureError(profile.profile_id, feature_key, feature.state, evidence)


def ensure_extended_profile_feature_allowed(
    plc_profile: object | None,
    ref: Any,
    extension: Any,
    *,
    strict_profile: bool,
) -> None:
    """Apply feature guards for Extended Device G/HG/J routes."""
    direct_memory = int(extension.direct_memory_specification)
    code = str(ref.code)
    if direct_memory == 0xF9:
        ensure_profile_feature_allowed(plc_profile, "ext_link_direct", strict_profile=strict_profile)
    elif code == "HG" or direct_memory == 0xFA:
        ensure_profile_feature_allowed(plc_profile, "hg_cpu_buffer", strict_profile=strict_profile)
    elif code == "G" or direct_memory == 0xF8:
        ensure_profile_feature_allowed(plc_profile, "ext_module_access", strict_profile=strict_profile)
