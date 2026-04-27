"""Real estate listing scraper package.

Public surface:
    * `get_settings()` - process-wide configuration accessor.
    * `run_pipeline()` - top-level orchestrator coroutine.
"""
from __future__ import annotations

from .config import get_settings
from .pipeline import run_pipeline

__all__ = ["get_settings", "run_pipeline"]
