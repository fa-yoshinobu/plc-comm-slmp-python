#!/usr/bin/env python
"""Run interactive manual write verification from device_access_matrix.csv."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import manual_write_verification_main

    raise SystemExit(manual_write_verification_main())
