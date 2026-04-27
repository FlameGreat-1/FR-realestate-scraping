"""DPE / energy-class resolver.

French DPE labels are letters A-G. We only accept *labelled*
appearances to avoid catching standalone single letters in unrelated
text.
"""
from __future__ import annotations

import re

from ..models import PageContext, ResolverResult
from ..utils.text import normalize_for_match

_LABELLED = (
    re.compile(r"\bdpe\b\s*[:\-]?\s*(?:classe\s*)?([A-G])\b", re.IGNORECASE),
    re.compile(
        r"\bdiagnostic(?:\s+de\s+performance)?(?:\s+energetique)?\b\s*"
        r"[:\-]?\s*(?:classe\s*)?([A-G])\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bclasse(?:ment)?(?:\s+energie|\s+energetique)?\b\s*[:\-]?\s*([A-G])\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bconsommation(?:\s+energetique)?\b\s*[:\-]?\s*([A-G])\b",
        re.IGNORECASE,
    ),
)


class DpeResolver:
    name = "dpe_rating"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_dpe = ctx.json_ld.get("dpe") if ctx.json_ld else None
        if isinstance(ld_dpe, str):
            match = re.search(r"\b([A-G])\b", ld_dpe, re.IGNORECASE)
            if match:
                return ResolverResult(match.group(1).upper(), 0.95, "json_ld")

        if not ctx.text:
            return ResolverResult("", 0.0, "")
        normalised = normalize_for_match(ctx.text)
        for pattern in _LABELLED:
            match = pattern.search(normalised)
            if match:
                return ResolverResult(match.group(1).upper(), 0.85, "label")

        return ResolverResult("", 0.0, "")
