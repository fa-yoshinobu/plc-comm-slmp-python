"""Sample script to read random and array labels."""

from __future__ import annotations

import argparse

from _common import add_connection_args, create_client_from_args, int_auto

from slmp import LabelArrayReadPoint


def parse_label_array(value: str) -> LabelArrayReadPoint:
    """Parse a label array read specification from a string."""
    label, first_sep, rest = value.partition(":")
    unit_text, second_sep, length_text = rest.partition(":")
    if not first_sep or not second_sep:
        raise argparse.ArgumentTypeError("expected LABEL:UNIT_SPECIFICATION:ARRAY_DATA_LENGTH")
    return LabelArrayReadPoint(
        label=label,
        unit_specification=int_auto(unit_text),
        array_data_length=int_auto(length_text),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for label read examples."""
    parser = argparse.ArgumentParser(description="Read random labels and array labels.")
    add_connection_args(parser)
    parser.add_argument("--label-random", action="append", default=[], help="Random label name")
    parser.add_argument(
        "--label-array",
        action="append",
        type=parse_label_array,
        default=[],
        metavar="LABEL:UNIT_SPECIFICATION:ARRAY_DATA_LENGTH",
        help="Array label read spec",
    )
    return parser


def main() -> int:
    """Run the label read examples."""
    args = build_parser().parse_args()
    if not args.label_random and not args.label_array:
        raise SystemExit("specify at least one --label-random or --label-array entry")

    with create_client_from_args(args) as cli:
        if args.label_random:
            print("random label results:")
            random_items = cli.read_random_labels(args.label_random)
            for label, random_item in zip(args.label_random, random_items, strict=True):
                print(
                    f"  {label}: "
                    f"type=0x{random_item.data_type_id:02X}, "
                    f"length={random_item.read_data_length}, "
                    f"data={random_item.data.hex(' ')}"
                )

        if args.label_array:
            print("array label results:")
            array_items = cli.read_array_labels(args.label_array)
            for point, array_item in zip(args.label_array, array_items, strict=True):
                print(
                    f"  {point.label}: "
                    f"type=0x{array_item.data_type_id:02X}, "
                    f"unit={array_item.unit_specification}, "
                    f"array_len={array_item.array_data_length}, "
                    f"data={array_item.data.hex(' ')}"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
