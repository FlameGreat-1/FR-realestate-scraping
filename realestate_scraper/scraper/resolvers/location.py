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
from urllib.parse import unquote, urlparse

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
    r"\u20ac|eur(?:o|os)?|/\s*mois|par\s+mois|m\s*[\u00b2\u00b22]|\bm2\b",
    re.IGNORECASE,
)
_TWO_DIGIT_RUNS = re.compile(r"\d{2,}")
# Reference labels ("Réf. : 417", "Ref 12345") are not place names.
_REFERENCE_LABEL = re.compile(r"\br[\u00e9e]f\b", re.IGNORECASE)
# Per-token markers used by the URL-slug fallback. After URL-decoding,
# slug tokens carrying any of these are property descriptors, never
# place names. The `digit-then-e` token (`900e`) is the French shorthand
# for `\u20ac` in URL slugs.
_SLUG_DESCRIPTOR_TOKEN = re.compile(
    r"\u20ac|^\d+[a-z]?[\u00b2\u00b22]?$|\bm2\b|m\s*[\u00b2\u00b22]|mois|^\d+e$",
    re.IGNORECASE,
)

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
    # Round 4 additions: page-flow labels surfaced by the audit.
    "transaction", "transactions",
    "decouvrir", "decouvrez",
    "voir", "voir plus", "voir tous", "voir tout",
    "tous les biens", "tous nos biens",
    "derniers biens", "nouveautes", "nouveaute",
    "coup de coeur", "coups de coeur",
    "exclusivites", "exclusivite",
    "selection", "selections",
    "nos biens", "nos selections", "nos exclusivites", "nos coups",
    "best of", "top", "top biens",
    # Round 5 additions: rental / programme / CTA labels surfaced by
    # the consolidated-output audit.
    "vacances", "location vacances", "location saisonniere",
    "neuf", "programme", "programmes", "programme neuf", "programmes neufs",
    "dispositif", "dispositifs", "aide", "aides",
    "investir", "investissement", "defiscalisation",
    "estimez", "evaluez", "evaluer", "estimez votre bien",
    "vendre mon bien", "louer mon bien",
    "chambres", "chambre", "pieces", "piece",
    "neuve", "neuves", "neufs",
    "sale", "house", "for sale",
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

    Real cities never carry a EUR sign, an "m^2", a "/mois", a
    "Réf." / "Ref" prefix, or two separate digit runs.
    """
    if not value:
        return False
    if _DESCRIPTOR_TOKENS.search(value):
        return True
    if _REFERENCE_LABEL.search(value):
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
    # Word-level decomposition: if every alphabetic word in the
    # candidate is a known nav label or property-type token, the
    # composite is a category phrase ("Location vacances appartement",
    # "Recherche appartement"), not a place name.
    alpha_words = [w for w in re.split(r"[\s\-]+", cleaned) if re.match(r"[A-Za-z\u00c0-\u017f]", w)]
    if alpha_words and all(
        normalize_for_match(w) in _NAV_LABELS or normalize_for_match(w) in _PROPERTY_TOKENS
        for w in alpha_words
    ):
        return False
    # Real French locations are at most 4-5 words (e.g. "Saint-Germain-
    # en-Laye 78100"). Strings with > 6 words are page titles or
    # descriptions that slipped past the nav-label check.
    if len(alpha_words) > 6:
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


def _slug_token_is_descriptor(token: str) -> bool:
    """True if a single URL-decoded slug token is a property descriptor.

    Cosialis-class URLs surfaced this defect: tokens like `27m²`,
    `900e`, `mois`, `€`, `m2` are surface / rent / currency markers,
    not place names. We reject them at the per-token level so the
    final commune candidate cannot be assembled out of them.
    """
    if not token:
        return True
    if "%" in token:
        # Token still carries a percent-encoded fragment after
        # `unquote` - the original URL was double-encoded or carried
        # invalid sequences. Either way, not a place name.
        return True
    if _SLUG_DESCRIPTOR_TOKEN.search(token):
        return True
    return False


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
    # URL-encoded query-like paths (`sale+house+ares+86927775`) are
    # search parameters, not location slugs.
    if "+" in url.split("?", 1)[0]:
        return ""
    parsed = urlparse(url)
    raw_path = parsed.path or ""
    if not raw_path:
        return ""
    # URL-decode FIRST. Cosialis-class URLs ship `%c2%b2` (m\u00b2 surface
    # marker) and `%20` (space) inside slug tokens; without decoding,
    # the tokens look opaque and slip past the descriptor filter.
    decoded_path = unquote(raw_path).lower()
    if not decoded_path:
        return ""
    segments = [seg for seg in decoded_path.split("/") if seg]
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
        # Drop property-descriptor tokens (m\u00b2, \u20ac, /mois, rent shorthand).
        if any(_slug_token_is_descriptor(tok) for tok in tokens):
            continue
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
