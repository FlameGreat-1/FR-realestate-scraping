"""Listing reference / SKU resolver.

Real estate sites use very different conventions, so we look in:
    1. JSON-LD `sku`, `productID`, `identifier`, `reference`.
    2. Visible labels (`Réf.\u00a0XYZ123`, `Reference: XYZ123`).
    3. URL slug heuristics (final path segment, comma-suffix, `-vp123`).

Guards:
    * Labels accept only identifier-shaped tokens: must contain a
      digit, mixed case, or an internal separator. Bare lower-case
      words (`aire`, `rue`, `page`) are rejected.
    * Junk tokens cover the full nav/category vocabulary observed
      across the input domains so hub-root slugs cannot leak through.
    * Slug fallback rejects slugs that look like nav roots (short,
      pure-alpha, lower-case).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..models import PageContext, ResolverResult

_LABEL_PATTERNS = (
    re.compile(
        r"(?:r[ée]f(?:[ée]rence)?|réf\.?|ref\.?|n°\s*id)\s*[:#\.\-]?\s*"
        r"([A-Za-z0-9][A-Za-z0-9_\-/]{2,})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\b)id\s*[:#\.\-]?\s*([A-Za-z0-9][A-Za-z0-9_\-/]{2,})\b",
        re.IGNORECASE,
    ),
)

_JUNK_TOKENS = (
    "partager", "facebook", "twitter", "linkedin", "share",
    "search", "result", "results", "page", "trouv", "aucun",
    "recherche", "liste", "user", "immobili", "estimation",
    "estimer", "prix-m2", "prix-rues",
    "location", "locations", "vente", "ventes",
    "annonce", "annonces", "contact", "contactez",
    "equipe", "agence", "agences", "team",
    "blog", "news", "actualite", "actualites", "article",
    "login", "connexion", "inscription", "register",
    "mentions", "privacy", "politique", "cookies",
    "plan-du-site", "sitemap", "newsletter",
    "recrutement", "emploi", "carriere",
    "accueil", "home", "about", "a-propos",
)

_VP_VM = re.compile(r"\b([A-Z]{1,3}\d{3,})\b")

# An identifier-shaped token: must contain at least one digit, OR mixed
# case, OR an internal separator. Bare lower-case words fail.
_IDENTIFIER_SHAPE = re.compile(
    r".*(?:\d|[A-Z][a-z]|[a-z][A-Z]|[\-_/]).*"
)

# A slug that looks like a nav root: short and purely lower-case alpha.
_NAV_ROOT = re.compile(r"^[a-z]{1,5}$")


def _is_junk(value: str) -> bool:
    lowered = (value or "").lower()
    return any(token in lowered for token in _JUNK_TOKENS)


def _is_identifier_shaped(value: str) -> bool:
    if not value or len(value) < 3:
        return False
    return bool(_IDENTIFIER_SHAPE.match(value))


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
    if not last or len(last) < 3:
        return ""
    if _is_junk(last):
        return ""
    # Strip a trailing extension before shape-checking.
    stem = last.rsplit(".", 1)[0] if "." in last else last
    if _NAV_ROOT.match(stem):
        return ""
    if not _is_identifier_shaped(stem):
        return ""
    return last


def _accept_label(value: str) -> str:
    candidate = (value or "").strip().strip(".,;:")
    if len(candidate) < 3:
        return ""
    if _is_junk(candidate):
        return ""
    if not _is_identifier_shaped(candidate):
        return ""
    return candidate


class ReferenceResolver:
    name = "reference_id"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_ref = ctx.json_ld.get("reference_id") if ctx.json_ld else None
        if isinstance(ld_ref, str):
            cleaned = _accept_label(ld_ref)
            if cleaned:
                return ResolverResult(cleaned, 0.95, "json_ld")

        for pattern in _LABEL_PATTERNS:
            match = pattern.search(ctx.text or "")
            if not match:
                continue
            cleaned = _accept_label(match.group(1))
            if cleaned:
                return ResolverResult(cleaned, 0.85, "label")

        vp_match = _VP_VM.search(ctx.url or "")
        if vp_match:
            return ResolverResult(vp_match.group(1), 0.7, "url_pattern")

        slug = _from_slug(ctx.url)
        if slug:
            return ResolverResult(slug, 0.5, "slug")

        return ResolverResult("", 0.0, "")
