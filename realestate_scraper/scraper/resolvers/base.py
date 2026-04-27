"""Resolver protocol shared by every field extractor.

Resolvers are pure functions over `PageContext`; they hold no I/O and
no mutable state, which is what makes them trivially testable.
"""
from __future__ import annotations

from typing import Protocol

from ..models import PageContext, ResolverResult


class Resolver(Protocol):
    """Callable interface for a field-level resolver."""

    name: str

    def resolve(self, ctx: PageContext) -> ResolverResult:  # pragma: no cover
        ...


EMPTY_RESULT = ResolverResult(value="", confidence=0.0, source="")
