"""Sample script to read the PLC type name and model code."""

from __future__ import annotations

import argparse

from _common import add_connection_args, create_client_from_args


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for reading the PLC type name."""
    parser = argparse.ArgumentParser(description="Read the PLC type name and model code.")
    add_connection_args(parser)
    return parser


def main() -> int:
    """Run the sample to read the PLC type name."""
    args = build_parser().parse_args()

    with create_client_from_args(args) as cli:
        info = cli.read_type_name()
        print(f"model: {info.model or '<empty>'}")
        if info.model_code is None:
            print("model_code: <none>")
        else:
            print(f"model_code: 0x{info.model_code:04X}")
        print(f"raw: {info.raw.hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
