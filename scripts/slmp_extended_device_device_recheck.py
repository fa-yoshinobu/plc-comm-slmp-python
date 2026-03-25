#!/usr/bin/env python
"""Recheck Extended Device word-device read-write-readback with restore."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import extended_device_device_recheck_main

    raise SystemExit(extended_device_device_recheck_main())
