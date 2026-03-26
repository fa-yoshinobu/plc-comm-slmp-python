"""Command-line entry points for the SLMP 4E binary library."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import threading
import time
import warnings
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from .client import SlmpClient
from .constants import (
    DEVICE_CODES,
    DIRECT_MEMORY_CPU_BUFFER,
    DIRECT_MEMORY_LINK_DIRECT,
    DIRECT_MEMORY_MODULE_ACCESS,
    Command,
    FrameType,
    ModuleIONo,
    PLCSeries,
)
from .core import (
    DeviceRef,
    ExtensionSpec,
    LabelArrayReadPoint,
    LabelArrayReadResult,
    LabelArrayWritePoint,
    LabelRandomReadResult,
    LabelRandomWritePoint,
    SlmpTarget,
    SlmpTraceFrame,
    TypeNameInfo,
    decode_device_words,
    encode_device_spec,
    pack_bit_values,
    parse_device,
    resolve_device_subcommand,
    unpack_bit_values,
)
from .errors import SlmpPracticalPathWarning


def _int_auto(text: str) -> int:
    return int(text, 0)


def _format_model_code(value: int | None) -> str:
    if isinstance(value, int):
        return f"0x{value:04X} ({value})"
    return "N/A"


TYPE_NAME_LABELS: dict[int, str] = {
    0x026C: "Q26UDHCPU, Q26UDEHCPU",
    0x026A: "Q06UDHCPU, Q06UDEHCPU",
    0x026B: "Q13UDHCPU, Q13UDEHCPU",
    0x0267: "Q20UDHCPU, Q20UDEHCPU",
    0x0268: "Q03UDCPU, Q03UDECPU",
    0x0269: "Q04UDHCPU, Q04UDEHCPU",
    0x026D: "Q50UDEHCPU",
    0x026E: "Q100UDEHCPU",
    0x0230: "QS001CPU",
    0x0641: "LJ72GF15-T2",
    0x0642: "NZ2GF-ETB",
    0x0260: "Q00UJCPU",
    0x0261: "Q00UCPU",
    0x0262: "Q01UCPU",
    0x0263: "Q02UCPU",
    0x0366: "Q03UDVCPU",
    0x0367: "Q04UDVCPU, Q04UDPVCPU",
    0x0368: "Q06UDVCPU, Q06UDPVCPU",
    0x036A: "Q13UDVCPU, Q13UDPVCPU",
    0x036C: "Q26UDVCPU, Q26UDPVCPU",
    0x4801: "R08CPU",
    0x4804: "R120CPU",
    0x4844: "R120PCPU",
}


SERIES_BY_MODEL_CODE: dict[int, PLCSeries] = {
    0x0041: PLCSeries.QL,
    0x0042: PLCSeries.QL,
    0x0043: PLCSeries.QL,
    0x0044: PLCSeries.QL,
    0x004B: PLCSeries.QL,
    0x004C: PLCSeries.QL,
    0x0230: PLCSeries.QL,
    0x0260: PLCSeries.QL,
    0x0261: PLCSeries.QL,
    0x0262: PLCSeries.QL,
    0x0263: PLCSeries.QL,
    0x0267: PLCSeries.QL,
    0x0268: PLCSeries.QL,
    0x0269: PLCSeries.QL,
    0x026A: PLCSeries.QL,
    0x026B: PLCSeries.QL,
    0x026C: PLCSeries.QL,
    0x026D: PLCSeries.QL,
    0x026E: PLCSeries.QL,
    0x0366: PLCSeries.QL,
    0x0367: PLCSeries.QL,
    0x0368: PLCSeries.QL,
    0x036A: PLCSeries.QL,
    0x036C: PLCSeries.QL,
    0x04800: PLCSeries.IQR,
    0x04801: PLCSeries.IQR,
    0x04802: PLCSeries.IQR,
    0x04803: PLCSeries.IQR,
    0x04804: PLCSeries.IQR,
    0x04805: PLCSeries.IQR,
    0x04806: PLCSeries.IQR,
    0x04807: PLCSeries.IQR,
    0x04808: PLCSeries.IQR,
    0x04809: PLCSeries.IQR,
    0x04820: PLCSeries.IQR,
    0x04841: PLCSeries.IQR,
    0x04842: PLCSeries.IQR,
    0x04843: PLCSeries.IQR,
    0x04844: PLCSeries.IQR,
    0x04851: PLCSeries.IQR,
    0x04852: PLCSeries.IQR,
    0x04853: PLCSeries.IQR,
    0x04854: PLCSeries.IQR,
    0x04860: PLCSeries.IQR,
    0x04861: PLCSeries.IQR,
    0x04862: PLCSeries.IQR,
    0x04891: PLCSeries.IQR,
    0x04892: PLCSeries.IQR,
    0x04893: PLCSeries.IQR,
    0x04894: PLCSeries.IQR,
    0x048A0: PLCSeries.IQR,
    0x048A1: PLCSeries.IQR,
    0x048A2: PLCSeries.IQR,
    0x048E9: PLCSeries.IQR,
    0x048EA: PLCSeries.IQR,
    0x048EB: PLCSeries.IQR,
    0x048EE: PLCSeries.IQR,
    0x048EF: PLCSeries.IQR,
    0x04E01: PLCSeries.IQR,
    0x0641: PLCSeries.IQR,
    0x0642: PLCSeries.IQR,
}


def _resolve_type_name_label(info: TypeNameInfo) -> str:
    if isinstance(info.model_code, int):
        label = TYPE_NAME_LABELS.get(info.model_code)
        if label:
            return label
    if info.model:
        return info.model
    if isinstance(info.model_code, int):
        return f"code_{info.model_code:04X}"
    return "unknown_target"


def _resolve_series_from_type_name(info: TypeNameInfo) -> PLCSeries | None:
    if isinstance(info.model_code, int):
        series = SERIES_BY_MODEL_CODE.get(info.model_code)
        if series is not None:
            return series
    model = info.model.strip().upper()
    if not model:
        return None
    if model.startswith(("Q", "L", "FX", "QS")):
        return PLCSeries.QL
    if model.startswith(("R", "RJ", "MI", "MXR", "NZ")):
        return PLCSeries.IQR
    return None


def _resolve_extended_device_targets(values: list[str] | None) -> list[str]:
    if not values:
        return []
    lowered = [v.lower() for v in values]
    if "all" in lowered:
        return ["j", "u", "cpu"]
    order = ["j", "u", "cpu"]
    return [name for name in order if name in lowered]


def _write_markdown_report(
    output: str,
    *,
    title: str,
    header_lines: Sequence[str],
    rows: Sequence[tuple[str, str, str]],
) -> None:
    lines = [title, ""]
    lines.extend(header_lines)
    lines.extend(["", "| Item | Status | Detail |", "|---|---|---|"])
    for item, status, detail in rows:
        lines.append(f"| {item} | {status} | {detail} |")
    _write_text_report(output, "\n".join(lines) + "\n")


def _archive_report_path(output: Path) -> Path | None:
    suffix = output.suffix.lower()
    if suffix not in {".md", ".json"}:
        return None
    if not output.name.endswith(f"_latest{suffix}"):
        return None
    archive_dir = output.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stem = output.stem.removesuffix("_latest")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return archive_dir / f"{stem}_{timestamp}{output.suffix}"


def _write_text_report(output: str | Path, content: str) -> None:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    archive_path = _archive_report_path(out)
    if archive_path is not None:
        archive_path.write_text(content, encoding="utf-8")


def _write_json_report(output: str | Path, data: object) -> None:
    _write_text_report(output, json.dumps(data, indent=2, sort_keys=True) + "\n")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _compatibility_default_output(*, plc_label: str, filename: str) -> str:
    return _default_report_output(series="compatibility", model=plc_label, filename=filename)


def _compatibility_selected_specs(
    *,
    command_codes: Sequence[str] | None,
    include_write_restore: bool,
    include_remote_control: bool,
    include_maintenance: bool,
) -> list[CompatibilityCommandSpec]:
    enabled_risks = {COMPATIBILITY_SAFE_RISK_GROUP}
    if include_write_restore:
        enabled_risks.add(COMPATIBILITY_WRITE_RESTORE_RISK_GROUP)
    if include_remote_control:
        enabled_risks.add(COMPATIBILITY_REMOTE_RISK_GROUP)
    if include_maintenance:
        enabled_risks.add(COMPATIBILITY_MAINTENANCE_RISK_GROUP)

    selected_codes = set(command_codes) if command_codes else None
    specs: list[CompatibilityCommandSpec] = []
    for spec in COMPATIBILITY_COMMAND_SPECS:
        if spec.risk_group not in enabled_risks:
            continue
        if selected_codes is not None and spec.code not in selected_codes:
            continue
        specs.append(spec)
    return specs


def _compatibility_summarize_subresults(subresults: Sequence[tuple[str, str, str]]) -> str:
    statuses = {status for _, status, _ in subresults}
    if not statuses:
        return "SKIP"
    if statuses == {"SKIP"}:
        return "SKIP"
    if "NG" in statuses and "OK" in statuses:
        return "PARTIAL"
    if "NG" in statuses and "PARTIAL" in statuses:
        return "PARTIAL"
    if "PARTIAL" in statuses:
        return "PARTIAL"
    if "OK" in statuses:
        return "OK"
    return "NG"


def _compatibility_format_subresults(subresults: Sequence[tuple[str, str, str]]) -> str:
    parts: list[str] = []
    for name, status, detail in subresults:
        if detail:
            parts.append(f"{name}={status} ({detail})")
        else:
            parts.append(f"{name}={status}")
    return "; ".join(parts)


def _compatibility_matrix_cell_status(results: Sequence[Mapping[str, object]]) -> str:
    executed_statuses = [str(row.get("status", "")).upper() for row in results if str(row.get("status", ""))]
    if not executed_statuses:
        return "PENDING"
    if all(status == "SKIP" for status in executed_statuses):
        return "PENDING"
    if any(status == "PARTIAL" for status in executed_statuses):
        return "PARTIAL"
    ok = any(status == "OK" for status in executed_statuses)
    ng = any(status == "NG" for status in executed_statuses)
    if ok and ng:
        return "PARTIAL"
    if ok:
        return "YES"
    if ng:
        return "NO"
    return "PENDING"


def _compatibility_combo_label(combo: Mapping[str, object]) -> str:
    return f"{combo.get('frame_type', '?')}/{combo.get('access_profile', '?')}"


def _compatibility_compact_detail(detail: str) -> str:
    if not detail:
        return ""
    codes = list(dict.fromkeys(re.findall(r"end_code=0x[0-9A-Fa-f]{4}", detail)))
    if codes:
        return ", ".join(f"0x{code[-4:].upper()}" for code in codes)
    lowered = detail.lower()
    if "timed out" in lowered:
        return "timed out"
    if "connection closed while receiving data" in lowered:
        return "connection closed"
    if "model=" in detail:
        model_part = detail.split(", model_code=", 1)[0]
        return model_part
    if len(detail) <= 96:
        return detail
    return detail[:93] + "..."


def _compatibility_reason_keys(detail: str) -> list[str]:
    if not detail:
        return []
    reasons: list[str] = []
    codes = list(dict.fromkeys(re.findall(r"end_code=0x[0-9A-Fa-f]{4}", detail)))
    reasons.extend(f"0x{code[-4:].upper()}" for code in codes)
    lowered = detail.lower()
    if "timed out" in lowered and "timed out" not in reasons:
        reasons.append("timed out")
    if "connection closed while receiving data" in lowered and "connection closed" not in reasons:
        reasons.append("connection closed")
    if not reasons:
        reasons.append("other")
    return reasons


def _compatibility_summarize_values(values: Sequence[str], *, max_items: int = 4) -> str:
    unique = list(dict.fromkeys(values))
    if len(unique) <= max_items:
        return ", ".join(unique)
    shown = ", ".join(unique[:max_items])
    return f"{shown}, +{len(unique) - max_items} more"


def _compatibility_command_entry(combo: Mapping[str, object], code: str) -> Mapping[str, object] | None:
    commands = combo.get("commands")
    if not isinstance(commands, list):
        return None
    for command in commands:
        if not isinstance(command, Mapping):
            continue
        if str(command.get("code", "")).upper() == code.upper():
            return command
    return None


def _compatibility_command_status(combo: Mapping[str, object], code: str) -> str | None:
    entry = _compatibility_command_entry(combo, code)
    if entry is None:
        return None
    status = str(entry.get("status", "")).upper()
    return status or None


def _compatibility_family_name(label: str) -> str:
    upper_label = label.upper()
    if upper_label.endswith("_MC") or upper_label.startswith("KV"):
        return "Third-Party MC-Compatible"
    if upper_label.startswith("RJ") or upper_label.startswith("R"):
        return "iQ-R"
    if upper_label.startswith("QJ") or upper_label.startswith("Q"):
        return "MELSEC-Q"
    if upper_label.startswith("L16H"):
        return "iQ-L"
    if upper_label.startswith("L"):
        return "MELSEC-L"
    if upper_label.startswith("FX"):
        return "iQ-F"
    return "Other"


_COMPATIBILITY_FAMILY_ORDER = (
    "iQ-R",
    "MELSEC-Q",
    "MELSEC-L",
    "iQ-L",
    "iQ-F",
    "Third-Party MC-Compatible",
    "Other",
)


def _compatibility_result_label(raw: Mapping[str, object]) -> str:
    return str(raw.get("plc_label") or raw.get("detected_model") or raw.get("host") or "unknown_target")


def _compatibility_result_sort_key(raw: Mapping[str, object]) -> tuple[int, str]:
    label = _compatibility_result_label(raw)
    family = _compatibility_family_name(label)
    try:
        family_index = _COMPATIBILITY_FAMILY_ORDER.index(family)
    except ValueError:
        family_index = len(_COMPATIBILITY_FAMILY_ORDER)
    return family_index, label.upper()


_COMPATIBILITY_COMBO_FALLBACK_ORDER = ("3e/ql", "4e/ql", "3e/iqr", "4e/iqr")


def _compatibility_default_policy_output() -> str:
    return "docs/validation/reports/compatibility_policy.json"


def _resolve_detected_family(*, label: str | None, model: str | None) -> str | None:
    candidate = model if model and model != "unknown_target" else label
    if not candidate:
        return None
    family = _compatibility_family_name(candidate)
    return None if family == "Other" else family


def _compatibility_combo_sort_key(
    combo: Mapping[str, object],
    *,
    label: str,
) -> tuple[int, int, int]:
    combo_label = _compatibility_combo_label(combo)
    ok_count = 0
    ng_count = 0
    commands = combo.get("commands")
    if isinstance(commands, list):
        for command in commands:
            if not isinstance(command, Mapping):
                continue
            status = str(command.get("status", "")).upper()
            if status == "OK":
                ok_count += 1
            elif status in {"NG", "PARTIAL"}:
                ng_count += 1
    try:
        fallback_index = _COMPATIBILITY_COMBO_FALLBACK_ORDER.index(combo_label)
    except ValueError:
        fallback_index = len(_COMPATIBILITY_COMBO_FALLBACK_ORDER)
    return (-ok_count, ng_count, fallback_index)


def _compatibility_extract_profile_preferences(
    raw: Mapping[str, object],
) -> tuple[list[str], list[dict[str, object]], list[str], str | None]:
    label = _compatibility_result_label(raw)
    combos = raw.get("results")
    combo_rows = combos if isinstance(combos, list) else []
    preferred_pairs: list[tuple[tuple[int, int, int], str]] = []
    avoid_profiles: list[dict[str, object]] = []
    seen_models: list[str] = []
    for combo in combo_rows:
        if not isinstance(combo, Mapping):
            continue
        combo_label = _compatibility_combo_label(combo)
        detected_model = combo.get("detected_model")
        if isinstance(detected_model, str) and detected_model and detected_model not in seen_models:
            seen_models.append(detected_model)
        batch_read_status = _compatibility_command_status(combo, "0401")
        if batch_read_status == "OK":
            preferred_pairs.append((_compatibility_combo_sort_key(combo, label=label), combo_label))
            continue
        if batch_read_status == "NG" or str(combo.get("connection_error", "")):
            reasons: list[str] = []
            commands = combo.get("commands")
            if isinstance(commands, list):
                for command in commands:
                    if not isinstance(command, Mapping):
                        continue
                    status = str(command.get("status", "")).upper()
                    if status in {"OK", "SKIP"}:
                        continue
                    reasons.extend(_compatibility_reason_keys(str(command.get("detail", ""))))
            avoid_profiles.append(
                {
                    "combo": combo_label,
                    "reasons": list(dict.fromkeys(reasons)),
                }
            )
    preferred_profiles = [combo for _, combo in sorted(preferred_pairs, key=lambda item: item[0])]
    detected_model = next((model for model in seen_models if model != "unknown_target"), None)
    return preferred_profiles, avoid_profiles, seen_models, detected_model


def _build_compatibility_policy(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    family_weights: dict[str, Counter[str]] = {}
    global_weights: Counter[str] = Counter()
    labels_payload: dict[str, object] = {}
    models_payload: dict[str, object] = {}
    for raw in sorted(results, key=_compatibility_result_sort_key):
        label = _compatibility_result_label(raw)
        preferred_profiles, avoid_profiles, seen_models, detected_model = _compatibility_extract_profile_preferences(
            raw
        )
        family = _resolve_detected_family(label=label, model=detected_model) or _compatibility_family_name(label)
        labels_payload[label] = {
            "family": family,
            "preferred_profiles": preferred_profiles,
            "avoid_profiles": avoid_profiles,
            "detected_models": seen_models,
        }
        for rank, combo in enumerate(preferred_profiles):
            weight = len(preferred_profiles) - rank
            global_weights[combo] += weight
            family_weights.setdefault(family, Counter())[combo] += weight
        for model in seen_models:
            if model == "unknown_target":
                continue
            entry = cast(
                dict[str, object],
                models_payload.setdefault(
                    model,
                    {"family": family, "preferred_profiles": [], "sources": []},
                ),
            )
            preferred_entry = cast(list[str], entry["preferred_profiles"])
            sources_entry = cast(list[str], entry["sources"])
            if not preferred_entry and preferred_profiles:
                entry["preferred_profiles"] = list(preferred_profiles)
                preferred_entry = cast(list[str], entry["preferred_profiles"])
            if label not in sources_entry:
                sources_entry.append(label)

    def _ordered_combos(counter: Counter[str]) -> list[str]:
        ordered = [
            combo
            for combo, _ in sorted(
                counter.items(),
                key=lambda item: (-item[1], _COMPATIBILITY_COMBO_FALLBACK_ORDER.index(item[0])),
            )
        ]
        for combo in _COMPATIBILITY_COMBO_FALLBACK_ORDER:
            if combo not in ordered:
                ordered.append(combo)
        return ordered

    families_payload = {
        family: {"preferred_profiles": _ordered_combos(counter)} for family, counter in family_weights.items()
    }
    return {
        "schema_version": 1,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "combo_fallback_order": list(_COMPATIBILITY_COMBO_FALLBACK_ORDER),
        "global": {"preferred_profiles": _ordered_combos(global_weights)},
        "families": families_payload,
        "labels": labels_payload,
        "models": models_payload,
    }


def _load_compatibility_policy(policy_path: str | None) -> Mapping[str, object] | None:
    path = Path(policy_path) if policy_path else Path(_compatibility_default_policy_output())
    if not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, Mapping) else None


def _policy_preferred_profiles(
    policy: Mapping[str, object] | None,
    *,
    label: str | None = None,
    model: str | None = None,
    family: str | None = None,
) -> list[str]:
    if policy is None:
        return list(_COMPATIBILITY_COMBO_FALLBACK_ORDER)

    def _profiles_from_entry(entry: object) -> list[str]:
        if not isinstance(entry, Mapping):
            return []
        profiles = entry.get("preferred_profiles")
        if not isinstance(profiles, list):
            return []
        return [str(item) for item in profiles if isinstance(item, str)]

    if label:
        labels = policy.get("labels")
        if isinstance(labels, Mapping) and label in labels:
            profiles = _profiles_from_entry(labels[label])
            if profiles:
                return profiles
    if model:
        models = policy.get("models")
        if isinstance(models, Mapping) and model in models:
            profiles = _profiles_from_entry(models[model])
            if profiles:
                return profiles
    if family:
        families = policy.get("families")
        if isinstance(families, Mapping) and family in families:
            profiles = _profiles_from_entry(families[family])
            if profiles:
                return profiles
    global_entry = policy.get("global")
    profiles = _profiles_from_entry(global_entry)
    if profiles:
        return profiles
    return list(_COMPATIBILITY_COMBO_FALLBACK_ORDER)


def _policy_candidate_pairs(
    *,
    requested_frame_type: str,
    requested_series: str,
    policy: Mapping[str, object] | None,
    label: str | None = None,
    model: str | None = None,
    family: str | None = None,
) -> list[tuple[FrameType, PLCSeries]]:
    allowed_frames = (
        [FrameType(args) for args in ("3e", "4e")]
        if requested_frame_type == "auto"
        else [FrameType(requested_frame_type)]
    )
    allowed_series = [PLCSeries.QL, PLCSeries.IQR] if requested_series == "auto" else [PLCSeries(requested_series)]
    allowed = {(frame.value, series.value): (frame, series) for frame in allowed_frames for series in allowed_series}
    ordered: list[tuple[FrameType, PLCSeries]] = []
    for combo in _policy_preferred_profiles(policy, label=label, model=model, family=family):
        frame_text, series_text = combo.split("/", 1)
        pair = allowed.get((frame_text, series_text))
        if pair is not None and pair not in ordered:
            ordered.append(pair)
    for combo in _COMPATIBILITY_COMBO_FALLBACK_ORDER:
        frame_text, series_text = combo.split("/", 1)
        pair = allowed.get((frame_text, series_text))
        if pair is not None and pair not in ordered:
            ordered.append(pair)
    return ordered


def _format_candidate_pairs(pairs: Sequence[tuple[FrameType, PLCSeries]]) -> str:
    return ", ".join(f"{frame_type.value}/{series.value}" for frame_type, series in pairs)


def _compatibility_endpoint_note(label: str, detected_models: Sequence[str]) -> str | None:
    upper_label = label.upper()
    if upper_label.startswith("RJ71EN71") or upper_label.startswith("QJ71E71"):
        return "Ethernet module endpoint; `0101` reflects the attached CPU path rather than the module part number."
    if upper_label.endswith("_MC") or upper_label.startswith("KV"):
        return "Third-party MC-compatible endpoint; results describe MC compatibility, not Mitsubishi native identity."
    if not detected_models:
        return "No stable type-name identity was returned; the operator label is the only endpoint identifier here."
    if all(model == "unknown_target" for model in detected_models):
        return "No stable type-name identity was returned; the operator label is the only endpoint identifier here."
    return None


def _render_compatibility_matrix_markdown(
    results: Sequence[Mapping[str, object]],
    *,
    source_paths: Sequence[Path],
    omit_pending_columns: bool = False,
) -> str:
    labels: list[str] = []
    cells: dict[tuple[str, str], str] = {}
    row_models: dict[str, str] = {}
    notes: list[str] = []
    reason_buckets: dict[str, list[tuple[str, str, str]]] = {}
    preferred_lines: list[str] = []
    avoid_lines: list[str] = []
    family_members: dict[str, list[str]] = {}
    family_preferred: dict[str, list[str]] = {}
    family_avoid_reasons: dict[str, list[str]] = {}
    family_notes: dict[str, list[str]] = {}
    issue_sections: list[str] = []

    for raw in sorted(results, key=_compatibility_result_sort_key):
        label = _compatibility_result_label(raw)
        labels.append(label)
        combos = raw.get("results")
        combo_rows = combos if isinstance(combos, list) else []
        by_code: dict[str, list[Mapping[str, object]]] = {}
        seen_combo_labels: list[str] = []
        seen_models: list[str] = []
        combo_map: dict[str, Mapping[str, object]] = {}
        for combo in combo_rows:
            if not isinstance(combo, Mapping):
                continue
            combo_label = _compatibility_combo_label(combo)
            seen_combo_labels.append(combo_label)
            combo_map[combo_label] = combo
            detected_model = combo.get("detected_model")
            if isinstance(detected_model, str) and detected_model and detected_model not in seen_models:
                seen_models.append(detected_model)
            commands = combo.get("commands")
            if not isinstance(commands, list):
                continue
            for command in commands:
                if not isinstance(command, Mapping):
                    continue
                code = str(command.get("code", "")).upper()
                if not code:
                    continue
                by_code.setdefault(code, []).append(command)
        for spec in COMPATIBILITY_COMMAND_SPECS:
            cells[(spec.code, label)] = _compatibility_matrix_cell_status(by_code.get(spec.code, []))
        combo_note = ", ".join(sorted(dict.fromkeys(seen_combo_labels)))
        model_note = ", ".join(seen_models) if seen_models else "unknown_target"
        row_models[label] = model_note
        endpoint_note = _compatibility_endpoint_note(label, seen_models)
        preferred_combos: list[str] = []
        avoid_combos: list[str] = []
        preferred_limit_codes: list[str] = []
        avoid_reason_values: list[str] = []
        for combo_label in seen_combo_labels:
            combo = combo_map.get(combo_label)
            if combo is None:
                continue
            batch_read_status = _compatibility_command_status(combo, "0401")
            if batch_read_status == "OK":
                preferred_combos.append(combo_label)
            elif batch_read_status == "NG" or str(combo.get("connection_error", "")):
                avoid_combos.append(combo_label)
            if combo_label in preferred_combos:
                for limit_code in ("0101", "0403", "0801", "0802", "0406", "0619", "0613"):
                    status = _compatibility_command_status(combo, limit_code)
                    if status in {"NG", "PARTIAL"} and limit_code not in preferred_limit_codes:
                        preferred_limit_codes.append(limit_code)
            if combo_label in avoid_combos:
                commands = combo.get("commands")
                if not isinstance(commands, list):
                    continue
                for command in commands:
                    if not isinstance(command, Mapping):
                        continue
                    status = str(command.get("status", "")).upper()
                    if status in {"OK", "SKIP"}:
                        continue
                    avoid_reason_values.extend(_compatibility_reason_keys(str(command.get("detail", ""))))
        if endpoint_note is None:
            notes.append(f"- `{label}`: combos={combo_note or 'none'}, detected_model={model_note}")
        else:
            notes.append(
                f"- `{label}`: combos={combo_note or 'none'}, detected_model={model_note}; note={endpoint_note}"
            )
        if preferred_combos:
            preferred_line = f"- `{label}`: prefer {', '.join(preferred_combos)}"
            if preferred_limit_codes:
                preferred_line += f"; limits={', '.join(preferred_limit_codes)}"
            preferred_lines.append(preferred_line)
        else:
            preferred_lines.append(f"- `{label}`: no clearly preferred profile from the current probe set")
        if avoid_combos:
            summarized_reasons = _compatibility_summarize_values(avoid_reason_values, max_items=4)
            avoid_lines.append(f"- `{label}`: avoid {', '.join(avoid_combos)}; reasons={summarized_reasons}")
        family = _compatibility_family_name(label)
        family_members.setdefault(family, []).append(label)
        family_preferred.setdefault(family, []).extend(preferred_combos)
        family_avoid_reasons.setdefault(family, []).extend(avoid_reason_values)
        if endpoint_note is not None:
            family_notes.setdefault(family, []).append(endpoint_note)

        issue_lines: list[str] = []
        for spec in COMPATIBILITY_COMMAND_SPECS:
            cell_status = cells[(spec.code, label)]
            if cell_status not in {"PARTIAL", "NO"}:
                continue
            combo_summaries: list[str] = []
            for combo_label in seen_combo_labels:
                combo = combo_map.get(combo_label)
                if combo is None:
                    continue
                commands = combo.get("commands")
                if not isinstance(commands, list):
                    continue
                for command in commands:
                    if not isinstance(command, Mapping):
                        continue
                    if str(command.get("code", "")).upper() != spec.code:
                        continue
                    status = str(command.get("status", "")).upper() or "UNKNOWN"
                    if status not in {"OK", "SKIP"}:
                        for reason in _compatibility_reason_keys(str(command.get("detail", ""))):
                            reason_buckets.setdefault(reason, []).append((label, spec.code, combo_label))
                    if status == "OK":
                        combo_summaries.append(f"{combo_label}=OK")
                        break
                    detail = _compatibility_compact_detail(str(command.get("detail", "")))
                    if detail:
                        combo_summaries.append(f"{combo_label}={status} ({detail})")
                    else:
                        combo_summaries.append(f"{combo_label}={status}")
                    break
            if combo_summaries:
                issue_lines.append(f"- `{spec.code} {spec.name}`: {'; '.join(combo_summaries)}")
        if issue_lines:
            issue_sections.extend(["", f"### {label}", ""])
            issue_sections.extend(issue_lines)

    source_line = ", ".join(f"`{path.as_posix()}`" for path in source_paths)
    visible_specs = list(COMPATIBILITY_COMMAND_SPECS)
    if omit_pending_columns:
        visible_specs = [
            spec
            for spec in COMPATIBILITY_COMMAND_SPECS
            if any(cells.get((spec.code, label), "PENDING") != "PENDING" for label in labels)
        ]
    lines = [
        "# SLMP PLC Compatibility Database (Generated)",
        "",
        "This document is generated from structured compatibility probe results.",
        "",
        f"- Source probe files: {source_line}",
        f"- Omit all-PENDING columns: {'yes' if omit_pending_columns else 'no'}",
        "",
        "## 1. Protocol Capability Matrix",
        "",
        f"| PLC | Detected Model | {' | '.join(f'**{spec.code}**' for spec in visible_specs)} |",
        f"|:---|:---|{'|'.join(':---:' for _ in visible_specs)}|",
    ]
    for label in labels:
        row = [cells.get((spec.code, label), "PENDING") for spec in visible_specs]
        lines.append(f"| {label} | {row_models.get(label, 'unknown_target')} | {' | '.join(row)} |")

    lines.extend(
        [
            "",
            "### Command Legend",
            "",
            "| Code | Name |",
            "|:---:|:---|",
        ]
    )
    for spec in visible_specs:
        lines.append(f"| **{spec.code}** | {spec.name} |")

    lines.extend(
        [
            "",
            (
                "Status legend: `YES` = every executed probe for that command succeeded, "
                "`PARTIAL` = mixed outcomes across combinations or subprobes, `NO` = "
                "executed but no successful probe, `PENDING` = not executed."
            ),
            "",
            "## 2. Probe Coverage Notes",
            "",
        ]
    )
    lines.extend(notes or ["- No probe results were provided."])
    lines.extend(
        [
            "",
            "## 3. Aggregated Non-OK Reasons",
            "",
        ]
    )
    if reason_buckets:
        lines.extend(
            [
                "| Reason | Count | PLCs | Commands | Combos |",
                "|:---|---:|:---|:---|:---|",
            ]
        )
        for reason, entries in sorted(reason_buckets.items(), key=lambda item: (-len(item[1]), item[0])):
            plc_values = _compatibility_summarize_values([label for label, _, _ in entries])
            command_values = _compatibility_summarize_values([code for _, code, _ in entries], max_items=6)
            combo_values = _compatibility_summarize_values([combo for _, _, combo in entries], max_items=6)
            lines.append(f"| {reason} | {len(entries)} | {plc_values} | {command_values} | {combo_values} |")
    else:
        lines.append("- No non-OK reasons were observed.")
    lines.extend(
        [
            "",
            "## 4. Practical Recommended Profiles",
            "",
        ]
    )
    lines.extend(preferred_lines or ["- No preferred profiles could be derived."])
    lines.extend(
        [
            "",
            "## 5. Non-Recommended Combinations",
            "",
        ]
    )
    lines.extend(avoid_lines or ["- No clearly non-recommended combinations were identified from `0401` outcomes."])
    lines.extend(
        [
            "",
            "## 6. Product-Family Conclusions",
            "",
        ]
    )
    for family in ("iQ-R", "MELSEC-Q", "MELSEC-L", "iQ-L", "iQ-F", "Third-Party MC-Compatible", "Other"):
        members = family_members.get(family)
        if not members:
            continue
        preferred_summary = _compatibility_summarize_values(family_preferred.get(family, []), max_items=6)
        reason_summary = _compatibility_summarize_values(family_avoid_reasons.get(family, []), max_items=4)
        note_summary = _compatibility_summarize_values(family_notes.get(family, []), max_items=2)
        line = f"- `{family}`: members={', '.join(members)}"
        if preferred_summary:
            line += f"; preferred_profiles={preferred_summary}"
        if reason_summary:
            line += f"; common_non_ok_reasons={reason_summary}"
        if note_summary:
            line += f"; notes={note_summary}"
        lines.append(line)
    lines.extend(
        [
            "",
            "## 7. Detailed PARTIAL or NO Breakdown",
            "",
        ]
    )
    if issue_sections:
        lines.extend(issue_sections)
    else:
        lines.append("- All executed command probes were fully successful.")
    return "\n".join(lines) + "\n"


def _default_regression_help_scripts() -> tuple[str, ...]:
    return (
        "slmp_connection_check.py",
        "slmp_compatibility_probe.py",
        "slmp_compatibility_matrix_render.py",
        "slmp_device_range_probe.py",
        "slmp_register_boundary_probe.py",
        "slmp_device_access_matrix_sync.py",
        "slmp_init_model_docs.py",
        "slmp_other_station_check.py",
        "slmp_open_items_recheck.py",
        "slmp_pending_live_verification.py",
        "slmp_manual_write_verification.py",
        "slmp_manual_label_verification.py",
        "slmp_supported_device_rw_probe.py",
        "slmp_special_device_probe.py",
        "slmp_read_soak.py",
        "slmp_mixed_read_load.py",
        "slmp_tcp_concurrency.py",
        "slmp_extended_device_device_recheck.py",
        "slmp_g_hg_extended_device_recheck.py",
        "slmp_g_hg_extended_device_coverage.py",
        "slmp_mixed_block_compare.py",
    )


def _build_regression_steps(
    *,
    python_executable: str,
    include_unit_tests: bool,
    include_ruff: bool,
    include_mypy: bool,
    include_cli_help: bool,
    include_live_connection_check: bool,
    host: str | None,
    port: int,
    transport: str,
    series: str | None,
) -> list[RegressionStep]:
    root = _project_root()
    steps: list[RegressionStep] = []
    if include_unit_tests:
        steps.append(
            RegressionStep(
                name="unit_tests",
                command=(python_executable, "-m", "unittest", "discover", "-s", "tests", "-v"),
            )
        )
    if include_ruff:
        steps.append(
            RegressionStep(
                name="ruff",
                command=(python_executable, "-m", "ruff", "check", "slmp", "tests", "scripts"),
            )
        )
    if include_mypy:
        steps.append(
            RegressionStep(
                name="mypy",
                command=(python_executable, "-m", "mypy", "slmp", "scripts"),
            )
        )
    if include_cli_help:
        for script_name in _default_regression_help_scripts():
            steps.append(
                RegressionStep(
                    name=f"cli_help:{script_name}",
                    command=(python_executable, str(root / "scripts" / script_name), "--help"),
                )
            )
    if include_live_connection_check:
        if not host or not series:
            raise ValueError("host and series are required when live connection check is enabled")
        steps.append(
            RegressionStep(
                name="live_connection_check",
                command=(
                    python_executable,
                    str(root / "scripts" / "slmp_connection_check.py"),
                    "--host",
                    host,
                    "--port",
                    str(port),
                    "--transport",
                    transport,
                    "--series",
                    series,
                ),
            )
        )
    return steps


def _run_regression_steps(
    steps: Sequence[RegressionStep],
    *,
    cwd: Path,
    fail_fast: bool,
) -> list[tuple[RegressionStep, subprocess.CompletedProcess[str], float]]:
    results: list[tuple[RegressionStep, subprocess.CompletedProcess[str], float]] = []
    for step in steps:
        print(f"[RUN] {step.name}")
        started = time.perf_counter()
        completed = subprocess.run(
            list(step.command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        duration = time.perf_counter() - started
        status = "PASS" if completed.returncode == 0 else "FAIL"
        print(f"[{status}] {step.name} rc={completed.returncode} elapsed={duration:.2f}s")
        results.append((step, completed, duration))
        if completed.returncode != 0 and fail_fast:
            break
    return results


def _write_regression_report(
    output: str | Path,
    *,
    steps: Sequence[RegressionStep],
    results: Sequence[tuple[RegressionStep, subprocess.CompletedProcess[str], float]],
    python_executable: str,
    fail_fast: bool,
    include_live_connection_check: bool,
) -> None:
    result_map = {step.name: (completed, duration) for step, completed, duration in results}
    lines = [
        "# Regression Suite Report",
        "",
        f"- Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"- Python: `{python_executable}`",
        f"- Working directory: `{_project_root()}`",
        f"- Fail fast: {fail_fast}",
        f"- Live connection check enabled: {include_live_connection_check}",
        "",
        "| Step | Status | Detail |",
        "|---|---|---|",
    ]
    for step in steps:
        outcome = result_map.get(step.name)
        if outcome is None:
            lines.append(f"| {step.name} | SKIP | not started because a previous step failed |")
            continue
        completed, duration = outcome
        status = "PASS" if completed.returncode == 0 else "FAIL"
        detail = f"rc={completed.returncode}; elapsed={duration:.2f}s; command=`{' '.join(step.command)}`"
        lines.append(f"| {step.name} | {status} | {detail} |")
    lines.extend(["", "## Captured Output", ""])
    for step in steps:
        outcome = result_map.get(step.name)
        if outcome is None:
            continue
        completed, _duration = outcome
        lines.append(f"### {step.name}")
        lines.append("")
        lines.append("Command:")
        lines.append("")
        lines.append("```text")
        lines.append(" ".join(step.command))
        lines.append("```")
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if stdout:
            lines.append("")
            lines.append("stdout:")
            lines.append("")
            lines.append("```text")
            lines.append(stdout)
            lines.append("```")
        if stderr:
            lines.append("")
            lines.append("stderr:")
            lines.append("")
            lines.append("```text")
            lines.append(stderr)
            lines.append("```")
        if not stdout and not stderr:
            lines.append("")
            lines.append("No captured output.")
        lines.append("")
    _write_text_report(output, "\n".join(lines))


@dataclass(frozen=True)
class NamedTarget:
    """A target PLC station with a display name."""

    name: str
    target: SlmpTarget


@dataclass(frozen=True)
class BoundarySpec:
    """Specifications for a device range boundary check."""

    label: str
    last_device: str
    bit_unit: bool
    span_points: int = 1


@dataclass(frozen=True)
class FocusedBoundarySpec:
    """Specifications for a focused device boundary check."""

    label: str
    edge_device: str
    bit_unit: bool
    edge_points: tuple[int, ...]
    next_points: tuple[int, ...]


@dataclass(frozen=True)
class RegressionStep:
    """A single step in a regression suite."""

    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class CompatibilityCommandSpec:
    """Specification for a command used in compatibility probing."""

    code: str
    category: str
    name: str
    risk_group: str


@dataclass(frozen=True)
class ExtendedDeviceWordProbeSpec:
    """Specification for an Extended Device word-device probe."""

    label: str
    device: str
    preferred_write_value: int
    direct_memory_specification: int


@dataclass(frozen=True)
class DeviceMatrixRow:
    """A row in the device access matrix."""

    device_code: str
    device: str
    kind: str
    unsupported: str
    read: str
    write: str
    note: str
    manual_write: str = ""
    manual_write_note: str = ""


@dataclass(frozen=True)
class LatencySummary:
    """Summary statistics for request latency."""

    count: int
    avg_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    elapsed_s: float
    rate_per_s: float


DEFAULT_FOCUSED_BOUNDARY_SPECS: tuple[FocusedBoundarySpec, ...] = (
    FocusedBoundarySpec("Z", "Z19", False, (1, 2), (1,)),
    FocusedBoundarySpec("LZ", "LZ1", False, (1, 2), (1, 2)),
    FocusedBoundarySpec("R", "R32767", False, (1, 2, 16, 64), (1, 2, 16)),
    FocusedBoundarySpec("ZR", "ZR163839", False, (1, 2, 3, 16, 64), (1, 2)),
    FocusedBoundarySpec("RD", "RD524286", False, (1, 2), (1, 2)),
)

COMPATIBILITY_SAFE_RISK_GROUP = "safe"
COMPATIBILITY_WRITE_RESTORE_RISK_GROUP = "write_restore"
COMPATIBILITY_REMOTE_RISK_GROUP = "remote"
COMPATIBILITY_MAINTENANCE_RISK_GROUP = "maintenance"

COMPATIBILITY_COMMAND_SPECS: tuple[CompatibilityCommandSpec, ...] = (
    CompatibilityCommandSpec("0101", "System", "Read Type Name", COMPATIBILITY_SAFE_RISK_GROUP),
    CompatibilityCommandSpec("0401", "Device", "Batch Read", COMPATIBILITY_SAFE_RISK_GROUP),
    CompatibilityCommandSpec("1401", "Device", "Batch Write", COMPATIBILITY_WRITE_RESTORE_RISK_GROUP),
    CompatibilityCommandSpec("0403", "Device", "Random Read", COMPATIBILITY_SAFE_RISK_GROUP),
    CompatibilityCommandSpec("1402", "Device", "Random Write", COMPATIBILITY_WRITE_RESTORE_RISK_GROUP),
    CompatibilityCommandSpec("0801", "Monitor", "Monitor Entry", COMPATIBILITY_SAFE_RISK_GROUP),
    CompatibilityCommandSpec("0802", "Monitor", "Monitor Execute", COMPATIBILITY_SAFE_RISK_GROUP),
    CompatibilityCommandSpec("0406", "Device", "Block Read", COMPATIBILITY_SAFE_RISK_GROUP),
    CompatibilityCommandSpec("1406", "Device", "Block Write", COMPATIBILITY_WRITE_RESTORE_RISK_GROUP),
    CompatibilityCommandSpec("1001", "Remote", "Remote RUN", COMPATIBILITY_REMOTE_RISK_GROUP),
    CompatibilityCommandSpec("1002", "Remote", "Remote STOP", COMPATIBILITY_REMOTE_RISK_GROUP),
    CompatibilityCommandSpec("1005", "Remote", "Latch Clear", COMPATIBILITY_REMOTE_RISK_GROUP),
    CompatibilityCommandSpec("0619", "Diag", "Self Test", COMPATIBILITY_SAFE_RISK_GROUP),
    CompatibilityCommandSpec("0613", "Memory", "Buffer Read", COMPATIBILITY_SAFE_RISK_GROUP),
    CompatibilityCommandSpec("1613", "Memory", "Buffer Write", COMPATIBILITY_WRITE_RESTORE_RISK_GROUP),
    CompatibilityCommandSpec("1617", "Diag", "Clear Error", COMPATIBILITY_MAINTENANCE_RISK_GROUP),
)
COMPATIBILITY_COMMAND_CODES = tuple(spec.code for spec in COMPATIBILITY_COMMAND_SPECS)


def _hex_bytes(data: bytes) -> str:
    return data.hex(" ").upper()


_TARGET_NAME_PATTERN = re.compile(r"^NW(?P<network>\d+)-ST(?P<station>\d+)$", re.IGNORECASE)
_SELF_TARGET_NAME = "SELF"
_SELF_CPU_TARGET_PATTERN = re.compile(r"^SELF-CPU(?P<cpu>[1-4])$", re.IGNORECASE)
_DEFAULT_OTHER_STATION_MODULE_IO = 0x03FF
_DEFAULT_OTHER_STATION_MULTIDROP = 0x00
_DEFAULT_SELF_NETWORK = 0x00
_DEFAULT_SELF_STATION = 0xFF


def _resolve_self_target_name(name: str) -> tuple[str, int] | None:
    upper_name = name.upper()
    if upper_name == _SELF_TARGET_NAME:
        return _SELF_TARGET_NAME, _DEFAULT_OTHER_STATION_MODULE_IO
    match = _SELF_CPU_TARGET_PATTERN.fullmatch(name)
    if not match:
        return None
    cpu_index = int(match.group("cpu"), 10)
    module_io = ModuleIONo[f"MULTIPLE_CPU_{cpu_index}"].value
    return f"SELF-CPU{cpu_index}", module_io


def _parse_named_target(text: str) -> NamedTarget:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) == 1:
        name = parts[0]
        if not name:
            raise ValueError("target name must not be empty")
        self_target = _resolve_self_target_name(name)
        if self_target is not None:
            resolved_name, module_io = self_target
            return NamedTarget(
                name=resolved_name,
                target=SlmpTarget(
                    network=_DEFAULT_SELF_NETWORK,
                    station=_DEFAULT_SELF_STATION,
                    module_io=module_io,
                    multidrop=_DEFAULT_OTHER_STATION_MULTIDROP,
                ),
            )
        name_match = _TARGET_NAME_PATTERN.fullmatch(name)
        if not name_match:
            raise ValueError("target must be SELF, SELF-CPU1..4, NWx-STy, or NAME,NETWORK,STATION,MODULE_IO,MULTIDROP")
        network = int(name_match.group("network"), 10)
        station = int(name_match.group("station"), 10)
        name = f"NW{network}-ST{station}"
        return NamedTarget(
            name=name,
            target=SlmpTarget(
                network=network,
                station=station,
                module_io=_DEFAULT_OTHER_STATION_MODULE_IO,
                multidrop=_DEFAULT_OTHER_STATION_MULTIDROP,
            ),
        )
    if len(parts) != 5:
        raise ValueError(
            "target must be SELF, SELF-CPU1..4, NWx-STy, or NAME,NETWORK,STATION,MODULE_IO,MULTIDROP "
            "(example: SELF, SELF-CPU1, NW1-ST2, or remote1,0x00,0x01,0x03FF,0x00)"
        )
    name = parts[0]
    if not name:
        raise ValueError("target name must not be empty")
    network = _int_auto(parts[1])
    station = _int_auto(parts[2])
    module_io = _int_auto(parts[3])
    self_target = _resolve_self_target_name(name)
    if self_target is not None:
        resolved_name, expected_module_io = self_target
        if (network, station) != (_DEFAULT_SELF_NETWORK, _DEFAULT_SELF_STATION):
            raise ValueError(
                f"target name does not match self target values: name={name!r}, network={network}, station={station}"
            )
        if module_io != expected_module_io:
            raise ValueError(
                "target name does not match self module I/O value: "
                f"name={name!r}, module_io=0x{module_io:04X}, expected=0x{expected_module_io:04X}"
            )
        name = resolved_name
    name_match = _TARGET_NAME_PATTERN.fullmatch(name)
    if name_match:
        name_network = int(name_match.group("network"), 10)
        name_station = int(name_match.group("station"), 10)
        if (name_network, name_station) != (network, station):
            raise ValueError(
                "target name does not match network/station values: "
                f"name={name!r}, network={network}, station={station}"
            )
        name = f"NW{name_network}-ST{name_station}"
    return NamedTarget(
        name=name,
        target=SlmpTarget(
            network=network,
            station=station,
            module_io=module_io,
            multidrop=_int_auto(parts[4]),
        ),
    )


def _load_named_targets(values: list[str] | None, file_path: str | None) -> list[NamedTarget]:
    targets: list[NamedTarget] = []
    for value in values or []:
        targets.append(_parse_named_target(value))
    if file_path:
        for line in Path(file_path).read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            targets.append(_parse_named_target(stripped))
    if not targets:
        raise ValueError("at least one --target or --target-file entry is required")
    return targets


def _default_named_target(target: SlmpTarget) -> NamedTarget:
    if (target.network, target.station, int(target.module_io), target.multidrop) == (
        _DEFAULT_SELF_NETWORK,
        _DEFAULT_SELF_STATION,
        _DEFAULT_OTHER_STATION_MODULE_IO,
        _DEFAULT_OTHER_STATION_MULTIDROP,
    ):
        return NamedTarget(name=_SELF_TARGET_NAME, target=target)
    for cpu_index in range(1, 5):
        if (
            target.network,
            target.station,
            int(target.module_io),
            target.multidrop,
        ) == (
            _DEFAULT_SELF_NETWORK,
            _DEFAULT_SELF_STATION,
            int(ModuleIONo[f"MULTIPLE_CPU_{cpu_index}"].value),
            _DEFAULT_OTHER_STATION_MULTIDROP,
        ):
            return NamedTarget(name=f"SELF-CPU{cpu_index}", target=target)
    return NamedTarget(
        name=(
            f"target_0x{target.network:02X}_0x{target.station:02X}_"
            f"0x{int(target.module_io):04X}_0x{target.multidrop:02X}"
        ),
        target=target,
    )


def _parse_boundary_spec(text: str) -> BoundarySpec:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) not in {3, 4}:
        raise ValueError(
            "boundary spec must be LABEL,LAST_DEVICE,UNIT[,SPAN_POINTS] (example: D,D10239,word or LTN,LTN1023,word,4)"
        )
    label, last_device, unit_text = parts[:3]
    if not label:
        raise ValueError("boundary spec label must not be empty")
    ref = parse_device(last_device)
    if ref.number >= 0xFFFFFFFF:
        raise ValueError(f"last device is already at maximum encodable number: {last_device}")
    unit = unit_text.lower()
    if unit not in {"bit", "word"}:
        raise ValueError(f"boundary spec unit must be bit or word: {unit_text}")
    span_points = 1
    if len(parts) == 4:
        span_points = _int_auto(parts[3])
    if span_points <= 0:
        raise ValueError(f"span_points must be >= 1: {span_points}")
    return BoundarySpec(
        label=label,
        last_device=str(ref),
        bit_unit=(unit == "bit"),
        span_points=span_points,
    )


def _load_boundary_specs(values: list[str] | None, file_path: str | None) -> list[BoundarySpec]:
    specs: list[BoundarySpec] = []
    for value in values or []:
        specs.append(_parse_boundary_spec(value))
    if file_path:
        for line in Path(file_path).read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            specs.append(_parse_boundary_spec(stripped))
    if not specs:
        raise ValueError("at least one --spec or --spec-file entry is required")
    return specs


def _parse_point_list(text: str) -> tuple[int, ...]:
    parts = [part.strip() for part in text.split("/")]
    if not parts or any(not part for part in parts):
        raise ValueError(f"point list must use slash-separated integers: {text!r}")
    values = tuple(_int_auto(part) for part in parts)
    if any(value <= 0 for value in values):
        raise ValueError(f"all point values must be >= 1: {text!r}")
    return values


def _parse_focused_boundary_spec(text: str) -> FocusedBoundarySpec:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 5:
        raise ValueError(
            "focused boundary spec must be LABEL,EDGE_DEVICE,UNIT,EDGE_POINTS,NEXT_POINTS "
            "(example: ZR,ZR163839,word,1/2/3/16/64,1/2)"
        )
    label, edge_device, unit_text, edge_points_text, next_points_text = parts
    if not label:
        raise ValueError("focused boundary spec label must not be empty")
    ref = parse_device(edge_device)
    if ref.number >= 0xFFFFFFFF:
        raise ValueError(f"edge device is already at maximum encodable number: {edge_device}")
    unit = unit_text.lower()
    if unit not in {"bit", "word"}:
        raise ValueError(f"focused boundary spec unit must be bit or word: {unit_text}")
    return FocusedBoundarySpec(
        label=label,
        edge_device=str(ref),
        bit_unit=(unit == "bit"),
        edge_points=_parse_point_list(edge_points_text),
        next_points=_parse_point_list(next_points_text),
    )


def _parse_label_array_probe_spec(text: str) -> LabelArrayReadPoint:
    parts = [part.strip() for part in text.rsplit(":", 2)]
    if len(parts) != 3:
        raise ValueError("label array spec must be LABEL:UNIT:LENGTH (example: DDD[0]:1:20 or GGG.ZZZ.ZZZ.DDD[0]:1:20)")
    label, unit_text, length_text = parts
    if not label:
        raise ValueError("label array spec label must not be empty")
    unit_specification = _int_auto(unit_text)
    if unit_specification not in {0, 1}:
        raise ValueError(f"label array spec unit must be 0(bit) or 1(byte): {unit_text}")
    array_data_length = _int_auto(length_text)
    if array_data_length <= 0:
        raise ValueError(f"label array spec length must be >= 1: {length_text}")
    return LabelArrayReadPoint(
        label=label,
        unit_specification=unit_specification,
        array_data_length=array_data_length,
    )


def _load_label_array_probe_specs(values: list[str] | None) -> list[LabelArrayReadPoint]:
    if not values:
        return [LabelArrayReadPoint(label="LabelW", unit_specification=1, array_data_length=2)]
    return [_parse_label_array_probe_spec(value) for value in values]


def _load_label_random_probe_labels(values: list[str] | None) -> list[str]:
    if not values:
        return ["LabelW"]
    labels = [value.strip() for value in values if value.strip()]
    if not labels:
        raise ValueError("at least one non-empty --label-random value is required")
    return labels


def _load_explicit_label_array_points(values: list[str] | None) -> list[LabelArrayReadPoint]:
    return [_parse_label_array_probe_spec(value) for value in values or []]


def _load_explicit_label_random_labels(values: list[str] | None) -> list[str]:
    labels = [value.strip() for value in values or [] if value.strip()]
    if values and not labels:
        raise ValueError("at least one non-empty --label-random value is required")
    return labels


def _format_label_array_read_detail(
    points: Sequence[LabelArrayReadPoint],
    results: Sequence[LabelArrayReadResult],
) -> str:
    parts: list[str] = []
    for point, result in zip(points, results, strict=False):
        parts.append(
            f"{point.label}:type=0x{result.data_type_id:02X},unit={result.unit_specification},"
            f"array_len={result.array_data_length},data_len={len(result.data)}"
        )
    return "; ".join(parts)


def _format_label_random_read_detail(
    labels: Sequence[str],
    results: Sequence[LabelRandomReadResult],
) -> str:
    parts: list[str] = []
    for label, result in zip(labels, results, strict=False):
        parts.append(
            f"{label}:type=0x{result.data_type_id:02X},len={result.read_data_length},data_len={len(result.data)}"
        )
    return "; ".join(parts)


def _format_label_value(data: bytes) -> str:
    if not data:
        return "raw=<empty>"
    if len(data) == 1:
        return f"0x{data[0]:02X} ({data[0]}), raw={_hex_bytes(data)}"
    if len(data) == 2:
        value = int.from_bytes(data, "little")
        return f"0x{value:04X} ({value}), raw={_hex_bytes(data)}"
    if len(data) == 4:
        value = int.from_bytes(data, "little")
        return f"0x{value:08X} ({value}), raw={_hex_bytes(data)}"
    preview = _hex_bytes(data[:16])
    if len(data) > 16:
        return f"raw={preview} ... ({len(data)} bytes)"
    return f"raw={preview} ({len(data)} bytes)"


def _format_label_array_point(point: LabelArrayReadPoint) -> str:
    return f"{point.label}:{point.unit_specification}:{point.array_data_length}"


def _make_manual_label_test_bytes(before: bytes) -> bytes:
    if not before:
        raise ValueError("manual label write requires non-empty data")
    candidate = bytearray(before)
    candidate[0] ^= 0x01
    return bytes(candidate)


def _load_focused_boundary_specs(
    values: list[str] | None,
    file_path: str | None,
) -> list[FocusedBoundarySpec]:
    specs: list[FocusedBoundarySpec] = []
    for value in values or []:
        specs.append(_parse_focused_boundary_spec(value))
    if file_path:
        for line in Path(file_path).read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            specs.append(_parse_focused_boundary_spec(stripped))
    if not specs:
        return list(DEFAULT_FOCUSED_BOUNDARY_SPECS)
    return specs


def _format_probe_values(values: object | None) -> str:
    if values is None:
        return "None"
    if isinstance(values, list):
        if len(values) <= 8:
            return repr(values)
        head = ", ".join(str(item) for item in values[:4])
        tail = ", ".join(str(item) for item in values[-2:])
        return f"len={len(values)} [{head}, ..., {tail}]"
    return repr(values)


def _sanitize_report_component(text: str) -> str:
    lowered = text.strip().lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in lowered)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "unknown"


def _model_folder_path(*, series: str, model: str) -> Path:
    folder = f"{_sanitize_report_component(series)}_{_sanitize_report_component(model)}"
    return Path("internal_docs") / folder


def _default_report_output(*, series: str, model: str, filename: str) -> str:
    return str(_model_folder_path(series=series, model=model) / filename)


def _default_capture_dir(*, series: str, model: str, dirname: str) -> Path:
    return _model_folder_path(series=series, model=model) / dirname


def _probe_target_model(
    *,
    host: str,
    port: int,
    transport: str,
    timeout: float,
    series: str,
    target: SlmpTarget,
    monitoring_timer: int = 0x0010,
) -> str:
    model, _ = _probe_target_model_and_series(
        host=host,
        port=port,
        transport=transport,
        timeout=timeout,
        series=series,
        target=target,
        monitoring_timer=monitoring_timer,
    )
    return model


def _probe_target_model_and_series(
    *,
    host: str,
    port: int,
    transport: str,
    timeout: float,
    series: str,
    target: SlmpTarget,
    monitoring_timer: int = 0x0010,
) -> tuple[str, str]:
    candidates = [series] if series != "auto" else [PLCSeries.QL.value, PLCSeries.IQR.value]
    for candidate in candidates:
        try:
            with SlmpClient(
                host,
                port=port,
                transport=transport,
                timeout=timeout,
                plc_series=candidate,
                default_target=target,
                monitoring_timer=monitoring_timer,
            ) as client:
                info = client.read_type_name()
        except Exception:  # noqa: BLE001
            continue
        model = info.model.strip() if info.model.strip() else "unknown_target"
        return model, candidate
    return "unknown_target", (series if series != "auto" else PLCSeries.QL.value)


def _resolve_report_output(
    *,
    output: str | None,
    series: str,
    host: str,
    port: int,
    transport: str,
    timeout: float,
    target: SlmpTarget,
    filename: str,
    monitoring_timer: int = 0x0010,
) -> str:
    if output:
        return output
    model, resolved_series = _probe_target_model_and_series(
        host=host,
        port=port,
        transport=transport,
        timeout=timeout,
        series=series,
        target=target,
        monitoring_timer=monitoring_timer,
    )
    return _default_report_output(series=resolved_series, model=model, filename=filename)


def _probe_device_read_with_series(
    client: SlmpClient,
    *,
    device: str,
    points: int,
    bit_unit: bool,
    series_candidates: Sequence[PLCSeries] = (PLCSeries.QL, PLCSeries.IQR),
) -> tuple[PLCSeries, list[bool] | list[int]]:
    last_error: Exception | None = None
    for candidate in series_candidates:
        try:
            values = client.read_devices(device, points, bit_unit=bit_unit, series=candidate)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        return candidate, values
    if last_error is not None:
        raise last_error
    raise RuntimeError("no series candidates available")


def _probe_device_read_with_frame_and_series(
    *,
    host: str,
    port: int,
    transport: str,
    timeout: float,
    target: SlmpTarget,
    monitoring_timer: int,
    device: str,
    points: int,
    bit_unit: bool,
    frame_candidates: Sequence[FrameType],
    series_candidates: Sequence[PLCSeries],
    candidate_pairs: Sequence[tuple[FrameType, PLCSeries]] | None = None,
) -> tuple[FrameType, PLCSeries, list[bool] | list[int]]:
    last_error: Exception | None = None
    pairs = (
        list(candidate_pairs)
        if candidate_pairs is not None
        else [(frame_type, series) for frame_type in frame_candidates for series in series_candidates]
    )
    for frame_type, series in pairs:
        try:
            with SlmpClient(
                host,
                port=port,
                transport=transport,
                timeout=timeout,
                plc_series=series,
                frame_type=frame_type,
                default_target=target,
                monitoring_timer=monitoring_timer,
            ) as client:
                values = client.read_devices(device, points, bit_unit=bit_unit, series=series)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        return frame_type, series, values
    if last_error is not None:
        raise last_error
    raise RuntimeError("no frame/series candidates available")


def _read_type_name_with_frame_and_series(
    *,
    host: str,
    port: int,
    transport: str,
    timeout: float,
    target: SlmpTarget,
    monitoring_timer: int,
    frame_type: FrameType,
    series: PLCSeries,
) -> TypeNameInfo:
    with SlmpClient(
        host,
        port=port,
        transport=transport,
        timeout=timeout,
        plc_series=series,
        frame_type=frame_type,
        default_target=target,
        monitoring_timer=monitoring_timer,
    ) as client:
        return client.read_type_name()


def _compatibility_subprobe(
    name: str,
    func: Callable[[], str],
) -> tuple[str, str, str]:
    try:
        return (name, "OK", func())
    except Exception as exc:  # noqa: BLE001
        return (name, "NG", str(exc))


def _compatibility_request_subprobe(
    client: SlmpClient,
    *,
    name: str,
    command: int | Command,
    payload: bytes = b"",
    subcommand: int = 0x0000,
) -> tuple[str, str, str]:
    try:
        resp = client.request(command, subcommand, payload, raise_on_error=False)
    except Exception as exc:  # noqa: BLE001
        return (name, "NG", str(exc))
    status = "OK" if resp.end_code == 0 else "NG"
    return (name, status, f"end_code=0x{resp.end_code:04X}, data_len={len(resp.data)}")


def _compatibility_probe_direct_word_write_restore(
    client: SlmpClient,
    *,
    device: str,
    preferred_write_value: int,
    series: PLCSeries,
) -> str:
    before = int(client.read_devices(device, 1, bit_unit=False, series=series)[0])
    write_value = _choose_probe_word_value(current=before, preferred=preferred_write_value)
    client.write_devices(device, [write_value], bit_unit=False, series=series)
    readback = int(client.read_devices(device, 1, bit_unit=False, series=series)[0])
    client.write_devices(device, [before], bit_unit=False, series=series)
    restored = int(client.read_devices(device, 1, bit_unit=False, series=series)[0])
    return (
        f"device={device}, before=0x{before:04X}, write=0x{write_value:04X}, "
        f"readback=0x{readback:04X}, restored=0x{restored:04X}"
    )


def _compatibility_probe_direct_bit_write_restore(
    client: SlmpClient,
    *,
    device: str,
    series: PLCSeries,
) -> str:
    before = bool(client.read_devices(device, 1, bit_unit=True, series=series)[0])
    write_value = not before
    client.write_devices(device, [write_value], bit_unit=True, series=series)
    readback = bool(client.read_devices(device, 1, bit_unit=True, series=series)[0])
    client.write_devices(device, [before], bit_unit=True, series=series)
    restored = bool(client.read_devices(device, 1, bit_unit=True, series=series)[0])
    return f"device={device}, before={before}, write={write_value}, readback={readback}, restored={restored}"


def _compatibility_probe_random_word_write_restore(
    client: SlmpClient,
    *,
    devices: Sequence[str],
    preferred_write_value: int,
    series: PLCSeries,
) -> str:
    before = client.read_random(word_devices=devices, series=series).word
    write_pairs: list[tuple[str, int]] = []
    for device in devices:
        current = int(before[str(device)])
        write_pairs.append((str(device), _choose_probe_word_value(current=current, preferred=preferred_write_value)))
    client.write_random_words(word_values=write_pairs, series=series)
    readback = client.read_random(word_devices=devices, series=series).word
    restore_pairs = [(str(device), int(before[str(device)])) for device in devices]
    client.write_random_words(word_values=restore_pairs, series=series)
    restored = client.read_random(word_devices=devices, series=series).word
    return (
        f"devices={list(devices)}, before={before}, write={dict(write_pairs)}, readback={readback}, restored={restored}"
    )


def _compatibility_probe_random_bit_write_restore(
    client: SlmpClient,
    *,
    devices: Sequence[str],
    series: PLCSeries,
) -> str:
    before = {str(device): bool(client.read_devices(device, 1, bit_unit=True, series=series)[0]) for device in devices}
    write_pairs = [(device, not before[str(device)]) for device in devices]
    client.write_random_bits(bit_values=write_pairs, series=series)
    readback = {
        str(device): bool(client.read_devices(device, 1, bit_unit=True, series=series)[0]) for device in devices
    }
    restore_pairs = [(device, before[str(device)]) for device in devices]
    client.write_random_bits(bit_values=restore_pairs, series=series)
    restored = {
        str(device): bool(client.read_devices(device, 1, bit_unit=True, series=series)[0]) for device in devices
    }
    return (
        f"devices={list(devices)}, before={before}, write={dict(write_pairs)}, readback={readback}, restored={restored}"
    )


def _compatibility_probe_block_write_restore(
    client: SlmpClient,
    *,
    word_device: str | None,
    bit_device: str | None,
    preferred_word_value: int,
    preferred_bit_value: int,
    series: PLCSeries,
) -> str:
    word_blocks = [(word_device, 1)] if word_device is not None else []
    bit_blocks = [(bit_device, 1)] if bit_device is not None else []
    before = client.read_block(word_blocks=word_blocks, bit_blocks=bit_blocks, series=series)

    write_word_blocks: list[tuple[str, list[int]]] = []
    write_bit_blocks: list[tuple[str, list[int]]] = []
    if word_device is not None:
        current = int(before.word_blocks[0].values[0])
        write_word_blocks.append(
            (word_device, [_choose_probe_word_value(current=current, preferred=preferred_word_value)])
        )
    if bit_device is not None:
        current = int(before.bit_blocks[0].values[0])
        write_bit_blocks.append(
            (bit_device, [_choose_probe_word_value(current=current, preferred=preferred_bit_value)])
        )

    client.write_block(
        word_blocks=write_word_blocks,
        bit_blocks=write_bit_blocks,
        series=series,
        split_mixed_blocks=False,
        retry_mixed_on_error=False,
    )
    readback = client.read_block(word_blocks=word_blocks, bit_blocks=bit_blocks, series=series)
    restore_word_blocks = [(row.device, row.values) for row in before.word_blocks]
    restore_bit_blocks = [(row.device, row.values) for row in before.bit_blocks]
    client.write_block(
        word_blocks=restore_word_blocks,
        bit_blocks=restore_bit_blocks,
        series=series,
        split_mixed_blocks=False,
        retry_mixed_on_error=False,
    )
    restored = client.read_block(word_blocks=word_blocks, bit_blocks=bit_blocks, series=series)
    return (
        f"word_device={word_device}, bit_device={bit_device}, "
        f"before_words={before.word_blocks}, before_bits={before.bit_blocks}, "
        f"write_words={write_word_blocks}, write_bits={write_bit_blocks}, "
        f"readback_words={readback.word_blocks}, readback_bits={readback.bit_blocks}, "
        f"restored_words={restored.word_blocks}, restored_bits={restored.bit_blocks}"
    )


def _compatibility_probe_memory_write_restore(
    client: SlmpClient,
    *,
    head_address: int,
    preferred_write_value: int,
) -> str:
    before = int(client.memory_read_words(head_address, 1)[0])
    write_value = _choose_probe_word_value(current=before, preferred=preferred_write_value)
    client.memory_write_words(head_address, [write_value])
    readback = int(client.memory_read_words(head_address, 1)[0])
    client.memory_write_words(head_address, [before])
    restored = int(client.memory_read_words(head_address, 1)[0])
    return (
        f"head=0x{head_address:08X}, before=0x{before:04X}, write=0x{write_value:04X}, "
        f"readback=0x{readback:04X}, restored=0x{restored:04X}"
    )


def _compatibility_run_command(
    spec: CompatibilityCommandSpec,
    client: SlmpClient,
    *,
    series: PLCSeries,
    args: argparse.Namespace,
) -> tuple[list[tuple[str, str, str]], dict[str, object]]:
    metadata: dict[str, object] = {}
    if spec.code == "0101":
        try:
            info = client.read_type_name()
        except Exception as exc:  # noqa: BLE001
            return ([("type_name", "NG", str(exc))], metadata)
        model_label = _resolve_type_name_label(info)
        model_code = _format_model_code(info.model_code)
        inferred_series = _resolve_series_from_type_name(info)
        metadata = {
            "detected_model": model_label,
            "model_code": model_code,
            "detected_series": inferred_series.value if inferred_series is not None else None,
        }
        return ([("type_name", "OK", f"model={model_label}, model_code={model_code}")], metadata)
    if spec.code == "0401":
        return (
            [
                _compatibility_subprobe(
                    "word_read",
                    lambda: (
                        f"device={args.word_device}, values={client.read_devices(args.word_device, 1, series=series)}"
                    ),
                ),
                _compatibility_subprobe(
                    "bit_read",
                    lambda: (
                        f"device={args.bit_device}, "
                        f"values={client.read_devices(args.bit_device, 1, bit_unit=True, series=series)}"
                    ),
                ),
            ],
            metadata,
        )
    if spec.code == "1401":
        return (
            [
                _compatibility_subprobe(
                    "word_write_restore",
                    lambda: _compatibility_probe_direct_word_write_restore(
                        client,
                        device=args.word_device,
                        preferred_write_value=args.word_write_value,
                        series=series,
                    ),
                ),
                _compatibility_subprobe(
                    "bit_write_restore",
                    lambda: _compatibility_probe_direct_bit_write_restore(
                        client,
                        device=args.bit_device,
                        series=series,
                    ),
                ),
            ],
            metadata,
        )
    if spec.code == "0403":
        return (
            [
                _compatibility_subprobe(
                    "random_read",
                    lambda: (
                        f"devices={args.random_read_word_device}, "
                        f"values={client.read_random(word_devices=args.random_read_word_device, series=series).word}"
                    ),
                )
            ],
            metadata,
        )
    if spec.code == "1402":
        return (
            [
                _compatibility_subprobe(
                    "random_word_write_restore",
                    lambda: _compatibility_probe_random_word_write_restore(
                        client,
                        devices=args.random_write_word_device,
                        preferred_write_value=args.random_write_word_value,
                        series=series,
                    ),
                ),
                _compatibility_subprobe(
                    "random_bit_write_restore",
                    lambda: _compatibility_probe_random_bit_write_restore(
                        client,
                        devices=args.random_write_bit_device,
                        series=series,
                    ),
                ),
            ],
            metadata,
        )
    if spec.code == "0801":

        def _monitor_entry_detail() -> str:
            client.register_monitor_devices(word_devices=[args.monitor_word_device], series=series)
            return f"word_device={args.monitor_word_device}"

        return (
            [
                _compatibility_subprobe(
                    "monitor_entry",
                    _monitor_entry_detail,
                )
            ],
            metadata,
        )
    if spec.code == "0802":

        def _monitor_execute_detail() -> str:
            client.register_monitor_devices(word_devices=[args.monitor_word_device], series=series)
            result = client.run_monitor_cycle(word_points=1, dword_points=0)
            return f"word_device={args.monitor_word_device}, values={result.word}"

        return ([_compatibility_subprobe("monitor_execute", _monitor_execute_detail)], metadata)
    if spec.code == "0406":

        def _block_read_mixed_detail() -> str:
            result = client.read_block(
                word_blocks=[(args.block_word_device, 1)],
                bit_blocks=[(args.block_bit_device, 1)],
                series=series,
            )
            return f"word_device={args.block_word_device}, bit_device={args.block_bit_device}, result={result}"

        return (
            [
                _compatibility_subprobe(
                    "block_read_word_only",
                    lambda: (
                        f"device={args.block_word_device}, "
                        "result="
                        f"{client.read_block(word_blocks=[(args.block_word_device, 1)], series=series).word_blocks}"
                    ),
                ),
                _compatibility_subprobe(
                    "block_read_bit_only",
                    lambda: (
                        f"device={args.block_bit_device}, "
                        f"result={client.read_block(bit_blocks=[(args.block_bit_device, 1)], series=series).bit_blocks}"
                    ),
                ),
                _compatibility_subprobe(
                    "block_read_mixed",
                    _block_read_mixed_detail,
                ),
            ],
            metadata,
        )
    if spec.code == "1406":
        return (
            [
                _compatibility_subprobe(
                    "block_write_word_only",
                    lambda: _compatibility_probe_block_write_restore(
                        client,
                        word_device=args.block_word_device,
                        bit_device=None,
                        preferred_word_value=args.block_word_write_value,
                        preferred_bit_value=args.block_bit_write_value,
                        series=series,
                    ),
                ),
                _compatibility_subprobe(
                    "block_write_bit_only",
                    lambda: _compatibility_probe_block_write_restore(
                        client,
                        word_device=None,
                        bit_device=args.block_bit_device,
                        preferred_word_value=args.block_word_write_value,
                        preferred_bit_value=args.block_bit_write_value,
                        series=series,
                    ),
                ),
                _compatibility_subprobe(
                    "block_write_mixed",
                    lambda: _compatibility_probe_block_write_restore(
                        client,
                        word_device=args.block_word_device,
                        bit_device=args.block_bit_device,
                        preferred_word_value=args.block_word_write_value,
                        preferred_bit_value=args.block_bit_write_value,
                        series=series,
                    ),
                ),
            ],
            metadata,
        )
    if spec.code == "1001":
        return (
            [
                _compatibility_request_subprobe(
                    client,
                    name="remote_run",
                    command=Command.REMOTE_RUN,
                    payload=b"\x01\x00\x00\x00",
                )
            ],
            metadata,
        )
    if spec.code == "1002":
        return (
            [
                _compatibility_request_subprobe(
                    client,
                    name="remote_stop",
                    command=Command.REMOTE_STOP,
                    payload=b"\x01\x00",
                )
            ],
            metadata,
        )
    if spec.code == "1005":
        return (
            [
                _compatibility_request_subprobe(
                    client,
                    name="remote_latch_clear",
                    command=Command.REMOTE_LATCH_CLEAR,
                    payload=b"\x01\x00",
                )
            ],
            metadata,
        )
    if spec.code == "0619":
        return (
            [
                _compatibility_request_subprobe(
                    client,
                    name="self_test",
                    command=Command.SELF_TEST,
                    payload=b"\x04\x00\x11\x22\x33\x44",
                )
            ],
            metadata,
        )
    if spec.code == "0613":
        return (
            [
                _compatibility_subprobe(
                    "memory_read",
                    lambda: (
                        f"head=0x{args.memory_head:08X}, "
                        f"values={client.memory_read_words(args.memory_head, args.memory_length)}"
                    ),
                )
            ],
            metadata,
        )
    if spec.code == "1613":
        return (
            [
                _compatibility_subprobe(
                    "memory_write_restore",
                    lambda: _compatibility_probe_memory_write_restore(
                        client,
                        head_address=args.memory_head,
                        preferred_write_value=args.memory_write_value,
                    ),
                )
            ],
            metadata,
        )
    if spec.code == "1617":
        return (
            [
                _compatibility_request_subprobe(
                    client,
                    name="clear_error",
                    command=Command.CLEAR_ERROR,
                    payload=b"",
                )
            ],
            metadata,
        )
    raise ValueError(f"unsupported compatibility command code: {spec.code}")


def _probe_sm400_series(client: SlmpClient) -> tuple[PLCSeries, list[bool]]:
    series, values = _probe_device_read_with_series(
        client,
        device="SM400",
        points=1,
        bit_unit=True,
    )
    return series, [bool(value) for value in values]


def _resolve_capture_dir(
    *,
    output_dir: str | None,
    series: str,
    model: str,
    dirname: str,
) -> Path:
    if output_dir:
        return Path(output_dir)
    return _default_capture_dir(series=series, model=model, dirname=dirname)


def _write_scaffold_file(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _load_device_access_matrix_rows(path: str | Path) -> list[DeviceMatrixRow]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"device access matrix has no header: {csv_path}")
        expected = {"device_code", "device", "kind", "unsupported", "read", "write", "note"}
        missing = sorted(expected - set(reader.fieldnames))
        if missing:
            raise ValueError(f"device access matrix is missing columns: {', '.join(missing)}")
        rows: list[DeviceMatrixRow] = []
        for raw in reader:
            row = DeviceMatrixRow(
                device_code=(raw.get("device_code") or "").strip(),
                device=(raw.get("device") or "").strip(),
                kind=(raw.get("kind") or "").strip(),
                unsupported=(raw.get("unsupported") or "").strip(),
                read=(raw.get("read") or "").strip(),
                write=(raw.get("write") or "").strip(),
                note=(raw.get("note") or "").strip(),
                manual_write=(raw.get("manual_write") or "").strip(),
                manual_write_note=(raw.get("manual_write_note") or "").strip(),
            )
            if not any(
                (
                    row.device_code,
                    row.device,
                    row.kind,
                    row.unsupported,
                    row.read,
                    row.write,
                    row.note,
                    row.manual_write,
                    row.manual_write_note,
                )
            ):
                continue
            rows.append(row)
    if not rows:
        raise ValueError(f"device access matrix has no rows: {csv_path}")
    return rows


def _escape_markdown_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def _render_device_access_matrix_markdown(rows: Sequence[DeviceMatrixRow], *, source_path: Path) -> str:
    summary: dict[str, int] = {}
    for row in rows:
        kind_key = row.kind.lower() or "unknown"
        for label, value in (("read", row.read), ("write", row.write)):
            status = value.strip()
            if not status:
                continue
            key = f"{kind_key}_{label}_{status.upper()}"
            summary[key] = summary.get(key, 0) + 1
        manual_status = row.manual_write.strip()
        if manual_status:
            key = f"manual_write_{manual_status.upper()}"
            summary[key] = summary.get(key, 0) + 1

    lines = [
        "# Device Access Matrix",
        "",
        f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Source: `{source_path.as_posix()}`",
        "",
        "## Summary",
        "",
    ]
    if summary:
        for key in sorted(summary):
            lines.append(f"- {key}: {summary[key]}")
    else:
        lines.append("- no populated read/write status values")

    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Device Code | Device | Kind | Unsupported | Read | Write | Manual Write | Note | Manual Write Note |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown_cell(row.device_code),
                    _escape_markdown_cell(row.device),
                    _escape_markdown_cell(row.kind),
                    _escape_markdown_cell(row.unsupported),
                    _escape_markdown_cell(row.read),
                    _escape_markdown_cell(row.write),
                    _escape_markdown_cell(row.manual_write),
                    _escape_markdown_cell(row.note),
                    _escape_markdown_cell(row.manual_write_note),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _manual_yes(text: str) -> bool:
    return text.strip().lower() in {"y", "yes", "true", "1", "unsupported"}


_SPECIAL_MANUAL_WRITE_CODES = frozenset({"LTC", "LTS", "LSTC", "LSTS"})


def _is_special_manual_write_row(row: DeviceMatrixRow) -> bool:
    return row.device_code.upper() in _SPECIAL_MANUAL_WRITE_CODES


def _select_manual_write_rows(
    rows: Sequence[DeviceMatrixRow],
    *,
    device_codes: set[str] | None = None,
    limit: int | None = None,
) -> list[DeviceMatrixRow]:
    selected: list[DeviceMatrixRow] = []
    for row in rows:
        explicit_request = bool(device_codes and row.device_code.upper() in device_codes)
        if device_codes and not explicit_request:
            continue
        if not row.device or row.device.upper() == "N/A":
            continue
        if row.kind.lower() not in {"bit", "word", "dword"}:
            continue
        if _manual_yes(row.unsupported):
            continue
        if row.read.strip().upper() in {"NG", "SKIP", "NO"} and not (
            explicit_request and _is_special_manual_write_row(row)
        ):
            continue
        if row.write.strip().upper() in {"NG", "SKIP", "NO"} and not (
            explicit_request and _is_special_manual_write_row(row)
        ):
            continue
        selected.append(row)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def _format_manual_value(kind: str, value: int | bool) -> str:
    lowered = kind.lower()
    if lowered == "bit":
        return "ON" if bool(value) else "OFF"
    if lowered == "dword":
        return f"0x{int(value):08X} ({int(value)})"
    return f"0x{int(value):04X} ({int(value)})"


def _read_manual_row_value(client: SlmpClient, row: DeviceMatrixRow, *, series: str) -> int | bool:
    code = row.device_code.upper()
    number = parse_device(row.device).number
    if code == "LTC":
        return bool(client.read_ltc_states(head_no=number, points=1, series=series)[0])
    if code == "LTS":
        return bool(client.read_lts_states(head_no=number, points=1, series=series)[0])
    if code == "LSTC":
        return bool(client.read_lstc_states(head_no=number, points=1, series=series)[0])
    if code == "LSTS":
        return bool(client.read_lsts_states(head_no=number, points=1, series=series)[0])
    kind = row.kind.lower()
    if kind == "bit":
        return bool(client.read_devices(row.device, 1, bit_unit=True, series=series)[0])
    if kind == "word":
        return int(client.read_devices(row.device, 1, bit_unit=False, series=series)[0])
    if kind == "dword":
        key = str(parse_device(row.device))
        return int(client.read_random(dword_devices=[row.device], series=series).dword[key])
    raise ValueError(f"unsupported manual-write row kind: {row.kind}")


def _write_manual_row_value(
    client: SlmpClient,
    row: DeviceMatrixRow,
    value: int | bool,
    *,
    series: str,
) -> None:
    code = row.device_code.upper()
    if code in _SPECIAL_MANUAL_WRITE_CODES:
        client.write_random_bits([(row.device, bool(value))], series=series)
        return
    kind = row.kind.lower()
    if kind == "bit":
        client.write_devices(row.device, [1 if bool(value) else 0], bit_unit=True, series=series)
        return
    if kind == "word":
        client.write_devices(row.device, [int(value) & 0xFFFF], bit_unit=False, series=series)
        return
    if kind == "dword":
        client.write_random_words(dword_values=[(row.device, int(value) & 0xFFFFFFFF)], series=series)
        return
    raise ValueError(f"unsupported manual-write row kind: {row.kind}")


def _make_manual_test_value(row: DeviceMatrixRow, before: int | bool) -> int | bool:
    kind = row.kind.lower()
    if kind == "bit":
        return not bool(before)
    mask = 0x00000001 if kind == "dword" else 0x0001
    before_int = int(before)
    candidate = before_int ^ mask
    if candidate == before_int:
        return 1 if before_int == 0 else 0
    return candidate


def _parse_manual_verdict(text: str) -> str | None:
    lowered = text.strip().lower()
    if lowered in {"y", "yes"}:
        return "OK"
    if lowered in {"n", "no"}:
        return "NG"
    if lowered in {"s", "skip"}:
        return "SKIP"
    return None


def _load_processed_manual_write_items(report_path: Path) -> set[str]:
    processed: set[str] = set()
    for line in report_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 3:
            continue
        item, status = parts[0], parts[1]
        if item == "Item" or status not in {"OK", "NG", "SKIP"}:
            continue
        processed.add(item)
    return processed


def _load_manual_write_report_rows(report_path: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in report_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 3:
            continue
        item, status, detail = parts[0], parts[1], parts[2]
        if item == "Item" or status not in {"OK", "NG", "SKIP"}:
            continue
        rows.append((item, status, detail))
    return rows


def _parse_positive_int_list(text: str) -> tuple[int, ...]:
    parts = [part.strip() for part in text.split(",")]
    if not parts or any(not part for part in parts):
        raise ValueError(f"comma-separated positive integer list expected: {text!r}")
    values = tuple(_int_auto(part) for part in parts)
    if any(value <= 0 for value in values):
        raise ValueError(f"all values must be >= 1: {text!r}")
    return values


def _render_model_docs_readme(*, series: str, model: str, folder_name: str) -> str:
    return "\n".join(
        [
            f"# {series} {model} Verification Folder",
            "",
            (
                "This folder stores generated live reports, sample spec inputs, "
                "curated frame dumps, and raw packet-capture placeholders for a target PLC."
            ),
            "",
            "## Target",
            "",
            f"- Series: `{series}`",
            f"- Model: `{model}`",
            "- Host: fill in when the target is assigned",
            "- Primary SLMP ports: fill in when the target is assigned",
            "",
            "## Expected Files",
            "",
            "- `device_access_matrix.csv`",
            "  - Excel-friendly device support management sheet and canonical editable source",
            "- `device_access_matrix.md`",
            "  - human-readable device access snapshot generated from the CSV when maintained",
            "- `manual_write_verification_latest.md`",
            "  - interactive human-confirmed temporary write verification report",
            "- `read_soak_latest.md`",
            "  - repeated single-command read soak result",
            "- `mixed_read_load_latest.md`",
            "  - mixed 0401/0403/0406 read load result",
            "- `tcp_concurrency_latest.md`",
            "  - practical multi-client TCP read concurrency result",
            "- `device_range_probe_latest.md`",
            "- `register_boundary_probe_latest.md`",
            "- `special_device_probe_latest.md`",
            "- `g_hg_extended_device_recheck_latest.md`",
            "- `open_items_recheck_latest.md`",
            "- `pending_live_verification_latest.md`",
            "- `other_station_check_latest.md`",
            "",
            "## Supporting Inputs",
            "",
            "- `current_plc_boundary_specs_example.txt`",
            "- `current_register_boundary_focus_specs_example.txt`",
            "- `other_station_targets_example.txt`",
            "",
            "## Captures",
            "",
            "- `frame_dumps_extended_device/`",
            "- `frame_dumps_extended_device_g_hg_recheck/`",
            "- `wireshark/`",
            "",
            "## Notes",
            "",
            f"- Folder name: `{folder_name}`",
            "- Replace the example spec files with current target values after the first real configuration review.",
            "- Keep generated `*_latest.md` files tracked and let `archive/` stay ignored.",
            "",
        ]
    )


def _render_model_wireshark_readme(*, series: str, model: str) -> str:
    return "\n".join(
        [
            f"# Wireshark Captures for {series} {model}",
            "",
            (
                "Store raw packet captures for this target in this folder when they "
                "materially support a protocol interpretation."
            ),
            "",
            "Policy:",
            "",
            "- prefer direct 4E request/response hex dumps in `../frame_dumps_extended_device/`",
            "  when those are sufficient",
            "- use raw packet captures here only when transport-level context or non-4E traffic matters",
            "- keep filenames descriptive and date-stamped",
            "",
        ]
    )


def _render_model_boundary_specs_example() -> str:
    return "\n".join(
        [
            "# Example input for scripts/slmp_device_range_probe.py",
            "# Format:",
            "#   LABEL,LAST_DEVICE,UNIT[,SPAN_POINTS]",
            "# Replace these with the actual configured ranges of the target PLC.",
            "",
            "D,D10239,word",
            "M,M12287,bit",
            "X,X2FFF,bit",
            "W,W1FFF,word",
            "ZR,ZR163839,word",
            "LTN,LTN1023,word,4",
            "LSTN,LSTN1023,word,4",
            "",
        ]
    )


def _render_model_register_boundary_specs_example() -> str:
    return "\n".join(
        [
            "# Example input for scripts/slmp_register_boundary_probe.py",
            "# Format:",
            "#   LABEL,EDGE_DEVICE,UNIT,EDGE_POINTS,NEXT_POINTS",
            "",
            "Z,Z19,word,1/2,1",
            "LZ,LZ1,word,1/2,1/2",
            "R,R32767,word,1/2/16/64,1/2/16",
            "ZR,ZR163839,word,1/2/3/16/64,1/2",
            "RD,RD524286,word,1/2,1/2",
            "",
        ]
    )


def _render_model_other_station_targets_example() -> str:
    return "\n".join(
        [
            "# Example target list for scripts/slmp_other_station_check.py",
            "# Format:",
            "#   SELF",
            "#   SELF-CPU1 .. SELF-CPU4",
            "#   NWx-STy",
            "#   or name,network,station,module_io,multidrop",
            "",
            "SELF",
            "SELF-CPU1",
            "remote_station_01,0x00,0x01,0x03FF,0x00",
            "remote_station_02,0x00,0x02,0x03FF,0x00",
            "",
        ]
    )


def _render_model_device_access_matrix_csv() -> str:
    return "\n".join(
        [
            "device_code,device,kind,unsupported,read,write,note,manual_write,manual_write_note",
            "D,D1000,word,,TODO,TODO,representative verification address; avoid head addresses,,",
            "M,M1000,bit,,TODO,TODO,fill unsupported manually if needed,,",
            "W,W100,word,,TODO,TODO,fill unsupported manually if needed,,",
            "B,B100,bit,,TODO,TODO,fill unsupported manually if needed,,",
            "R,R1000,word,,TODO,TODO,fill unsupported manually if needed,,",
            "ZR,ZR1000,word,,TODO,TODO,fill unsupported manually if needed,,",
            "",
        ]
    )


def _initialize_model_docs(
    *,
    root: Path,
    series: str,
    model: str,
    force: bool = False,
) -> tuple[Path, list[Path], list[Path]]:
    folder_name = f"{_sanitize_report_component(series)}_{_sanitize_report_component(model)}"
    model_dir = root / folder_name
    created: list[Path] = []
    skipped: list[Path] = []
    files: list[tuple[Path, str]] = [
        (model_dir / "README.md", _render_model_docs_readme(series=series, model=model, folder_name=folder_name)),
        (model_dir / "device_access_matrix.csv", _render_model_device_access_matrix_csv()),
        (model_dir / "current_plc_boundary_specs_example.txt", _render_model_boundary_specs_example()),
        (
            model_dir / "current_register_boundary_focus_specs_example.txt",
            _render_model_register_boundary_specs_example(),
        ),
        (model_dir / "other_station_targets_example.txt", _render_model_other_station_targets_example()),
        (model_dir / "wireshark" / "README.md", _render_model_wireshark_readme(series=series, model=model)),
    ]
    (model_dir / "frame_dumps_extended_device").mkdir(parents=True, exist_ok=True)
    for path, content in files:
        if _write_scaffold_file(path, content, force=force):
            created.append(path)
        else:
            skipped.append(path)
    return model_dir, created, skipped


def _increment_device_text(device: str) -> str:
    ref = parse_device(device)
    next_number = ref.number + 1
    radix = DEVICE_CODES[ref.code].radix
    suffix = f"{next_number:X}" if radix == 16 else str(next_number)
    return f"{ref.code}{suffix}"


def _offset_device_text(device: str | DeviceRef, offset: int) -> str:
    ref = parse_device(device)
    next_number = ref.number + offset
    if next_number < 0 or next_number > 0xFFFFFFFF:
        raise ValueError(f"device offset out of encodable range: {device} + {offset}")
    radix = DEVICE_CODES[ref.code].radix
    suffix = f"{next_number:X}" if radix == 16 else str(next_number)
    return f"{ref.code}{suffix}"


def _choose_probe_word_value(*, current: int, preferred: int) -> int:
    candidate = preferred & 0xFFFF
    if candidate != current:
        return candidate
    return (candidate + 1) & 0xFFFF


def _choose_probe_word_values(*, current_values: Sequence[int], preferred_base: int) -> list[int]:
    values: list[int] = []
    for index, current in enumerate(current_values):
        candidate = (preferred_base + index) & 0xFFFF
        if candidate == current:
            candidate = (candidate + 1) & 0xFFFF
        values.append(candidate)
    return values


def _format_word_values(values: Sequence[int]) -> str:
    return "[" + ", ".join(f"0x{int(value) & 0xFFFF:04X}" for value in values) + "]"


def _parse_positive_u16(text: str) -> int:
    value = _int_auto(text)
    if value <= 0 or value > 0xFFFF:
        raise ValueError(f"point count must be in 1..65535: {text!r}")
    return value


def _dedupe_preserve_order(values: Sequence[str | int]) -> list[str | int]:
    seen: set[str | int] = set()
    ordered: list[str | int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _parse_extended_device_word_probe(text: str, *, default_direct_memory: int) -> ExtendedDeviceWordProbeSpec:
    parts = next(csv.reader([text], skipinitialspace=True))
    if len(parts) not in {3, 4}:
        raise ValueError("probe must be LABEL,DEVICE,WRITE_VALUE[,DIRECT_MEMORY]")
    label = parts[0].strip()
    device = parts[1].strip()
    if not label:
        raise ValueError("probe label must not be empty")
    if not device:
        raise ValueError("probe device must not be empty")
    preferred_write_value = _int_auto(parts[2].strip())
    direct_memory = default_direct_memory if len(parts) == 3 else _int_auto(parts[3].strip())
    return ExtendedDeviceWordProbeSpec(
        label=label,
        device=device,
        preferred_write_value=preferred_write_value,
        direct_memory_specification=direct_memory,
    )


def _make_frame_dump_trace_hook(
    *,
    dump_dir_ref: list[Path | None],
) -> tuple[Callable[[SlmpTraceFrame], None], list[int]]:
    trace_counter = [0]

    def _trace_hook(trace: SlmpTraceFrame) -> None:
        dump_dir = dump_dir_ref[0]
        if dump_dir is None:
            return
        trace_counter[0] += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        end_txt = "NONE" if trace.response_end_code is None else f"{trace.response_end_code:04X}"
        base = f"{trace_counter[0]:04d}_{ts}_cmd{trace.command:04X}_sub{trace.subcommand:04X}_end{end_txt}"
        (dump_dir / f"{base}_request.hex.txt").write_text(trace.request_frame.hex(" ").upper(), encoding="utf-8")
        (dump_dir / f"{base}_response.hex.txt").write_text(trace.response_frame.hex(" ").upper(), encoding="utf-8")

    return _trace_hook, trace_counter


def _run_extended_device_word_probe(
    client: SlmpClient,
    *,
    item_name: str,
    device: str,
    preferred_write_value: int,
    extension: ExtensionSpec,
    series: str,
    restore_enabled: bool,
    record: Callable[[str, str, str], None],
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SlmpPracticalPathWarning)
        before_values = client.read_devices_ext(device, 1, extension=extension, bit_unit=False, series=series)
        before = int(before_values[0])
        write_value = _choose_probe_word_value(current=before, preferred=preferred_write_value)
        client.write_devices_ext(device, [write_value], extension=extension, bit_unit=False, series=series)
        readback_values = client.read_devices_ext(device, 1, extension=extension, bit_unit=False, series=series)
        readback = int(readback_values[0])

        detail_parts = [
            f"device={device}",
            f"before=0x{before:04X}",
            f"write=0x{write_value:04X}",
            f"readback=0x{readback:04X}",
        ]

        if readback != write_value:
            record(item_name, "NG", ", ".join(detail_parts + ["readback_mismatch=yes"]))
            return

        if not restore_enabled:
            record(item_name, "OK", ", ".join(detail_parts + ["restore=disabled"]))
            return

        client.write_devices_ext(device, [before], extension=extension, bit_unit=False, series=series)
        restored_values = client.read_devices_ext(device, 1, extension=extension, bit_unit=False, series=series)
        restored = int(restored_values[0])
        detail_parts.append(f"restored=0x{restored:04X}")
        if restored != before:
            record(item_name, "NG", ", ".join(detail_parts + ["restore_mismatch=yes"]))
            return

        record(item_name, "OK", ", ".join(detail_parts + ["restore=ok"]))


def _run_extended_device_word_span_probe(
    client: SlmpClient,
    *,
    item_name: str,
    device: str,
    points: int,
    preferred_write_value: int,
    extension: ExtensionSpec,
    series: str,
    restore_enabled: bool,
    write_check: bool,
    record: Callable[[str, str, str], None],
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SlmpPracticalPathWarning)
        before_values = [
            int(value) & 0xFFFF
            for value in client.read_devices_ext(
                device,
                points,
                extension=extension,
                bit_unit=False,
                series=series,
            )
        ]
        if len(before_values) != points:
            record(
                item_name,
                "NG",
                f"device={device}, points={points}, read_count={len(before_values)}, expected_points={points}",
            )
            return

        detail_parts = [
            f"device={device}",
            f"points={points}",
            f"before={_format_word_values(before_values)}",
        ]

        if not write_check:
            record(item_name, "OK", ", ".join(detail_parts + ["mode=read_only"]))
            return

        write_values = _choose_probe_word_values(current_values=before_values, preferred_base=preferred_write_value)
        client.write_devices_ext(device, write_values, extension=extension, bit_unit=False, series=series)
        readback_values = [
            int(value) & 0xFFFF
            for value in client.read_devices_ext(device, points, extension=extension, bit_unit=False, series=series)
        ]
        detail_parts.extend(
            [
                f"write={_format_word_values(write_values)}",
                f"readback={_format_word_values(readback_values)}",
            ]
        )
        if readback_values != write_values:
            record(item_name, "NG", ", ".join(detail_parts + ["readback_mismatch=yes"]))
            return

        if not restore_enabled:
            record(item_name, "OK", ", ".join(detail_parts + ["restore=disabled"]))
            return

        client.write_devices_ext(device, before_values, extension=extension, bit_unit=False, series=series)
        restored_values = [
            int(value) & 0xFFFF
            for value in client.read_devices_ext(device, points, extension=extension, bit_unit=False, series=series)
        ]
        detail_parts.append(f"restored={_format_word_values(restored_values)}")
        if restored_values != before_values:
            record(item_name, "NG", ", ".join(detail_parts + ["restore_mismatch=yes"]))
            return

        record(item_name, "OK", ", ".join(detail_parts + ["restore=ok"]))


def _percentile_value(samples: Sequence[float], percentile: float) -> float:
    if not samples:
        raise ValueError("samples must not be empty")
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    rank = percentile * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    fraction = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def _summarize_durations(durations: Sequence[float], *, elapsed_s: float | None = None) -> LatencySummary:
    if not durations:
        raise ValueError("durations must not be empty")
    total_elapsed = float(elapsed_s) if elapsed_s is not None else float(sum(durations))
    avg = sum(durations) / len(durations)
    return LatencySummary(
        count=len(durations),
        avg_ms=avg * 1000.0,
        p95_ms=_percentile_value(durations, 0.95) * 1000.0,
        p99_ms=_percentile_value(durations, 0.99) * 1000.0,
        max_ms=max(durations) * 1000.0,
        elapsed_s=total_elapsed,
        rate_per_s=(len(durations) / total_elapsed) if total_elapsed > 0 else 0.0,
    )


def _format_counter(counter: dict[str, int] | Sequence[tuple[str, int]]) -> str:
    items = counter.items() if isinstance(counter, dict) else counter
    rendered = [f"{key}={value}" for key, value in items if value]
    return ", ".join(rendered) if rendered else "none"


def _raw_device_read(
    client: SlmpClient,
    *,
    device: str,
    points: int,
    bit_unit: bool,
    series: str,
) -> tuple[int, object | None]:
    resolved_series = PLCSeries(series) if series else client.plc_series
    subcommand = resolve_device_subcommand(bit_unit=bit_unit, series=resolved_series, extension=False)
    payload = encode_device_spec(device, series=resolved_series)
    payload += points.to_bytes(2, "little")
    resp = client.request(Command.DEVICE_READ, subcommand=subcommand, data=payload, raise_on_error=False)
    values: object | None = None
    if resp.end_code == 0:
        values = unpack_bit_values(resp.data, points) if bit_unit else decode_device_words(resp.data)
    return resp.end_code, values


def _raw_device_write(
    client: SlmpClient,
    *,
    device: str,
    values: Sequence[int | bool],
    bit_unit: bool,
    series: str,
) -> int:
    resolved_series = PLCSeries(series) if series else client.plc_series
    subcommand = resolve_device_subcommand(bit_unit=bit_unit, series=resolved_series, extension=False)
    payload = bytearray()
    payload += encode_device_spec(device, series=resolved_series)
    payload += len(values).to_bytes(2, "little")
    if bit_unit:
        payload += pack_bit_values(values)
    else:
        for value in values:
            payload += int(value).to_bytes(2, "little", signed=False)
    resp = client.request(Command.DEVICE_WRITE, subcommand=subcommand, data=bytes(payload), raise_on_error=False)
    return resp.end_code


def _known_boundary_probe_limitation(device: str, series: str) -> str | None:
    if series != "iqr":
        return None
    code = parse_device(device).code
    if code in {"LTC", "LTS", "LSTC", "LSTS"}:
        return "known direct-path issue on validated iQ-R target"
    return None


def connection_check_main(argv: Sequence[str] | None = None) -> int:
    """Perform SLMP binary connection check."""
    parser = argparse.ArgumentParser(description="SLMP binary connection check")
    parser.add_argument("--host", required=True, help="PLC IP address or host name")
    parser.add_argument("--port", type=int, default=5000, help="SLMP port (default: 5000)")
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="ql")
    parser.add_argument(
        "--frame-type",
        choices=("3e", "4e"),
        default="3e",
        help="frame type used for the connection check (default: 3e)",
    )
    parser.add_argument(
        "--compatibility-policy",
        help=(f"optional compatibility policy JSON; defaults to {_compatibility_default_policy_output()} when present"),
    )
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="e.g. 0x0010")
    parser.add_argument("--network", type=_int_auto, default=0x00, help="e.g. 0x00")
    parser.add_argument("--station", type=_int_auto, default=0xFF, help="e.g. 0xFF")
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF, help="e.g. 0x03FF")
    parser.add_argument("--multidrop", type=_int_auto, default=0x00, help="e.g. 0x00")
    parser.add_argument("--read-device", help="optional device read test, e.g. D100 or M10")
    parser.add_argument("--points", type=int, default=1, help="points for --read-device")
    parser.add_argument("--bit-unit", action="store_true", help="read in bit units")
    parser.add_argument(
        "--dump-frame-dir",
        help="optional directory to dump request/response frames as hex text files",
    )
    parser.add_argument(
        "--extended_device",
        nargs="+",
        choices=("all", "j", "u", "cpu"),
        help="Extended Device extension check target(s): j(link direct), u(module access), cpu(cpu buffer)",
    )
    parser.add_argument("--extended_device-points", type=int, default=1, help="points for Extended Device checks")
    parser.add_argument("--extended_device-bit-unit", action="store_true", help="bit unit for Extended Device J check")
    parser.add_argument("--extended_device-j-device", default="W100", help="J check device (default: W100)")
    parser.add_argument(
        "--extended_device-j-network", type=_int_auto, default=0x0001, help="J extension spec (network no.)"
    )
    parser.add_argument("--extended_device-u-device", default="G0", help="U check device (default: G0)")
    parser.add_argument(
        "--extended_device-u-io",
        type=_int_auto,
        default=0x0000,
        help="U extension spec (start I/O upper 3 digits, default: 0x0000)",
    )
    parser.add_argument("--extended_device-cpu-device", default="G0", help="CPU buffer check device (default: G0)")
    parser.add_argument(
        "--extended_device-cpu-io",
        type=_int_auto,
        default=0x03E0,
        help="CPU buffer extension spec (default: 0x03E0)",
    )
    parser.add_argument(
        "--extended_device-ext-mod",
        type=_int_auto,
        default=0x00,
        help="extension specification modification (index register no.)",
    )
    parser.add_argument(
        "--extended_device-dev-mod-index",
        type=_int_auto,
        default=0x00,
        help="device modification index register number",
    )
    parser.add_argument(
        "--extended_device-reg",
        choices=("none", "z", "lz"),
        default="none",
        help="device modification register mode",
    )
    parser.add_argument(
        "--extended_device-indirect",
        action="store_true",
        help="use indirect specification flag (@)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    extended_device_targets = _resolve_extended_device_targets(args.extended_device)

    dump_dir: Path | None = None
    trace_counter = 0
    if args.dump_frame_dir:
        dump_dir = Path(args.dump_frame_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] Frame dump directory: {dump_dir}")

    def _trace_hook(trace: SlmpTraceFrame) -> None:
        nonlocal trace_counter
        if dump_dir is None:
            return
        trace_counter += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        end_txt = "NONE" if trace.response_end_code is None else f"{trace.response_end_code:04X}"
        base = f"{trace_counter:04d}_{ts}_cmd{trace.command:04X}_sub{trace.subcommand:04X}_end{end_txt}"
        (dump_dir / f"{base}_request.hex.txt").write_text(trace.request_frame.hex(" ").upper(), encoding="utf-8")
        (dump_dir / f"{base}_response.hex.txt").write_text(trace.response_frame.hex(" ").upper(), encoding="utf-8")

    policy = _load_compatibility_policy(args.compatibility_policy)
    candidate_pairs = _policy_candidate_pairs(
        requested_frame_type=args.frame_type,
        requested_series=args.series,
        policy=policy,
    )

    print("=== SLMP Binary Connection Check ===")
    print(f"Host={args.host}, Port={args.port}, Transport={args.transport}, Requested access_profile={args.series}")
    print(f"Requested frame={args.frame_type}")
    print(
        "Target="
        f"network=0x{target.network:02X}, station=0x{target.station:02X}, "
        f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
    )
    print(f"[INFO] Candidate order={_format_candidate_pairs(candidate_pairs)}")
    if policy is not None:
        print("[INFO] Compatibility policy loaded")

    last_error: Exception | None = None
    for frame_type, series_candidate in candidate_pairs:
        try:
            with SlmpClient(
                args.host,
                port=args.port,
                transport=args.transport,
                timeout=args.timeout,
                plc_series=series_candidate,
                frame_type=frame_type,
                default_target=target,
                monitoring_timer=args.monitoring_timer,
                trace_hook=_trace_hook,
            ) as client:
                sm400_series, sm400_values = _probe_sm400_series(client)
                resolved_access_profile = sm400_series
                model = "unknown_target"
                detected_family: str | None = None
                print(f"[INFO] Resolved frame={frame_type.value}, access_profile={resolved_access_profile.value}")
                print("[OK] Read SM400 (0401)")
                print(f"  values={sm400_values}")

                if frame_type == FrameType.FRAME_4E:
                    try:
                        info = client.read_type_name()
                    except Exception as exc:  # noqa: BLE001
                        print(f"[SKIP] Read Type Name (0101): {exc}")
                    else:
                        model = _resolve_type_name_label(info)
                        inferred_series = _resolve_series_from_type_name(info)
                        if inferred_series is not None:
                            resolved_access_profile = inferred_series
                        detected_family = _resolve_detected_family(label=None, model=model)
                        print("[OK] Read Type Name (0101)")
                        print(f"  model_code={_format_model_code(info.model_code)}")
                        print(f"  model={model}")
                        print(f"  raw={info.raw.hex(' ').upper()}")
                        if detected_family is not None:
                            print(f"[INFO] Detected family={detected_family}")
                        print(f"[INFO] Type name suggests access_profile={resolved_access_profile.value}")
                        if policy is not None:
                            preferred_profiles = _policy_preferred_profiles(
                                policy,
                                model=model,
                                family=detected_family,
                            )
                            print(f"[INFO] Policy preferred profiles={', '.join(preferred_profiles)}")

                if extended_device_targets and dump_dir is None:
                    dump_dir = _resolve_capture_dir(
                        output_dir=None,
                        series=resolved_access_profile.value,
                        model=model,
                        dirname="frame_dumps_extended_device",
                    )
                    dump_dir.mkdir(parents=True, exist_ok=True)
                    print(f"[INFO] Frame dump directory: {dump_dir}")

                if args.read_device:
                    values = client.read_devices(
                        args.read_device,
                        args.points,
                        bit_unit=args.bit_unit,
                        series=resolved_access_profile,
                    )
                    print(
                        f"[OK] Read Device (0401): device={args.read_device}, "
                        f"points={args.points}, bit_unit={args.bit_unit}"
                    )
                    print(f"  values={values}")

                failures: list[tuple[str, str]] = []
                if extended_device_targets:
                    print("[INFO] Extended Device extension checks")

                    def _run_ext_check(
                        name: str,
                        *,
                        device: str,
                        ext_spec: int,
                        direct_mem: int,
                        resolved_series: PLCSeries,
                        failures: list[tuple[str, str]],
                        bit_unit: bool = False,
                    ) -> None:
                        try:
                            ext = client.make_extension_spec(
                                extension_specification=ext_spec,
                                extension_specification_modification=args.extended_device_ext_mod,
                                device_modification_index=args.extended_device_dev_mod_index,
                                use_indirect_specification=args.extended_device_indirect,
                                register_mode=args.extended_device_reg,
                                direct_memory_specification=direct_mem,
                                series=resolved_series.value,
                            )
                            values = client.read_devices_ext(
                                device,
                                args.extended_device_points,
                                extension=ext,
                                bit_unit=bit_unit,
                                series=resolved_series.value,
                            )
                            print(
                                f"[OK] extended_device {name}: device={device}, points={args.extended_device_points}, "
                                f"ext=0x{ext_spec:04X}, direct_mem=0x{direct_mem:02X}"
                            )
                            print(f"  values={values}")
                        except Exception as exc:  # noqa: BLE001
                            failures.append((name, str(exc)))
                            print(f"[NG] extended_device {name}: {exc}")

                    if "j" in extended_device_targets:
                        _run_ext_check(
                            "J(link direct)",
                            device=args.extended_device_j_device,
                            ext_spec=args.extended_device_j_network,
                            direct_mem=DIRECT_MEMORY_LINK_DIRECT,
                            bit_unit=args.extended_device_bit_unit,
                            resolved_series=resolved_access_profile,
                            failures=failures,
                        )
                    if "u" in extended_device_targets:
                        _run_ext_check(
                            "U(module access)",
                            device=args.extended_device_u_device,
                            ext_spec=args.extended_device_u_io,
                            direct_mem=DIRECT_MEMORY_MODULE_ACCESS,
                            bit_unit=False,
                            resolved_series=resolved_access_profile,
                            failures=failures,
                        )
                    if "cpu" in extended_device_targets:
                        _run_ext_check(
                            "CPU buffer",
                            device=args.extended_device_cpu_device,
                            ext_spec=args.extended_device_cpu_io,
                            direct_mem=DIRECT_MEMORY_CPU_BUFFER,
                            bit_unit=False,
                            resolved_series=resolved_access_profile,
                            failures=failures,
                        )

                    if failures:
                        print("[RESULT] Extended Device checks failed:")
                        for name, reason in failures:
                            print(f"  - {name}: {reason}")
                        return 2

                print("=== COMPLETED ===")
                return 0
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    print(f"[NG] Connection check failed: {last_error}")
    return 2


def extended_device_device_recheck_main(argv: Sequence[str] | None = None) -> int:
    """Recheck Extended Device word-device read-write-readback with restore."""
    parser = argparse.ArgumentParser(description="Recheck Extended Device word-device read-write-readback with restore")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="ql")
    parser.add_argument(
        "--frame-type",
        choices=("3e", "4e"),
        default="3e",
        help="frame type used for the connection check (default: 3e)",
    )
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="e.g. 0x0010")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument(
        "--probe",
        action="append",
        help="LABEL,DEVICE,WRITE_VALUE[,DIRECT_MEMORY], repeatable",
    )
    parser.add_argument(
        "--extension-specification",
        type=_int_auto,
        default=0x0000,
        help="base Extended Device extension specification for unqualified devices",
    )
    parser.add_argument(
        "--direct-memory",
        type=_int_auto,
        default=DIRECT_MEMORY_MODULE_ACCESS,
        help="default direct memory specification when a probe omits its fourth field",
    )
    parser.add_argument(
        "--keep-written-value",
        action="store_true",
        help="leave the temporary value written instead of restoring the original value",
    )
    parser.add_argument("--dump-frame-dir", help="optional directory for request/response hex dumps")
    parser.add_argument(
        "--output",
        help=(
            "optional markdown output path; default is "
            "internal_docs/<series>_<model>/extended_device_device_recheck_latest.md"
        ),
    )
    parser.add_argument(
        "--extended_device-ext-mod",
        type=_int_auto,
        default=0x00,
        help="extension specification modification (index register no.)",
    )
    parser.add_argument(
        "--extended_device-dev-mod-index",
        type=_int_auto,
        default=0x00,
        help="device modification index register number",
    )
    parser.add_argument(
        "--extended_device-reg",
        choices=("none", "z", "lz"),
        default="none",
        help="device modification register mode",
    )
    parser.add_argument(
        "--extended_device-indirect",
        action="store_true",
        help="use indirect specification flag (@)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.probe:
        parser.error("at least one --probe is required")

    try:
        probes = [
            _parse_extended_device_word_probe(text, default_direct_memory=args.direct_memory) for text in args.probe
        ]
    except ValueError as exc:
        parser.error(str(exc))

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="extended_device_device_recheck_latest.md",
        monitoring_timer=args.monitoring_timer,
    )

    dump_dir_ref: list[Path | None] = [None]
    if args.dump_frame_dir:
        dump_dir = Path(args.dump_frame_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir_ref[0] = dump_dir
    trace_hook, _ = _make_frame_dump_trace_hook(dump_dir_ref=dump_dir_ref)

    rows: list[tuple[str, str, str]] = []

    def record(item: str, status: str, detail: str) -> None:
        rows.append((item, status, detail))
        print(f"[{status}] {item}: {detail}")

    print("=== Extended Device Device Recheck ===")
    print(f"Host={args.host}, Port={args.port}, Transport={args.transport}, Series={args.series}")
    print(
        "Target="
        f"network=0x{target.network:02X}, station=0x{target.station:02X}, "
        f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
    )

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
        monitoring_timer=args.monitoring_timer,
        trace_hook=trace_hook,
    ) as cli:
        info = cli.read_type_name()
        model = info.model or "unknown_target"
        print(f"[OK] Read Type Name: model={model}, model_code={_format_model_code(info.model_code)}")
        if dump_dir_ref[0] is None:
            dump_dir_ref[0] = _resolve_capture_dir(
                output_dir=None,
                series=args.series,
                model=model,
                dirname="frame_dumps_extended_device_device_recheck",
            )
            resolved_dump_dir = dump_dir_ref[0]
            assert resolved_dump_dir is not None
            resolved_dump_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] Frame dump directory: {dump_dir_ref[0]}")

        restore_enabled = not args.keep_written_value
        for probe in probes:
            extension = cli.make_extension_spec(
                extension_specification=args.extension_specification,
                extension_specification_modification=args.extended_device_ext_mod,
                device_modification_index=args.extended_device_dev_mod_index,
                use_indirect_specification=args.extended_device_indirect,
                register_mode=args.extended_device_reg,
                direct_memory_specification=probe.direct_memory_specification,
                series=args.series,
            )
            try:
                _run_extended_device_word_probe(
                    cli,
                    item_name=probe.label,
                    device=probe.device,
                    preferred_write_value=probe.preferred_write_value,
                    extension=extension,
                    series=args.series,
                    restore_enabled=restore_enabled,
                    record=record,
                )
            except Exception as exc:  # noqa: BLE001
                record(probe.label, "NG", str(exc))

    summary = Counter(status for _, status, _ in rows)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_lines = [
        f"- Date: {now}",
        f"- Host: {args.host}",
        f"- Port: {args.port}",
        f"- Transport: {args.transport}",
        f"- Series: {args.series}",
        (
            f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
            f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
        ),
        f"- Base extension specification: 0x{args.extension_specification:04X}",
        f"- Default direct memory specification: 0x{args.direct_memory:02X}",
        f"- Restore enabled: {'no' if args.keep_written_value else 'yes'}",
        f"- Summary: OK={summary['OK']}, NG={summary['NG']}, SKIP={summary['SKIP']}",
    ]
    for probe in probes:
        header_lines.append(
            f"- Probe: {probe.label}, device={probe.device}, "
            f"preferred_write=0x{probe.preferred_write_value & 0xFFFF:04X}, "
            f"direct_memory=0x{probe.direct_memory_specification:02X}"
        )
    _write_markdown_report(
        output_path,
        title="# Extended Device Device Recheck Report",
        header_lines=header_lines,
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if summary["NG"] == 0 else 2


def g_hg_extended_device_recheck_main(argv: Sequence[str] | None = None) -> int:
    """Recheck iQ-R Extended Device G/HG read-write-readback with restore."""
    parser = argparse.ArgumentParser(description="Recheck iQ-R Extended Device G/HG read-write-readback with restore")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="e.g. 0x0010")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument("--cpu-io", type=_int_auto, default=0x03E0, help="CPU buffer extension spec")
    parser.add_argument("--g-device", default="G10", help="Extended Device G device to probe")
    parser.add_argument("--hg-device", default="HG20", help="Extended Device HG device to probe")
    parser.add_argument(
        "--g-write-value",
        type=_int_auto,
        default=0x001E,
        help="preferred temporary write value for G",
    )
    parser.add_argument(
        "--hg-write-value",
        type=_int_auto,
        default=0x0032,
        help="preferred temporary write value for HG",
    )
    parser.add_argument(
        "--keep-written-value",
        action="store_true",
        help="leave the temporary value written instead of restoring the original value",
    )
    parser.add_argument("--dump-frame-dir", help="optional directory for request/response hex dumps")
    parser.add_argument(
        "--output",
        help=(
            "optional markdown output path; default is "
            "internal_docs/<series>_<model>/g_hg_extended_device_recheck_latest.md"
        ),
    )
    parser.add_argument(
        "--extended_device-ext-mod",
        type=_int_auto,
        default=0x00,
        help="extension specification modification (index register no.)",
    )
    parser.add_argument(
        "--extended_device-dev-mod-index",
        type=_int_auto,
        default=0x00,
        help="device modification index register number",
    )
    parser.add_argument(
        "--extended_device-reg",
        choices=("none", "z", "lz"),
        default="none",
        help="device modification register mode",
    )
    parser.add_argument(
        "--extended_device-indirect",
        action="store_true",
        help="use indirect specification flag (@)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="g_hg_extended_device_recheck_latest.md",
        monitoring_timer=args.monitoring_timer,
    )

    dump_dir: Path | None = None
    trace_counter = 0
    if args.dump_frame_dir:
        dump_dir = Path(args.dump_frame_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)

    def _trace_hook(trace: SlmpTraceFrame) -> None:
        nonlocal trace_counter
        if dump_dir is None:
            return
        trace_counter += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        end_txt = "NONE" if trace.response_end_code is None else f"{trace.response_end_code:04X}"
        base = f"{trace_counter:04d}_{ts}_cmd{trace.command:04X}_sub{trace.subcommand:04X}_end{end_txt}"
        (dump_dir / f"{base}_request.hex.txt").write_text(trace.request_frame.hex(" ").upper(), encoding="utf-8")
        (dump_dir / f"{base}_response.hex.txt").write_text(trace.response_frame.hex(" ").upper(), encoding="utf-8")

    rows: list[tuple[str, str, str]] = []

    def record(item: str, status: str, detail: str) -> None:
        rows.append((item, status, detail))
        print(f"[{status}] {item}: {detail}")

    print("=== G/HG Extended Device Recheck ===")
    print(f"Host={args.host}, Port={args.port}, Transport={args.transport}, Series={args.series}")
    print(
        "Target="
        f"network=0x{target.network:02X}, station=0x{target.station:02X}, "
        f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
    )

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
        monitoring_timer=args.monitoring_timer,
        trace_hook=_trace_hook,
    ) as cli:
        info = cli.read_type_name()
        model = info.model or "unknown_target"
        print(f"[OK] Read Type Name: model={model}, model_code={_format_model_code(info.model_code)}")
        if dump_dir is None:
            dump_dir = _resolve_capture_dir(
                output_dir=None,
                series=args.series,
                model=model,
                dirname="frame_dumps_extended_device_g_hg_recheck",
            )
            dump_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] Frame dump directory: {dump_dir}")

        extension = cli.make_extension_spec(
            extension_specification=args.cpu_io,
            extension_specification_modification=args.extended_device_ext_mod,
            device_modification_index=args.extended_device_dev_mod_index,
            use_indirect_specification=args.extended_device_indirect,
            register_mode=args.extended_device_reg,
            direct_memory_specification=DIRECT_MEMORY_CPU_BUFFER,
            series=args.series,
        )

        restore_enabled = not args.keep_written_value

        def run_probe(item_name: str, *, device: str, preferred_write_value: int) -> None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SlmpPracticalPathWarning)
                before_values = cli.read_devices_ext(device, 1, extension=extension, bit_unit=False, series=args.series)
                before = int(before_values[0])
                write_value = _choose_probe_word_value(current=before, preferred=preferred_write_value)
                cli.write_devices_ext(device, [write_value], extension=extension, bit_unit=False, series=args.series)
                readback_values = cli.read_devices_ext(
                    device,
                    1,
                    extension=extension,
                    bit_unit=False,
                    series=args.series,
                )
                readback = int(readback_values[0])

                detail_parts = [
                    f"device={device}",
                    f"before=0x{before:04X}",
                    f"write=0x{write_value:04X}",
                    f"readback=0x{readback:04X}",
                ]

                if readback != write_value:
                    record(item_name, "NG", ", ".join(detail_parts + ["readback_mismatch=yes"]))
                    return

                if not restore_enabled:
                    record(item_name, "OK", ", ".join(detail_parts + ["restore=disabled"]))
                    return

                cli.write_devices_ext(device, [before], extension=extension, bit_unit=False, series=args.series)
                restored_values = cli.read_devices_ext(
                    device,
                    1,
                    extension=extension,
                    bit_unit=False,
                    series=args.series,
                )
                restored = int(restored_values[0])
                detail_parts.append(f"restored=0x{restored:04X}")
                if restored != before:
                    record(item_name, "NG", ", ".join(detail_parts + ["restore_mismatch=yes"]))
                    return

                record(item_name, "OK", ", ".join(detail_parts + ["restore=ok"]))

        try:
            run_probe(
                "G extended_device read/write/readback", device=args.g_device, preferred_write_value=args.g_write_value
            )
        except Exception as exc:  # noqa: BLE001
            record("G extended_device read/write/readback", "NG", str(exc))
        try:
            run_probe(
                "HG extended_device read/write/readback",
                device=args.hg_device,
                preferred_write_value=args.hg_write_value,
            )
        except Exception as exc:  # noqa: BLE001
            record("HG extended_device read/write/readback", "NG", str(exc))

    summary = Counter(status for _, status, _ in rows)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_markdown_report(
        output_path,
        title="# G/HG Extended Device Recheck Report",
        header_lines=[
            f"- Date: {now}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            (
                f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
                f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
            ),
            f"- CPU I/O: 0x{args.cpu_io:04X}",
            f"- G device: {args.g_device} (preferred write=0x{args.g_write_value & 0xFFFF:04X})",
            f"- HG device: {args.hg_device} (preferred write=0x{args.hg_write_value & 0xFFFF:04X})",
            f"- Restore enabled: {'no' if args.keep_written_value else 'yes'}",
            f"- Summary: OK={summary['OK']}, NG={summary['NG']}, SKIP={summary['SKIP']}",
        ],
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if summary["NG"] == 0 else 2


def other_station_check_main(argv: Sequence[str] | None = None) -> int:
    """Verify SLMP access to other targets/stations."""
    parser = argparse.ArgumentParser(description="Verify SLMP access to other targets/stations")
    parser.add_argument("--host", required=True, help="PLC IP address or host name")
    parser.add_argument("--port", type=int, default=1025, help="SLMP port")
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--frame-type", choices=("3e", "4e"), default="4e")
    parser.add_argument(
        "--compatibility-policy",
        help=(f"optional compatibility policy JSON; defaults to {_compatibility_default_policy_output()} when present"),
    )
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="e.g. 0x0010")
    parser.add_argument(
        "--target",
        action="append",
        help="SELF, SELF-CPU1..4, NWx-STy, or NAME,NETWORK,STATION,MODULE_IO,MULTIDROP (repeatable)",
    )
    parser.add_argument(
        "--target-file",
        help=(
            "optional UTF-8 file with one SELF, SELF-CPU1..4, NWx-STy, "
            "or NAME,NETWORK,STATION,MODULE_IO,MULTIDROP per line"
        ),
    )
    parser.add_argument("--read-device", default="D1000", help="device for optional read verification")
    parser.add_argument("--points", type=int, default=1, help="points for --read-device")
    parser.add_argument("--bit-unit", action="store_true", help="read in bit units")
    parser.add_argument(
        "--skip-device-read",
        action="store_true",
        help="reserved for compatibility; other-station checks now use 0401 only",
    )
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is internal_docs/<series>_<model>/other_station_check_latest.md",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        targets = _load_named_targets(args.target, args.target_file)
    except Exception as exc:  # noqa: BLE001
        parser.error(str(exc))

    rows: list[tuple[str, str, str]] = []
    failures = 0
    resolved_series_for_output: str | None = None
    resolved_frame_for_output: str | None = None
    resolved_access_profile_for_output: str | None = None
    resolved_model_for_output: str | None = None
    resolved_family_for_output: str | None = None
    policy = _load_compatibility_policy(args.compatibility_policy)

    def add(item: str, status: str, detail: str) -> None:
        nonlocal failures
        rows.append((item, status, detail))
        print(f"[{status}] {item}: {detail}")
        if status != "OK":
            failures += 1

    for entry in targets:
        target = entry.target
        target_text = (
            f"name={entry.name}, network=0x{target.network:02X}, station=0x{target.station:02X}, "
            f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
        )
        candidate_pairs = _policy_candidate_pairs(
            requested_frame_type=args.frame_type,
            requested_series=args.series,
            policy=policy,
            label=entry.name,
        )
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", SlmpPracticalPathWarning)
                resolved_frame, resolved_series, device_values = _probe_device_read_with_frame_and_series(
                    host=args.host,
                    port=args.port,
                    transport=args.transport,
                    timeout=args.timeout,
                    target=target,
                    monitoring_timer=args.monitoring_timer,
                    device=args.read_device,
                    points=args.points,
                    bit_unit=args.bit_unit,
                    frame_candidates=[frame_type for frame_type, _ in candidate_pairs],
                    series_candidates=[series for _, series in candidate_pairs],
                    candidate_pairs=candidate_pairs,
                )
            warning_text = ""
            if caught:
                warning_text = " warnings=" + "; ".join(str(item.message) for item in caught)
            if resolved_series_for_output is None:
                resolved_series_for_output = resolved_series.value
            if resolved_frame_for_output is None:
                resolved_frame_for_output = resolved_frame.value
            if resolved_access_profile_for_output is None:
                resolved_access_profile_for_output = resolved_series.value
            print(f"[INFO] Candidate order={_format_candidate_pairs(candidate_pairs)}")
            if policy is not None:
                print("[INFO] Compatibility policy loaded")
            print(f"[INFO] Resolved frame={resolved_frame.value}, access_profile={resolved_series.value}")
            type_name_text = ""
            try:
                info = _read_type_name_with_frame_and_series(
                    host=args.host,
                    port=args.port,
                    transport=args.transport,
                    timeout=args.timeout,
                    target=target,
                    monitoring_timer=args.monitoring_timer,
                    frame_type=resolved_frame,
                    series=resolved_series,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[INFO] Read Type Name unavailable: error={exc}")
                type_name_text = f", type_name_error={exc}"
            else:
                model_label = _resolve_type_name_label(info)
                model_code_text = _format_model_code(info.model_code)
                model_series = _resolve_series_from_type_name(info)
                detected_family = _resolve_detected_family(label=entry.name, model=model_label)
                print(f"[INFO] Read Type Name: model={model_label}, model_code={model_code_text}")
                if detected_family is not None:
                    print(f"[INFO] Detected family={detected_family}")
                type_name_text = f", model={model_label}, model_code={model_code_text}"
                if resolved_model_for_output is None:
                    resolved_model_for_output = model_label
                if detected_family is not None and resolved_family_for_output is None:
                    resolved_family_for_output = detected_family
                if model_series is not None:
                    resolved_series_for_output = model_series.value
                if policy is not None:
                    preferred_profiles = _policy_preferred_profiles(
                        policy,
                        label=entry.name,
                        model=model_label,
                        family=detected_family,
                    )
                    print(f"[INFO] Policy preferred profiles={', '.join(preferred_profiles)}")
                if detected_family is not None:
                    type_name_text += f", detected_family={detected_family}"
            add(
                entry.name,
                "OK",
                (
                    f"{target_text}, access_profile={resolved_series.value}, "
                    f"device={args.read_device}, points={args.points}, bit_unit={args.bit_unit}, "
                    f"values={device_values}{type_name_text}{warning_text}"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            add(f"{entry.name}", "NG", f"{target_text}, error={exc}")

    if args.output:
        output_path = args.output
    else:
        output_path = _default_report_output(
            series=resolved_series_for_output or (args.series if args.series != "auto" else "ql"),
            model=resolved_model_for_output or "unknown_target",
            filename="other_station_check_latest.md",
        )

    q_practical_note = None
    if (
        any(entry.name != _SELF_TARGET_NAME for entry in targets)
        and resolved_model_for_output is None
        and args.series in {"auto", "ql"}
    ):
        q_practical_note = (
            "Validated Q26UDEHCPU built-in Ethernet accepted SELF route probing but timed out on "
            "tested NW1/NW2 other-station probes; compare failures against live routing evidence "
            "before assuming broader Q-series support."
        )
        print(f"[INFO] Practical note: {q_practical_note}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_lines = [
        f"- Date: {now}",
        f"- Host: {args.host}",
        f"- Port: {args.port}",
        f"- Transport: {args.transport}",
        f"- Requested series: {args.series}",
        f"- Requested frame: {args.frame_type}",
        f"- Resolved frame: {resolved_frame_for_output or args.frame_type}",
        f"- Resolved access profile: {resolved_access_profile_for_output or args.series}",
        f"- Targets: {len(targets)}",
        (
            "- Device read: skipped"
            if args.skip_device_read
            else f"- Device read: {args.read_device}, points={args.points}, bit_unit={args.bit_unit}"
        ),
    ]
    if resolved_family_for_output is not None:
        header_lines.append(f"- Detected family: {resolved_family_for_output}")
    if q_practical_note is not None:
        header_lines.append(f"- Practical note: {q_practical_note}")
    _write_markdown_report(
        output_path,
        title="# Other Station Check Report",
        header_lines=header_lines,
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if failures == 0 else 2


def device_range_probe_main(argv: Sequence[str] | None = None) -> int:
    """Probe configured device-range boundaries against a live PLC."""
    parser = argparse.ArgumentParser(description="Probe configured device-range boundaries against a live PLC")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010)
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument(
        "--spec",
        action="append",
        help="LABEL,LAST_DEVICE,UNIT[,SPAN_POINTS] (repeatable), e.g. D,D10239,word or LTN,LTN1023,word,4",
    )
    parser.add_argument(
        "--spec-file",
        help="optional UTF-8 file with one LABEL,LAST_DEVICE,UNIT[,SPAN_POINTS] per line",
    )
    parser.add_argument(
        "--include-writeback",
        action="store_true",
        help="safe same-value writeback at the configured last point when the in-range read succeeds",
    )
    parser.add_argument(
        "--include-out-of-range-write",
        action="store_true",
        help="attempt a write to last+1 using zero/false; use only on a dedicated test PLC",
    )
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is internal_docs/<series>_<model>/device_range_probe_latest.md",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        specs = _load_boundary_specs(args.spec, args.spec_file)
    except Exception as exc:  # noqa: BLE001
        parser.error(str(exc))

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="device_range_probe_latest.md",
    )
    rows: list[tuple[str, str, str]] = []
    summary = {"PASS": 0, "WARN": 0, "NG": 0, "SKIP": 0}

    def add(item: str, status: str, detail: str) -> None:
        rows.append((item, status, detail))
        if status in summary:
            summary[status] += 1
        print(f"[{status}] {item}: {detail}")

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
        monitoring_timer=args.monitoring_timer,
    ) as client:
        for spec in specs:
            try:
                next_device = _increment_device_text(spec.last_device)
                limitation = _known_boundary_probe_limitation(spec.last_device, args.series)

                in_end_code, in_values = _raw_device_read(
                    client,
                    device=spec.last_device,
                    points=spec.span_points,
                    bit_unit=spec.bit_unit,
                    series=args.series,
                )
                in_status = "PASS" if in_end_code == 0 else "WARN"
                in_detail = (
                    f"device={spec.last_device}, points={spec.span_points}, expected=end_code=0x0000, "
                    f"observed=end_code=0x{in_end_code:04X}"
                )
                if in_values is not None:
                    in_detail += f", values={in_values}"
                if limitation:
                    in_detail += f", note={limitation}"
                add(f"{spec.label} in-range read", in_status, in_detail)

                if in_end_code != 0:
                    skip_detail = (
                        f"baseline in-range read failed with end_code=0x{in_end_code:04X}; "
                        "boundary behavior is not isolated"
                    )
                    add(f"{spec.label} crossing read", "SKIP", skip_detail)
                    add(f"{spec.label} out-of-range read", "SKIP", skip_detail)
                    if args.include_writeback:
                        add(f"{spec.label} in-range same-value writeback", "SKIP", skip_detail)
                    if args.include_out_of_range_write:
                        add(f"{spec.label} out-of-range write", "SKIP", skip_detail)
                    continue

                cross_end_code, cross_values = _raw_device_read(
                    client,
                    device=spec.last_device,
                    points=spec.span_points + 1,
                    bit_unit=spec.bit_unit,
                    series=args.series,
                )
                cross_status = "PASS" if cross_end_code != 0 else "WARN"
                cross_detail = (
                    f"device={spec.last_device}, points={spec.span_points + 1}, expected=end_code!=0x0000, "
                    f"observed=end_code=0x{cross_end_code:04X}"
                )
                if cross_values is not None:
                    cross_detail += f", values={cross_values}"
                add(f"{spec.label} crossing read", cross_status, cross_detail)

                out_end_code, out_values = _raw_device_read(
                    client,
                    device=next_device,
                    points=1,
                    bit_unit=spec.bit_unit,
                    series=args.series,
                )
                out_status = "PASS" if out_end_code != 0 else "WARN"
                out_detail = (
                    f"device={next_device}, points=1, expected=end_code!=0x0000, observed=end_code=0x{out_end_code:04X}"
                )
                if out_values is not None:
                    out_detail += f", values={out_values}"
                add(f"{spec.label} out-of-range read", out_status, out_detail)

                if args.include_writeback:
                    if not isinstance(in_values, list) or len(in_values) != spec.span_points:
                        add(
                            f"{spec.label} in-range same-value writeback",
                            "SKIP",
                            f"unexpected in-range readback payload for points={spec.span_points}: {in_values}",
                        )
                    else:
                        write_end_code = _raw_device_write(
                            client,
                            device=spec.last_device,
                            values=in_values,
                            bit_unit=spec.bit_unit,
                            series=args.series,
                        )
                        write_status = "PASS" if write_end_code == 0 else "WARN"
                        add(
                            f"{spec.label} in-range same-value writeback",
                            write_status,
                            (
                                f"device={spec.last_device}, expected=end_code=0x0000, "
                                f"observed=end_code=0x{write_end_code:04X}, values={in_values}"
                            ),
                        )

                if args.include_out_of_range_write:
                    out_write_values: list[int | bool] = [False] if spec.bit_unit else [0]
                    out_write_end_code = _raw_device_write(
                        client,
                        device=next_device,
                        values=out_write_values,
                        bit_unit=spec.bit_unit,
                        series=args.series,
                    )
                    out_write_status = "PASS" if out_write_end_code != 0 else "WARN"
                    add(
                        f"{spec.label} out-of-range write",
                        out_write_status,
                        (
                            f"device={next_device}, expected=end_code!=0x0000, "
                            f"observed=end_code=0x{out_write_end_code:04X}, values={out_write_values}"
                        ),
                    )
            except Exception as exc:  # noqa: BLE001
                add(f"{spec.label}", "NG", f"device={spec.last_device}, error={exc}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_markdown_report(
        output_path,
        title="# Device Range Probe Report",
        header_lines=[
            f"- Date: {now}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            (
                f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
                f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
            ),
            f"- Specs: {len(specs)}",
            f"- Include writeback: {args.include_writeback}",
            f"- Include out-of-range write: {args.include_out_of_range_write}",
            (f"- Summary: PASS={summary['PASS']}, WARN={summary['WARN']}, NG={summary['NG']}, SKIP={summary['SKIP']}"),
        ],
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if summary["WARN"] == 0 and summary["NG"] == 0 else 2


def register_boundary_probe_main(argv: Sequence[str] | None = None) -> int:
    """Probe focused register-boundary behavior against a live PLC."""
    parser = argparse.ArgumentParser(description="Probe focused register-boundary behavior against a live PLC")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument(
        "--spec",
        action="append",
        help=("LABEL,EDGE_DEVICE,UNIT,EDGE_POINTS,NEXT_POINTS (repeatable), e.g. ZR,ZR163839,word,1/2/3/16/64,1/2"),
    )
    parser.add_argument(
        "--spec-file",
        help="optional UTF-8 file with one LABEL,EDGE_DEVICE,UNIT,EDGE_POINTS,NEXT_POINTS per line",
    )
    parser.add_argument(
        "--output",
        help=(
            "optional markdown output path; default is internal_docs/<series>_<model>/register_boundary_probe_latest.md"
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        specs = _load_focused_boundary_specs(args.spec, args.spec_file)
    except Exception as exc:  # noqa: BLE001
        parser.error(str(exc))

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="register_boundary_probe_latest.md",
    )
    rows: list[tuple[str, str, str]] = []
    summary = {"OK": 0, "NG": 0, "SKIP": 0}

    def add(item: str, status: str, detail: str) -> None:
        rows.append((item, status, detail))
        if status in summary:
            summary[status] += 1
        print(f"[{status}] {item}: {detail}")

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
    ) as client:
        for spec in specs:
            next_device = _increment_device_text(spec.edge_device)
            edge_reads: dict[int, object | None] = {}

            for points in spec.edge_points:
                try:
                    end_code, values = _raw_device_read(
                        client,
                        device=spec.edge_device,
                        points=points,
                        bit_unit=spec.bit_unit,
                        series=args.series,
                    )
                    edge_reads[points] = values
                    add(
                        f"{spec.label} read {spec.edge_device} x{points}",
                        "OK",
                        f"end_code=0x{end_code:04X}, values={_format_probe_values(values)}",
                    )
                except Exception as exc:  # noqa: BLE001
                    add(f"{spec.label} read {spec.edge_device} x{points}", "NG", str(exc))

            for points in spec.next_points:
                try:
                    end_code, values = _raw_device_read(
                        client,
                        device=next_device,
                        points=points,
                        bit_unit=spec.bit_unit,
                        series=args.series,
                    )
                    add(
                        f"{spec.label} read {next_device} x{points}",
                        "OK",
                        f"end_code=0x{end_code:04X}, values={_format_probe_values(values)}",
                    )
                except Exception as exc:  # noqa: BLE001
                    add(f"{spec.label} read {next_device} x{points}", "NG", str(exc))

            for points in spec.edge_points:
                values = edge_reads.get(points)
                if not isinstance(values, list) or len(values) != points:
                    add(
                        f"{spec.label} write {spec.edge_device} x{points}",
                        "SKIP",
                        f"same-value writeback skipped because read payload was unavailable: {values}",
                    )
                    continue
                try:
                    end_code = _raw_device_write(
                        client,
                        device=spec.edge_device,
                        values=values,
                        bit_unit=spec.bit_unit,
                        series=args.series,
                    )
                    add(
                        f"{spec.label} write {spec.edge_device} x{points}",
                        "OK",
                        f"end_code=0x{end_code:04X}, values={_format_probe_values(values)}",
                    )
                except Exception as exc:  # noqa: BLE001
                    add(f"{spec.label} write {spec.edge_device} x{points}", "NG", str(exc))

            for points in spec.next_points:
                write_values: list[int | bool] = [False] * points if spec.bit_unit else [0] * points
                try:
                    end_code = _raw_device_write(
                        client,
                        device=next_device,
                        values=write_values,
                        bit_unit=spec.bit_unit,
                        series=args.series,
                    )
                    add(
                        f"{spec.label} write {next_device} x{points}",
                        "OK",
                        f"end_code=0x{end_code:04X}, values={_format_probe_values(write_values)}",
                    )
                except Exception as exc:  # noqa: BLE001
                    add(f"{spec.label} write {next_device} x{points}", "NG", str(exc))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    spec_source = args.spec_file if args.spec_file else ("builtin defaults" if not args.spec else "command line")
    _write_markdown_report(
        output_path,
        title="# Register Boundary Probe Report",
        header_lines=[
            f"- Date: {now}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            (
                f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
                f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
            ),
            f"- Specs: {len(specs)}",
            f"- Spec source: {spec_source}",
            f"- Summary: OK={summary['OK']}, NG={summary['NG']}, SKIP={summary['SKIP']}",
        ],
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if summary["NG"] == 0 else 2


def g_hg_extended_device_coverage_main(argv: Sequence[str] | None = None) -> int:
    """Sweep qualified Extended Device G/HG devices across addresses and point counts."""
    parser = argparse.ArgumentParser(
        description="Sweep qualified Extended Device G/HG devices across addresses and point counts"
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument(
        "--transport",
        choices=("tcp", "udp"),
        action="append",
        help="transport to sweep; repeatable, defaults to tcp",
    )
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="e.g. 0x0010")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument(
        "--target",
        action="append",
        help="optional target override: SELF, SELF-CPU1..4, NWx-STy, or NAME,NETWORK,STATION,MODULE_IO,MULTIDROP",
    )
    parser.add_argument(
        "--target-file",
        help="optional UTF-8 file with one target override per line; same format as --target",
    )
    parser.add_argument(
        "--device",
        action="append",
        help="qualified Extended Device G/HG device such as U3E0\\G10 or U01\\G22; repeatable",
    )
    parser.add_argument(
        "--points",
        action="append",
        type=_parse_positive_u16,
        help="point count to sweep; repeatable, defaults to 1",
    )
    parser.add_argument(
        "--direct-memory",
        action="append",
        type=_int_auto,
        help="Extended Device direct memory specification; repeatable, defaults to 0xFA for iqr and 0xF8 for ql",
    )
    parser.add_argument(
        "--extension-specification",
        type=_int_auto,
        default=0x0000,
        help="base Extended Device extension specification for unqualified devices",
    )
    parser.add_argument(
        "--write-check",
        action="store_true",
        help="perform temporary write/readback/restore instead of read-only coverage",
    )
    parser.add_argument(
        "--preferred-write-base",
        type=_int_auto,
        default=0x001E,
        help="base temporary write value used when --write-check is enabled",
    )
    parser.add_argument(
        "--keep-written-value",
        action="store_true",
        help="leave the temporary values written instead of restoring the original values",
    )
    parser.add_argument("--dump-frame-dir", help="optional directory for request/response hex dumps")
    parser.add_argument(
        "--output",
        help=(
            "optional markdown output path; default is "
            "internal_docs/<series>_<model>/g_hg_extended_device_coverage_latest.md"
        ),
    )
    parser.add_argument(
        "--extended_device-ext-mod",
        type=_int_auto,
        default=0x00,
        help="extension specification modification (index register no.)",
    )
    parser.add_argument(
        "--extended_device-dev-mod-index",
        type=_int_auto,
        default=0x00,
        help="device modification index register number",
    )
    parser.add_argument(
        "--extended_device-reg",
        choices=("none", "z", "lz"),
        default="none",
        help="device modification register mode",
    )
    parser.add_argument(
        "--extended_device-indirect",
        action="store_true",
        help="use indirect specification flag (@)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.device:
        parser.error("at least one --device is required")

    devices = [str(value) for value in _dedupe_preserve_order([item.strip() for item in args.device if item.strip()])]
    if not devices:
        parser.error("at least one non-empty --device is required")
    point_counts = [int(value) for value in _dedupe_preserve_order(args.points or [1])]
    default_direct_memory = DIRECT_MEMORY_CPU_BUFFER if args.series == "iqr" else DIRECT_MEMORY_MODULE_ACCESS
    direct_memories = [int(value) for value in _dedupe_preserve_order(args.direct_memory or [default_direct_memory])]
    transports = [str(value) for value in _dedupe_preserve_order(args.transport or ["tcp"])]

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    targets = (
        _load_named_targets(args.target, args.target_file)
        if args.target or args.target_file
        else [_default_named_target(target)]
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=transports[0],
        timeout=args.timeout,
        target=targets[0].target,
        filename="g_hg_extended_device_coverage_latest.md",
        monitoring_timer=args.monitoring_timer,
    )

    dump_dir_ref: list[Path | None] = [None]
    if args.dump_frame_dir:
        dump_dir = Path(args.dump_frame_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_dir_ref[0] = dump_dir
    trace_hook, _ = _make_frame_dump_trace_hook(dump_dir_ref=dump_dir_ref)

    rows: list[tuple[str, str, str]] = []

    def record(item: str, status: str, detail: str) -> None:
        rows.append((item, status, detail))
        print(f"[{status}] {item}: {detail}")

    print("=== G/HG Extended Device Coverage Sweep ===")
    print(f"Host={args.host}, Port={args.port}, Transports={transports}, Series={args.series}")
    print(f"[INFO] Targets={[entry.name for entry in targets]}")
    print(f"[INFO] Devices={devices}")
    print(f"[INFO] Points={point_counts}")
    print(f"[INFO] Direct memory={[f'0x{value:02X}' for value in direct_memories]}")

    explicit_target_mode = bool(args.target or args.target_file)
    restore_enabled = not args.keep_written_value
    for transport in transports:
        for entry in targets:
            current_target = entry.target
            print(
                "[INFO] Sweep target="
                f"{entry.name}, transport={transport}, network=0x{current_target.network:02X}, "
                f"station=0x{current_target.station:02X}, module_io=0x{int(current_target.module_io):04X}, "
                f"multidrop=0x{current_target.multidrop:02X}"
            )
            with SlmpClient(
                args.host,
                port=args.port,
                transport=transport,
                timeout=args.timeout,
                plc_series=args.series,
                default_target=current_target,
                monitoring_timer=args.monitoring_timer,
                trace_hook=trace_hook,
            ) as cli:
                model = "unknown_target"
                try:
                    info = cli.read_type_name()
                except Exception as exc:  # noqa: BLE001
                    print(f"[INFO] Read Type Name unavailable: target={entry.name}, transport={transport}, error={exc}")
                else:
                    model = _resolve_type_name_label(info)
                    print(
                        "[OK] Read Type Name: "
                        f"target={entry.name}, transport={transport}, model={model}, "
                        f"model_code={_format_model_code(info.model_code)}"
                    )
                if dump_dir_ref[0] is None:
                    dump_dir_ref[0] = _resolve_capture_dir(
                        output_dir=None,
                        series=args.series,
                        model=model,
                        dirname="frame_dumps_g_hg_extended_device_coverage",
                    )
                    resolved_dump_dir = dump_dir_ref[0]
                    assert resolved_dump_dir is not None
                    resolved_dump_dir.mkdir(parents=True, exist_ok=True)
                print(f"[INFO] Frame dump directory: {dump_dir_ref[0]}")

                for direct_memory in direct_memories:
                    extension = cli.make_extension_spec(
                        extension_specification=args.extension_specification,
                        extension_specification_modification=args.extended_device_ext_mod,
                        device_modification_index=args.extended_device_dev_mod_index,
                        use_indirect_specification=args.extended_device_indirect,
                        register_mode=args.extended_device_reg,
                        direct_memory_specification=direct_memory,
                        series=args.series,
                    )
                    for device in devices:
                        for points in point_counts:
                            item_name = f"{device} points={points} direct=0x{direct_memory:02X}"
                            if explicit_target_mode or len(targets) > 1:
                                item_name = f"{entry.name} {item_name}"
                            if len(transports) > 1:
                                item_name = f"{transport} {item_name}"
                            try:
                                _run_extended_device_word_span_probe(
                                    cli,
                                    item_name=item_name,
                                    device=device,
                                    points=points,
                                    preferred_write_value=args.preferred_write_base,
                                    extension=extension,
                                    series=args.series,
                                    restore_enabled=restore_enabled,
                                    write_check=args.write_check,
                                    record=record,
                                )
                            except Exception as exc:  # noqa: BLE001
                                record(item_name, "NG", str(exc))

    summary = Counter(status for _, status, _ in rows)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_lines = [
        f"- Date: {now}",
        f"- Host: {args.host}",
        f"- Port: {args.port}",
        f"- Transports: {', '.join(transports)}",
        f"- Series: {args.series}",
        (
            "- Targets: "
            + "; ".join(
                (
                    f"{entry.name}(network=0x{entry.target.network:02X}, station=0x{entry.target.station:02X}, "
                    f"module_io=0x{int(entry.target.module_io):04X}, multidrop=0x{entry.target.multidrop:02X})"
                )
                for entry in targets
            )
        ),
        f"- Devices: {', '.join(devices)}",
        f"- Point counts: {', '.join(str(value) for value in point_counts)}",
        f"- Direct memory values: {', '.join(f'0x{value:02X}' for value in direct_memories)}",
        f"- Mode: {'write_check' if args.write_check else 'read_only'}",
        f"- Restore enabled: {'no' if args.keep_written_value else 'yes'}",
        f"- Preferred write base: 0x{args.preferred_write_base & 0xFFFF:04X}",
        f"- Summary: OK={summary['OK']}, NG={summary['NG']}, SKIP={summary['SKIP']}",
    ]
    _write_markdown_report(
        output_path,
        title="# G/HG Extended Device Coverage Report",
        header_lines=header_lines,
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if summary["NG"] == 0 else 2


def open_items_recheck_main(argv: Sequence[str] | None = None) -> int:
    """Recheck open SLMP items."""
    parser = argparse.ArgumentParser(description="Recheck open SLMP items")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument("--cpu-io", type=_int_auto, default=0x03E0, help="CPU buffer start I/O")
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is internal_docs/<series>_<model>/open_items_recheck_latest.md",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="open_items_recheck_latest.md",
    )
    rows: list[tuple[str, str, str]] = []

    def record(item: str, status: str, detail: str) -> None:
        rows.append((item, status, detail))
        print(f"[{status}] {item}: {detail}")

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
    ) as cli:
        for dev in ("LSTC0", "LSTS0", "LTC0", "LTS0"):
            try:
                values = cli.read_devices(dev, 1, bit_unit=True, series=args.series)
                record(f"{dev} read bit", "OK", f"values={values}")
            except Exception as exc:  # noqa: BLE001
                record(f"{dev} read bit", "NG", str(exc))

        ext = cli.make_extension_spec(
            extension_specification=args.cpu_io,
            direct_memory_specification=DIRECT_MEMORY_CPU_BUFFER,
            series=args.series,
        )
        for dev in ("G0", "HG0"):
            try:
                values = cli.read_devices_ext(dev, 1, extension=ext, bit_unit=False, series=args.series)
                record(f"{dev} CPU buffer ext read", "OK", f"values={values}")
            except Exception as exc:  # noqa: BLE001
                record(f"{dev} CPU buffer ext read", "NG", str(exc))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_markdown_report(
        output_path,
        title="# Open Items Recheck Report",
        header_lines=[
            f"- Date: {now}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            f"- CPU I/O: 0x{args.cpu_io:04X}",
        ],
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0


def pending_live_verification_main(argv: Sequence[str] | None = None) -> int:
    """Perform SLMP pending live verification against a live PLC."""
    parser = argparse.ArgumentParser(description="SLMP pending live verification")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="e.g. 0x0010")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument(
        "--label-array",
        action="append",
        help=(
            "optional 041A/141A probe as LABEL:UNIT:LENGTH; repeatable. "
            "141A writes back the value read by 041A when the read succeeds."
        ),
    )
    parser.add_argument(
        "--label-random",
        action="append",
        help=(
            "optional 041C/141B probe label name; repeatable. "
            "141B writes back the value read by 041C when the read succeeds."
        ),
    )
    parser.add_argument("--password", default="123456")
    parser.add_argument(
        "--output",
        help=(
            "optional markdown output path; default is "
            "internal_docs/<series>_<model>/pending_live_verification_latest.md"
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        label_array_points = _load_label_array_probe_specs(args.label_array)
        label_random_labels = _load_label_random_probe_labels(args.label_random)
    except ValueError as exc:
        parser.error(str(exc))

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="pending_live_verification_latest.md",
        monitoring_timer=args.monitoring_timer,
    )
    rows: list[tuple[str, str, str]] = []

    def add(item: str, status: str, detail: str) -> None:
        rows.append((item, status, detail))
        print(f"[{status}] {item}: {detail}")

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
        monitoring_timer=args.monitoring_timer,
    ) as cli:
        array_read_results: list[LabelArrayReadResult] | None = None
        try:
            array_read_results = list(cli.read_array_labels(label_array_points))
            add(
                "041A label array read",
                "OK",
                _format_label_array_read_detail(label_array_points, array_read_results),
            )
        except Exception as exc:  # noqa: BLE001
            add("041A label array read", "NG", str(exc))

        if array_read_results is not None:
            try:
                array_write_points = [
                    LabelArrayWritePoint(
                        label=point.label,
                        unit_specification=result.unit_specification,
                        array_data_length=result.array_data_length,
                        data=result.data,
                    )
                    for point, result in zip(label_array_points, array_read_results, strict=False)
                ]
                cli.write_array_labels(array_write_points)
                add(
                    "141A label array write",
                    "OK",
                    _format_label_array_read_detail(label_array_points, array_read_results),
                )
            except Exception as exc:  # noqa: BLE001
                add("141A label array write", "NG", str(exc))
        elif args.label_array:
            add("141A label array write", "SKIP", "array read unavailable; no safe same-value payload")
        else:
            try:
                payload = cli.build_array_label_write_payload(
                    [LabelArrayWritePoint(label="LabelW", unit_specification=1, array_data_length=2, data=b"\x31\x00")]
                )
                resp = cli.request(Command.LABEL_ARRAY_WRITE, 0x0000, payload, raise_on_error=False)
                add(
                    "141A label array write",
                    "OK" if resp.end_code == 0 else "NG",
                    f"end_code=0x{resp.end_code:04X}, payload_len={len(payload)}, data_len={len(resp.data)}",
                )
            except Exception as exc:  # noqa: BLE001
                add("141A label array write", "NG", str(exc))

        random_read_results: list[LabelRandomReadResult] | None = None
        try:
            random_read_results = list(cli.read_random_labels(label_random_labels))
            add(
                "041C label random read",
                "OK",
                _format_label_random_read_detail(label_random_labels, random_read_results),
            )
        except Exception as exc:  # noqa: BLE001
            add("041C label random read", "NG", str(exc))

        if random_read_results is not None:
            try:
                random_write_points = [
                    LabelRandomWritePoint(label=label, data=result.data)
                    for label, result in zip(label_random_labels, random_read_results, strict=False)
                ]
                cli.write_random_labels(random_write_points)
                add(
                    "141B label random write",
                    "OK",
                    _format_label_random_read_detail(label_random_labels, random_read_results),
                )
            except Exception as exc:  # noqa: BLE001
                add("141B label random write", "NG", str(exc))
        elif args.label_random:
            add("141B label random write", "SKIP", "random read unavailable; no safe same-value payload")
        else:
            try:
                payload = cli.build_label_write_random_payload(
                    [LabelRandomWritePoint(label="LabelW", data=b"\x31\x00")]
                )
                resp = cli.request(Command.LABEL_WRITE_RANDOM, 0x0000, payload, raise_on_error=False)
                add(
                    "141B label random write",
                    "OK" if resp.end_code == 0 else "NG",
                    f"end_code=0x{resp.end_code:04X}, payload_len={len(payload)}, data_len={len(resp.data)}",
                )
            except Exception as exc:  # noqa: BLE001
                add("141B label random write", "NG", str(exc))

        last_exc = "no pattern succeeded"
        extend_verified = False
        for module_no in (0x03E0, 0x0000, 0x03FF):
            for head in (0x0000, 0x0002):
                try:
                    data = cli.extend_unit_read_bytes(head, 2, module_no)
                    cli.extend_unit_write_bytes(head, module_no, data)
                    add(
                        "0601/1601 extend unit read/write",
                        "OK",
                        f"module_no=0x{module_no:04X}, head=0x{head:08X}, data={data.hex(' ')}",
                    )
                    extend_verified = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = str(exc)
            if extend_verified:
                break
        if not extend_verified:
            add("0601/1601 extend unit read/write", "NG", last_exc)

        remote_cmds = [
            ("1002 remote stop", Command.REMOTE_STOP, 0x0000, b"\x01\x00"),
            ("1001 remote run", Command.REMOTE_RUN, 0x0000, b"\x01\x00\x02\x00"),
            ("1003 remote pause", Command.REMOTE_PAUSE, 0x0000, b"\x01\x00"),
            ("1005 remote latch clear", Command.REMOTE_LATCH_CLEAR, 0x0000, b"\x01\x00"),
            ("1002 remote stop (restore)", Command.REMOTE_STOP, 0x0000, b"\x01\x00"),
        ]
        for name, cmd, sub, payload in remote_cmds:
            try:
                resp = cli.request(cmd, sub, payload, raise_on_error=False)
                status = "OK" if resp.end_code == 0 else "NG"
                add(name, status, f"end_code=0x{resp.end_code:04X}")
            except Exception as exc:  # noqa: BLE001
                add(name, "NG", str(exc))

        try:
            if args.series == "iqr":
                raw = args.password.encode("ascii")
                if len(raw) < 6 or len(raw) > 32:
                    raise ValueError("password length for iQ-R/iQ-L must be 6..32")
                pwd_payload = len(raw).to_bytes(2, "little") + raw
            else:
                pwd_payload = (4).to_bytes(2, "little") + args.password.encode("ascii")[:4].ljust(4, b" ")
            pre = cli.request(Command.REMOTE_PASSWORD_UNLOCK, 0x0000, pwd_payload, raise_on_error=False)
            add("1630 unlock (pre)", "OK" if pre.end_code == 0 else "NG", f"end_code=0x{pre.end_code:04X}")
            lock = cli.request(Command.REMOTE_PASSWORD_LOCK, 0x0000, pwd_payload, raise_on_error=False)
            add("1631 lock", "OK" if lock.end_code == 0 else "NG", f"end_code=0x{lock.end_code:04X}")
            unlock = cli.request(Command.REMOTE_PASSWORD_UNLOCK, 0x0000, pwd_payload, raise_on_error=False)
            add("1630 unlock", "OK" if unlock.end_code == 0 else "NG", f"end_code=0x{unlock.end_code:04X}")
        except Exception as exc:  # noqa: BLE001
            add("1631/1630 lock-unlock", "NG", str(exc))

        try:
            clr = cli.request(Command.CLEAR_ERROR, 0x0000, b"", raise_on_error=False)
            add("1617 clear error", "OK" if clr.end_code == 0 else "NG", f"end_code=0x{clr.end_code:04X}")
        except Exception as exc:  # noqa: BLE001
            add("1617 clear error", "NG", str(exc))

        add("1006 remote reset", "SKIP", "excluded from live verification scope")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_markdown_report(
        output_path,
        title="# Pending Live Verification Report",
        header_lines=[
            f"- Date: {now}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
        ],
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0


def compatibility_probe_main(argv: Sequence[str] | None = None) -> int:
    """Probe SLMP compatibility across frame/profile combinations."""
    parser = argparse.ArgumentParser(description="Probe SLMP compatibility across frame/profile combinations")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="ql")
    parser.add_argument("--frame-type", choices=("3e", "4e"), default="3e")
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="e.g. 0x0010")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument(
        "--target",
        help="optional SELF, SELF-CPU1..4, NWx-STy, or NAME,NETWORK,STATION,MODULE_IO,MULTIDROP",
    )
    parser.add_argument("--plc-label", help="stable label used for JSON/matrix output")
    parser.add_argument("--command", action="append", choices=COMPATIBILITY_COMMAND_CODES)
    parser.add_argument("--include-write-restore", action="store_true", help="include write/readback/restore probes")
    parser.add_argument("--include-remote-control", action="store_true", help="include remote RUN/STOP/Latch Clear")
    parser.add_argument("--include-maintenance", action="store_true", help="include Clear Error")
    parser.add_argument("--word-device", default="D130")
    parser.add_argument("--bit-device", default="M120")
    parser.add_argument("--random-read-word-device", action="append")
    parser.add_argument("--random-write-word-device", action="append")
    parser.add_argument("--random-write-bit-device", action="append")
    parser.add_argument("--monitor-word-device", default="D130")
    parser.add_argument("--block-word-device", default="D140")
    parser.add_argument("--block-bit-device", default="M140")
    parser.add_argument("--memory-head", type=_int_auto, default=0x0000)
    parser.add_argument("--memory-length", type=int, default=1)
    parser.add_argument("--word-write-value", type=_int_auto, default=0x0000)
    parser.add_argument("--random-write-word-value", type=_int_auto, default=0x0000)
    parser.add_argument("--block-word-write-value", type=_int_auto, default=0x0000)
    parser.add_argument("--block-bit-write-value", type=_int_auto, default=0x0000)
    parser.add_argument("--memory-write-value", type=_int_auto, default=0x0000)
    parser.add_argument("--output-markdown")
    parser.add_argument("--output-json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    selected_specs = _compatibility_selected_specs(
        command_codes=args.command,
        include_write_restore=args.include_write_restore,
        include_remote_control=args.include_remote_control,
        include_maintenance=args.include_maintenance,
    )
    if not selected_specs:
        parser.error("no commands selected; enable at least one probe group or command")
    if args.command:
        selected_codes = {spec.code for spec in selected_specs}
        missing = [code for code in args.command if code not in selected_codes]
        if missing:
            parser.error(
                "requested commands are not enabled by the selected risk flags: " + ", ".join(sorted(set(missing)))
            )

    if args.target:
        try:
            target = _parse_named_target(args.target).target
        except ValueError as exc:
            parser.error(str(exc))
    else:
        target = SlmpTarget(
            network=args.network,
            station=args.station,
            module_io=args.module_io,
            multidrop=args.multidrop,
        )

    args.random_read_word_device = args.random_read_word_device or [args.word_device, "D131"]
    args.random_write_word_device = args.random_write_word_device or ["D135"]
    args.random_write_bit_device = args.random_write_bit_device or ["M125"]
    plc_label = args.plc_label or f"{args.host}_n{target.network:02X}_s{target.station:02X}"
    markdown_output = args.output_markdown or _compatibility_default_output(
        plc_label=plc_label,
        filename="compatibility_probe_latest.md",
    )
    json_output = args.output_json or _compatibility_default_output(
        plc_label=plc_label,
        filename="compatibility_probe_latest.json",
    )

    frame_candidates = [FrameType(args.frame_type)]
    series_candidates = [PLCSeries(args.series)]

    rows: list[tuple[str, str, str]] = []
    result_rows: list[dict[str, object]] = []
    selected_command_codes = [spec.code for spec in selected_specs]
    risk_groups = sorted({spec.risk_group for spec in selected_specs})

    print("=== Compatibility Probe ===")
    print(f"PLC Label={plc_label}")
    print(f"Host={args.host}, Port={args.port}, Transport={args.transport}")
    print(
        "Target="
        f"network=0x{target.network:02X}, station=0x{target.station:02X}, "
        f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
    )
    print(
        "Combinations="
        + ",".join(f"{frame.value}/{series.value}" for frame in frame_candidates for series in series_candidates)
    )
    print(f"Commands={','.join(selected_command_codes)}")

    for frame_type in frame_candidates:
        for series in series_candidates:
            combo_label = f"{frame_type.value}/{series.value}"
            command_rows: list[dict[str, object]] = []
            combo_result: dict[str, object] = {
                "frame_type": frame_type.value,
                "access_profile": series.value,
                "commands": command_rows,
            }
            try:
                with SlmpClient(
                    args.host,
                    port=args.port,
                    transport=args.transport,
                    timeout=args.timeout,
                    plc_series=series,
                    frame_type=frame_type,
                    default_target=target,
                    monitoring_timer=args.monitoring_timer,
                ) as client:
                    for spec in selected_specs:
                        subresults, metadata = _compatibility_run_command(spec, client, series=series, args=args)
                        status = _compatibility_summarize_subresults(subresults)
                        detail = _compatibility_format_subresults(subresults)
                        item = f"{combo_label} {spec.code} {spec.name}"
                        rows.append((item, status, detail))
                        print(f"[{status}] {item}: {detail}")
                        command_row: dict[str, object] = {
                            "code": spec.code,
                            "category": spec.category,
                            "name": spec.name,
                            "risk_group": spec.risk_group,
                            "status": status,
                            "detail": detail,
                            "subresults": [
                                {"name": name, "status": sub_status, "detail": sub_detail}
                                for name, sub_status, sub_detail in subresults
                            ],
                        }
                        command_rows.append(command_row)
                        for key, value in metadata.items():
                            if value is not None and key not in combo_result:
                                combo_result[key] = value
            except Exception as exc:  # noqa: BLE001
                detail = str(exc)
                print(f"[NG] {combo_label} connection: {detail}")
                combo_result["connection_error"] = detail
                for spec in selected_specs:
                    item = f"{combo_label} {spec.code} {spec.name}"
                    rows.append((item, "NG", detail))
                    command_rows.append(
                        {
                            "code": spec.code,
                            "category": spec.category,
                            "name": spec.name,
                            "risk_group": spec.risk_group,
                            "status": "NG",
                            "detail": detail,
                            "subresults": [{"name": "connection", "status": "NG", "detail": detail}],
                        }
                    )
            result_rows.append(combo_result)

    json_payload: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plc_label": plc_label,
        "host": args.host,
        "port": args.port,
        "transport": args.transport,
        "requested_series": args.series,
        "requested_frame_type": args.frame_type,
        "risk_groups": risk_groups,
        "selected_commands": selected_command_codes,
        "target": {
            "network": target.network,
            "station": target.station,
            "module_io": int(target.module_io),
            "multidrop": target.multidrop,
        },
        "results": result_rows,
    }
    _write_json_report(json_output, json_payload)

    summary = Counter(status for _, status, _ in rows)
    _write_markdown_report(
        markdown_output,
        title="# Compatibility Probe Report",
        header_lines=[
            f"- Date: {json_payload['generated_at']}",
            f"- PLC Label: {plc_label}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Requested series: {args.series}",
            f"- Requested frame: {args.frame_type}",
            (
                f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
                f"module_io=0x{int(target.module_io):04X}, multidrop=0x{target.multidrop:02X}"
            ),
            f"- Risk groups: {', '.join(risk_groups)}",
            f"- Commands: {', '.join(selected_command_codes)}",
            f"- Summary: OK={summary['OK']}, PARTIAL={summary['PARTIAL']}, NG={summary['NG']}, SKIP={summary['SKIP']}",
            f"- JSON: {json_output}",
        ],
        rows=rows,
    )
    print(f"[DONE] markdown={markdown_output}")
    print(f"[DONE] json={json_output}")
    return 0


def compatibility_matrix_render_main(argv: Sequence[str] | None = None) -> int:
    """Render PLC_COMPATIBILITY.md from compatibility probe JSON files."""
    parser = argparse.ArgumentParser(description="Render PLC_COMPATIBILITY.md from compatibility probe JSON files")
    parser.add_argument("--input", action="append", required=True, help="compatibility_probe_latest.json; repeatable")
    parser.add_argument("--output", default="docs/validation/reports/PLC_COMPATIBILITY.md")
    parser.add_argument(
        "--policy-output",
        default=_compatibility_default_policy_output(),
        help="structured policy JSON generated from the same probe inputs",
    )
    parser.add_argument(
        "--omit-pending-columns",
        action="store_true",
        help="hide command columns that are PENDING for every PLC row",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    source_paths = [Path(path) for path in args.input]
    loaded: list[Mapping[str, object]] = []
    for path in source_paths:
        loaded.append(json.loads(path.read_text(encoding="utf-8")))

    content = _render_compatibility_matrix_markdown(
        loaded,
        source_paths=source_paths,
        omit_pending_columns=args.omit_pending_columns,
    )
    _write_text_report(args.output, content)
    _write_json_report(args.policy_output, _build_compatibility_policy(loaded))
    print(f"[DONE] output={args.output}")
    print(f"[DONE] policy={args.policy_output}")
    return 0


def device_access_matrix_sync_main(argv: Sequence[str] | None = None) -> int:
    """Render device_access_matrix.md from device_access_matrix.csv."""
    parser = argparse.ArgumentParser(description="Render device_access_matrix.md from device_access_matrix.csv")
    parser.add_argument(
        "--csv",
        required=True,
        help="path to device_access_matrix.csv",
    )
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is the CSV path with .md suffix",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    csv_path = Path(args.csv)
    output_path = Path(args.output) if args.output else csv_path.with_suffix(".md")
    rows = _load_device_access_matrix_rows(csv_path)
    content = _render_device_access_matrix_markdown(rows, source_path=csv_path)
    _write_text_report(output_path, content)
    print(f"[DONE] report={output_path}")
    return 0


def manual_write_verification_main(argv: Sequence[str] | None = None) -> int:
    """Perform interactive manual device write verification with restore."""
    parser = argparse.ArgumentParser(
        description=(
            "Write temporary test values to representative devices from device_access_matrix.csv, "
            "let a human verify the effect, and then restore the original values"
        )
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument(
        "--matrix",
        help=(
            "path to device_access_matrix.csv; default is "
            "internal_docs/<series>_<model>/device_access_matrix.csv after probing 0101"
        ),
    )
    parser.add_argument(
        "--device-code",
        action="append",
        help="device code filter, repeatable (example: D or ZR)",
    )
    parser.add_argument("--limit", type=int, help="optional maximum number of rows to process")
    parser.add_argument(
        "--output",
        help=(
            "optional markdown output path; default is "
            "internal_docs/<series>_<model>/manual_write_verification_latest.md"
        ),
    )
    parser.add_argument(
        "--resume-from-report",
        help="skip rows already present in an earlier manual_write_verification report",
    )
    parser.add_argument(
        "--keep-written-value",
        action="store_true",
        help="do not restore the original value after the human judgement step",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    model = _probe_target_model(
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        series=args.series,
        target=target,
    )
    matrix_path = (
        Path(args.matrix)
        if args.matrix
        else _model_folder_path(series=args.series, model=model) / "device_access_matrix.csv"
    )
    if not matrix_path.exists():
        raise FileNotFoundError(f"device access matrix not found: {matrix_path}")
    output_path = args.output or _default_report_output(
        series=args.series,
        model=model,
        filename="manual_write_verification_latest.md",
    )

    rows = _load_device_access_matrix_rows(matrix_path)
    selected = _select_manual_write_rows(
        rows,
        device_codes={code.upper() for code in args.device_code} if args.device_code else None,
        limit=args.limit,
    )
    existing_report_rows: list[tuple[str, str, str]] = []
    if args.resume_from_report:
        resume_report_path = Path(args.resume_from_report)
        processed = _load_processed_manual_write_items(resume_report_path)
        existing_report_rows = _load_manual_write_report_rows(resume_report_path)
        selected = [row for row in selected if f"{row.device_code} {row.device}" not in processed]
    if not selected:
        print(f"[SKIP] no manual-write candidates matched matrix={matrix_path}")
        return 0

    report_rows: list[tuple[str, str, str]] = list(existing_report_rows)
    summary = {"OK": 0, "NG": 0, "SKIP": 0}
    for _, status, _ in existing_report_rows:
        summary[status] = summary.get(status, 0) + 1

    def record(item: str, status: str, detail: str) -> None:
        report_rows.append((item, status, detail))
        summary[status] = summary.get(status, 0) + 1
        print(f"[{status}] {item}: {detail}")

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
    ) as cli:
        for index, row in enumerate(selected, start=1):
            item = f"{row.device_code} {row.device}"
            print("")
            print(f"=== [{index}/{len(selected)}] {item} ({row.kind}) ===")
            if row.note:
                print(f"note: {row.note}")
            try:
                before = _read_manual_row_value(cli, row, series=args.series)
            except Exception as exc:  # noqa: BLE001
                record(item, "NG", f"read_before_failed={exc}")
                continue

            test_value = _make_manual_test_value(row, before)
            before_text = _format_manual_value(row.kind, before)
            test_text = _format_manual_value(row.kind, test_value)
            print(f"temporary write: {row.device} {before_text} -> {test_text}")
            start = input("Press Enter to write temporarily, or type 'skip' to skip this row: ").strip().lower()
            if start in {"s", "skip"}:
                record(item, "SKIP", "operator skipped before write")
                continue

            restore_detail = "not attempted"
            try:
                _write_manual_row_value(cli, row, test_value, series=args.series)
                print("Temporary write completed. Verify the reflected value in your engineering tool.")
                verdict: str | None = None
                while verdict is None:
                    verdict = _parse_manual_verdict(input("Human check result [Y/N/Skip]: "))
                    if verdict is None:
                        print("Enter Y, N, or Skip.")
            except Exception as exc:  # noqa: BLE001
                record(item, "NG", f"temporary_write_failed={exc}")
                continue
            finally:
                if not args.keep_written_value:
                    try:
                        _write_manual_row_value(cli, row, before, series=args.series)
                        restore_detail = f"restored={before_text}"
                    except Exception as exc:  # noqa: BLE001
                        restore_detail = f"restore_failed={exc}"

            assert verdict is not None
            detail = f"before={before_text}, test={test_text}, {restore_detail}"
            if restore_detail.startswith("restore_failed="):
                record(item, "NG", detail)
            else:
                record(item, verdict, detail)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_markdown_report(
        output_path,
        title="# Manual Write Verification Report",
        header_lines=[
            f"- Date: {now}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
            f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}",
            f"- Matrix: `{matrix_path.as_posix()}`",
            f"- Rows processed: {len(selected)}",
            (f"- Summary: OK={summary['OK']}, NG={summary['NG']}, SKIP={summary['SKIP']}"),
            (
                "- Behavior: each row writes a temporary value, waits for human confirmation, "
                "and restores the original value unless --keep-written-value is set"
            ),
        ],
        rows=report_rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if summary["NG"] == 0 else 2


def manual_label_verification_main(argv: Sequence[str] | None = None) -> int:
    """Perform interactive manual label write verification with restore."""
    parser = argparse.ArgumentParser(
        description=(
            "Write temporary values to explicit label tags, let a human verify the effect, "
            "and then restore the original values"
        )
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="e.g. 0x0010")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument(
        "--label-random",
        action="append",
        help="label name for 041C/141B style single-point verification; repeatable",
    )
    parser.add_argument(
        "--label-array",
        action="append",
        help="label spec as LABEL:UNIT:LENGTH for 041A/141A style verification; repeatable",
    )
    parser.add_argument(
        "--output",
        help=(
            "optional markdown output path; default is "
            "internal_docs/<series>_<model>/manual_label_verification_latest.md"
        ),
    )
    parser.add_argument(
        "--keep-written-value",
        action="store_true",
        help="do not restore the original value after the human judgement step",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        random_labels = _load_explicit_label_random_labels(args.label_random)
        array_points = _load_explicit_label_array_points(args.label_array)
    except ValueError as exc:
        parser.error(str(exc))
    if not random_labels and not array_points:
        parser.error("at least one --label-random or --label-array entry is required")

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="manual_label_verification_latest.md",
        monitoring_timer=args.monitoring_timer,
    )

    report_rows: list[tuple[str, str, str]] = []
    summary = {"OK": 0, "NG": 0, "SKIP": 0}

    def record(item: str, status: str, detail: str) -> None:
        report_rows.append((item, status, detail))
        summary[status] = summary.get(status, 0) + 1
        print(f"[{status}] {item}: {detail}")

    total = len(random_labels) + len(array_points)
    processed = 0
    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
        monitoring_timer=args.monitoring_timer,
    ) as client:
        for label in random_labels:
            processed += 1
            item = f"random {label}"
            print("")
            print(f"=== [{processed}/{total}] {item} ===")
            try:
                before_random = client.read_random_labels([label])[0]
            except Exception as exc:  # noqa: BLE001
                record(item, "NG", f"read_before_failed={exc}")
                continue

            before_text = _format_label_value(before_random.data)
            try:
                test_data = _make_manual_label_test_bytes(before_random.data)
            except ValueError as exc:
                record(item, "NG", str(exc))
                continue
            test_text = _format_label_value(test_data)
            print(f"temporary write: {label} {before_text} -> {test_text}")
            start = input("Press Enter to write temporarily, or type 'skip' to skip this label: ").strip().lower()
            if start in {"s", "skip"}:
                record(item, "SKIP", "operator skipped before write")
                continue

            verdict_random: str | None = None
            restore_detail = "not attempted"
            try:
                client.write_random_labels([LabelRandomWritePoint(label=label, data=test_data)])
                print("Temporary write completed. Verify the reflected value in your engineering tool.")
                while verdict_random is None:
                    verdict_random = _parse_manual_verdict(input("Human check result [Y/N/Skip]: "))
                    if verdict_random is None:
                        print("Enter Y, N, or Skip.")
            except Exception as exc:  # noqa: BLE001
                record(item, "NG", f"temporary_write_failed={exc}")
                continue
            finally:
                if not args.keep_written_value:
                    try:
                        client.write_random_labels([LabelRandomWritePoint(label=label, data=before_random.data)])
                        restore_detail = f"restored={before_text}"
                    except Exception as exc:  # noqa: BLE001
                        restore_detail = f"restore_failed={exc}"

            assert verdict_random is not None
            detail = f"before={before_text}, test={test_text}, {restore_detail}"
            if restore_detail.startswith("restore_failed="):
                record(item, "NG", detail)
            else:
                record(item, verdict_random, detail)

        for point in array_points:
            processed += 1
            spec_text = _format_label_array_point(point)
            item = f"array {spec_text}"
            print("")
            print(f"=== [{processed}/{total}] {item} ===")
            try:
                before_array = client.read_array_labels([point])[0]
            except Exception as exc:  # noqa: BLE001
                record(item, "NG", f"read_before_failed={exc}")
                continue

            before_text = _format_label_value(before_array.data)
            try:
                test_data = _make_manual_label_test_bytes(before_array.data)
            except ValueError as exc:
                record(item, "NG", str(exc))
                continue
            test_text = _format_label_value(test_data)
            print(f"temporary write: {spec_text} {before_text} -> {test_text}")
            start = input("Press Enter to write temporarily, or type 'skip' to skip this label: ").strip().lower()
            if start in {"s", "skip"}:
                record(item, "SKIP", "operator skipped before write")
                continue

            verdict_array: str | None = None
            restore_detail = "not attempted"
            try:
                client.write_array_labels(
                    [
                        LabelArrayWritePoint(
                            label=point.label,
                            unit_specification=before_array.unit_specification,
                            array_data_length=before_array.array_data_length,
                            data=test_data,
                        )
                    ]
                )
                print("Temporary write completed. Verify the reflected value in your engineering tool.")
                while verdict_array is None:
                    verdict_array = _parse_manual_verdict(input("Human check result [Y/N/Skip]: "))
                    if verdict_array is None:
                        print("Enter Y, N, or Skip.")
            except Exception as exc:  # noqa: BLE001
                record(item, "NG", f"temporary_write_failed={exc}")
                continue
            finally:
                if not args.keep_written_value:
                    try:
                        client.write_array_labels(
                            [
                                LabelArrayWritePoint(
                                    label=point.label,
                                    unit_specification=before_array.unit_specification,
                                    array_data_length=before_array.array_data_length,
                                    data=before_array.data,
                                )
                            ]
                        )
                        restore_detail = f"restored={before_text}"
                    except Exception as exc:  # noqa: BLE001
                        restore_detail = f"restore_failed={exc}"

            assert verdict_array is not None
            detail = f"before={before_text}, test={test_text}, {restore_detail}"
            if restore_detail.startswith("restore_failed="):
                record(item, "NG", detail)
            else:
                record(item, verdict_array, detail)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    array_label_text = ", ".join(_format_label_array_point(point) for point in array_points) if array_points else "none"
    _write_markdown_report(
        output_path,
        title="# Manual Label Verification Report",
        header_lines=[
            f"- Date: {now}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            f"- Monitoring timer: 0x{args.monitoring_timer:04X}",
            f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
            f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}",
            f"- Random labels: {', '.join(random_labels) if random_labels else 'none'}",
            f"- Array labels: {array_label_text}",
            f"- Rows processed: {total}",
            (f"- Summary: OK={summary['OK']}, NG={summary['NG']}, SKIP={summary['SKIP']}"),
            (
                "- Behavior: each row reads the current label value, writes a temporary value, "
                "waits for human confirmation, and restores the original value unless "
                "--keep-written-value is set"
            ),
        ],
        rows=report_rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if summary["NG"] == 0 else 2


def read_soak_main(argv: Sequence[str] | None = None) -> int:
    """Perform repeated single-command read soak test."""
    parser = argparse.ArgumentParser(description="Repeated single-command read soak test")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument("--device", default="D1000")
    parser.add_argument("--points", type=int, default=1)
    parser.add_argument("--bit-unit", action="store_true")
    parser.add_argument("--rounds", type=int, default=5000)
    parser.add_argument(
        "--rotate-span",
        type=int,
        default=200,
        help="offset span for rotating device addresses; 0 keeps the device fixed",
    )
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is internal_docs/<series>_<model>/read_soak_latest.md",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.rounds <= 0:
        parser.error("--rounds must be >= 1")
    if args.rotate_span < 0:
        parser.error("--rotate-span must be >= 0")

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="read_soak_latest.md",
    )

    durations: list[float] = []
    errors: Counter[str] = Counter()
    sample_errors: list[str] = []
    values_seen: Counter[str] = Counter()

    started = time.perf_counter()
    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
    ) as cli:
        for iteration in range(args.rounds):
            device = (
                _offset_device_text(args.device, iteration % args.rotate_span)
                if args.rotate_span > 0
                else str(parse_device(args.device))
            )
            t0 = time.perf_counter()
            try:
                values = cli.read_devices(device, args.points, bit_unit=args.bit_unit, series=args.series)
                values_seen[_format_probe_values(values)] += 1
            except Exception as exc:  # noqa: BLE001
                errors[type(exc).__name__] += 1
                if len(sample_errors) < 3:
                    sample_errors.append(f"{device}: {exc}")
            durations.append(time.perf_counter() - t0)
    elapsed = time.perf_counter() - started
    stats = _summarize_durations(durations, elapsed_s=elapsed)

    rows = [
        (
            "read soak",
            "OK" if not errors else "NG",
            (
                f"count={stats.count}, avg_ms={stats.avg_ms:.3f}, p95_ms={stats.p95_ms:.3f}, "
                f"p99_ms={stats.p99_ms:.3f}, max_ms={stats.max_ms:.3f}, "
                f"rate_per_s={stats.rate_per_s:.1f}, errors={_format_counter(dict(errors))}"
            ),
        )
    ]
    for index, detail in enumerate(sample_errors, start=1):
        rows.append((f"sample error {index}", "NG", detail))

    top_values = ", ".join(f"{value} x{count}" for value, count in values_seen.most_common(5))
    _write_markdown_report(
        output_path,
        title="# Read Soak Report",
        header_lines=[
            f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            f"- Device: {args.device}",
            f"- Points: {args.points}",
            f"- Bit unit: {args.bit_unit}",
            f"- Rounds: {args.rounds}",
            f"- Rotate span: {args.rotate_span}",
            f"- Top values: {top_values or 'none'}",
        ],
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if not errors else 2


def mixed_read_load_main(argv: Sequence[str] | None = None) -> int:
    """Perform mixed 0401/0403/0406 read load test."""
    parser = argparse.ArgumentParser(description="Mixed 0401/0403/0406 read load test")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument("--base-device", default="D1000")
    parser.add_argument("--rotate-span", type=int, default=200)
    parser.add_argument("--rounds", type=int, default=2000)
    parser.add_argument("--direct-points", type=int, default=1)
    parser.add_argument("--random-word-count", type=int, default=2)
    parser.add_argument("--block-points", type=int, default=16)
    parser.add_argument("--block-offset", type=int, default=100)
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is internal_docs/<series>_<model>/mixed_read_load_latest.md",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.rounds <= 0:
        parser.error("--rounds must be >= 1")
    if args.rotate_span < 0:
        parser.error("--rotate-span must be >= 0")
    if args.direct_points <= 0 or args.random_word_count <= 0 or args.block_points <= 0:
        parser.error("--direct-points, --random-word-count, and --block-points must be >= 1")

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=target,
        filename="mixed_read_load_latest.md",
    )

    op_durations: dict[str, list[float]] = {
        "0401 direct read": [],
        "0403 random read": [],
        "0406 block read": [],
    }
    op_errors: dict[str, Counter[str]] = {name: Counter() for name in op_durations}
    sample_errors: dict[str, list[str]] = {name: [] for name in op_durations}

    started = time.perf_counter()
    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
    ) as cli:
        for cycle in range(args.rounds):
            base_offset = cycle % args.rotate_span if args.rotate_span > 0 else 0

            direct_device = _offset_device_text(args.base_device, base_offset)
            t0 = time.perf_counter()
            try:
                cli.read_devices(direct_device, args.direct_points, bit_unit=False, series=args.series)
            except Exception as exc:  # noqa: BLE001
                op_errors["0401 direct read"][type(exc).__name__] += 1
                if len(sample_errors["0401 direct read"]) < 3:
                    sample_errors["0401 direct read"].append(f"{direct_device}: {exc}")
            op_durations["0401 direct read"].append(time.perf_counter() - t0)

            random_devices = [
                _offset_device_text(args.base_device, base_offset + index) for index in range(args.random_word_count)
            ]
            t0 = time.perf_counter()
            try:
                cli.read_random(word_devices=random_devices, series=args.series)
            except Exception as exc:  # noqa: BLE001
                op_errors["0403 random read"][type(exc).__name__] += 1
                if len(sample_errors["0403 random read"]) < 3:
                    sample_errors["0403 random read"].append(f"{random_devices[0]}..: {exc}")
            op_durations["0403 random read"].append(time.perf_counter() - t0)

            block_device = _offset_device_text(args.base_device, base_offset + args.block_offset)
            t0 = time.perf_counter()
            try:
                cli.read_block(word_blocks=[(block_device, args.block_points)], bit_blocks=(), series=args.series)
            except Exception as exc:  # noqa: BLE001
                op_errors["0406 block read"][type(exc).__name__] += 1
                if len(sample_errors["0406 block read"]) < 3:
                    sample_errors["0406 block read"].append(f"{block_device}: {exc}")
            op_durations["0406 block read"].append(time.perf_counter() - t0)
    elapsed = time.perf_counter() - started

    rows: list[tuple[str, str, str]] = []
    total_errors = 0
    for name in ("0401 direct read", "0403 random read", "0406 block read"):
        stats = _summarize_durations(op_durations[name])
        error_count = sum(op_errors[name].values())
        total_errors += error_count
        rows.append(
            (
                name,
                "OK" if error_count == 0 else "NG",
                (
                    f"count={stats.count}, avg_ms={stats.avg_ms:.3f}, p95_ms={stats.p95_ms:.3f}, "
                    f"p99_ms={stats.p99_ms:.3f}, max_ms={stats.max_ms:.3f}, "
                    f"rate_per_s={stats.rate_per_s:.1f}, errors={_format_counter(dict(op_errors[name]))}"
                ),
            )
        )
        for index, detail in enumerate(sample_errors[name], start=1):
            rows.append((f"{name} sample error {index}", "NG", detail))

    overall_stats = _summarize_durations(
        [duration for items in op_durations.values() for duration in items],
        elapsed_s=elapsed,
    )
    rows.insert(
        0,
        (
            "overall",
            "OK" if total_errors == 0 else "NG",
            (
                f"count={overall_stats.count}, avg_ms={overall_stats.avg_ms:.3f}, "
                f"p95_ms={overall_stats.p95_ms:.3f}, p99_ms={overall_stats.p99_ms:.3f}, "
                f"max_ms={overall_stats.max_ms:.3f}, rate_per_s={overall_stats.rate_per_s:.1f}, "
                f"errors={total_errors}"
            ),
        ),
    )

    _write_markdown_report(
        output_path,
        title="# Mixed Read Load Report",
        header_lines=[
            f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            f"- Base device: {args.base_device}",
            f"- Rotate span: {args.rotate_span}",
            f"- Rounds: {args.rounds}",
            f"- Direct points: {args.direct_points}",
            f"- Random word count: {args.random_word_count}",
            f"- Block points: {args.block_points}",
            f"- Block offset: {args.block_offset}",
        ],
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if total_errors == 0 else 2


def tcp_concurrency_main(argv: Sequence[str] | None = None) -> int:
    """Perform practical multi-client TCP read concurrency test."""
    parser = argparse.ArgumentParser(description="Practical multi-client TCP read concurrency test")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--network", type=_int_auto, default=0x00)
    parser.add_argument("--station", type=_int_auto, default=0xFF)
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF)
    parser.add_argument("--multidrop", type=_int_auto, default=0x00)
    parser.add_argument("--device", default="D1000")
    parser.add_argument("--points", type=int, default=1)
    parser.add_argument("--bit-unit", action="store_true")
    parser.add_argument(
        "--clients",
        default="1,2,4,8,16,32",
        help="comma-separated client counts, e.g. 1,2,4,8,16,32",
    )
    parser.add_argument("--rounds-per-client", type=int, default=100)
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is internal_docs/<series>_<model>/tcp_concurrency_latest.md",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.rounds_per_client <= 0:
        parser.error("--rounds-per-client must be >= 1")
    try:
        client_levels = _parse_positive_int_list(args.clients)
    except Exception as exc:  # noqa: BLE001
        parser.error(str(exc))

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport="tcp",
        timeout=args.timeout,
        target=target,
        filename="tcp_concurrency_latest.md",
    )

    rows: list[tuple[str, str, str]] = []
    total_failures = 0

    for level in client_levels:
        barrier = threading.Barrier(level)
        lock = threading.Lock()
        durations: list[float] = []
        errors: Counter[str] = Counter()
        sample_errors: list[str] = []

        def worker(
            index: int,
            *,
            _barrier: threading.Barrier = barrier,
            _lock: threading.Lock = lock,
            _durations: list[float] = durations,
            _errors: Counter[str] = errors,
            _sample_errors: list[str] = sample_errors,
        ) -> None:
            local_durations: list[float] = []
            local_errors: list[tuple[str, str]] = []
            try:
                with SlmpClient(
                    args.host,
                    port=args.port,
                    transport="tcp",
                    timeout=args.timeout,
                    plc_series=args.series,
                    default_target=target,
                ) as cli:
                    try:
                        _barrier.wait(timeout=max(args.timeout * 4.0, 5.0))
                    except threading.BrokenBarrierError as exc:
                        local_errors.append((type(exc).__name__, f"barrier failed for client {index}: {exc}"))
                        return
                    for iteration in range(args.rounds_per_client):
                        device = _offset_device_text(args.device, index * args.rounds_per_client + iteration)
                        t0 = time.perf_counter()
                        try:
                            cli.read_devices(device, args.points, bit_unit=args.bit_unit, series=args.series)
                        except Exception as exc:  # noqa: BLE001
                            local_errors.append((type(exc).__name__, f"{device}: {exc}"))
                        local_durations.append(time.perf_counter() - t0)
            except Exception as exc:  # noqa: BLE001
                local_errors.append((type(exc).__name__, str(exc)))
            with _lock:
                _durations.extend(local_durations)
                for name, detail in local_errors:
                    _errors[name] += 1
                    if len(_sample_errors) < 3:
                        _sample_errors.append(detail)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(level)]
        started = time.perf_counter()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        elapsed = time.perf_counter() - started
        total_failures += sum(errors.values())
        if durations:
            stats = _summarize_durations(durations, elapsed_s=elapsed)
            detail = (
                f"count={stats.count}, avg_ms={stats.avg_ms:.3f}, p95_ms={stats.p95_ms:.3f}, "
                f"p99_ms={stats.p99_ms:.3f}, max_ms={stats.max_ms:.3f}, "
                f"rate_per_s={stats.rate_per_s:.1f}, errors={_format_counter(dict(errors))}"
            )
        else:
            detail = f"count=0, elapsed_s={elapsed:.3f}, errors={_format_counter(dict(errors))}"
            total_failures += 1
        rows.append((f"clients={level}", "OK" if durations and not errors else "NG", detail))
        for index, detail in enumerate(sample_errors, start=1):
            rows.append((f"clients={level} sample error {index}", "NG", detail))

    _write_markdown_report(
        output_path,
        title="# TCP Concurrency Report",
        header_lines=[
            f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Series: {args.series}",
            f"- Device: {args.device}",
            f"- Points: {args.points}",
            f"- Bit unit: {args.bit_unit}",
            f"- Client levels: {', '.join(str(level) for level in client_levels)}",
            f"- Rounds per client: {args.rounds_per_client}",
            "- Address allocation: each client uses a distinct offset range to avoid same-address access",
        ],
        rows=rows,
    )
    print(f"[DONE] report={output_path}")
    return 0 if total_failures == 0 else 2


def regression_suite_main(argv: Sequence[str] | None = None) -> int:
    """Run the local regression suite and optional safe live connection smoke check."""
    parser = argparse.ArgumentParser(
        description="Run the local regression suite and optional safe live connection smoke check"
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to spawn subcommands (default: current interpreter)",
    )
    parser.add_argument(
        "--skip-unit-tests",
        action="store_true",
        help="skip `python -m unittest discover -s tests -v`",
    )
    parser.add_argument(
        "--skip-ruff",
        action="store_true",
        help="skip `python -m ruff check slmp tests scripts`",
    )
    parser.add_argument(
        "--skip-mypy",
        action="store_true",
        help="skip `python -m mypy slmp scripts`",
    )
    parser.add_argument(
        "--skip-cli-help",
        action="store_true",
        help="skip `--help` smoke checks for maintained wrapper scripts",
    )
    parser.add_argument(
        "--include-live-connection-check",
        action="store_true",
        help="also run the safe connection check against a live PLC",
    )
    parser.add_argument("--host", help="PLC host for the optional live connection check")
    parser.add_argument("--port", type=int, default=1025, help="PLC port for the optional live connection check")
    parser.add_argument(
        "--transport",
        choices=("tcp", "udp"),
        default="tcp",
        help="transport for the optional live connection check",
    )
    parser.add_argument(
        "--series",
        choices=("ql", "iqr"),
        help="PLC series for the optional live connection check",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="stop after the first failed step",
    )
    parser.add_argument(
        "--output",
        default="internal_docs/regression_suite_latest.md",
        help="markdown report path (default: internal_docs/regression_suite_latest.md)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.include_live_connection_check and (not args.host or not args.series):
        parser.error("--include-live-connection-check requires --host and --series")

    steps = _build_regression_steps(
        python_executable=args.python,
        include_unit_tests=not args.skip_unit_tests,
        include_ruff=not args.skip_ruff,
        include_mypy=not args.skip_mypy,
        include_cli_help=not args.skip_cli_help,
        include_live_connection_check=args.include_live_connection_check,
        host=args.host,
        port=args.port,
        transport=args.transport,
        series=args.series,
    )
    results = _run_regression_steps(
        steps,
        cwd=_project_root(),
        fail_fast=args.fail_fast,
    )
    _write_regression_report(
        args.output,
        steps=steps,
        results=results,
        python_executable=args.python,
        fail_fast=args.fail_fast,
        include_live_connection_check=args.include_live_connection_check,
    )
    failures = sum(1 for _step, completed, _duration in results if completed.returncode != 0)
    print(f"[DONE] report={args.output}")
    return 0 if failures == 0 and len(results) == len(steps) else 2


def init_model_docs_main(argv: Sequence[str] | None = None) -> int:
    """Initialize internal_docs/<series>_<model>/ scaffolding for a new target."""
    parser = argparse.ArgumentParser(
        description="Initialize internal_docs/<series>_<model>/ scaffolding for a new target"
    )
    parser.add_argument("--series", required=True, help="target series label, e.g. iqr")
    parser.add_argument("--model", required=True, help="target model name, e.g. R08CPU")
    parser.add_argument(
        "--output-root",
        default="internal_docs",
        help="root directory where the model folder will be created (default: internal_docs)",
    )
    parser.add_argument("--force", action="store_true", help="overwrite existing scaffold files")
    args = parser.parse_args(list(argv) if argv is not None else None)

    model_dir, created, skipped = _initialize_model_docs(
        root=Path(args.output_root),
        series=args.series,
        model=args.model,
        force=args.force,
    )
    print(f"[DONE] model_dir={model_dir}")
    for path in created:
        print(f"[CREATED] {path}")
    for path in skipped:
        print(f"[SKIPPED] {path}")
    return 0
