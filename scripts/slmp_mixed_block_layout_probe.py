#!/usr/bin/env python
"""Live probe: compare 0x1406 Write Block payload layouts on a real PLC.

Resolved investigation:
internal_docs/validation/reports/MIXED_BLOCK_WRITE_1406_LAYOUT_ROOT_CAUSE_2026-06-12.md
records why [all block specs][all word data][all bit data] is invalid for
mixed or multi-block writes. The SLMP manual (sh080956engn.pdf PDF pages 76-78)
shows each block's write data inline immediately after that block's own spec.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slmp import SlmpClient, SlmpTarget  # noqa: E402

DEVICE_CODES = {
    "ql": {"D": 0xA8, "M": 0x90},
    "iqr": {"D": 0x00A8, "M": 0x0090},
}


def spec(series: str, device: str, number: int) -> bytes:
    code = DEVICE_CODES[series][device]
    if series == "iqr":
        return number.to_bytes(4, "little") + code.to_bytes(2, "little")
    return number.to_bytes(3, "little") + code.to_bytes(1, "little")


def words(values: list[int]) -> bytes:
    return b"".join(v.to_bytes(2, "little") for v in values)


def payload_manual_layout(
    series: str,
    word_blocks: list[tuple[str, int, list[int]]],
    bit_blocks: list[tuple[str, int, list[int]]],
) -> bytes:
    """Manual-conformant: each block spec immediately followed by its data."""
    out = bytearray([len(word_blocks), len(bit_blocks)])
    for dev, num, values in word_blocks:
        out += spec(series, dev, num) + len(values).to_bytes(2, "little") + words(values)
    for dev, num, values in bit_blocks:
        out += spec(series, dev, num) + len(values).to_bytes(2, "little") + words(values)
    return bytes(out)


def payload_current_layout(
    series: str,
    word_blocks: list[tuple[str, int, list[int]]],
    bit_blocks: list[tuple[str, int, list[int]]],
) -> bytes:
    """Replicates the current library layout: all specs first, then all data."""
    out = bytearray([len(word_blocks), len(bit_blocks)])
    for dev, num, values in word_blocks:
        out += spec(series, dev, num) + len(values).to_bytes(2, "little")
    for dev, num, values in bit_blocks:
        out += spec(series, dev, num) + len(values).to_bytes(2, "little")
    for _, _, values in word_blocks:
        out += words(values)
    for _, _, values in bit_blocks:
        out += words(values)
    return bytes(out)


def fmt(values: list[int]) -> str:
    return "[" + ", ".join(f"0x{v:04X}" for v in values) + "]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.250.100")
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--series", choices=("ql", "iqr"), default=None, help="auto-detect from model when omitted")
    parser.add_argument("--frame-type", choices=("3e", "4e"), default="4e")
    args = parser.parse_args()

    target = SlmpTarget(network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00)
    with SlmpClient(
        args.host,
        port=args.port,
        transport="tcp",
        timeout=3.0,
        frame_type=args.frame_type,
        plc_series=args.series or "ql",
        monitoring_timer=0x0010,
        default_target=target,
    ) as cli:
        try:
            model = cli.read_type_name().model.strip()
        except Exception as exc:  # noqa: BLE001 - some targets do not support 0x0101
            model = f"unknown({exc})"
        series = args.series
        if series is None:
            series = "iqr" if model.upper().startswith("R") else "ql"
        subcommand = 0x0002 if series == "iqr" else 0x0000
        print(f"model={model} series={series} subcommand=0x{subcommand:04X}")
        print()

        def read_d(num: int, points: int) -> list[int]:
            r = cli.read_block(word_blocks=[(f"D{num}", points)], bit_blocks=(), series=series)
            return [int(v) for v in r.word_blocks[0].values]

        def read_m(num: int, points: int) -> list[int]:
            r = cli.read_block(word_blocks=(), bit_blocks=[(f"M{num}", points)], series=series)
            return [int(v) for v in r.bit_blocks[0].values]

        before_d300 = read_d(300, 2)
        before_d310 = read_d(310, 2)
        before_m200 = read_m(200, 1)
        print(f"before: D300x2={fmt(before_d300)} D310x2={fmt(before_d310)} M200={fmt(before_m200)}")
        print()

        def send(name: str, payload: bytes, expect_d300=None, expect_d310=None, expect_m200=None) -> None:
            resp = cli.raw_command(0x1406, subcommand=subcommand, payload=payload, raise_on_error=False)
            line = f"{name}: end_code=0x{resp.end_code:04X}"
            checks = []
            if expect_d300 is not None:
                got = read_d(300, 2)
                status = "MATCH" if got == expect_d300 else f"MISMATCH(exp {fmt(expect_d300)})"
                checks.append(f"D300={fmt(got)} {status}")
            if expect_d310 is not None:
                got = read_d(310, 2)
                status = "MATCH" if got == expect_d310 else f"MISMATCH(exp {fmt(expect_d310)})"
                checks.append(f"D310={fmt(got)} {status}")
            if expect_m200 is not None:
                got = read_m(200, 1)
                status = "MATCH" if got == expect_m200 else f"MISMATCH(exp {fmt(expect_m200)})"
                checks.append(f"M200={fmt(got)} {status}")
            print(line)
            print(f"  payload: {payload.hex(' ').upper()}")
            for check in checks:
                print(f"  {check}")
            print()

        # 1. mixed word+bit, current library layout (specs..., then data)
        wb = [("D", 300, [0x1111, 0x2222])]
        bb = [("M", 200, [0x00FF])]
        send(
            "mixed 1word+1bit CURRENT layout",
            payload_current_layout(series, wb, bb),
            expect_d300=[0x1111, 0x2222],
            expect_m200=[0x00FF],
        )

        # 2. mixed word+bit, manual layout (spec+data inline per block)
        wb = [("D", 300, [0x3333, 0x4444])]
        bb = [("M", 200, [0x0F0F])]
        send(
            "mixed 1word+1bit MANUAL layout",
            payload_manual_layout(series, wb, bb),
            expect_d300=[0x3333, 0x4444],
            expect_m200=[0x0F0F],
        )

        # 3. two word blocks, current library layout
        wb = [("D", 300, [0x5555, 0x6666]), ("D", 310, [0x7777, 0x8888])]
        send(
            "2 word blocks CURRENT layout",
            payload_current_layout(series, wb, []),
            expect_d300=[0x5555, 0x6666],
            expect_d310=[0x7777, 0x8888],
        )

        # 4. two word blocks, manual layout
        wb = [("D", 300, [0x9999, 0xAAAA]), ("D", 310, [0xBBBB, 0xCCCC])]
        send(
            "2 word blocks MANUAL layout",
            payload_manual_layout(series, wb, []),
            expect_d300=[0x9999, 0xAAAA],
            expect_d310=[0xBBBB, 0xCCCC],
        )

        # restore originals via known-good single-block writes
        cli.write_block(word_blocks=[("D300", before_d300)], bit_blocks=(), series=series)
        cli.write_block(word_blocks=[("D310", before_d310)], bit_blocks=(), series=series)
        cli.write_block(word_blocks=(), bit_blocks=[("M200", before_m200)], series=series)
        after_d300 = read_d(300, 2)
        after_d310 = read_d(310, 2)
        after_m200 = read_m(200, 1)
        restored = after_d300 == before_d300 and after_d310 == before_d310 and after_m200 == before_m200
        print(
            f"restore: D300={fmt(after_d300)} D310={fmt(after_d310)} "
            f"M200={fmt(after_m200)} -> {'OK' if restored else 'NG'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
