"""Total-rooms resolver.

Matches both `Pièces : 3` and `3 pièces`, plus the French T-notation
(`T3` -> 3 rooms). Stays restrained: any digit > 30 is rejected to
avoid catching noisy text like `30000 €`.
"""
from __future__ import annotations

import re

from ..models import PageContext, ResolverResult

_PATTERN = re.compile(
    r"(?:pi[èe]ces?|rooms?)\s*[:\-]?\s*(\d{1,2})"
    r"|(\d{1,2})\s*(?:pi[èe]ces?|rooms?)",
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
    if n <= 0 or n > 30:
        return ""
    return str(n)


class RoomsResolver:
    name = "rooms"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        match = _PATTERN.search(ctx.text or "")
        if match:
            value = _bounded(match.group(1) or match.group(2) or "")
            if value:
                return ResolverResult(value, 0.9, "label")

        haystack = f"{ctx.title} {ctx.h1} {ctx.url}"
        match = _T_NOTATION.search(haystack)
        if match:
            value = _bounded(match.group(1))
            if value:
                return ResolverResult(value, 0.7, "t_notation")

        return ResolverResult("", 0.0, "")
