#!/usr/bin/env python3
"""Verify that a release tag, source versions, and built artifacts agree."""

from __future__ import annotations

import argparse
import email
import importlib
import re
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "plc-comm-slmp"
WHEEL_NAME = "plc_comm_slmp"


def version_from_tag(tag: str) -> str:
    if not tag.startswith("v") or len(tag) == 1:
        raise ValueError(f"release tag must start with 'v': {tag!r}")
    return tag[1:]


def source_versions(root: Path = ROOT) -> tuple[str, str]:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    project_section = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", pyproject)
    version_match = (
        re.search(r'^version\s*=\s*"([^"]+)"\s*$', project_section.group(1), re.MULTILINE) if project_section else None
    )
    if version_match is None:
        raise ValueError("pyproject.toml [project] does not define a string version")
    project_version = version_match.group(1)
    runtime_version = str(importlib.import_module("slmp").__version__)
    return project_version, runtime_version


def validate_source_versions(tag: str, root: Path = ROOT) -> str:
    expected = version_from_tag(tag)
    project_version, runtime_version = source_versions(root)
    if project_version != expected or runtime_version != expected:
        raise ValueError(
            f"release version mismatch: tag={expected}, pyproject={project_version}, slmp.__version__={runtime_version}"
        )
    return expected


def read_metadata(payload: bytes, artifact: Path) -> tuple[str, str]:
    metadata = email.message_from_bytes(payload)
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise ValueError(f"{artifact.name} has incomplete package metadata")
    return name, version


def wheel_metadata(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError(f"{path.name} must contain exactly one .dist-info/METADATA file")
        return read_metadata(archive.read(names[0]), path)


def sdist_metadata(path: Path) -> tuple[str, str]:
    with tarfile.open(path, "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if len(Path(member.name).parts) == 2 and Path(member.name).name == "PKG-INFO"
        ]
        if len(members) != 1:
            raise ValueError(f"{path.name} must contain exactly one top-level PKG-INFO file")
        stream = archive.extractfile(members[0])
        if stream is None:
            raise ValueError(f"cannot read package metadata from {path.name}")
        return read_metadata(stream.read(), path)


def validate_dist(dist: Path, version: str) -> None:
    expected = {
        f"{WHEEL_NAME}-{version}-py3-none-any.whl",
        f"{WHEEL_NAME}-{version}.tar.gz",
    }
    actual = {path.name for path in dist.iterdir() if path.is_file()}
    if actual != expected:
        raise ValueError(f"release artifact names mismatch: expected={sorted(expected)}, actual={sorted(actual)}")

    artifacts = [dist / name for name in sorted(expected)]
    for artifact in artifacts:
        name, artifact_version = wheel_metadata(artifact) if artifact.suffix == ".whl" else sdist_metadata(artifact)
        if name != PACKAGE_NAME or artifact_version != version:
            raise ValueError(
                f"{artifact.name} metadata mismatch: expected {PACKAGE_NAME} {version}, got {name} {artifact_version}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="existing release tag, including the leading v")
    parser.add_argument("--dist", type=Path, help="optional built distribution directory to validate")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        version = validate_source_versions(args.tag)
        if args.dist is not None:
            validate_dist(args.dist, version)
    except (OSError, KeyError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"release-version-check-failed: {exc}")
        return 1
    print(f"release-version-check-ok version={version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
