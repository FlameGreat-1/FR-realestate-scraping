"""Location resolver.

We collect, in order of confidence:
    1. JSON-LD `address` already normalised by `utils.json_ld`.
    2. The French URL pattern `<slug>-<postal_code>` or
       `/<postal_code>-<slug>` (`...-bordeaux-33000`, `/33000-bordeaux/`).
    3. The breadcrumb trail's best place-shaped node (NOT just the
       last alphabetic one - that catches "Maison", "Accueil", etc.).
    4. `og:locality` / `place:location:locality` meta tags.
    5. The agency CSV city/postcode, but ONLY for pages that look like
       real detail pages, never for hubs / contact / template pages.

The output is a free-form string (the brief stores `location` as text).
"""
from __future__ import annotations

import re
from typing import Optional

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult
from ..utils.text import collapse_whitespace, normalize_for_match

_URL_LOCATION = re.compile(
    r"(?:^|[/\-])([a-z][a-z0-9\-]{2,})-(\d{5})(?:[/,?\-]|$)"
    r"|(?:^|[/\-])(\d{5})-([a-z][a-z0-9\-]{2,})(?:[/,?\-]|$)",
    re.IGNORECASE,
)
_BREADCRUMB_SELECTOR = (
    ".breadcrumb, .breadcrumbs, nav.breadcrumb, ol.breadcrumb, ul.breadcrumb, "
    "[itemtype*='BreadcrumbList'], [class*='breadcrumb' i], [class*='chemin' i]"
)
_POSTAL_RE = re.compile(r"\b\d{5}\b")
_REFERENCE_SHAPE = re.compile(
    r"(?:/\d{5,}|-vp\d{3,}|-vm\d{3,}|/[a-z0-9-]{12,}-\d{3,}|,[A-Z]{1,3}\d{3,})",
    re.IGNORECASE,
)

# Words that look like cities to a naive scanner but never are. Sourced
# from the navigation, breadcrumb, and template strings observed across
# the input domains. Compared after `normalize_for_match`, so accents
# and casing are irrelevant.
_NAV_LABELS: frozenset[str] = frozenset({
    "accueil", "home", "maison", "maisons", "appartement", "appartements",
    "villa", "villas", "terrain", "terrains", "studio", "studios",
    "garage", "garages", "parking", "parkings", "loft", "chalet",
    "chateau", "immeuble", "local", "bureau", "bureaux", "hotel", "ferme",
    "vente", "ventes", "location", "locations", "a vendre", "a louer",
    "annonce", "annonces", "biens", "bien", "propriete", "proprietes",
    "property", "properties", "contact", "agence", "agences", "equipe",
    "team", "actualites", "blog", "recherche", "search", "resultats",
    "results", "liste", "detail", "details", "page", "acheter", "louer",
    "buy", "rent", "estimer", "estimation",
})

# Property-type tokens we want to filter out of URL-derived slugs.
_PROPERTY_TOKENS: frozenset[str] = frozenset({
    "maison", "appartement", "villa", "terrain", "studio", "loft",
    "garage", "parking", "immeuble", "chalet", "chateau", "local",
    "bureau", "bureaux", "hotel", "ferme", "duplex", "moulin",
})


def _is_nav_label(value: str) -> bool:
    return normalize_for_match(value) in _NAV_LABELS


def _looks_place_like(value: str) -> bool:
    if not value:
        return False
    cleaned = collapse_whitespace(value)
    if len(cleaned) < 3 or len(cleaned) > 60:
        return False
    if _is_nav_label(cleaned):
        return False
    # A place name has letters and spaces and possibly hyphens / apostrophes.
    if not re.search(r"[A-Za-z\u00c0-\u017f]", cleaned):
        return False
    # Reject pure-digit items and item that are mostly digits.
    digit_ratio = sum(ch.isdigit() for ch in cleaned) / max(1, len(cleaned))
    if digit_ratio > 0.5:
        return False
    return True


