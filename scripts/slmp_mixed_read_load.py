#!/usr/bin/env python
"""Run mixed 0401/0403/0406 read load test."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import mixed_read_load_main

    raise SystemExit(mixed_read_load_main())
