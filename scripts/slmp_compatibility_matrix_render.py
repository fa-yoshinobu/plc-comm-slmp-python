#!/usr/bin/env python
"""Render PLC compatibility markdown from probe JSON files."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import compatibility_matrix_render_main

    raise SystemExit(compatibility_matrix_render_main())
