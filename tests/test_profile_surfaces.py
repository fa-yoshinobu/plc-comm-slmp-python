"""Tests for user-facing profile selectors outside the core library."""

from __future__ import annotations

import argparse
import sys

import pytest

from samples import _common, _operational_common, high_level_async, high_level_sync, polling_reconnect

MXR_RJ71EN71 = "melsec:mx-r:rj71en71"


def test_shared_sample_connection_parser_accepts_mxr_rj71en71() -> None:
    parser = argparse.ArgumentParser()
    _common.add_connection_args(parser)

    args = parser.parse_args(
        [
            "--host",
            "127.0.0.1",
            "--port",
            "1025",
            "--transport",
            "tcp",
            "--plc-profile",
            MXR_RJ71EN71,
        ]
    )

    assert args.plc_profile == MXR_RJ71EN71


def test_operational_sample_profile_choices_include_mxr_rj71en71() -> None:
    assert MXR_RJ71EN71 in _operational_common.PLC_PROFILES


@pytest.mark.parametrize("sample", (high_level_sync, high_level_async, polling_reconnect))
def test_standalone_sample_profile_choices_follow_public_descriptors(
    sample: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sample",
            "--host",
            "127.0.0.1",
            "--port",
            "1025",
            "--transport",
            "tcp",
            "--plc-profile",
            MXR_RJ71EN71,
        ],
    )

    args = sample.parse_args()  # type: ignore[attr-defined]

    assert args.plc_profile == MXR_RJ71EN71
