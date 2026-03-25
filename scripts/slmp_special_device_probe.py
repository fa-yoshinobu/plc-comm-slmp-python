#!/usr/bin/env python
"""Focused live probe for G/HG and LT/LST-related devices."""

from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _int_auto(text: str) -> int:
    return int(text, 0)


def _sanitize(text: object) -> str:
    return str(text).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def _write_report(
    output: Path,
    *,
    header_lines: Sequence[str],
    rows: Sequence[tuple[str, str, str, str]],
) -> None:
    from slmp.cli import _write_text_report

    lines = ["# Focused Special Device Probe Report", ""]
    lines.extend(header_lines)
    lines.extend(["", "| Category | Item | Status | Detail |", "|---|---|---|---|"])
    for category, item, status, detail in rows:
        lines.append(f"| {category} | {item} | {status} | {detail} |")
    _write_text_report(output, "\n".join(lines) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    from slmp.cli import _resolve_report_output
    from slmp.client import SlmpClient
    from slmp.constants import DIRECT_MEMORY_CPU_BUFFER, DIRECT_MEMORY_MODULE_ACCESS, Command, PLCSeries
    from slmp.core import (
        SlmpPracticalPathWarning,
        SlmpTarget,
        decode_device_words,
        encode_device_spec,
        encode_extended_device_spec,
        resolve_device_subcommand,
    )

    parser = argparse.ArgumentParser(description="Focused probe for G/HG and LT/LST families")
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
        "--alt-target-module-io",
        type=_int_auto,
        default=0x03E0,
        help="alternative 4E header target module I/O for G/HG checks",
    )
    parser.add_argument(
        "--output",
        help="optional markdown output path; default is internal_docs/<series>_<model>/special_device_probe_latest.md",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    base_target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.module_io,
        multidrop=args.multidrop,
    )
    alt_target = SlmpTarget(
        network=args.network,
        station=args.station,
        module_io=args.alt_target_module_io,
        multidrop=args.multidrop,
    )
    resolved_series = PLCSeries(args.series)
    output_path = _resolve_report_output(
        output=args.output,
        series=args.series,
        host=args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        target=base_target,
        filename="special_device_probe_latest.md",
    )
    rows: list[tuple[str, str, str, str]] = []

    def record(category: str, item: str, status: str, detail: object) -> None:
        text = _sanitize(detail)
        rows.append((category, item, status, text))
        print(f"[{status}] {category} / {item}: {text}")

    def probe_random_bit_toggle(
        cli: SlmpClient,
        *,
        label: str,
        write_device: str,
        read_method_name: str,
    ) -> None:
        reader = getattr(cli, read_method_name)
        try:
            before = bool(reader(head_no=0, points=1, series=args.series)[0])
        except Exception as exc:  # noqa: BLE001
            record("LT/LST manual write", label, "NG", exc)
            return
        test = not before
        try:
            cli.write_random_bits({write_device: test}, series=args.series)
            after = bool(reader(head_no=0, points=1, series=args.series)[0])
            cli.write_random_bits({write_device: before}, series=args.series)
            restored = bool(reader(head_no=0, points=1, series=args.series)[0])
        except Exception as exc:  # noqa: BLE001
            record("LT/LST manual write", label, "NG", exc)
            return
        if after == test and restored == before:
            record(
                "LT/LST manual write",
                label,
                "OK",
                f"before={before}, test={test}, after={after}, restored={restored}",
            )
            return
        record(
            "LT/LST manual write",
            label,
            "WARN",
            (
                "command accepted but helper-state readback did not match the written bit; "
                f"before={before}, test={test}, after={after}, restored={restored}"
            ),
        )

    def probe_random_dword_toggle(
        cli: SlmpClient,
        *,
        label: str,
        device: str,
        read_current_value: Callable[[], int],
    ) -> None:
        try:
            before = int(read_current_value())
        except Exception as exc:  # noqa: BLE001
            record("LT/LST/LC manual write", label, "NG", exc)
            return
        test = 1 if before == 0 else 0
        try:
            cli.write_random_words(dword_values={device: test}, series=args.series)
            after = int(read_current_value())
            cli.write_random_words(dword_values={device: before}, series=args.series)
            restored = int(read_current_value())
        except Exception as exc:  # noqa: BLE001
            record("LT/LST/LC manual write", label, "NG", exc)
            return
        status = "OK" if after == test and restored == before else "WARN"
        record(
            "LT/LST/LC manual write",
            label,
            status,
            f"before={before}, test={test}, after={after}, restored={restored}",
        )

    def probe_word_bulk_word_toggle(
        cli: SlmpClient,
        *,
        label: str,
        device: str,
    ) -> None:
        try:
            before = int(cli.read_devices(device, 1, bit_unit=False, series=args.series)[0])
        except Exception as exc:  # noqa: BLE001
            record("LC manual write", label, "NG", exc)
            return
        test = 1 if before == 0 else 0
        try:
            cli.write_devices(device, [test], bit_unit=False, series=args.series)
            after = int(cli.read_devices(device, 1, bit_unit=False, series=args.series)[0])
            cli.write_devices(device, [before], bit_unit=False, series=args.series)
            restored = int(cli.read_devices(device, 1, bit_unit=False, series=args.series)[0])
        except Exception as exc:  # noqa: BLE001
            record("LC manual write", label, "NG", exc)
            return
        status = "OK" if after == test and restored == before else "WARN"
        record("LC manual write", label, status, f"before={before}, test={test}, after={after}, restored={restored}")

    def probe_bit_bulk_toggle(
        cli: SlmpClient,
        *,
        label: str,
        device: str,
    ) -> None:
        try:
            before = bool(cli.read_devices(device, 1, bit_unit=True, series=args.series)[0])
        except Exception as exc:  # noqa: BLE001
            record("LC manual write", label, "NG", exc)
            return
        test = not before
        try:
            cli.write_devices(device, [test], bit_unit=True, series=args.series)
            after = bool(cli.read_devices(device, 1, bit_unit=True, series=args.series)[0])
            cli.write_devices(device, [before], bit_unit=True, series=args.series)
            restored = bool(cli.read_devices(device, 1, bit_unit=True, series=args.series)[0])
        except Exception as exc:  # noqa: BLE001
            record("LC manual write", label, "NG", exc)
            return
        status = "OK" if after == test and restored == before else "WARN"
        record("LC manual write", label, status, f"before={before}, test={test}, after={after}, restored={restored}")

    def probe_random_bit_toggle_direct(
        cli: SlmpClient,
        *,
        label: str,
        device: str,
    ) -> None:
        try:
            before = bool(cli.read_devices(device, 1, bit_unit=True, series=args.series)[0])
        except Exception as exc:  # noqa: BLE001
            record("LC manual write", label, "NG", exc)
            return
        test = not before
        try:
            cli.write_random_bits({device: test}, series=args.series)
            after = bool(cli.read_devices(device, 1, bit_unit=True, series=args.series)[0])
            cli.write_random_bits({device: before}, series=args.series)
            restored = bool(cli.read_devices(device, 1, bit_unit=True, series=args.series)[0])
        except Exception as exc:  # noqa: BLE001
            record("LC manual write", label, "NG", exc)
            return
        status = "OK" if after == test and restored == before else "WARN"
        record("LC manual write", label, status, f"before={before}, test={test}, after={after}, restored={restored}")

    def probe_word_bulk_dword_toggle(
        cli: SlmpClient,
        *,
        label: str,
        device: str,
    ) -> None:
        try:
            before_words = [int(v) for v in cli.read_devices(device, 2, bit_unit=False, series=args.series)]
            before = int(cli.read_random(dword_devices=[device], series=args.series).dword[device])
        except Exception as exc:  # noqa: BLE001
            record("LC manual write", label, "NG", exc)
            return
        test = 1 if before == 0 else 0
        test_words = [test & 0xFFFF, (test >> 16) & 0xFFFF]
        try:
            cli.write_devices(device, test_words, bit_unit=False, series=args.series)
            after = int(cli.read_random(dword_devices=[device], series=args.series).dword[device])
            cli.write_devices(device, before_words, bit_unit=False, series=args.series)
            restored = int(cli.read_random(dword_devices=[device], series=args.series).dword[device])
        except Exception as exc:  # noqa: BLE001
            record("LC manual write", label, "NG", exc)
            return
        status = "OK" if after == test and restored == before else "WARN"
        record("LC manual write", label, status, f"before={before}, test={test}, after={after}, restored={restored}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SlmpPracticalPathWarning)
        with SlmpClient(
            args.host,
            port=args.port,
            transport=args.transport,
            timeout=args.timeout,
            plc_series=args.series,
            default_target=base_target,
        ) as cli:
            for device, helper_name in (
                ("LTC0", "read_ltc_states"),
                ("LTS0", "read_lts_states"),
                ("LSTC0", "read_lstc_states"),
                ("LSTS0", "read_lsts_states"),
            ):
                record(
                    "LT/LST direct",
                    f"{device} direct probe",
                    "SKIP",
                    (
                        "state devices are evaluated through helper-backed normal access on this project; "
                        f"use {helper_name}(head_no=0, points=1) instead of direct 0401/0406"
                    ),
                )

            try:
                words = cli.read_devices("LTN0", 4, bit_unit=False, series=args.series)
                record("LT/LST alternative", "LTN0 0401 word x4", "OK", f"values={words}")
            except Exception as exc:  # noqa: BLE001
                record("LT/LST alternative", "LTN0 0401 word x4", "NG", exc)

        try:
            decoded = cli.read_long_timer(head_no=0, points=1, series=args.series)
            record("LT/LST alternative", "read_long_timer(head_no=0, points=1)", "OK", decoded)
        except Exception as exc:  # noqa: BLE001
            record("LT/LST alternative", "read_long_timer(head_no=0, points=1)", "NG", exc)

        for item_name, method_name in (
            ("read_ltc_states(head_no=0, points=1)", "read_ltc_states"),
            ("read_lts_states(head_no=0, points=1)", "read_lts_states"),
        ):
            try:
                values = getattr(cli, method_name)(head_no=0, points=1, series=args.series)
                record("LT/LST helper", item_name, "OK", f"values={values}")
            except Exception as exc:  # noqa: BLE001
                record("LT/LST helper", item_name, "NG", exc)

        try:
            words = cli.read_devices("LSTN0", 4, bit_unit=False, series=args.series)
            record("LT/LST alternative", "LSTN0 0401 word x4", "OK", f"values={words}")
        except Exception as exc:  # noqa: BLE001
            record("LT/LST alternative", "LSTN0 0401 word x4", "NG", exc)

        try:
            decoded = cli.read_long_retentive_timer(head_no=0, points=1, series=args.series)
            record("LT/LST alternative", "read_long_retentive_timer(head_no=0, points=1)", "OK", decoded)
        except Exception as exc:  # noqa: BLE001
            record("LT/LST alternative", "read_long_retentive_timer(head_no=0, points=1)", "NG", exc)

        for item_name, method_name in (
            ("read_lstc_states(head_no=0, points=1)", "read_lstc_states"),
            ("read_lsts_states(head_no=0, points=1)", "read_lsts_states"),
        ):
            try:
                values = getattr(cli, method_name)(head_no=0, points=1, series=args.series)
                record("LT/LST helper", item_name, "OK", f"values={values}")
            except Exception as exc:  # noqa: BLE001
                record("LT/LST helper", item_name, "NG", exc)

        probe_random_bit_toggle(
            cli,
            label="LTC0 1402 bit random write with read_ltc_states readback",
            write_device="LTC0",
            read_method_name="read_ltc_states",
        )
        probe_random_bit_toggle(
            cli,
            label="LTS0 1402 bit random write with read_lts_states readback",
            write_device="LTS0",
            read_method_name="read_lts_states",
        )
        probe_random_bit_toggle(
            cli,
            label="LSTC0 1402 bit random write with read_lstc_states readback",
            write_device="LSTC0",
            read_method_name="read_lstc_states",
        )
        probe_random_bit_toggle(
            cli,
            label="LSTS0 1402 bit random write with read_lsts_states readback",
            write_device="LSTS0",
            read_method_name="read_lsts_states",
        )
        probe_random_dword_toggle(
            cli,
            label="LTN0 1402 dword random write",
            device="LTN0",
            read_current_value=lambda: cli.read_long_timer(head_no=0, points=1, series=args.series)[0].current_value,
        )
        probe_random_dword_toggle(
            cli,
            label="LSTN0 1402 dword random write",
            device="LSTN0",
            read_current_value=(
                lambda: cli.read_long_retentive_timer(head_no=0, points=1, series=args.series)[0].current_value
            ),
        )
        probe_random_dword_toggle(
            cli,
            label="LCN0 1402 dword random write",
            device="LCN0",
            read_current_value=lambda: cli.read_random(dword_devices=["LCN0"], series=args.series).dword["LCN0"],
        )
        probe_word_bulk_word_toggle(cli, label="LCS0 1401 word bulk write", device="LCS0")
        probe_bit_bulk_toggle(cli, label="LCC0 1401 bit bulk write", device="LCC0")
        probe_random_bit_toggle_direct(cli, label="LCC0 1402 bit random write", device="LCC0")
        probe_word_bulk_dword_toggle(cli, label="LCN0 1401 word bulk write", device="LCN0")

        for device in ("G0", "HG0"):
            try:
                sub = resolve_device_subcommand(bit_unit=False, series=resolved_series, extension=False)
                payload = encode_device_spec(device, series=resolved_series) + (1).to_bytes(2, "little")
                resp = cli.request(Command.DEVICE_READ, subcommand=sub, data=payload, raise_on_error=False)
                if resp.end_code == 0:
                    values = decode_device_words(resp.data)
                    record("G/HG direct", f"{device} raw 0401 normal", "OK", f"values={values}")
                else:
                    record(
                        "G/HG direct",
                        f"{device} raw 0401 normal",
                        "NG",
                        f"end_code=0x{resp.end_code:04X}",
                    )
            except Exception as exc:  # noqa: BLE001
                record("G/HG direct", f"{device} raw 0401 normal", "NG", exc)

        for module_no in (0x03E0, 0x0000, 0x03FF):
            for head in (0x00000000, 0x00000002, 0x00000004):
                try:
                    data = cli.extend_unit_read_bytes(head, 2, module_no)
                    record(
                        "G/HG alternative",
                        f"0601 module=0x{module_no:04X} head=0x{head:08X}",
                        "OK",
                        f"data={data.hex(' ')}",
                    )
                except Exception as exc:  # noqa: BLE001
                    record(
                        "G/HG alternative",
                        f"0601 module=0x{module_no:04X} head=0x{head:08X}",
                        "NG",
                        exc,
                    )

        try:
            before = cli.cpu_buffer_read_word(0x00000000)
            cli.cpu_buffer_write_word(0x00000000, before)
            after = cli.cpu_buffer_read_word(0x00000000)
            record(
                "G/HG helper",
                "cpu_buffer_write_word writeback @0x00000000",
                "OK",
                f"before=0x{before:04X}, after=0x{after:04X}",
            )
        except Exception as exc:  # noqa: BLE001
            record("G/HG helper", "cpu_buffer_write_word writeback @0x00000000", "NG", exc)

        try:
            before = cli.cpu_buffer_read_dword(0x00000000)
            cli.cpu_buffer_write_dword(0x00000000, before)
            after = cli.cpu_buffer_read_dword(0x00000000)
            record(
                "G/HG helper",
                "cpu_buffer_write_dword writeback @0x00000000",
                "OK",
                f"before=0x{before:08X}, after=0x{after:08X}",
            )
        except Exception as exc:  # noqa: BLE001
            record("G/HG helper", "cpu_buffer_write_dword writeback @0x00000000", "NG", exc)

        ghg_targets = [("cpu_default", base_target), ("module_header", alt_target)]
        ext_specs = (0x03E0, 0x3E00, 0x0000)
        direct_memories = (
            ("cpu_buffer", DIRECT_MEMORY_CPU_BUFFER),
            ("module_access", DIRECT_MEMORY_MODULE_ACCESS),
        )
        for target_name, target in ghg_targets:
            cli.default_target = target
            for device in ("G0", "HG0"):
                for ext_spec in ext_specs:
                    for memory_name, memory_code in direct_memories:
                        try:
                            extension = cli.make_extension_spec(
                                extension_specification=ext_spec,
                                direct_memory_specification=memory_code,
                                series=args.series,
                            )
                            sub = resolve_device_subcommand(bit_unit=False, series=resolved_series, extension=True)
                            payload = encode_extended_device_spec(device, series=resolved_series, extension=extension)
                            payload += (1).to_bytes(2, "little")
                            resp = cli.request(Command.DEVICE_READ, subcommand=sub, data=payload, raise_on_error=False)
                            if resp.end_code == 0:
                                values = decode_device_words(resp.data)
                                record(
                                    "G/HG extended_device",
                                    (
                                        f"{target_name} {device} raw 0401/0082 "
                                        f"ext=0x{ext_spec:04X} direct=0x{memory_code:02X}"
                                    ),
                                    "OK",
                                    f"mode={memory_name}, values={values}",
                                )
                            else:
                                record(
                                    "G/HG extended_device",
                                    (
                                        f"{target_name} {device} raw 0401/0082 "
                                        f"ext=0x{ext_spec:04X} direct=0x{memory_code:02X}"
                                    ),
                                    "NG",
                                    f"mode={memory_name}, end_code=0x{resp.end_code:04X}",
                                )
                        except Exception as exc:  # noqa: BLE001
                            record(
                                "G/HG extended_device",
                                (
                                    f"{target_name} {device} raw 0401/0082 "
                                    f"ext=0x{ext_spec:04X} direct=0x{memory_code:02X}"
                                ),
                                "NG",
                                f"mode={memory_name}, {exc}",
                            )

    output = Path(output_path)
    _write_report(
        output,
        header_lines=[
            f"- Host: {args.host}",
            f"- Port: {args.port}",
            f"- Transport: {args.transport}",
            f"- Series: {args.series}",
            (
                "- Target header: "
                f"network=0x{base_target.network:02X}, station=0x{base_target.station:02X}, "
                f"module_io=0x{base_target.module_io:04X}, multidrop=0x{base_target.multidrop:02X}"
            ),
            f"- Alternative target header module I/O for G/HG checks: 0x{alt_target.module_io:04X}",
        ],
        rows=rows,
    )
    print(f"[DONE] report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
