#!/usr/bin/env python
"""Live verification for pending command groups."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import pending_live_verification_main

    raise SystemExit(pending_live_verification_main())
