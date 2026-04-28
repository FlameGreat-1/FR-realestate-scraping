"""Property-type resolver.

Property types are highly stable French/English vocabulary. We scan, in
order of confidence:
    1. The URL category segment (Apimo / Hektor templates expose this
       as `/ventes-<category>-<commune>/...` or
       `/vente-pro/.../<category>/...`).
    2. The page title and H1.
    3. JSON-LD `name` and `description`.
    4. The full URL as a last resort.

Matching rules:
    * Each canonical category carries an explicit *rank* so when a
      page legitimately mentions two categories ("maison avec garage",
      "maison avec terrain") the dominant residential category wins
      over the ancillary or land category.
    * Inside a single rank, longest synonym wins (so "local
      commercial" beats "local" and plurals beat singulars).
    * Output is the canonical singular form, regardless of which
      synonym matched, so the property_type column is a stable
      category rather than whatever inflection the page happened to
      use.
"""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

from ..models import PageContext, ResolverResult
from ..utils.text import normalize_for_match


# (canonical_singular, rank, synonyms). Lower rank = stronger category.
# When two synonyms appear in the same text, the one with the lower
# rank wins. Inside a rank, longest synonym wins.
_PROPERTY_TYPES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    # Rank 1: primary residential dwellings.
    ("maison", 1, ("maisons", "maison")),
    ("appartement", 1, ("appartements", "appartement")),
    ("villa", 1, ("villas", "villa")),
    ("studio", 1, ("studios", "studio")),
    ("duplex", 1, ("duplex",)),
    ("loft", 1, ("lofts", "loft")),
    ("chalet", 1, ("chalets", "chalet")),
    ("chateau", 1, ("chateaux", "chateau")),
    ("moulin", 1, ("moulins", "moulin")),
    ("ferme", 1, ("fermes", "ferme")),
    # Rank 2: collective dwellings.
    ("immeuble", 2, ("immeubles", "immeuble")),
    # Rank 3: commercial.
    ("local commercial", 3, ("local commercial", "locaux commerciaux")),
    ("bureau", 3, ("bureaux", "bureau")),
    ("hotel", 3, ("hotels", "hotel")),
    # Rank 4: ancillary spaces.
    ("garage", 4, ("garages", "garage")),
    ("parking", 4, ("parkings", "parking")),
    ("local", 4, ("locaux", "local")),
    # Rank 5: land.
    ("terrain", 5, ("terrains", "terrain")),
)

# URL category segments observed on Apimo / Hektor / WP templates.
# Order matters: first match wins, so the more specific `*-pro`
# (commercial) segments are placed BEFORE their residential
# counterparts to avoid misclassifying `vente-pro/.../bureaux/...`
# as a residential listing.
_URL_SEGMENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # --- Commercial sub-tree (vente-pro / location-pro) ---
    (re.compile(r"/(?:vente|location)s?-pro/[^/]*/bureaux\b", re.IGNORECASE), "bureau"),
    (re.compile(r"/(?:vente|location)s?-pro/[^/]*/locaux\b", re.IGNORECASE), "local"),
    (re.compile(r"/(?:vente|location)s?-pro/[^/]*/(?:entrepots?|commerces?|fonds-de-commerce)\b", re.IGNORECASE), "local commercial"),
    (re.compile(r"/(?:vente|location)s?-pro/[^/]*/garages?\b", re.IGNORECASE), "garage"),
    (re.compile(r"/(?:vente|location)s?-pro/[^/]*/parkings?\b", re.IGNORECASE), "parking"),
    (re.compile(r"/(?:vente|location)s?-pro/[^/]*/immeubles?\b", re.IGNORECASE), "immeuble"),
    # --- Residential category-anchored URL prefixes ---
    (re.compile(r"/ventes?-maisons?\b", re.IGNORECASE), "maison"),
    (re.compile(r"/ventes?-appartements?\b", re.IGNORECASE), "appartement"),
    (re.compile(r"/ventes?-villas?\b", re.IGNORECASE), "villa"),
    (re.compile(r"/ventes?-studios?\b", re.IGNORECASE), "studio"),
    (re.compile(r"/ventes?-immeubles?\b", re.IGNORECASE), "immeuble"),
    (re.compile(r"/ventes?-terrains?\b", re.IGNORECASE), "terrain"),
    (re.compile(r"/ventes?-locaux\b", re.IGNORECASE), "local"),
    (re.compile(r"/ventes?-bureaux\b", re.IGNORECASE), "bureau"),
    (re.compile(r"/ventes?-garages?\b", re.IGNORECASE), "garage"),
    (re.compile(r"/ventes?-parkings?\b", re.IGNORECASE), "parking"),
    (re.compile(r"/locations?-maisons?\b", re.IGNORECASE), "maison"),
    (re.compile(r"/locations?-appartements?\b", re.IGNORECASE), "appartement"),
    # --- /<vente|location>/<commune>/<category>/ shape ---
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/maisons?(?:/|$)", re.IGNORECASE), "maison"),
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/appartements?(?:/|$)", re.IGNORECASE), "appartement"),
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/villas?(?:/|$)", re.IGNORECASE), "villa"),
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/terrains?(?:/|$)", re.IGNORECASE), "terrain"),
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/bureaux\b", re.IGNORECASE), "bureau"),
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/locaux\b", re.IGNORECASE), "local"),
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/(?:entrepots?|commerces?|fonds-de-commerce)\b", re.IGNORECASE), "local commercial"),
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/garages?\b", re.IGNORECASE), "garage"),
    (re.compile(r"/(?:vente|location)/\d*-?[a-z\-]+/parkings?\b", re.IGNORECASE), "parking"),
)


