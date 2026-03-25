#!/usr/bin/env python
"""Focused register-boundary probe for repeatable live checks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import register_boundary_probe_main

    raise SystemExit(register_boundary_probe_main())
