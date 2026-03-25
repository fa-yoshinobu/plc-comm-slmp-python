#!/usr/bin/env python
"""Sweep qualified Extended Device G/HG devices across addresses and point counts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import g_hg_extended_device_coverage_main

    raise SystemExit(g_hg_extended_device_coverage_main())
