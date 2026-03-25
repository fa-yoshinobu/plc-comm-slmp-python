#!/usr/bin/env python
"""SLMP binary connection check script."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import connection_check_main

    raise SystemExit(connection_check_main())
