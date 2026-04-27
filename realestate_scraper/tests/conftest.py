"""Shared pytest configuration.

Makes the `scraper` package importable when tests are run from the
repository root or from `realestate_scraper/`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