def _flattened_terms() -> tuple[tuple[str, str, int], ...]:
    """Return every (synonym, canonical, rank) tuple for the matcher.

    The list is *not* sorted here; the matcher chooses the best hit
    by rank-then-length per scan.
    """
    out: list[tuple[str, str, int]] = []
    for canonical, rank, synonyms in _PROPERTY_TYPES:
        for synonym in synonyms:
            normalised = normalize_for_match(synonym)
            if normalised:
                out.append((normalised, canonical, rank))
    return tuple(out)


_TERMS: tuple[tuple[str, str, int], ...] = _flattened_terms()


def _scan_best(text: str, terms: Iterable[tuple[str, str, int]] = _TERMS) -> str:
    """Return the canonical category whose match has the lowest rank.

    Ties are broken by synonym length (longer first), then
    alphabetical for determinism.
    """
    if not text:
        return ""
    normalised = normalize_for_match(text)
    if not normalised:
        return ""
    best: tuple[int, int, str, str] | None = None  # (rank, -len, syn, canonical)
    for synonym, canonical, rank in terms:
        if synonym in normalised:
            score = (rank, -len(synonym), synonym, canonical)
            if best is None or score < best:
                best = score
    return best[3] if best else ""


def _from_url_segments(url: str) -> str:
    """Pull the category from an explicit URL segment, if any."""
    if not url:
        return ""
    path = (urlparse(url).path or "").lower()
    if not path:
        return ""
    for pattern, canonical in _URL_SEGMENT_PATTERNS:
        if pattern.search(path):
            return canonical
    return ""


class PropertyTypeResolver:
    name = "property_type"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        # 1. Strong URL signal first: a category segment in the path is
        #    almost always correct on Apimo / Hektor / WP templates.
        from_url = _from_url_segments(ctx.url or "")
        if from_url:
            return ResolverResult(from_url, 0.9, "url_segment")

        # 2. Title / H1 / JSON-LD scans, with rank-aware tiebreak so
        #    "maison avec garage" returns maison, not garage.
        haystacks = (
            ctx.title,
            ctx.h1,
            ctx.json_ld.get("name") if ctx.json_ld else "",
            ctx.json_ld.get("description") if ctx.json_ld else "",
        )
        for raw in haystacks:
            value = _scan_best(str(raw or ""))
            if value:
                return ResolverResult(value, 0.8, "title_h1_jsonld")

        # 3. Whole-URL fallback (looser than segment matching above).
        value = _scan_best(ctx.url or "")
        if value:
            return ResolverResult(value, 0.55, "url")

        return ResolverResult("", 0.0, "")
