#!/usr/bin/env python
"""Live comparison helper for block read/write mixed word+bit scenarios."""

from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slmp import SlmpClient, SlmpTarget, SlmpTraceFrame  # noqa: E402
from slmp.cli import _resolve_report_output, _write_text_report  # noqa: E402
from slmp.client import BlockReadResult  # noqa: E402


@dataclass(frozen=True)
class OperationResult:
    """Result of a single SLMP operation."""

    success: bool
    result: object | None
    end_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    error: str
    traces: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ScenarioResult:
    """Result of a test scenario."""

    name: str
    status: str
    summary: str
    end_codes: str
    memory_changed: str
    detail_lines: tuple[str, ...]
    traces: tuple[dict[str, Any], ...]


class TraceCollector:
    """Collector for SLMP request/response traces."""

    def __init__(self) -> None:
        """Initialize the trace collector."""
        self.events: list[dict[str, Any]] = []

    def __call__(self, trace: dict[str, Any] | SlmpTraceFrame) -> None:
        """Record a single trace event."""
        if isinstance(trace, SlmpTraceFrame):
            self.events.append(asdict(trace))
        else:
            self.events.append(dict(trace))

    def hook(self, trace: SlmpTraceFrame) -> None:
        """Record a single trace event from SlmpClient."""
        self.events.append(asdict(trace))

    def clear(self) -> None:
        """Clear all recorded trace events."""
        self.events.clear()

    def take(self) -> tuple[dict[str, Any], ...]:
        """Take a snapshot of recorded trace events and clear the buffer."""
        snapshot = tuple(self.events)
        self.events.clear()
        return snapshot


def _int_auto(text: str) -> int:
    return int(text, 0)


