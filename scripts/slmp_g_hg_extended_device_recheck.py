#!/usr/bin/env python
"""Recheck iQ-R Extended Device G/HG read-write-readback with restore."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import g_hg_extended_device_recheck_main

    raise SystemExit(g_hg_extended_device_recheck_main())
