#!/usr/bin/env python
"""Probe configured device-range boundaries against a live PLC."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import device_range_probe_main

    raise SystemExit(device_range_probe_main())
