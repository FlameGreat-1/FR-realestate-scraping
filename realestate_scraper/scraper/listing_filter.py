"""Generic, language-agnostic listing-URL classifier.

This is the scalability lever for 55k+ domains: instead of hand-curated
per-domain allowlists, we score URLs against a corpus of real estate
listing heuristics that hold across French/English real estate CMSes
(Apimo, Hektor, Périclès, Nestenn, Stéphane Plaza, Guy Hoquet,
Laforet, Era, Century 21, Orpi, Nestoria, Logic-Immo, custom WP, etc.).

The classifier returns a numeric score; the listing extractor accepts
URLs scoring >= a small positive threshold. The thresholds and rules
live in one place so they are auditable and testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from .utils.url import canonicalize

# --- Negative signals (downrank or reject outright) -------------------

_BAD_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".css", ".js", ".mp4", ".mp3", ".zip", ".doc", ".docx",
)

_BAD_SCHEMES = ("mailto:", "tel:", "javascript:", "data:")

_SOCIAL_HOSTS = (
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    "x.com", "youtube.com", "tiktok.com", "pinterest.com",
    "google.com/maps", "goo.gl",
)

_NON_LISTING_TERMS = (
    "contact", "a-propos", "apropos", "about", "team", "equipe",
    "blog", "news", "actualites", "actualite", "article", "tag",
    "author", "mentions-legales", "privacy", "politique-confidentialite",
    "politique", "estimation", "estimer", "vendre-nous",
    "recrutement", "emploi", "carriere", "agences", "agence",
    "cookies", "newsletter",
)

_HUB_PATHS = {
    "/", "/lots", "/lot", "/search", "/recherche", "/result",
    "/results", "/buy", "/listing-categorie", "/produits/all",
    "/biens/result", "/resultat.php", "/annonces", "/biens",
    "/proprietes", "/properties",
}

_HUB_PATTERNS = re.compile(
    r"(achat-immobilier|vente-immobilier|listing-categorie|prix-m2|"
    r"prix-rues|/search(?:/|$)|/recherche(?:/|$)|/result(?:/|$)|"
    r"/results(?:/|$)|/biens/result|/produits/all|"
    r"^/annonces/?$|^/annonce/?$|"
    r"^/proprietes/?$|^/properties/?$)",
    re.IGNORECASE,
)

# --- Positive signals --------------------------------------------------

_POSITIVE_TERMS = (
    "listing", "listings", "lots", "lot", "biens", "bien",
    "vente", "ventes", "buy", "property", "properties",
    "propriete", "proprietes", "produit", "produits",
    "maison", "maisons", "appartement", "appartements", "villa",
    "villas", "terrain", "terrains", "studio", "garage",
    "parking", "loft", "duplex", "chalet", "chateau", "immeuble",
    "detail", "details", "annonce", "location", "locations",
)

_REFERENCE_HINTS = re.compile(
    r"(ref-?[a-z0-9]{3,}|reference[-_=][a-z0-9]{3,}|id[-_=]\d{3,}|"
    r"-vp\d{3,}|-vm\d{3,}|/\d{6,}(?:[/?,]|$)|/[a-z0-9-]{12,}-\d{3,}"
    r"(?:[/?]|$))",
    re.IGNORECASE,
)

_QUERY_HINTS = re.compile(
    r"(page=|rooms=|budget=|zipcode=|loc=vente|type=all|piece|chambre)",
    re.IGNORECASE,
)

_T_NOTATION = re.compile(r"\bt\d\b", re.IGNORECASE)

# Reasons the detail classifier emits when it rejects a URL specifically
# because it looks like a hub/index. Used by `classify_seed` to decide
# whether the URL is worth expanding (rather than scraping directly).
_HUB_REJECTION_REASONS: frozenset[str] = frozenset({
    "hub_path",
    "hub_pattern",
})


class SeedKind(str, Enum):
    """Outcome of seed classification.

    DETAIL: the URL itself is a candidate property page; scrape it.
    HUB:    the URL is an index/search/category page; fetch it and
            expand its child anchors as further seeds.
    REJECT: not useful (asset, social, blog, contact, etc.).
    """

    DETAIL = "detail"
    HUB = "hub"
    REJECT = "reject"


@dataclass(slots=True)
class UrlClassification:
    score: int
    reason: str

    @property
    def accepted(self) -> bool:
        return self.score > 0


def _normalised_path(url: str) -> tuple[str, str]:
    parsed = urlparse(canonicalize(url))
    path = (parsed.path or "/").lower()
    query = (parsed.query or "").lower()
    full = f"{path}?{query}" if query else path
    return path, full


def classify_url(url: str) -> UrlClassification:
    """Return a positive score for likely listing URLs, <=0 to reject."""
    if not url:
        return UrlClassification(0, "empty")

    lowered = url.strip().lower()
    if lowered.startswith(_BAD_SCHEMES):
        return UrlClassification(-100, "bad_scheme")
    if any(host in lowered for host in _SOCIAL_HOSTS):
        return UrlClassification(-50, "social")
    if any(lowered.endswith(ext) for ext in _BAD_EXTENSIONS):
        return UrlClassification(-50, "asset_extension")

    path, full = _normalised_path(url)
    if not path or path == "/":
        return UrlClassification(0, "root")

    if any(term in full for term in _NON_LISTING_TERMS):
        return UrlClassification(-20, "non_listing_term")

    normalised = path.rstrip("/")
    if normalised in _HUB_PATHS:
        return UrlClassification(-10, "hub_path")
    if _HUB_PATTERNS.search(full):
        return UrlClassification(-10, "hub_pattern")

    score = 0
    reason_bits: list[str] = []

    for term in _POSITIVE_TERMS:
        if term in full:
            score += 2
            reason_bits.append(term)
            break

    if _REFERENCE_HINTS.search(full):
        score += 4
        reason_bits.append("ref")

    if _QUERY_HINTS.search(full):
        score += 1
        reason_bits.append("query")

    if _T_NOTATION.search(full):
        score += 1
        reason_bits.append("t-notation")

    segments = [seg for seg in path.split("/") if seg]
    if len(segments) >= 3:
        score += 1
        reason_bits.append("deep_path")

    last = segments[-1] if segments else ""
    if re.search(r"\d{4,}", last):
        score += 1
        reason_bits.append("numeric_slug")

    # Reject 1-2 segment paths with no signal at all - these are nav
    # pages even if they happen to mention 'maison'.
    if score <= 0 and len(segments) <= 2:
        return UrlClassification(-1, "shallow_no_signal")

    return UrlClassification(score, ",".join(reason_bits) or "none")


def classify_seed(url: str) -> SeedKind:
    """Classify a URL as a detail page, an expandable hub, or rejected.

    Reuses the same `classify_url` heuristics so we never disagree with
    the detail-page classifier. Hubs are exactly the URLs that
    `classify_url` rejects with a hub-shaped reason - we don't add new
    rules, we just stop throwing that signal away.
    """
    if not url:
        return SeedKind.REJECT
    if not is_candidate_seed_url(url, base_url=url):
        return SeedKind.REJECT
    verdict = classify_url(url)
    if verdict.accepted:
        return SeedKind.DETAIL
    if verdict.reason in _HUB_REJECTION_REASONS:
        return SeedKind.HUB
    return SeedKind.REJECT


def is_candidate_listing_url(url: str) -> bool:
    """Boolean wrapper for callers that don't need the score breakdown."""
    return classify_url(url).accepted


def is_candidate_seed_url(url: str, base_url: str) -> bool:
    """Permissive filter for second-pass *crawl* seeds (not detail pages)."""
    if not url:
        return False
    if not url.startswith(("http://", "https://")):
        return False
    lowered = url.lower()
    if any(lowered.endswith(ext) for ext in _BAD_EXTENSIONS):
        return False
    if any(host in lowered for host in _SOCIAL_HOSTS):
        return False
    if any(token in lowered for token in (
        "contact", "blog", "news", "article", "mentions-legales",
        "privacy", "politique",
    )):
        return False
    return True
