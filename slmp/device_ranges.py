"""Device-range catalogs resolved from one PLC-profile-specific SD block read."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, cast

from .core import DeviceRef, SlmpPlcProfile
from .errors import SlmpError


class SlmpDeviceRangeCategory(str, Enum):
    """Logical grouping for monitor-oriented range output."""

    Bit = "bit"
    Word = "word"
    TimerCounter = "timer-counter"
    Index = "index"
    FileRefresh = "file-refresh"


class SlmpDeviceRangeNotation(str, Enum):
    """Public address notation for the rendered range string."""

    Base10 = "base10"
    Base8 = "base8"
    Base16 = "base16"


@dataclass(frozen=True)
class SlmpDeviceRangeEntry:
    """One device entry in the resolved catalog."""

    device: str
    category: SlmpDeviceRangeCategory
    is_bit_device: bool
    supported: bool
    lower_bound: int
    upper_bound: int | None
    point_count: int | None
    address_range: str | None
    notation: SlmpDeviceRangeNotation
    source: str
    notes: str | None


@dataclass(frozen=True)
class SlmpDeviceRangeCatalog:
    """Resolved device-range catalog for one explicit PLC profile."""

    model: str
    model_code: int | None
    has_model_code: bool
    plc_profile: SlmpPlcProfile
    entries: list[SlmpDeviceRangeEntry]


class _RangeValueKind(str, Enum):
    Unsupported = "unsupported"
    Undefined = "undefined"
    Fixed = "fixed"
    WordRegister = "word-register"
    DWordRegister = "dword-register"
    WordRegisterClipped = "word-register-clipped"
    DWordRegisterClipped = "dword-register-clipped"


@dataclass(frozen=True)
class _RangeValueSpec:
    kind: _RangeValueKind
    register: int
    fixed_value: int
    clip_value: int
    source: str
    notes: str | None = None


@dataclass(frozen=True)
class _RangeRow:
    category: SlmpDeviceRangeCategory
    devices: tuple[tuple[str, bool], ...]
    notation: SlmpDeviceRangeNotation


@dataclass(frozen=True)
class _RangeProfile:
    plc_profile: SlmpPlcProfile
    register_start: int
    register_count: int
    rules: dict[str, _RangeValueSpec]


_ORDERED_ITEMS = (
    "X",
    "Y",
    "M",
    "B",
    "SB",
    "F",
    "V",
    "L",
    "S",
    "D",
    "W",
    "SW",
    "R",
    "T",
    "ST",
    "C",
    "LT",
    "LST",
    "LC",
    "Z",
    "LZ",
    "ZR",
    "RD",
    "SM",
    "SD",
)

_MAX_RUNTIME_RANGE_PROBE_COUNT = 1_048_576
_ZR_RUNTIME_FAMILIES = {
    SlmpPlcProfile.QCpu,
    SlmpPlcProfile.LCpu,
    SlmpPlcProfile.QnU,
    SlmpPlcProfile.QnUDV,
}

_ROWS: dict[str, _RangeRow] = {
    "X": _RangeRow(SlmpDeviceRangeCategory.Bit, (("X", True),), SlmpDeviceRangeNotation.Base16),
    "Y": _RangeRow(SlmpDeviceRangeCategory.Bit, (("Y", True),), SlmpDeviceRangeNotation.Base16),
    "M": _RangeRow(SlmpDeviceRangeCategory.Bit, (("M", True),), SlmpDeviceRangeNotation.Base10),
    "B": _RangeRow(SlmpDeviceRangeCategory.Bit, (("B", True),), SlmpDeviceRangeNotation.Base16),
    "SB": _RangeRow(SlmpDeviceRangeCategory.Bit, (("SB", True),), SlmpDeviceRangeNotation.Base16),
    "F": _RangeRow(SlmpDeviceRangeCategory.Bit, (("F", True),), SlmpDeviceRangeNotation.Base10),
    "V": _RangeRow(SlmpDeviceRangeCategory.Bit, (("V", True),), SlmpDeviceRangeNotation.Base10),
    "L": _RangeRow(SlmpDeviceRangeCategory.Bit, (("L", True),), SlmpDeviceRangeNotation.Base10),
    "S": _RangeRow(SlmpDeviceRangeCategory.Bit, (("S", True),), SlmpDeviceRangeNotation.Base10),
    "D": _RangeRow(SlmpDeviceRangeCategory.Word, (("D", False),), SlmpDeviceRangeNotation.Base10),
    "W": _RangeRow(SlmpDeviceRangeCategory.Word, (("W", False),), SlmpDeviceRangeNotation.Base16),
    "SW": _RangeRow(SlmpDeviceRangeCategory.Word, (("SW", False),), SlmpDeviceRangeNotation.Base16),
    "R": _RangeRow(SlmpDeviceRangeCategory.Word, (("R", False),), SlmpDeviceRangeNotation.Base10),
    "T": _RangeRow(
        SlmpDeviceRangeCategory.TimerCounter,
        (("TS", True), ("TC", True), ("TN", False)),
        SlmpDeviceRangeNotation.Base10,
    ),
    "ST": _RangeRow(
        SlmpDeviceRangeCategory.TimerCounter,
        (("STS", True), ("STC", True), ("STN", False)),
        SlmpDeviceRangeNotation.Base10,
    ),
    "C": _RangeRow(
        SlmpDeviceRangeCategory.TimerCounter,
        (("CS", True), ("CC", True), ("CN", False)),
        SlmpDeviceRangeNotation.Base10,
    ),
    "LT": _RangeRow(
        SlmpDeviceRangeCategory.TimerCounter,
        (("LTS", True), ("LTC", True), ("LTN", False)),
        SlmpDeviceRangeNotation.Base10,
    ),
    "LST": _RangeRow(
        SlmpDeviceRangeCategory.TimerCounter,
        (("LSTS", True), ("LSTC", True), ("LSTN", False)),
        SlmpDeviceRangeNotation.Base10,
    ),
    "LC": _RangeRow(
        SlmpDeviceRangeCategory.TimerCounter,
        (("LCS", True), ("LCC", True), ("LCN", False)),
        SlmpDeviceRangeNotation.Base10,
    ),
    "Z": _RangeRow(SlmpDeviceRangeCategory.Index, (("Z", False),), SlmpDeviceRangeNotation.Base10),
    "LZ": _RangeRow(SlmpDeviceRangeCategory.Index, (("LZ", False),), SlmpDeviceRangeNotation.Base10),
    "ZR": _RangeRow(SlmpDeviceRangeCategory.FileRefresh, (("ZR", False),), SlmpDeviceRangeNotation.Base10),
    "RD": _RangeRow(SlmpDeviceRangeCategory.FileRefresh, (("RD", False),), SlmpDeviceRangeNotation.Base10),
    "SM": _RangeRow(SlmpDeviceRangeCategory.Bit, (("SM", True),), SlmpDeviceRangeNotation.Base10),
    "SD": _RangeRow(SlmpDeviceRangeCategory.Word, (("SD", False),), SlmpDeviceRangeNotation.Base10),
}

_CANONICAL_FAMILIES = {member.value: member for member in SlmpPlcProfile}


def _fixed(value: int, source: str) -> _RangeValueSpec:
    return _RangeValueSpec(_RangeValueKind.Fixed, 0, value, 0, source)


def _word(register: int, source: str, notes: str | None = None) -> _RangeValueSpec:
    return _RangeValueSpec(_RangeValueKind.WordRegister, register, 0, 0, source, notes)


def _dword(register: int, source: str, notes: str | None = None) -> _RangeValueSpec:
    return _RangeValueSpec(_RangeValueKind.DWordRegister, register, 0, 0, source, notes)


def _word_clipped(register: int, clip_value: int, source: str, notes: str | None = None) -> _RangeValueSpec:
    return _RangeValueSpec(_RangeValueKind.WordRegisterClipped, register, 0, clip_value, source, notes)


def _dword_clipped(register: int, clip_value: int, source: str, notes: str | None = None) -> _RangeValueSpec:
    return _RangeValueSpec(_RangeValueKind.DWordRegisterClipped, register, 0, clip_value, source, notes)


def _unsupported(notes: str) -> _RangeValueSpec:
    return _RangeValueSpec(_RangeValueKind.Unsupported, 0, 0, 0, "Unsupported", notes)


def _undefined(notes: str) -> _RangeValueSpec:
    return _RangeValueSpec(_RangeValueKind.Undefined, 0, 0, 0, "Undefined", notes)


_PROFILES: dict[SlmpPlcProfile, _RangeProfile] = {
    SlmpPlcProfile.IqR: _RangeProfile(
        SlmpPlcProfile.IqR,
        260,
        50,
        {
            "X": _dword(260, "SD260-SD261 (32-bit)"),
            "Y": _dword(262, "SD262-SD263 (32-bit)"),
            "M": _dword(264, "SD264-SD265 (32-bit)"),
            "B": _dword(266, "SD266-SD267 (32-bit)"),
            "SB": _dword(268, "SD268-SD269 (32-bit)"),
            "F": _dword(270, "SD270-SD271 (32-bit)"),
            "V": _dword(272, "SD272-SD273 (32-bit)"),
            "L": _dword(274, "SD274-SD275 (32-bit)"),
            "S": _dword(276, "SD276-SD277 (32-bit)"),
            "D": _dword(280, "SD280-SD281 (32-bit)"),
            "W": _dword(282, "SD282-SD283 (32-bit)"),
            "SW": _dword(284, "SD284-SD285 (32-bit)"),
            "R": _dword_clipped(306, 32768, "SD306-SD307 (32-bit)", "Upper bound is clipped to 32768."),
            "T": _dword(288, "SD288-SD289 (32-bit)"),
            "ST": _dword(290, "SD290-SD291 (32-bit)"),
            "C": _dword(292, "SD292-SD293 (32-bit)"),
            "LT": _dword(294, "SD294-SD295 (32-bit)"),
            "LST": _dword(296, "SD296-SD297 (32-bit)"),
            "LC": _dword(298, "SD298-SD299 (32-bit)"),
            "Z": _word(300, "SD300"),
            "LZ": _word(302, "SD302"),
            "ZR": _dword(306, "SD306-SD307 (32-bit)"),
            "RD": _dword(308, "SD308-SD309 (32-bit)"),
            "SM": _fixed(4096, "Fixed family limit"),
            "SD": _fixed(4096, "Fixed family limit"),
        },
    ),
    SlmpPlcProfile.IqL: _RangeProfile(
        SlmpPlcProfile.IqL,
        260,
        50,
        {
            "X": _dword(260, "SD260-SD261 (32-bit)"),
            "Y": _dword(262, "SD262-SD263 (32-bit)"),
            "M": _dword(264, "SD264-SD265 (32-bit)"),
            "B": _dword(266, "SD266-SD267 (32-bit)"),
            "SB": _dword(268, "SD268-SD269 (32-bit)"),
            "F": _dword(270, "SD270-SD271 (32-bit)"),
            "V": _dword(272, "SD272-SD273 (32-bit)"),
            "L": _dword(274, "SD274-SD275 (32-bit)"),
            "S": _dword(276, "SD276-SD277 (32-bit)"),
            "D": _dword(280, "SD280-SD281 (32-bit)"),
            "W": _dword(282, "SD282-SD283 (32-bit)"),
            "SW": _dword(284, "SD284-SD285 (32-bit)"),
            "R": _dword_clipped(306, 32768, "SD306-SD307 (32-bit)", "Upper bound is clipped to 32768."),
            "T": _dword(288, "SD288-SD289 (32-bit)"),
            "ST": _dword(290, "SD290-SD291 (32-bit)"),
            "C": _dword(292, "SD292-SD293 (32-bit)"),
            "LT": _dword(294, "SD294-SD295 (32-bit)"),
            "LST": _dword(296, "SD296-SD297 (32-bit)"),
            "LC": _dword(298, "SD298-SD299 (32-bit)"),
            "Z": _word(300, "SD300"),
            "LZ": _word(302, "SD302"),
            "ZR": _dword(306, "SD306-SD307 (32-bit)"),
            "RD": _dword(308, "SD308-SD309 (32-bit)"),
            "SM": _fixed(4096, "Fixed family limit"),
            "SD": _fixed(4096, "Fixed family limit"),
        },
    ),
    SlmpPlcProfile.MxF: _RangeProfile(
        SlmpPlcProfile.MxF,
        260,
        50,
        {
            "X": _dword(260, "SD260-SD261 (32-bit)"),
            "Y": _dword(262, "SD262-SD263 (32-bit)"),
            "M": _dword(264, "SD264-SD265 (32-bit)"),
            "B": _dword(266, "SD266-SD267 (32-bit)"),
            "SB": _dword(268, "SD268-SD269 (32-bit)"),
            "F": _dword(270, "SD270-SD271 (32-bit)"),
            "V": _dword(272, "SD272-SD273 (32-bit)"),
            "L": _dword(274, "SD274-SD275 (32-bit)"),
            "S": _unsupported("Not supported on MX-F."),
            "D": _dword(280, "SD280-SD281 (32-bit)"),
            "W": _dword(282, "SD282-SD283 (32-bit)"),
            "SW": _dword(284, "SD284-SD285 (32-bit)"),
            "R": _dword_clipped(306, 32768, "SD306-SD307 (32-bit)", "Upper bound is clipped to 32768."),
            "T": _dword(288, "SD288-SD289 (32-bit)"),
            "ST": _dword(290, "SD290-SD291 (32-bit)"),
            "C": _dword(292, "SD292-SD293 (32-bit)"),
            "LT": _dword(294, "SD294-SD295 (32-bit)"),
            "LST": _dword(296, "SD296-SD297 (32-bit)"),
            "LC": _dword(298, "SD298-SD299 (32-bit)"),
            "Z": _word(300, "SD300"),
            "LZ": _word(302, "SD302"),
            "ZR": _dword(306, "SD306-SD307 (32-bit)"),
            "RD": _dword(308, "SD308-SD309 (32-bit)"),
            "SM": _fixed(10000, "Fixed family limit"),
            "SD": _fixed(10000, "Fixed family limit"),
        },
    ),
    SlmpPlcProfile.MxR: _RangeProfile(
        SlmpPlcProfile.MxR,
        260,
        50,
        {
            "X": _dword(260, "SD260-SD261 (32-bit)"),
            "Y": _dword(262, "SD262-SD263 (32-bit)"),
            "M": _dword(264, "SD264-SD265 (32-bit)"),
            "B": _dword(266, "SD266-SD267 (32-bit)"),
            "SB": _dword(268, "SD268-SD269 (32-bit)"),
            "F": _dword(270, "SD270-SD271 (32-bit)"),
            "V": _dword(272, "SD272-SD273 (32-bit)"),
            "L": _dword(274, "SD274-SD275 (32-bit)"),
            "S": _unsupported("Not supported on MX-R."),
            "D": _dword(280, "SD280-SD281 (32-bit)"),
            "W": _dword(282, "SD282-SD283 (32-bit)"),
            "SW": _dword(284, "SD284-SD285 (32-bit)"),
            "R": _dword_clipped(306, 32768, "SD306-SD307 (32-bit)", "Upper bound is clipped to 32768."),
            "T": _dword(288, "SD288-SD289 (32-bit)"),
            "ST": _dword(290, "SD290-SD291 (32-bit)"),
            "C": _dword(292, "SD292-SD293 (32-bit)"),
            "LT": _dword(294, "SD294-SD295 (32-bit)"),
            "LST": _dword(296, "SD296-SD297 (32-bit)"),
            "LC": _dword(298, "SD298-SD299 (32-bit)"),
            "Z": _word(300, "SD300"),
            "LZ": _word(302, "SD302"),
            "ZR": _dword(306, "SD306-SD307 (32-bit)"),
            "RD": _dword(308, "SD308-SD309 (32-bit)"),
            "SM": _fixed(4496, "Fixed family limit"),
            "SD": _fixed(4496, "Fixed family limit"),
        },
    ),
    SlmpPlcProfile.IqF: _RangeProfile(
        SlmpPlcProfile.IqF,
        260,
        46,
        {
            "X": _dword(260, "SD260-SD261 (32-bit)", "Manual addressing for iQ-F X devices is octal."),
            "Y": _dword(262, "SD262-SD263 (32-bit)", "Manual addressing for iQ-F Y devices is octal."),
            "M": _dword(264, "SD264-SD265 (32-bit)"),
            "B": _dword(266, "SD266-SD267 (32-bit)"),
            "SB": _dword(268, "SD268-SD269 (32-bit)"),
            "F": _dword(270, "SD270-SD271 (32-bit)"),
            "V": _unsupported("Not supported on iQ-F."),
            "L": _dword(274, "SD274-SD275 (32-bit)"),
            "S": _unsupported("Not supported on iQ-F."),
            "D": _dword(280, "SD280-SD281 (32-bit)"),
            "W": _dword(282, "SD282-SD283 (32-bit)"),
            "SW": _dword(284, "SD284-SD285 (32-bit)"),
            "R": _dword(304, "SD304-SD305 (32-bit)"),
            "T": _dword(288, "SD288-SD289 (32-bit)"),
            "ST": _dword(290, "SD290-SD291 (32-bit)"),
            "C": _dword(292, "SD292-SD293 (32-bit)"),
            "LT": _unsupported("Not supported on iQ-F."),
            "LST": _unsupported("Not supported on iQ-F."),
            "LC": _dword(298, "SD298-SD299 (32-bit)"),
            "Z": _word(300, "SD300"),
            "LZ": _word(302, "SD302"),
            "ZR": _unsupported("Not supported on iQ-F."),
            "RD": _unsupported("Not supported on iQ-F."),
            "SM": _fixed(10000, "Fixed family limit"),
            "SD": _fixed(12000, "Fixed family limit"),
        },
    ),
    SlmpPlcProfile.QCpu: _RangeProfile(
        SlmpPlcProfile.QCpu,
        290,
        15,
        {
            "X": _word(290, "SD290"),
            "Y": _word(291, "SD291"),
            "M": _word_clipped(292, 32768, "SD292", "Upper bound is clipped to 32768."),
            "B": _word_clipped(294, 32768, "SD294", "Upper bound is clipped to 32768."),
            "SB": _word(296, "SD296"),
            "F": _word(295, "SD295"),
            "V": _word(297, "SD297"),
            "L": _word(293, "SD293"),
            "S": _word(298, "SD298"),
            "D": _word_clipped(
                302,
                32768,
                "SD302",
                "Upper bound is clipped to 32768 and excludes extended area.",
            ),
            "W": _word_clipped(
                303,
                32768,
                "SD303",
                "Upper bound is clipped to 32768 and excludes extended area.",
            ),
            "SW": _word(304, "SD304"),
            "R": _fixed(32768, "Fixed family limit"),
            "T": _word(299, "SD299"),
            "ST": _word(300, "SD300"),
            "C": _word(301, "SD301"),
            "LT": _unsupported("Not supported on QCPU."),
            "LST": _unsupported("Not supported on QCPU."),
            "LC": _unsupported("Not supported on QCPU."),
            "Z": _fixed(10, "Fixed family limit"),
            "LZ": _unsupported("Not supported on QCPU."),
            "ZR": _undefined("No finite upper-bound register is defined for QCPU ZR."),
            "RD": _unsupported("Not supported on QCPU."),
            "SM": _fixed(1024, "Fixed family limit"),
            "SD": _fixed(1024, "Fixed family limit"),
        },
    ),
    SlmpPlcProfile.LCpu: _RangeProfile(
        SlmpPlcProfile.LCpu,
        286,
        26,
        {
            "X": _word(290, "SD290"),
            "Y": _word(291, "SD291"),
            "M": _dword(286, "SD286-SD287 (32-bit)"),
            "B": _dword(288, "SD288-SD289 (32-bit)"),
            "SB": _word(296, "SD296"),
            "F": _word(295, "SD295"),
            "V": _word(297, "SD297"),
            "L": _word(293, "SD293"),
            "S": _word(298, "SD298"),
            "D": _dword(308, "SD308-SD309 (32-bit)"),
            "W": _dword(310, "SD310-SD311 (32-bit)"),
            "SW": _word(304, "SD304"),
            "R": _dword_clipped(306, 32768, "SD306-SD307 (32-bit)", "Upper bound is clipped to 32768."),
            "T": _word(299, "SD299"),
            "ST": _word(300, "SD300"),
            "C": _word(301, "SD301"),
            "LT": _unsupported("Not supported on LCPU."),
            "LST": _unsupported("Not supported on LCPU."),
            "LC": _unsupported("Not supported on LCPU."),
            "Z": _fixed(20, "Fixed family limit"),
            "LZ": _unsupported("Not supported on LCPU."),
            "ZR": _dword(306, "SD306-SD307 (32-bit)"),
            "RD": _unsupported("Not supported on LCPU."),
            "SM": _fixed(2048, "Fixed family limit"),
            "SD": _fixed(2048, "Fixed family limit"),
        },
    ),
    SlmpPlcProfile.QnU: _RangeProfile(
        SlmpPlcProfile.QnU,
        286,
        26,
        {
            "X": _word(290, "SD290"),
            "Y": _word(291, "SD291"),
            "M": _dword(286, "SD286-SD287 (32-bit)"),
            "B": _dword(288, "SD288-SD289 (32-bit)"),
            "SB": _word(296, "SD296"),
            "F": _word(295, "SD295"),
            "V": _word(297, "SD297"),
            "L": _word(293, "SD293"),
            "S": _word(298, "SD298"),
            "D": _dword(308, "SD308-SD309 (32-bit)"),
            "W": _dword(310, "SD310-SD311 (32-bit)"),
            "SW": _word(304, "SD304"),
            "R": _dword_clipped(306, 32768, "SD306-SD307 (32-bit)", "Upper bound is clipped to 32768."),
            "T": _word(299, "SD299"),
            "ST": _word(300, "SD300"),
            "C": _word(301, "SD301"),
            "LT": _unsupported("Not supported on QnU."),
            "LST": _unsupported("Not supported on QnU."),
            "LC": _unsupported("Not supported on QnU."),
            "Z": _fixed(20, "Fixed family limit"),
            "LZ": _unsupported("Not supported on QnU."),
            "ZR": _dword(306, "SD306-SD307 (32-bit)"),
            "RD": _unsupported("Not supported on QnU."),
            "SM": _fixed(2048, "Fixed family limit"),
            "SD": _fixed(2048, "Fixed family limit"),
        },
    ),
    SlmpPlcProfile.QnUDV: _RangeProfile(
        SlmpPlcProfile.QnUDV,
        286,
        26,
        {
            "X": _word(290, "SD290"),
            "Y": _word(291, "SD291"),
            "M": _dword(286, "SD286-SD287 (32-bit)"),
            "B": _dword(288, "SD288-SD289 (32-bit)"),
            "SB": _word(296, "SD296"),
            "F": _word(295, "SD295"),
            "V": _word(297, "SD297"),
            "L": _word(293, "SD293"),
            "S": _word(298, "SD298"),
            "D": _dword(308, "SD308-SD309 (32-bit)"),
            "W": _dword(310, "SD310-SD311 (32-bit)"),
            "SW": _word(304, "SD304"),
            "R": _dword_clipped(306, 32768, "SD306-SD307 (32-bit)", "Upper bound is clipped to 32768."),
            "T": _word(299, "SD299"),
            "ST": _word(300, "SD300"),
            "C": _word(301, "SD301"),
            "LT": _unsupported("Not supported on QnUDV."),
            "LST": _unsupported("Not supported on QnUDV."),
            "LC": _unsupported("Not supported on QnUDV."),
            "Z": _fixed(20, "Fixed family limit"),
            "LZ": _unsupported("Not supported on QnUDV."),
            "ZR": _dword(306, "SD306-SD307 (32-bit)"),
            "RD": _unsupported("Not supported on QnUDV."),
            "SM": _fixed(2048, "Fixed family limit"),
            "SD": _fixed(2048, "Fixed family limit"),
        },
    ),
}


def normalize_plc_profile(value: SlmpPlcProfile | str) -> SlmpPlcProfile:
    """Normalize one canonical PLC profile identifier."""

    if isinstance(value, SlmpPlcProfile):
        return value
    normalized = str(value).strip().lower()
    if normalized in _CANONICAL_FAMILIES:
        return _CANONICAL_FAMILIES[normalized]
    supported = ", ".join(sorted(_CANONICAL_FAMILIES))
    raise ValueError(f"Unsupported PLC profile {value!r}. Supported profiles: {supported}")


def plc_profile_label(plc_profile: SlmpPlcProfile | str) -> str:
    """Return the synthetic model label used for explicit PLC-profile reads."""

    normalized = normalize_plc_profile(plc_profile)
    return {
        SlmpPlcProfile.IqR: "IQ-R",
        SlmpPlcProfile.IqL: "iQ-L",
        SlmpPlcProfile.MxF: "MX-F",
        SlmpPlcProfile.MxR: "MX-R",
        SlmpPlcProfile.IqF: "IQ-F",
        SlmpPlcProfile.QCpu: "QCPU",
        SlmpPlcProfile.LCpu: "LCPU",
        SlmpPlcProfile.QnU: "QnU",
        SlmpPlcProfile.QnUDV: "QnUDV",
    }[normalized]


def build_device_range_catalog_for_plc_profile(
    plc_profile: SlmpPlcProfile | str,
    registers: Mapping[int, int],
) -> SlmpDeviceRangeCatalog:
    """Build one catalog from already-read profile SD registers."""

    normalized_profile = normalize_plc_profile(plc_profile)
    profile = _PROFILES[normalized_profile]
    entries: list[SlmpDeviceRangeEntry] = []
    for item in _ORDERED_ITEMS:
        row = _ROWS[item]
        spec = profile.rules[item]
        point_count = _evaluate_point_count(spec, registers)
        upper_bound = None if point_count is None or point_count <= 0 else point_count - 1
        supported = spec.kind is not _RangeValueKind.Unsupported
        for device, is_bit_device in row.devices:
            notation = _resolve_notation(profile.plc_profile, device, row.notation)
            entries.append(
                SlmpDeviceRangeEntry(
                    device=device,
                    category=row.category,
                    is_bit_device=is_bit_device,
                    supported=supported,
                    lower_bound=0,
                    upper_bound=upper_bound,
                    point_count=point_count,
                    address_range=_format_address_range(device, notation, upper_bound),
                    notation=notation,
                    source=spec.source,
                    notes=spec.notes,
                )
            )
    return SlmpDeviceRangeCatalog(
        model=plc_profile_label(normalized_profile),
        model_code=0,
        has_model_code=False,
        plc_profile=normalized_profile,
        entries=entries,
    )


def read_device_range_catalog_for_plc_profile_sync(
    client: Any,
    plc_profile: SlmpPlcProfile | str,
) -> SlmpDeviceRangeCatalog:
    """Read one canonical profile SD window in a single request and build a catalog."""

    normalized_profile = normalize_plc_profile(plc_profile)
    profile = _PROFILES[normalized_profile]
    words = cast(
        list[int],
        client.read_devices(DeviceRef("SD", profile.register_start), profile.register_count, bit_unit=False),
    )
    registers = {profile.register_start + index: int(value) for index, value in enumerate(words)}
    catalog = build_device_range_catalog_for_plc_profile(normalized_profile, registers)
    return _resolve_runtime_limits_sync(client, catalog)


async def read_device_range_catalog_for_plc_profile(
    client: Any,
    plc_profile: SlmpPlcProfile | str,
) -> SlmpDeviceRangeCatalog:
    """Async variant of the canonical explicit-profile device-range catalog read."""

    normalized_profile = normalize_plc_profile(plc_profile)
    profile = _PROFILES[normalized_profile]
    words = cast(
        list[int],
        await client.read_devices(DeviceRef("SD", profile.register_start), profile.register_count, bit_unit=False),
    )
    registers = {profile.register_start + index: int(value) for index, value in enumerate(words)}
    catalog = build_device_range_catalog_for_plc_profile(normalized_profile, registers)
    return await _resolve_runtime_limits_async(client, catalog)


def _resolve_runtime_limits_sync(client: Any, catalog: SlmpDeviceRangeCatalog) -> SlmpDeviceRangeCatalog:
    if catalog.plc_profile not in _ZR_RUNTIME_FAMILIES:
        return catalog

    if catalog.plc_profile is SlmpPlcProfile.QCpu:
        z_count = 16 if _can_read_one_word_sync(client, "Z15") else 10
        catalog = _replace_fixed_point_count(
            catalog,
            "Z",
            z_count,
            "Runtime access check",
            "QCPU Z register count is selected by probing Z15.",
        )

    zr_count = _resolve_readable_point_count_sync(client, "ZR")
    catalog = _replace_fixed_point_count(
        catalog,
        "ZR",
        zr_count,
        "Runtime access check",
        "ZR register count is selected by probing readable ZR addresses.",
    )
    return _replace_fixed_point_count(
        catalog,
        "R",
        min(zr_count, 32768),
        "Runtime access check",
        "R register count follows the probed ZR count and is capped at R32767.",
    )


async def _resolve_runtime_limits_async(client: Any, catalog: SlmpDeviceRangeCatalog) -> SlmpDeviceRangeCatalog:
    if catalog.plc_profile not in _ZR_RUNTIME_FAMILIES:
        return catalog

    if catalog.plc_profile is SlmpPlcProfile.QCpu:
        z_count = 16 if await _can_read_one_word_async(client, "Z15") else 10
        catalog = _replace_fixed_point_count(
            catalog,
            "Z",
            z_count,
            "Runtime access check",
            "QCPU Z register count is selected by probing Z15.",
        )

    zr_count = await _resolve_readable_point_count_async(client, "ZR")
    catalog = _replace_fixed_point_count(
        catalog,
        "ZR",
        zr_count,
        "Runtime access check",
        "ZR register count is selected by probing readable ZR addresses.",
    )
    return _replace_fixed_point_count(
        catalog,
        "R",
        min(zr_count, 32768),
        "Runtime access check",
        "R register count follows the probed ZR count and is capped at R32767.",
    )


def _resolve_readable_point_count_sync(client: Any, device: str) -> int:
    if not _can_read_one_word_sync(client, f"{device}0"):
        return 0

    upper_limit = _MAX_RUNTIME_RANGE_PROBE_COUNT - 1
    low = 0
    high = 1
    while high < upper_limit and _can_read_one_word_sync(client, f"{device}{high}"):
        low = high
        high = min(upper_limit, (high * 2) + 1)

    if high == upper_limit and _can_read_one_word_sync(client, f"{device}{high}"):
        return _MAX_RUNTIME_RANGE_PROBE_COUNT

    left = low + 1
    right = high - 1
    while left <= right:
        mid = left + ((right - left) // 2)
        if _can_read_one_word_sync(client, f"{device}{mid}"):
            low = mid
            left = mid + 1
        else:
            right = mid - 1

    return low + 1


async def _resolve_readable_point_count_async(client: Any, device: str) -> int:
    if not await _can_read_one_word_async(client, f"{device}0"):
        return 0

    upper_limit = _MAX_RUNTIME_RANGE_PROBE_COUNT - 1
    low = 0
    high = 1
    while high < upper_limit and await _can_read_one_word_async(client, f"{device}{high}"):
        low = high
        high = min(upper_limit, (high * 2) + 1)

    if high == upper_limit and await _can_read_one_word_async(client, f"{device}{high}"):
        return _MAX_RUNTIME_RANGE_PROBE_COUNT

    left = low + 1
    right = high - 1
    while left <= right:
        mid = left + ((right - left) // 2)
        if await _can_read_one_word_async(client, f"{device}{mid}"):
            low = mid
            left = mid + 1
        else:
            right = mid - 1

    return low + 1


def _can_read_one_word_sync(client: Any, address: str) -> bool:
    try:
        client.read_devices(address, 1, bit_unit=False)
        return True
    except SlmpError:
        return False


async def _can_read_one_word_async(client: Any, address: str) -> bool:
    try:
        await client.read_devices(address, 1, bit_unit=False)
        return True
    except SlmpError:
        return False


def _replace_fixed_point_count(
    catalog: SlmpDeviceRangeCatalog,
    device: str,
    point_count: int,
    source: str,
    note: str,
) -> SlmpDeviceRangeCatalog:
    upper_bound = None if point_count <= 0 else point_count - 1
    entries = [
        replace(
            entry,
            upper_bound=upper_bound,
            point_count=point_count,
            address_range=_format_address_range(entry.device, entry.notation, upper_bound),
            source=source,
            notes=note if not entry.notes else f"{entry.notes} {note}",
        )
        if entry.device == device
        else entry
        for entry in catalog.entries
    ]
    return replace(catalog, entries=entries)


def _evaluate_point_count(spec: _RangeValueSpec, registers: Mapping[int, int]) -> int | None:
    if spec.kind in {_RangeValueKind.Unsupported, _RangeValueKind.Undefined}:
        return None
    if spec.kind is _RangeValueKind.Fixed:
        return spec.fixed_value
    if spec.kind is _RangeValueKind.WordRegister:
        return _read_word(registers, spec.register)
    if spec.kind is _RangeValueKind.DWordRegister:
        return _read_dword(registers, spec.register)
    if spec.kind is _RangeValueKind.WordRegisterClipped:
        return min(_read_word(registers, spec.register), spec.clip_value)
    if spec.kind is _RangeValueKind.DWordRegisterClipped:
        return min(_read_dword(registers, spec.register), spec.clip_value)
    raise AssertionError(f"Unhandled range kind: {spec.kind}")


def _read_word(registers: Mapping[int, int], register: int) -> int:
    if register not in registers:
        raise SlmpError(f"Device-range resolver is missing SD{register}.")
    return int(registers[register]) & 0xFFFF


def _read_dword(registers: Mapping[int, int], register: int) -> int:
    low = _read_word(registers, register)
    high = _read_word(registers, register + 1)
    return low | (high << 16)


def _resolve_notation(
    plc_profile: SlmpPlcProfile,
    device: str,
    default_notation: SlmpDeviceRangeNotation,
) -> SlmpDeviceRangeNotation:
    if plc_profile is SlmpPlcProfile.IqF and device in {"X", "Y"}:
        return SlmpDeviceRangeNotation.Base8
    return default_notation


def _format_address_range(
    device: str,
    notation: SlmpDeviceRangeNotation,
    upper_bound: int | None,
) -> str | None:
    if upper_bound is None:
        return None
    if notation is SlmpDeviceRangeNotation.Base10:
        return f"{device}0-{device}{upper_bound}"
    if notation is SlmpDeviceRangeNotation.Base8:
        width = max(3, len(f"{upper_bound:o}"))
        return f"{device}{0:0{width}o}-{device}{upper_bound:0{width}o}"
    width = max(3, len(f"{upper_bound:X}"))
    return f"{device}{0:0{width}X}-{device}{upper_bound:0{width}X}"
