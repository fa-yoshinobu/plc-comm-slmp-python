#!/usr/bin/env python
"""Initialize internal_docs scaffolding for a new model folder."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    from slmp.cli import init_model_docs_main

    raise SystemExit(init_model_docs_main())
