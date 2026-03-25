"""Sample script to run read-only random and block access examples."""

from __future__ import annotations

import argparse

from _common import add_connection_args, create_client_from_args, parse_device_points


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for random and block access examples."""
    parser = argparse.ArgumentParser(description="Run read-only random and block access examples.")
    add_connection_args(parser)
    parser.add_argument("--random-word", action="append", default=["D100", "D101"], help="Random-read word device")
    parser.add_argument("--random-dword", action="append", default=["D200"], help="Random-read dword device")
    parser.add_argument(
        "--word-block",
        action="append",
        default=["D100:2"],
        metavar="DEVICE:POINTS",
        help="Word block read spec",
    )
    parser.add_argument(
        "--bit-block",
        action="append",
        default=["M200:1"],
        metavar="DEVICE:POINTS",
        help="Bit block read spec (packed 16-bit units)",
    )
    return parser


def main() -> int:
    """Run the random and block access examples."""
    args = build_parser().parse_args()
    word_blocks = [parse_device_points(spec) for spec in args.word_block]
    bit_blocks = [parse_device_points(spec) for spec in args.bit_block]

    with create_client_from_args(args) as cli:
        random_result = cli.read_random(word_devices=args.random_word, dword_devices=args.random_dword)
        print("random word values:")
        for device, value in random_result.word.items():
            print(f"  {device}: 0x{value:04X} ({value})")
        print("random dword values:")
        for device, value in random_result.dword.items():
            print(f"  {device}: 0x{value:08X} ({value})")

        block_result = cli.read_block(word_blocks=word_blocks, bit_blocks=bit_blocks)
        print("word blocks:")
        for block in block_result.word_blocks:
            print(f"  {block.device}: {block.values}")
        print("bit blocks (packed 16-bit words):")
        for block in block_result.bit_blocks:
            print(f"  {block.device}: {block.values}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
