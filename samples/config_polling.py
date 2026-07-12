# ruff: noqa: E402
"""Read-only periodic collection driven by a JSON or YAML configuration file."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples._operational_common import (
    PlcEndpoint,
    TagSpec,
    monitor_endpoint,
    positive_float,
    positive_int,
    validate_profile,
)


@dataclass(frozen=True)
class PollingPlan:
    """Resolved polling plan from a config file."""

    endpoints: tuple[PlcEndpoint, ...]
    tags_by_plc: dict[str, tuple[TagSpec, ...]]
    csv_path: Path | None
    cycles: int | None
    initial_backoff: float
    max_backoff: float


class CsvSnapshotWriter:
    """Append tag values as long-form CSV rows."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()

    async def write_snapshot(self, endpoint: PlcEndpoint, snapshot: Mapping[str, object]) -> None:
        """Append one timestamped snapshot to the CSV file."""

        timestamp = datetime.now().isoformat(timespec="seconds")
        async with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            needs_header = not self._path.exists() or self._path.stat().st_size == 0
            with self._path.open("a", newline="", encoding="utf-8") as fp:
                writer = csv.writer(fp)
                if needs_header:
                    writer.writerow(["timestamp", "plc", "tag", "value"])
                for tag_name, value in snapshot.items():
                    writer.writerow([timestamp, endpoint.name, tag_name, value])


