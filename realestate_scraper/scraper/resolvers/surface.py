"""Surface area resolver (square metres).

We accept multiple French/English notations: `90 m²`, `90,76 m2`,
`90.76 m²`, `Surface : 90 m2`, `Surface habitable: 90,76 m²`.
The stored value is the numeric portion using a `.` decimal separator.
"""
from __future__ import annotations

import re

from ..models import PageContext, ResolverResult

_PATTERN_LABEL = re.compile(
    r"(?:surface(?:\s+habitable)?|superficie|living\s+area)\s*[:\-]?\s*"
    r"([\d][\d\s\xa0., ]*)\s*m\s*[²2²]",
    re.IGNORECASE,
)
_PATTERN_LOOSE = re.compile(
    r"([\d][\d\s\xa0., ]*)\s*m\s*[²2²]",
    re.IGNORECASE,
)


def _normalize(raw: str) -> str:
    if not raw:
        return ""
    cleaned = raw.replace("\xa0", " ").strip()
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace(",", ".")
    if cleaned.count(".") > 1:
        # Remove thousand separators that ended up as dots.
        whole, _, fraction = cleaned.rpartition(".")
        cleaned = whole.replace(".", "") + "." + fraction
    if not cleaned:
        return ""
    if cleaned.startswith("."):
        return ""
    return cleaned


class SurfaceResolver:
    name = "surface_area"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        if not ctx.text:
            return ResolverResult("", 0.0, "")

        match = _PATTERN_LABEL.search(ctx.text)
        if match:
            value = _normalize(match.group(1))
            if value:
                return ResolverResult(value, 0.9, "label")

        match = _PATTERN_LOOSE.search(ctx.text)
        if match:
            value = _normalize(match.group(1))
            if value:
                return ResolverResult(value, 0.7, "loose")

        return ResolverResult("", 0.0, "")
