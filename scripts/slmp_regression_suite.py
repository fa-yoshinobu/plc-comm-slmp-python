#!/usr/bin/env python
"""Run the local regression suite and optional safe live connection smoke check."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import regression_suite_main

    raise SystemExit(regression_suite_main())
