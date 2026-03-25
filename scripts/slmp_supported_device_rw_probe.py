#!/usr/bin/env python
"""Probe supported device families with 10 write-read-restore checks each."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slmp import SlmpClient, SlmpTarget  # noqa: E402
from slmp.cli import (  # noqa: E402
    DeviceMatrixRow,
    _default_report_output,
    _format_manual_value,
    _increment_device_text,
    _load_boundary_specs,
    _load_device_access_matrix_rows,
    _model_folder_path,
    _write_markdown_report,
)
from slmp.core import parse_device  # noqa: E402

_UNSUPPORTED_CODES = {"G", "HG", "S"}
_LT_LST_CODES = {"LTC", "LTS", "LSTC", "LSTS"}
_KNOWN_LAST_START_DEVICES = {
    "LZ": "LZ1",
}


@dataclass(frozen=True)
class ProbeResult:
    family: str
    device: str
    status: str
    detail: str


def _parse_target(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write-read-restore probe across supported device families using 10 addresses each"
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr")
    parser.add_argument("--network", type=lambda x: int(x, 0), default=0x00)
    parser.add_argument("--station", type=lambda x: int(x, 0), default=0xFF)
    parser.add_argument("--module-io", type=lambda x: int(x, 0), default=0x03FF)
    parser.add_argument("--multidrop", type=lambda x: int(x, 0), default=0x00)
    parser.add_argument(
        "--matrix",
        help="path to device_access_matrix.csv; default is internal_docs/<series>_<model>/device_access_matrix.csv",
    )
    parser.add_argument(
        "--boundary-spec-file",
        help=(
            "optional current_plc_boundary_specs file; when present, "
            "per-family counts are capped by the configured range"
        ),
    )
    parser.add_argument("--count", type=int, default=10, help="addresses per device family")
    parser.add_argument("--output", help="optional markdown output path")
    return parser.parse_args(list(argv) if argv is not None else None)


def _select_rows(rows: Sequence[DeviceMatrixRow]) -> list[DeviceMatrixRow]:
    selected: list[DeviceMatrixRow] = []
    for row in rows:
        code = row.device_code.upper()
        if code in _UNSUPPORTED_CODES:
            continue
        if not row.device or row.device.upper() == "N/A":
            continue
        if row.kind.lower() not in {"bit", "word", "dword"}:
            continue
        selected.append(row)
    return selected


def _read_value(client: SlmpClient, row: DeviceMatrixRow, device: str, *, series: str) -> int | bool:
    code = row.device_code.upper()
    number = parse_device(device).number
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
        return bool(client.read_devices(device, 1, bit_unit=True, series=series)[0])
    if kind == "word":
        return int(client.read_devices(device, 1, bit_unit=False, series=series)[0])
    if kind == "dword":
        return int(client.read_random(dword_devices=[device], series=series).dword[str(parse_device(device))])
    raise ValueError(f"unsupported probe row kind: {row.kind}")


def _write_value(client: SlmpClient, row: DeviceMatrixRow, device: str, value: int | bool, *, series: str) -> None:
    code = row.device_code.upper()
    if code in _LT_LST_CODES:
        client.write_random_bits([(device, bool(value))], series=series)
        return
    kind = row.kind.lower()
    if kind == "bit":
        client.write_devices(device, [1 if bool(value) else 0], bit_unit=True, series=series)
        return
    if kind == "word":
        client.write_devices(device, [int(value) & 0xFFFF], bit_unit=False, series=series)
        return
    if kind == "dword":
        client.write_random_words(dword_values=[(device, int(value) & 0xFFFFFFFF)], series=series)
        return
    raise ValueError(f"unsupported probe row kind: {row.kind}")


def _make_test_value(row: DeviceMatrixRow, before: int | bool) -> int | bool:
    if row.kind.lower() == "bit":
        return not bool(before)
    mask = 0x00000001 if row.kind.lower() == "dword" else 0x0001
    return int(before) ^ mask


def _default_boundary_spec_file(model_dir: Path) -> Path | None:
    candidates = sorted(model_dir.glob("current_plc_boundary_specs*.txt"))
    return candidates[-1] if candidates else None


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_target(argv)
    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
    ) as client:
        model = client.read_type_name().model.strip() or "unknown_target"
    matrix_path = (
        Path(args.matrix)
        if args.matrix
        else _model_folder_path(series=args.series, model=model) / "device_access_matrix.csv"
    )
    model_dir = matrix_path.parent
    boundary_spec_file = (
        Path(args.boundary_spec_file) if args.boundary_spec_file else _default_boundary_spec_file(model_dir)
    )
    output_path = args.output or _default_report_output(
        series=args.series,
        model=model,
        filename="supported_device_rw_probe_latest.md",
    )
    rows = _select_rows(_load_device_access_matrix_rows(matrix_path))
    boundary_limits: dict[str, int] = {}
    if boundary_spec_file and boundary_spec_file.exists():
        for spec in _load_boundary_specs(None, str(boundary_spec_file)):
            boundary_limits[parse_device(spec.last_device).code] = parse_device(spec.last_device).number
    for code, last_device in _KNOWN_LAST_START_DEVICES.items():
        boundary_limits.setdefault(code, parse_device(last_device).number)

    results: list[ProbeResult] = []
    status_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    family_ng_counts: Counter[str] = Counter()

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        default_target=target,
    ) as client:
        for row in rows:
            device = row.device
            start_no = parse_device(device).number
            code = row.device_code.upper()
            family_limit = args.count
            if code in boundary_limits:
                family_limit = min(args.count, max(0, boundary_limits[code] - start_no + 1))
            if family_limit <= 0:
                continue
            for _ in range(family_limit):
                try:
                    before = _read_value(client, row, device, series=args.series)
                    test_value = _make_test_value(row, before)
                    _write_value(client, row, device, test_value, series=args.series)
                    after = _read_value(client, row, device, series=args.series)
                    _write_value(client, row, device, before, series=args.series)
                    restored = _read_value(client, row, device, series=args.series)
                    detail = (
                        f"before={_format_manual_value(row.kind, before)}, "
                        f"test={_format_manual_value(row.kind, test_value)}, "
                        f"after={_format_manual_value(row.kind, after)}, "
                        f"restored={_format_manual_value(row.kind, restored)}"
                    )
                    ok = after == test_value and restored == before
                    status = "OK" if ok else "NG"
                    if not ok:
                        family_ng_counts[row.device_code] += 1
                except Exception as exc:  # noqa: BLE001
                    status = "NG"
                    detail = f"exception={exc}"
                    family_ng_counts[row.device_code] += 1
                results.append(ProbeResult(family=row.device_code, device=device, status=status, detail=detail))
                status_counts[status] += 1
                family_counts[row.device_code] += 1
                device = _increment_device_text(device)

    row_tuples = [(f"{r.family} {r.device}", r.status, r.detail) for r in results]
    family_summary = ", ".join(
        f"{code}:{family_counts[code]} tested/{family_ng_counts.get(code, 0)} NG" for code in sorted(family_counts)
    )
    _write_markdown_report(
        output_path,
        title="# Supported Device Write-Read Probe Report",
        header_lines=[
            f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            (
                f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
                f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
            ),
            f"- Matrix: `{matrix_path.as_posix()}`",
            f"- Families tested: {len(rows)}",
            f"- Requested addresses per family: {args.count}",
            (
                f"- Boundary spec file: `{boundary_spec_file.as_posix()}`"
                if boundary_spec_file and boundary_spec_file.exists()
                else "- Boundary spec file: none"
            ),
            f"- Summary: OK={status_counts.get('OK', 0)}, NG={status_counts.get('NG', 0)}",
            f"- Family summary: {family_summary}",
            "- Scope: all currently supported device families except typed-API-blocked `G`, `HG`, and `S`",
            "- Note: `LTC/LTS/LSTC/LSTS` use helper-backed read and `1402` random bit write in this probe",
        ],
        rows=row_tuples,
    )
    print(f"[DONE] report={output_path}")
    return 0 if status_counts.get("NG", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
