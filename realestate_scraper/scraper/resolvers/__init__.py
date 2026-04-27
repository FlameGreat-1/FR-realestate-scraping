"""Composable single-field resolvers.

Each resolver implements a small, narrow contract: take a `PageContext`,
return a `ResolverResult`. The `pipeline_extract` module wires them in
order of confidence and stops at the first definitive answer.
"""
from __future__ import annotations

from .base import Resolver

__all__ = ["Resolver"]