async def ignore_snapshot(_endpoint: PlcEndpoint, _snapshot: Mapping[str, object]) -> None:
    """Use when no CSV output was requested."""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Run read-only SLMP polling from a JSON or YAML config file.")
    parser.add_argument("--config", required=True, type=Path, help="Path to JSON or YAML polling config")
    parser.add_argument("--cycles", type=positive_int, default=None, help="Override config cycles")
    parser.add_argument("--once", action="store_true", help="Read one snapshot per PLC and exit")
    parser.add_argument("--initial-backoff", type=positive_float, default=None, help="Override first reconnect delay")
    parser.add_argument("--max-backoff", type=positive_float, default=None, help="Override maximum reconnect delay")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and print the plan without connecting")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    """Load a JSON config, or YAML when PyYAML is installed."""

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SystemExit("YAML config requires PyYAML. Use JSON or run: pip install PyYAML") from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    if not isinstance(data, dict):
        raise SystemExit("config root must be an object")
    return data


def as_mapping(value: object, *, field_name: str) -> Mapping[str, Any]:
    """Validate an object-like config section."""

    if not isinstance(value, dict):
        raise SystemExit(f"{field_name} must be an object")
    return value


def as_sequence(value: object, *, field_name: str) -> list[object]:
    """Validate a list-like config section."""

    if not isinstance(value, list):
        raise SystemExit(f"{field_name} must be a list")
    return value


def optional_float(section: Mapping[str, Any], key: str, default: float) -> float:
    """Read a float config value with a default."""

    value = section.get(key, default)
    if not isinstance(value, int | float):
        raise SystemExit(f"{key} must be a number")
    parsed = float(value)
    if parsed <= 0:
        raise SystemExit(f"{key} must be greater than zero")
    return parsed


def optional_int(section: Mapping[str, Any], key: str, default: int | None) -> int | None:
    """Read a positive integer config value with a default."""

    value = section.get(key, default)
    if value is None:
        return None
    if not isinstance(value, int):
        raise SystemExit(f"{key} must be an integer")
    if value <= 0:
        raise SystemExit(f"{key} must be greater than zero")
    return value


def parse_tags(raw_tags: object, *, plc_name: str) -> tuple[TagSpec, ...]:
    """Parse tag definitions from config."""

    tags: list[TagSpec] = []
    for index, raw in enumerate(as_sequence(raw_tags, field_name=f"plcs[{plc_name}].tags")):
        if isinstance(raw, str):
            tags.append(TagSpec(name=raw.replace(":", "_").replace(".", "_").lower(), address=raw))
            continue
        item = as_mapping(raw, field_name=f"plcs[{plc_name}].tags[{index}]")
        name = item.get("name")
        address = item.get("address")
        if not isinstance(name, str) or not isinstance(address, str):
            raise SystemExit(f"plcs[{plc_name}].tags[{index}] requires string name and address")
        tags.append(TagSpec(name=name, address=address))
    if not tags:
        raise SystemExit(f"plcs[{plc_name}].tags must contain at least one tag")
    return tuple(tags)


def resolve_path(config_path: Path, raw_path: object) -> Path | None:
    """Resolve an optional output path relative to the config file."""

    if raw_path is None:
        return None
    if not isinstance(raw_path, str):
        raise SystemExit("output.csv must be a string")
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()


def build_plan(config_path: Path, args: argparse.Namespace) -> PollingPlan:
    """Build a polling plan from config data and CLI overrides."""

    data = load_config(config_path)
    defaults = as_mapping(data.get("defaults", {}), field_name="defaults")
    output = as_mapping(data.get("output", {}), field_name="output")

    default_transport_raw = defaults.get("transport")
    if default_transport_raw is not None and not isinstance(default_transport_raw, str):
        raise SystemExit("defaults.transport must be tcp or udp")
    default_transport = default_transport_raw
    default_port_raw = defaults.get("port")
    if default_port_raw is not None and not isinstance(default_port_raw, int):
        raise SystemExit("defaults.port must be an integer")
    default_port = default_port_raw
    default_timeout = optional_float(defaults, "timeout", 3.0)
    default_interval = optional_float(defaults, "interval", 1.0)
    default_profile = defaults.get("plc_profile")
    if default_profile is not None and not isinstance(default_profile, str):
        raise SystemExit("defaults.plc_profile must be a string")

    endpoints: list[PlcEndpoint] = []
    tags_by_plc: dict[str, tuple[TagSpec, ...]] = {}
    for index, raw_plc in enumerate(as_sequence(data.get("plcs"), field_name="plcs")):
        plc = as_mapping(raw_plc, field_name=f"plcs[{index}]")
        name = plc.get("name")
        host = plc.get("host")
        profile = plc.get("plc_profile", default_profile)
        if not isinstance(name, str) or not isinstance(host, str) or not isinstance(profile, str):
            raise SystemExit(f"plcs[{index}] requires string name, host, and plc_profile")

        transport = plc.get("transport", default_transport)
        if transport not in {"tcp", "udp"}:
            raise SystemExit(f"plcs[{index}].transport is required and must be tcp or udp")
        port = plc.get("port", default_port)
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise SystemExit(f"plcs[{index}].port is required and must be an integer in range 1..65535")

        endpoint = PlcEndpoint(
            name=name,
            host=host,
            plc_profile=validate_profile(profile),
            port=port,
            transport=transport,
            timeout=optional_float(plc, "timeout", default_timeout),
            interval=optional_float(plc, "interval", default_interval),
        )
        endpoints.append(endpoint)
        tags_by_plc[name] = parse_tags(plc.get("tags"), plc_name=name)

    cycles = 1 if args.once else args.cycles
    if cycles is None:
        cycles = optional_int(data, "cycles", None)
    initial_backoff = (
        args.initial_backoff if args.initial_backoff is not None else optional_float(data, "initial_backoff", 1.0)
    )
    max_backoff = args.max_backoff if args.max_backoff is not None else optional_float(data, "max_backoff", 30.0)
    if max_backoff < initial_backoff:
        raise SystemExit("max_backoff must be greater than or equal to initial_backoff")

    return PollingPlan(
        endpoints=tuple(endpoints),
        tags_by_plc=tags_by_plc,
        csv_path=resolve_path(config_path, output.get("csv")),
        cycles=cycles,
        initial_backoff=initial_backoff,
        max_backoff=max_backoff,
    )


async def run(args: argparse.Namespace) -> None:
    """Run all configured polling tasks."""

    plan = build_plan(args.config, args)
    if args.dry_run:
        for endpoint in plan.endpoints:
            print(
                f"{endpoint.name}: {endpoint.transport} {endpoint.host}:{endpoint.port} "
                f"profile={endpoint.plc_profile} interval={endpoint.interval}s"
            )
            tags = ", ".join(f"{tag.name}={tag.address}" for tag in plan.tags_by_plc[endpoint.name])
            print(f"  tags: {tags}")
        print(f"cycles: {plan.cycles if plan.cycles is not None else 'forever'}")
        if plan.csv_path is not None:
            print(f"csv: {plan.csv_path}")
        return

    writer = CsvSnapshotWriter(plan.csv_path) if plan.csv_path is not None else None
    handler = writer.write_snapshot if writer is not None else ignore_snapshot

    await asyncio.gather(
        *(
            monitor_endpoint(
                endpoint,
                plan.tags_by_plc[endpoint.name],
                cycles=plan.cycles,
                initial_backoff=plan.initial_backoff,
                max_backoff=plan.max_backoff,
                handle_snapshot=handler,
            )
            for endpoint in plan.endpoints
        )
    )


def main() -> int:
    """CLI entry point."""

    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