def _from_breadcrumb(parser: HTMLParser) -> str:
    """Pick the best place-shaped node in the breadcrumb trail.

    Strategy:
        1. Prefer items that contain a postal code.
        2. Otherwise prefer the *deepest* item that looks place-like
           and is not a nav label.
        3. Otherwise return empty.
    """
    try:
        nodes = parser.css(_BREADCRUMB_SELECTOR)
    except Exception:
        return ""

    candidates: list[str] = []
    for node in nodes:
        for item in node.css("li, a, span"):
            text = collapse_whitespace(
                item.text(deep=True, separator=" ", strip=True)
            )
            if text:
                candidates.append(text)
        if candidates:
            break

    # Tier 1: postal-code-bearing item, scanned from deepest to root.
    for item in reversed(candidates):
        if _POSTAL_RE.search(item) and not _is_nav_label(item):
            return item

    # Tier 2: deepest place-like item.
    for item in reversed(candidates):
        if _looks_place_like(item):
            return item
    return ""


def _from_meta(parser: HTMLParser) -> str:
    selectors = (
        "meta[property='og:locality']",
        "meta[property='place:location:locality']",
        "meta[name='geo.placename']",
    )
    for selector in selectors:
        try:
            node = parser.css_first(selector)
        except Exception:
            continue
        if node:
            content = (node.attributes.get("content") or "").strip()
            if content and not _is_nav_label(content):
                return content
    return ""


def _from_url(url: str) -> str:
    """Pull a `<commune> <postal>` pair from the listing URL."""
    if not url:
        return ""
    match = _URL_LOCATION.search(url)
    if not match:
        return ""
    slug = match.group(1) or match.group(4) or ""
    postal = match.group(2) or match.group(3) or ""
    if not slug or not postal:
        return ""
    # Slug may be `vente-appartement-bordeaux`; keep only the last token
    # because earlier tokens are nav-style category words.
    last = slug.split("-")[-1]
    if not last or normalize_for_match(last) in _PROPERTY_TOKENS:
        return ""
    return f"{last.capitalize()} {postal}"


def _is_listing_page(ctx: PageContext, parser: Optional[HTMLParser]) -> bool:
    """Heuristic: does this page look like a property detail page?

    Used as the gate for the agency-csv fallback so that hub /
    contact / template pages do not silently inherit the agency's
    own city.
    """
    if ctx.json_ld:
        for key in ("price", "reference_id", "description", "name"):
            if ctx.json_ld.get(key):
                return True
    if ctx.url and _REFERENCE_SHAPE.search(ctx.url):
        return True
    if parser is not None:
        try:
            crumbs = parser.css(_BREADCRUMB_SELECTOR)
        except Exception:
            crumbs = []
        for node in crumbs:
            items = node.css("li, a")
            if len(items) >= 3:
                return True
    return False


def _validate_jsonld_address(value: str) -> str:
    cleaned = collapse_whitespace(value)
    if len(cleaned) < 3:
        return ""
    if _is_nav_label(cleaned):
        return ""
    return cleaned


class LocationResolver:
    name = "location"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_loc = ctx.json_ld.get("location") if ctx.json_ld else ""
        if isinstance(ld_loc, str) and ld_loc.strip():
            cleaned = _validate_jsonld_address(ld_loc)
            if cleaned:
                return ResolverResult(cleaned, 0.9, "json_ld")

        url_value = _from_url(ctx.url or "")
        if url_value:
            return ResolverResult(url_value, 0.7, "url")

        parser: Optional[HTMLParser] = None
        if ctx.html:
            try:
                parser = HTMLParser(ctx.html)
            except Exception:
                parser = None
            if parser is not None:
                value = _from_breadcrumb(parser)
                if value:
                    return ResolverResult(value, 0.65, "breadcrumb")
                value = _from_meta(parser)
                if value:
                    return ResolverResult(value, 0.6, "meta")

        # Agency-csv fallback: only if the page genuinely looks like a
        # detail page. Otherwise we leave location empty rather than
        # contaminating hub/contact/template pages.
        if ctx.domain_job and _is_listing_page(ctx, parser):
            fallback = collapse_whitespace(
                f"{ctx.domain_job.city} {ctx.domain_job.postalcode}"
            )
            if fallback:
                return ResolverResult(fallback, 0.2, "agency_csv")

        return ResolverResult("", 0.0, "")
