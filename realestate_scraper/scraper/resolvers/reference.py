"""Listing reference / SKU resolver.

Real estate sites use very different conventions, so we look in:
    1. JSON-LD `sku`, `productID`, `identifier`, `reference`.
    2. Visible labels (`Réf.\u00a0XYZ123`, `Reference: XYZ123`).
    3. URL slug heuristics (final path segment, comma-suffix, `-vp123`).

We deliberately reject obvious junk (`partager`, `search`, `result`,
`page`) and slugs shorter than 3 chars.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..models import PageContext, ResolverResult

_LABEL_PATTERNS = (
    re.compile(
        r"(?:r[ée]f(?:[ée]rence)?|réf\.?|ref\.?|n°\s*id)\s*[:#\.\-]?\s*"
        r"([A-Za-z0-9][A-Za-z0-9_\-/]{2,})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\b)id\s*[:#\.\-]?\s*([A-Za-z0-9][A-Za-z0-9_\-/]{2,})",
        re.IGNORECASE,
    ),
)

_JUNK_TOKENS = (
    "partager", "facebook", "twitter", "linkedin", "share",
    "search", "result", "results", "page", "trouv", "aucun",
    "recherche", "liste", "user", "immobili", "estimation",
    "prix-m2",
)

_VP_VM = re.compile(r"\b([A-Z]{1,3}\d{3,})\b")


def _is_junk(value: str) -> bool:
    lowered = (value or "").lower()
    return any(token in lowered for token in _JUNK_TOKENS)


def _from_slug(url: str) -> str:
    if not url:
        return ""
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    last = path.split("/")[-1]
    if "," in last:
        last = last.split(",")[-1]
    last = last.strip(".,;:")
    if len(last) < 3:
        return ""
    if _is_junk(last):
        return ""
    return last


class ReferenceResolver:
    name = "reference_id"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_ref = ctx.json_ld.get("reference_id") if ctx.json_ld else None
        if isinstance(ld_ref, str) and len(ld_ref.strip()) >= 3 and not _is_junk(ld_ref):
            return ResolverResult(ld_ref.strip(), 0.95, "json_ld")

        for pattern in _LABEL_PATTERNS:
            match = pattern.search(ctx.text or "")
            if not match:
                continue
            candidate = match.group(1).strip().strip(".,;:")
            if len(candidate) >= 3 and not _is_junk(candidate):
                return ResolverResult(candidate, 0.85, "label")

        vp_match = _VP_VM.search(ctx.url or "")
        if vp_match:
            return ResolverResult(vp_match.group(1), 0.7, "url_pattern")

        slug = _from_slug(ctx.url)
        if slug:
            return ResolverResult(slug, 0.5, "slug")

        return ResolverResult("", 0.0, "")
