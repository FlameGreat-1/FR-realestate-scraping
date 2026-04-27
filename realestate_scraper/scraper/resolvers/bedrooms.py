"""Bedrooms resolver.

Uses the same bidirectional matching as rooms; falls back to
`max(0, total_rooms - 1)` from the T-notation only if no explicit
bedroom label is found.
"""
from __future__ import annotations

import re

from ..models import PageContext, ResolverResult

_PATTERN = re.compile(
    r"(?:chambres?|bedrooms?)\s*[:\-]?\s*(\d{1,2})"
    r"|(\d{1,2})\s*(?:chambres?|bedrooms?)",
    re.IGNORECASE,
)

_T_NOTATION = re.compile(r"\bT(\d{1,2})\b", re.IGNORECASE)


def _bounded(value: str) -> str:
    if not value:
        return ""
    try:
        n = int(value)
    except ValueError:
        return ""
    if n < 0 or n > 30:
        return ""
    return str(n)


class BedroomsResolver:
    name = "bedrooms"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        match = _PATTERN.search(ctx.text or "")
        if match:
            value = _bounded(match.group(1) or match.group(2) or "")
            if value:
                return ResolverResult(value, 0.9, "label")

        haystack = f"{ctx.title} {ctx.h1} {ctx.url}"
        match = _T_NOTATION.search(haystack)
        if match:
            try:
                rooms = int(match.group(1))
            except ValueError:
                rooms = 0
            if 1 <= rooms <= 30:
                return ResolverResult(str(max(0, rooms - 1)), 0.55, "t_notation")

        return ResolverResult("", 0.0, "")
