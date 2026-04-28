"""Location resolver.

We collect, in order of confidence:
    1. JSON-LD `address` already normalised by `utils.json_ld`.
    2. The French URL pattern `<slug>-<postal_code>` or
       `/<postal_code>-<slug>` (`...-bordeaux-33000`, `/33000-bordeaux/`).
    3. The breadcrumb trail's best place-shaped node (NOT just the
       last alphabetic one - that catches "Maison", "Accueil", title
       descriptors carrying "39m^2" or "1 007 EUR/mois", etc.).
    4. The URL category-then-commune slug (`/ventes-maisons-t4-toulon/...`)
       which is the dominant pattern on Apimo / Hektor templates that
       do not embed a postal code in their listing URLs.
    5. `og:locality` / `place:location:locality` meta tags.
    6. The agency CSV city/postcode, but ONLY for pages that look like
       real detail pages, never for hubs / contact / template pages.

The output is a free-form string (the brief stores `location` as text).
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

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

# Markers that prove a breadcrumb candidate is actually a property
# descriptor (price, surface, rent term), not a place name.
_DESCRIPTOR_TOKENS = re.compile(
    r"\u20ac|eur(?:o|os)?|/\s*mois|par\s+mois|m\s*[²²2]|\bm2\b",
    re.IGNORECASE,
)
_TWO_DIGIT_RUNS = re.compile(r"\d{2,}")

# Words that look like cities to a naive scanner but never are. Sourced
# from the navigation, breadcrumb, and template strings observed across
# the input domains. Compared after `normalize_for_match`, so accents
# and casing are irrelevant.
_NAV_LABELS: frozenset[str] = frozenset({
    # property-type tokens (these are categories, not cities)
    "maison", "maisons", "appartement", "appartements",
    "villa", "villas", "terrain", "terrains", "studio", "studios",
    "garage", "garages", "parking", "parkings", "loft", "chalet",
    "chateau", "immeuble", "local", "bureau", "bureaux", "hotel",
    "ferme",
    # transactional categories
    "vente", "ventes", "location", "locations", "a vendre", "a louer",
    "acheter", "louer", "buy", "rent", "achat",
    # listing-index templates
    "annonce", "annonces", "biens", "bien", "propriete", "proprietes",
    "property", "properties", "liste", "detail", "details", "page",
    "resultats", "results",
    # navigation-only labels and dashboards
    "accueil", "home", "contact", "agence", "agences", "equipe",
    "team", "actualites", "blog", "recherche", "search",
    "estimer", "estimation", "financement", "simulateur", "simulation",
    "taux",
    # parties / roles in template UIs
    "bailleurs", "vendeurs", "acquereurs", "acheteurs", "locataires",
    "mandataire", "mandataires", "immobilier", "immobiliere",
    # account / dashboard fragments
    "mes biens", "mes alertes", "mes favoris", "mes recherches",
    "mon compte", "mon espace", "espace client", "espace candidat",
    "connexion", "se connecter", "deconnexion", "inscription",
    "dashboard", "bienvenue",
})

# Property-type tokens we want to filter out of URL-derived slugs.
_PROPERTY_TOKENS: frozenset[str] = frozenset({
    "maison", "maisons", "appartement", "appartements",
    "villa", "villas", "terrain", "terrains", "studio", "studios",
    "loft", "lofts", "garage", "garages", "parking", "parkings",
    "immeuble", "immeubles", "chalet", "chalets", "chateau", "chateaux",
    "local", "locaux", "bureau", "bureaux", "hotel", "hotels",
    "ferme", "fermes", "duplex", "moulin", "moulins",
})

# Category tokens that must appear inside the URL path before we trust
# the trailing slug as a commune name.
_URL_CATEGORY_TOKENS: tuple[str, ...] = (
    "vente", "ventes", "location", "locations", "biens", "bien",
    "annonce", "annonces", "acheter", "louer", "vente-pro",
    "location-pro",
)

# A T-notation (T1, T2, ...) often sits between the category and the
# commune slug on Apimo / Hektor URLs (`/ventes-maisons-t4-toulon/...`).
_T_TOKEN = re.compile(r"^t\d+$", re.IGNORECASE)


def _is_nav_label(value: str) -> bool:
    return normalize_for_match(value) in _NAV_LABELS


def _breadcrumb_is_descriptor(value: str) -> bool:
    """Reject breadcrumb candidates that are clearly property descriptors.

    Real cities never carry a EUR sign, an "m^2", a "/mois", or two
    separate digit runs.
    """
    if not value:
        return False
    if _DESCRIPTOR_TOKENS.search(value):
        return True
    if len(_TWO_DIGIT_RUNS.findall(value)) >= 2:
        return True
    return False


def _looks_place_like(value: str) -> bool:
    if not value:
        return False
    cleaned = collapse_whitespace(value)
    if len(cleaned) < 3 or len(cleaned) > 60:
        return False
    if _is_nav_label(cleaned):
        return False
    if _breadcrumb_is_descriptor(cleaned):
        return False
    if not re.search(r"[A-Za-z\u00c0-\u017f]", cleaned):
        return False
    digit_ratio = sum(ch.isdigit() for ch in cleaned) / max(1, len(cleaned))
    if digit_ratio > 0.5:
        return False
    return True


def _from_breadcrumb(parser: HTMLParser) -> str:
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
            if not _breadcrumb_is_descriptor(item):
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


def _from_url_postal(url: str) -> str:
    if not url:
        return ""
    match = _URL_LOCATION.search(url)
    if not match:
        return ""
    slug = match.group(1) or match.group(4) or ""
    postal = match.group(2) or match.group(3) or ""
    if not slug or not postal:
        return ""
    last = slug.split("-")[-1]
    if not last or normalize_for_match(last) in _PROPERTY_TOKENS:
        return ""
    return f"{last.capitalize()} {postal}"


def _from_url_slug(url: str) -> str:
    """Pull a commune name from category-anchored URL slugs.

    Example matches:
        /ventes-maisons-t4-toulon/123.html  -> Toulon
        /vente/1-melun/maison/2330-...      -> Melun
        /location/appartement/strasbourg/67200 -> Strasbourg
        /vente/22-gujan-mestras/...         -> Gujan-Mestras

    The path must contain at least one of `_URL_CATEGORY_TOKENS` so
    we never guess a city out of an arbitrary slug.
    """
    if not url:
        return ""
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    if not path:
        return ""
    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return ""
    has_category = any(
        any(token in seg for token in _URL_CATEGORY_TOKENS)
        for seg in segments
    )
    if not has_category:
        return ""

    # Walk segments looking for the rightmost commune-shaped token.
    for raw in reversed(segments):
        # Strip a numeric prefix like "22-gujan-mestras".
        cleaned = raw
        if "-" in cleaned:
            head, _, tail = cleaned.partition("-")
            if head.isdigit() and tail:
                cleaned = tail
        # Strip query / file extension fragments.
        cleaned = cleaned.split(".", 1)[0]
        # Tokenise on hyphen / underscore.
        tokens = re.split(r"[\-_]", cleaned)
        tokens = [tok for tok in tokens if tok]
        if not tokens:
            continue
        # Drop trailing T-notation tokens.
        tokens = [tok for tok in tokens if not _T_TOKEN.match(tok)]
        # Drop trailing pure-numeric tokens (page numbers, refs).
        tokens = [tok for tok in tokens if not tok.isdigit()]
        # Drop property-type tokens.
        tokens = [
            tok for tok in tokens
            if normalize_for_match(tok) not in _PROPERTY_TOKENS
        ]
        # Drop category and nav tokens.
        tokens = [
            tok for tok in tokens
            if normalize_for_match(tok) not in _NAV_LABELS
            and tok not in _URL_CATEGORY_TOKENS
        ]
        if not tokens:
            continue
        joined = " ".join(tok.capitalize() for tok in tokens)
        if 3 <= len(joined) <= 60 and not _is_nav_label(joined):
            return joined
    return ""


def _is_listing_page(ctx: PageContext, parser: Optional[HTMLParser]) -> bool:
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
    if _breadcrumb_is_descriptor(cleaned):
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

        url_postal = _from_url_postal(ctx.url or "")
        if url_postal:
            return ResolverResult(url_postal, 0.7, "url_postal")

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

        url_slug = _from_url_slug(ctx.url or "")
        if url_slug:
            return ResolverResult(url_slug, 0.6, "url_slug")

        if parser is not None:
            value = _from_meta(parser)
            if value:
                return ResolverResult(value, 0.55, "meta")

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