def _parse_u16_list(text: str) -> list[int]:
    values = [part.strip() for part in text.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one comma-separated value")
    parsed: list[int] = []
    for value in values:
        number = _int_auto(value)
        if number < 0 or number > 0xFFFF:
            raise argparse.ArgumentTypeError(f"value out of range (0..65535): {value}")
        parsed.append(number)
    return parsed


def _sanitize(text: object) -> str:
    return str(text).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def _hex_bytes(data: object) -> str:
    if isinstance(data, bytes):
        return data.hex(" ").upper() if data else "-"
    return "-"


def _format_values(values: list[int]) -> str:
    return "[" + ", ".join(f"0x{value:04X}" for value in values) + "]"


def _format_traces(traces: tuple[dict[str, Any], ...]) -> str:
    if not traces:
        return "none"
    lines: list[str] = []
    for index, trace in enumerate(traces, start=1):
        end_code = trace.get("response_end_code")
        end_text = "None" if end_code is None else f"0x{int(end_code):04X}"
        lines.append(f"attempt {index}: end_code={end_text}")
        lines.append(f"request: {_hex_bytes(trace.get('request_frame'))}")
        lines.append(f"response: {_hex_bytes(trace.get('response_frame'))}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_warnings(items: tuple[str, ...]) -> str:
    if not items:
        return "none"
    return " || ".join(items)


def _read_word_values(cli: SlmpClient, *, device: str, points: int, series: str) -> list[int]:
    result = cli.read_block(word_blocks=[(device, points)], bit_blocks=(), series=series)
    return [int(value) for value in result.word_blocks[0].values]


def _read_bit_values(cli: SlmpClient, *, device: str, points: int, series: str) -> list[int]:
    result = cli.read_block(word_blocks=(), bit_blocks=[(device, points)], series=series)
    return [int(value) for value in result.bit_blocks[0].values]


def _run_operation(collector: TraceCollector, func: Callable[[], object]) -> OperationResult:
    collector.clear()
    captured_result: object | None = None
    error = ""
    success = True
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            captured_result = func()
        except Exception as exc:  # noqa: BLE001
            success = False
            error = str(exc)
    traces = collector.take()
    end_codes = tuple(
        "None" if trace.get("response_end_code") is None else f"0x{int(trace['response_end_code']):04X}"
        for trace in traces
    )
    if not end_codes and not success and error:
        end_codes = ("none",)
    warning_messages = tuple(str(item.message) for item in caught)
    return OperationResult(
        success=success,
        result=captured_result,
        end_codes=end_codes,
        warnings=warning_messages,
        error=error or "none",
        traces=traces,
    )


def _restore_word_values(
    cli: SlmpClient,
    collector: TraceCollector,
    *,
    device: str,
    values: list[int],
    series: str,
) -> tuple[str, str]:
    collector.clear()
    try:
        cli.write_block(word_blocks=[(device, values)], bit_blocks=(), series=series)
        collector.clear()
        restored = _read_word_values(cli, device=device, points=len(values), series=series)
    except Exception as exc:  # noqa: BLE001
        collector.clear()
        return "NG", f"restore_error={exc}"
    return ("OK", _format_values(restored)) if restored == values else ("WARN", _format_values(restored))


def _restore_bit_values(
    cli: SlmpClient,
    collector: TraceCollector,
    *,
    device: str,
    values: list[int],
    series: str,
) -> tuple[str, str]:
    collector.clear()
    try:
        cli.write_block(word_blocks=(), bit_blocks=[(device, values)], series=series)
        collector.clear()
        restored = _read_bit_values(cli, device=device, points=len(values), series=series)
    except Exception as exc:  # noqa: BLE001
        collector.clear()
        return "NG", f"restore_error={exc}"
    return ("OK", _format_values(restored)) if restored == values else ("WARN", _format_values(restored))


def _summarize_status(*, success: bool, after_matches: bool, restore_ok: bool | None) -> str:
    if not success:
        return "NG"
    if after_matches and (restore_ok is None or restore_ok):
        return "OK"
    return "WARN"


def _scenario_read_mixed(
    cli: SlmpClient,
    collector: TraceCollector,
    *,
    word_device: str,
    word_points: int,
    bit_device: str,
    bit_points: int,
    series: str,
) -> ScenarioResult:
    operation = _run_operation(
        collector,
        lambda: cli.read_block(
            word_blocks=[(word_device, word_points)],
            bit_blocks=[(bit_device, bit_points)],
            series=series,
            split_mixed_blocks=False,
        ),
    )
    detail_lines = [
        (
            "API: read_block("
            f"word_blocks=[('{word_device}', {word_points})], "
            f"bit_blocks=[('{bit_device}', {bit_points})], split_mixed_blocks=False)"
        ),
        f"Devices: word={word_device} x{word_points}, bit={bit_device} x{bit_points} packed",
        f"Warnings: {_format_warnings(operation.warnings)}",
        f"Error: {operation.error}",
    ]
    summary = "read failed"
    if operation.success and isinstance(operation.result, BlockReadResult):
        words = [int(value) for value in operation.result.word_blocks[0].values]
        bits = [int(value) for value in operation.result.bit_blocks[0].values]
        detail_lines.extend(
            [
                f"Returned words: {_format_values(words)}",
                f"Returned bits: {_format_values(bits)}",
            ]
        )
        summary = f"words={_format_values(words)}, bits={_format_values(bits)}"
    return ScenarioResult(
        name="readBlock words+bits",
        status="OK" if operation.success else "NG",
        summary=summary,
        end_codes=" -> ".join(operation.end_codes) if operation.end_codes else "none",
        memory_changed="n/a",
        detail_lines=tuple(detail_lines),
        traces=operation.traces,
    )


def _scenario_write_words(
    cli: SlmpClient,
    collector: TraceCollector,
    *,
    device: str,
    before: list[int],
    test_values: list[int],
    keep_written_value: bool,
    series: str,
) -> ScenarioResult:
    operation = _run_operation(
        collector,
        lambda: cli.write_block(word_blocks=[(device, test_values)], bit_blocks=(), series=series),
    )
    after_text = "unavailable"
    after_matches = False
    memory_changed = "unknown"
    restore_status = "SKIP"
    restored_text = "not_checked"
    restore_ok: bool | None = None
    try:
        after = _read_word_values(cli, device=device, points=len(test_values), series=series)
        after_text = _format_values(after)
        after_matches = after == test_values
        memory_changed = "yes" if after != before else "no"
        if keep_written_value:
            restore_status = "KEPT"
            restored_text = "kept_written_value"
            restore_ok = None
        elif after != before:
            restore_status, restored_text = _restore_word_values(
                cli,
                collector,
                device=device,
                values=before,
                series=series,
            )
            restore_ok = restore_status == "OK"
        else:
            restore_status = "SKIP"
            restored_text = "unchanged"
            restore_ok = True
    except Exception as exc:  # noqa: BLE001
        after_text = f"readback_error={exc}"
        restore_status = "SKIP"
        restored_text = "not_checked"
        restore_ok = False if operation.success else None
    status = _summarize_status(success=operation.success, after_matches=after_matches, restore_ok=restore_ok)
    return ScenarioResult(
        name="writeBlock words only",
        status=status,
        summary=f"after={after_text}, restore={restore_status}",
        end_codes=" -> ".join(operation.end_codes) if operation.end_codes else "none",
        memory_changed=memory_changed,
        detail_lines=(
            f"API: write_block(word_blocks=[('{device}', {_format_values(test_values)})], bit_blocks=[])",
            f"Before words: {_format_values(before)}",
            f"Test words: {_format_values(test_values)}",
            f"After words: {after_text}",
            f"Restore status: {restore_status}",
            f"Restored words: {restored_text}",
            f"Warnings: {_format_warnings(operation.warnings)}",
            f"Error: {operation.error}",
        ),
        traces=operation.traces,
    )


def _scenario_write_bits(
    cli: SlmpClient,
    collector: TraceCollector,
    *,
    device: str,
    before: list[int],
    test_values: list[int],
    keep_written_value: bool,
    series: str,
) -> ScenarioResult:
    operation = _run_operation(
        collector,
        lambda: cli.write_block(word_blocks=(), bit_blocks=[(device, test_values)], series=series),
    )
    after_text = "unavailable"
    after_matches = False
    memory_changed = "unknown"
    restore_status = "SKIP"
    restored_text = "not_checked"
    restore_ok: bool | None = None
    try:
        after = _read_bit_values(cli, device=device, points=len(test_values), series=series)
        after_text = _format_values(after)
        after_matches = after == test_values
        memory_changed = "yes" if after != before else "no"
        if keep_written_value:
            restore_status = "KEPT"
            restored_text = "kept_written_value"
            restore_ok = None
        elif after != before:
            restore_status, restored_text = _restore_bit_values(
                cli,
                collector,
                device=device,
                values=before,
                series=series,
            )
            restore_ok = restore_status == "OK"
        else:
            restore_status = "SKIP"
            restored_text = "unchanged"
            restore_ok = True
    except Exception as exc:  # noqa: BLE001
        after_text = f"readback_error={exc}"
        restore_status = "SKIP"
        restored_text = "not_checked"
        restore_ok = False if operation.success else None
    status = _summarize_status(success=operation.success, after_matches=after_matches, restore_ok=restore_ok)
    return ScenarioResult(
        name="writeBlock bits only",
        status=status,
        summary=f"after={after_text}, restore={restore_status}",
        end_codes=" -> ".join(operation.end_codes) if operation.end_codes else "none",
        memory_changed=memory_changed,
        detail_lines=(
            f"API: write_block(word_blocks=[], bit_blocks=[('{device}', {_format_values(test_values)})])",
            f"Before bits: {_format_values(before)}",
            f"Test bits: {_format_values(test_values)}",
            f"After bits: {after_text}",
            f"Restore status: {restore_status}",
            f"Restored bits: {restored_text}",
            f"Warnings: {_format_warnings(operation.warnings)}",
            f"Error: {operation.error}",
        ),
        traces=operation.traces,
    )


def _scenario_write_mixed(
    cli: SlmpClient,
    collector: TraceCollector,
    *,
    word_device: str,
    word_before: list[int],
    word_test_values: list[int],
    bit_device: str,
    bit_before: list[int],
    bit_test_values: list[int],
    keep_written_value: bool,
    split_mixed_blocks: bool,
    retry_mixed_on_error: bool,
    series: str,
) -> ScenarioResult:
    operation = _run_operation(
        collector,
        lambda: cli.write_block(
            word_blocks=[(word_device, word_test_values)],
            bit_blocks=[(bit_device, bit_test_values)],
            series=series,
            split_mixed_blocks=split_mixed_blocks,
            retry_mixed_on_error=retry_mixed_on_error,
        ),
    )
    after_words_text = "unavailable"
    after_bits_text = "unavailable"
    after_matches = False
    memory_changed = "unknown"
    restore_status = "SKIP"
    restored_words_text = "not_checked"
    restored_bits_text = "not_checked"
    restore_ok: bool | None = None
    try:
        after_words = _read_word_values(cli, device=word_device, points=len(word_test_values), series=series)
        after_bits = _read_bit_values(cli, device=bit_device, points=len(bit_test_values), series=series)
        after_words_text = _format_values(after_words)
        after_bits_text = _format_values(after_bits)
        after_matches = after_words == word_test_values and after_bits == bit_test_values
        memory_changed = "yes" if after_words != word_before or after_bits != bit_before else "no"
        if keep_written_value:
            restore_status = "KEPT"
            restored_words_text = "kept_written_value"
            restored_bits_text = "kept_written_value"
            restore_ok = None
        elif memory_changed == "yes":
            word_restore_status, restored_words_text = _restore_word_values(
                cli,
                collector,
                device=word_device,
                values=word_before,
                series=series,
            )
            bit_restore_status, restored_bits_text = _restore_bit_values(
                cli,
                collector,
                device=bit_device,
                values=bit_before,
                series=series,
            )
            restore_ok = word_restore_status == "OK" and bit_restore_status == "OK"
            if word_restore_status == "OK" and bit_restore_status == "OK":
                restore_status = "OK"
            elif word_restore_status == "NG" or bit_restore_status == "NG":
                restore_status = "NG"
            else:
                restore_status = "WARN"
        else:
            restore_status = "SKIP"
            restored_words_text = "unchanged"
            restored_bits_text = "unchanged"
            restore_ok = True
    except Exception as exc:  # noqa: BLE001
        after_words_text = f"readback_error={exc}"
        after_bits_text = f"readback_error={exc}"
        restore_status = "SKIP"
        restore_ok = False if operation.success else None
    status = _summarize_status(success=operation.success, after_matches=after_matches, restore_ok=restore_ok)
    request_count = len(operation.traces)
    return ScenarioResult(
        name="writeBlock mixed",
        status=status,
        summary=f"after_words={after_words_text}, after_bits={after_bits_text}, request_count={request_count}",
        end_codes=" -> ".join(operation.end_codes) if operation.end_codes else "none",
        memory_changed=memory_changed,
        detail_lines=(
            (
                "API: write_block("
                f"word_blocks=[('{word_device}', {_format_values(word_test_values)})], "
                f"bit_blocks=[('{bit_device}', {_format_values(bit_test_values)})], "
                f"split_mixed_blocks={split_mixed_blocks}, retry_mixed_on_error={retry_mixed_on_error})"
            ),
            f"Before words: {_format_values(word_before)}",
            f"Before bits: {_format_values(bit_before)}",
            f"Test words: {_format_values(word_test_values)}",
            f"Test bits: {_format_values(bit_test_values)}",
            f"After words: {after_words_text}",
            f"After bits: {after_bits_text}",
            f"Request count: {request_count}",
            f"Restore status: {restore_status}",
            f"Restored words: {restored_words_text}",
            f"Restored bits: {restored_bits_text}",
            f"Warnings: {_format_warnings(operation.warnings)}",
            f"Error: {operation.error}",
        ),
        traces=operation.traces,
    )


def _write_report(
    output: Path,
    *,
    header_lines: list[str],
    scenarios: list[ScenarioResult],
) -> None:
    lines = ["# Mixed Block Comparison Report", ""]
    lines.extend(header_lines)
    lines.extend(
        [
            "",
            "| Scenario | Status | End codes | Memory changed | Trace count | Notes |",
            "|---|---|---|---|---|---|",
        ]
    )
    for scenario in scenarios:
        lines.append(
            "| "
            f"{scenario.name} | {scenario.status} | {scenario.end_codes} | {scenario.memory_changed} | "
            f"{len(scenario.traces)} | {_sanitize(scenario.summary)} |"
        )
    for scenario in scenarios:
        lines.extend(["", f"## {scenario.name}", ""])
        for detail_line in scenario.detail_lines:
            lines.append(f"- {detail_line}")
        lines.extend(["", "```text", _format_traces(scenario.traces), "```"])
    _write_text_report(output, "\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Main entry point for mixed block comparison."""
    parser = argparse.ArgumentParser(description="Compare word-only, bit-only, and mixed block access on a live PLC")
    parser.add_argument("--host", required=True, help="PLC or Ethernet module host name / IP")
    parser.add_argument("--port", type=int, default=1025, help="SLMP port number")
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp", help="Transport protocol")
    parser.add_argument("--series", choices=("ql", "iqr"), default="iqr", help="PLC device encoding family")
    parser.add_argument("--timeout", type=float, default=3.0, help="Socket timeout in seconds")
    parser.add_argument("--monitoring-timer", type=_int_auto, default=0x0010, help="SLMP monitoring timer")
    parser.add_argument("--network", type=_int_auto, default=0x00, help="Target network number")
    parser.add_argument("--station", type=_int_auto, default=0xFF, help="Target station number")
    parser.add_argument("--module-io", type=_int_auto, default=0x03FF, help="Target module I/O number")
    parser.add_argument("--multidrop", type=_int_auto, default=0x00, help="Target multidrop station number")
    parser.add_argument("--word-device", default="D300", help="Word block device head")
    parser.add_argument(
        "--word-values",
        type=_parse_u16_list,
        default=_parse_u16_list("0x87F7,0x80BE"),
        help="Comma-separated word values, for example 0x87F7,0x80BE",
    )
    parser.add_argument("--bit-device", default="M200", help="Bit block device head")
    parser.add_argument(
        "--bit-values",
        type=_parse_u16_list,
        default=_parse_u16_list("0x6DFE"),
        help="Comma-separated packed 16-bit bit-block values, for example 0x6DFE",
    )
    parser.add_argument(
        "--split-mixed-blocks",
        action="store_true",
        help="Send the mixed write as two requests instead of one combined request",
    )
    parser.add_argument(
        "--retry-mixed-on-error",
        action="store_true",
        help="Try one mixed write first and only split on known mixed-write rejection end codes",
    )
    parser.add_argument(
        "--keep-written-value",
        action="store_true",
        help="Do not restore the original PLC values after each write scenario",
    )
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is internal_docs/<series>_<model>/mixed_block_compare_latest.md",
    )
    args = parser.parse_args(argv)

    target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    collector = TraceCollector()

    with SlmpClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_series=args.series,
        monitoring_timer=args.monitoring_timer,
        default_target=target,
        trace_hook=collector.hook,
    ) as cli:
        model = cli.read_type_name().model.strip() or "unknown_target"
        collector.clear()

        word_before = _read_word_values(cli, device=args.word_device, points=len(args.word_values), series=args.series)
        bit_before = _read_bit_values(cli, device=args.bit_device, points=len(args.bit_values), series=args.series)

        scenarios = [
            _scenario_read_mixed(
                cli,
                collector,
                word_device=args.word_device,
                word_points=len(args.word_values),
                bit_device=args.bit_device,
                bit_points=len(args.bit_values),
                series=args.series,
            ),
            _scenario_write_words(
                cli,
                collector,
                device=args.word_device,
                before=word_before,
                test_values=list(args.word_values),
                keep_written_value=args.keep_written_value,
                series=args.series,
            ),
            _scenario_write_bits(
                cli,
                collector,
                device=args.bit_device,
                before=bit_before,
                test_values=list(args.bit_values),
                keep_written_value=args.keep_written_value,
                series=args.series,
            ),
            _scenario_write_mixed(
                cli,
                collector,
                word_device=args.word_device,
                word_before=word_before,
                word_test_values=list(args.word_values),
                bit_device=args.bit_device,
                bit_before=bit_before,
                bit_test_values=list(args.bit_values),
                keep_written_value=args.keep_written_value,
                split_mixed_blocks=args.split_mixed_blocks,
                retry_mixed_on_error=args.retry_mixed_on_error,
                series=args.series,
            ),
        ]

    output_path = Path(
        _resolve_report_output(
            output=args.output,
            series=args.series,
            host=args.host,
            port=args.port,
            transport=args.transport,
            timeout=args.timeout,
            target=target,
            filename="mixed_block_compare_latest.md",
        )
    )
    header_lines = [
        f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Host: {args.host}",
        f"- Port: {args.port}",
        f"- Transport: {args.transport}",
        f"- Series: {args.series}",
        f"- Model: {model}",
        (
            f"- Target: network=0x{target.network:02X}, station=0x{target.station:02X}, "
            f"module_io=0x{target.module_io:04X}, multidrop=0x{target.multidrop:02X}"
        ),
        f"- Word block: {args.word_device} x{len(args.word_values)} -> {_format_values(list(args.word_values))}",
        f"- Bit block: {args.bit_device} x{len(args.bit_values)} packed -> {_format_values(list(args.bit_values))}",
        (
            "- Mixed write options: "
            f"split_mixed_blocks={args.split_mixed_blocks}, "
            f"retry_mixed_on_error={args.retry_mixed_on_error}"
        ),
        f"- Keep written value: {args.keep_written_value}",
        (
            "- First-pass comparison recommendation: keep both mixed-write "
            "fallback options disabled so the first PLC response is preserved"
        ),
        (
            "- Note: if retry_mixed_on_error=True triggers an internal retry, the reported memory-changed state is the "
            "post-call state, not an observation between the first failed request and the retry"
        ),
    ]
    _write_report(output_path, header_lines=header_lines, scenarios=scenarios)
    print(f"[DONE] report={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
