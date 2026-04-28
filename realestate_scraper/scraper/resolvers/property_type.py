"""Property-type resolver.

Property types are highly stable French/English vocabulary. We scan the
title, H1, and JSON-LD `name`/`description` for a hit, and fall back
to the URL slug.

Matching rules:
    * The token table is ordered (display_value, synonyms_in_match_order)
      and scanned longest-synonym-first so multi-word categories
      ("local commercial") win over their substring ("local"), and
      plurals win over singulars ("bureaux" before "bureau").
    * Output is the canonical singular form, regardless of which
      synonym matched, so the property_type column is a stable
      category rather than whatever inflection the page happened to
      use.
"""
from __future__ import annotations

from typing import Iterable

from ..models import PageContext, ResolverResult
from ..utils.text import normalize_for_match


# (canonical_singular, synonyms). Synonyms include plurals and common
# multi-word forms. Order inside `_PROPERTY_TYPES` does not matter; the
# scanner sorts all synonyms by length descending so the most specific
# match always wins.
_PROPERTY_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("local commercial", ("local commercial", "locaux commerciaux")),
    ("appartement", ("appartements", "appartement")),
    ("maison", ("maisons", "maison")),
    ("villa", ("villas", "villa")),
    ("terrain", ("terrains", "terrain")),
    ("studio", ("studios", "studio")),
    ("chalet", ("chalets", "chalet")),
    ("chateau", ("chateaux", "chateau")),
    ("duplex", ("duplex",)),
    ("loft", ("lofts", "loft")),
    ("moulin", ("moulins", "moulin")),
    ("immeuble", ("immeubles", "immeuble")),
    ("parking", ("parkings", "parking")),
    ("garage", ("garages", "garage")),
    ("bureau", ("bureaux", "bureau")),
    ("hotel", ("hotels", "hotel")),
    ("ferme", ("fermes", "ferme")),
    ("local", ("locaux", "local")),
)


def _flattened_terms() -> tuple[tuple[str, str], ...]:
    """Return every (synonym, canonical) pair, sorted longest-first."""
    pairs: list[tuple[str, str]] = []
    for canonical, synonyms in _PROPERTY_TYPES:
        for synonym in synonyms:
            normalised = normalize_for_match(synonym)
            if normalised:
                pairs.append((normalised, canonical))
    # Stable sort: longest first, then alphabetical for determinism.
    pairs.sort(key=lambda item: (-len(item[0]), item[0]))
    return tuple(pairs)


_TERMS: tuple[tuple[str, str], ...] = _flattened_terms()


def _scan(text: str, terms: Iterable[tuple[str, str]] = _TERMS) -> str:
    if not text:
        return ""
    normalised = normalize_for_match(text)
    if not normalised:
        return ""
    for synonym, canonical in terms:
        if synonym in normalised:
            return canonical
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
