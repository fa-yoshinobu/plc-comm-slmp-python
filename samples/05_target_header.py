"""Sample script to read the type name using an explicit target header."""

from __future__ import annotations

import argparse

from _common import add_connection_args, add_target_args, build_target_from_args, create_client_from_args


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for reading the type name with target header."""
    parser = argparse.ArgumentParser(description="Read the type name using an explicit target header.")
    add_connection_args(parser)
    add_target_args(parser)
    return parser


def main() -> int:
    """Run the sample to read the type name with target header."""
    args = build_parser().parse_args()
    target = build_target_from_args(args)

    with create_client_from_args(args, default_target=target) as cli:
        info = cli.read_type_name()
        print(
            "target="
            f"network=0x{target.network:02X}, "
            f"station=0x{target.station:02X}, "
            f"module_io=0x{target.module_io:04X}, "
            f"multidrop=0x{target.multidrop:02X}"
        )
        print(f"model: {info.model or '<empty>'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
