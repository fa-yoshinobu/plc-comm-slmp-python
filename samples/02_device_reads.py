"""Sample script to read word and bit devices."""

from __future__ import annotations

import argparse

from _common import add_connection_args, create_client_from_args


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for reading word and bit devices."""
    parser = argparse.ArgumentParser(description="Read normal word and bit devices.")
    add_connection_args(parser)
    parser.add_argument("--word-device", default="D100", help="Representative word device, for example D100")
    parser.add_argument("--word-points", type=int, default=2, help="Number of word points to read")
    parser.add_argument("--bit-device", default="M100", help="Representative bit device, for example M100")
    parser.add_argument("--bit-points", type=int, default=5, help="Number of bit points to read")
    return parser


def main() -> int:
    """Run the sample to read word and bit devices."""
    args = build_parser().parse_args()
    if args.word_points < 0 or args.bit_points < 0:
        raise SystemExit("word-points and bit-points must be >= 0")

    with create_client_from_args(args) as cli:
        if args.word_points:
            words = cli.read_devices(args.word_device, args.word_points, bit_unit=False)
            print(f"{args.word_device} words: {words}")
        if args.bit_points:
            bits = cli.read_devices(args.bit_device, args.bit_points, bit_unit=True)
            print(f"{args.bit_device} bits: {bits}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
