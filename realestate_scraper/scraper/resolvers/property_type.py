"""Property-type resolver.

Property types are highly stable French/English vocabulary. We scan the
title, H1, and JSON-LD `name`/`description` for a hit. The url is used
as a tertiary tie-breaker.
"""
from __future__ import annotations

from ..models import PageContext, ResolverResult
from ..utils.text import normalize_for_match

_PROPERTY_TYPES = (
    "maison", "appartement", "villa", "terrain", "garage",
    "studio", "chalet", "moulin", "duplex", "loft",
    "chateau", "parking", "immeuble", "local commercial",
    "local", "bureau", "bureaux", "hotel", "ferme",
)


def _scan(text: str) -> str:
    if not text:
        return ""
    normalised = normalize_for_match(text)
    for value in _PROPERTY_TYPES:
        target = normalize_for_match(value)
        if target and target in normalised:
            return value
    return ""


class PropertyTypeResolver:
    name = "property_type"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        haystacks = (
            ctx.title,
            ctx.h1,
            ctx.json_ld.get("name") if ctx.json_ld else "",
            ctx.json_ld.get("description") if ctx.json_ld else "",
        )
        for raw in haystacks:
            value = _scan(str(raw or ""))
            if value:
                return ResolverResult(value, 0.85, "title_h1_jsonld")

        value = _scan(ctx.url or "")
        if value:
            return ResolverResult(value, 0.55, "url")

        return ResolverResult("", 0.0, "")
