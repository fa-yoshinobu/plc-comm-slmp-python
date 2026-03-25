#!/usr/bin/env python
"""Run repeated single-command read soak test."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import read_soak_main

    raise SystemExit(read_soak_main())
