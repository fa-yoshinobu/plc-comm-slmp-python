#!/usr/bin/env python
"""Verify SLMP access to multiple target stations/other targets."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import other_station_check_main

    raise SystemExit(other_station_check_main())
