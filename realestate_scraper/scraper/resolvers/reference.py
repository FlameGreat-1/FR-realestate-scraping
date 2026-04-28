"""Listing reference / SKU resolver.

Real estate sites use very different conventions, so we look in:
    1. JSON-LD `sku`, `productID`, `identifier`, `reference`.
    2. Visible labels (`Réf.\u00a0XYZ123`, `Reference: XYZ123`).
    3. URL slug heuristics (final path segment, comma-suffix, `-vp123`).

Guards (Round 4):
    * Labels accept only identifier-shaped tokens.
    * Junk tokens cover the full nav/category vocabulary, plus the
      CTA / form vocabulary observed in the Round 3 outputs
      (`estimez-votre-bien`, `mettre-en-location`, `evaluer-mon-bien`,
      `vendre-mon-bien`, ...).
    * Slug fallback enforces a hyphen budget (<= 3) and a length
      ceiling (<= 30 chars). A real reference is short.
    * Comma-suffix slugs are validated on BOTH halves: the stem must
      itself be identifier-shaped (so a UI verb is rejected), and the
      tail must not be a bare 1-3 digit number (so the `,107` /
      `,123` query-style tails do not slip through).
    * The full slug must not be a pure-numeric short token; real
      references with a leading numeric stem also carry a typed
      prefix or a separator.
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
    # Round 2 additions
    "accession", "personnaliser", "copropriete",
    "bailleurs", "vendeurs", "acquereurs", "acheteurs",
    "mandataire", "locataires",
    "mes-biens", "mes-alertes", "mes-favoris",
    "mon-compte", "mon-espace", "espace-client",
    "financement", "simulateur", "simulation", "taux",
    "reglementation", "environnementale",
    "d-architecture", "hqe", "habitat-durable",
    "choisir", "realiser", "reception",
    "parrainage", "taxe", "vendre",
    # Round 4 additions: CTA / form slugs surfaced by Round 3 audit.
    "estimez-votre-bien", "estimez", "estimer-mon-bien",
    "evaluer-mon-bien", "evaluation",
    "mettre-en-location", "mettre-en-vente", "mettre-en",
    "vendre-mon-bien", "vendre-son-bien",
    "acheter-un-bien", "louer-un-bien",
    "deposer-une-annonce", "poster-une-annonce",
    "prendre-rendez-vous", "rendez-vous",
    "demande-de-rappel", "rappelez-moi", "rappel-immediat",
    "transaction",
)

# UI-verb roots: a slug whose first hyphen-token is one of these is a
# call-to-action, not a listing detail page. Used for the no-comma path.
_UI_VERB_ROOTS: frozenset[str] = frozenset({
    "mettre", "estimez", "estimer", "evaluer", "evaluez",
    "vendre", "vendez", "acheter", "achetez", "louer", "louez",
    "contacter", "contactez", "demander", "demandez",
    "deposer", "deposez", "poster", "prendre", "rappeler",
    "rappelez", "calculer", "calculez", "simuler", "simulez",
    "choisir", "choisissez", "trouver", "trouvez",
    "reserver", "reservez", "signaler", "signalez",
})

_VP_VM = re.compile(r"\b([A-Z]{1,3}\d{3,})\b")

# Franchise / CMS URL-tail patterns. The slug-shape gate enforces a
# `_MAX_SLUG_HYPHENS=3` budget which legitimately rejects the long
# descriptive slugs Nestenn / ERA / Century21 / Hektor templates emit.
# These patterns recover the embedded reference identifier from those
# tails directly. They are deliberately anchored on the URL string
# (path + query) and do not look at body text.
#   * `-ref-<digits>`         Nestenn, ERA, generic Apimo: 4+ digits.
#   * `-fp<digits>`           Century 21: 4+ digits.
#   * `,<acronym><digits>`    Hektor / Periscope: 1-3 letter prefix +
#                             3+ digits, anchored on a comma so a bare
#                             trailing number (page index) is rejected.
_URL_TAIL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-ref-?(\d{4,})(?:[/?,]|$)", re.IGNORECASE),
    re.compile(r"-fp(\d{4,})(?:[/?,]|$)", re.IGNORECASE),
    re.compile(r",([A-Za-z]{1,3}\d{3,})(?:[/?,]|$)"),
)

# An identifier-shaped token: must contain at least one digit, OR mixed
# case, OR an internal separator. Bare lower-case words fail.
_IDENTIFIER_SHAPE = re.compile(
    r".*(?:\d|[A-Z][a-z]|[a-z][A-Z]|[\-_/]).*"
)

# A slug that looks like a nav root: short and purely lower-case alpha.
_NAV_ROOT = re.compile(r"^[a-z]{1,5}$")

# Slug shape constraints for the URL fallback.
_MAX_SLUG_HYPHENS = 3
_MAX_SLUG_LENGTH = 30

# Pre-compiled checks for slug acceptability.
_HAS_DIGIT = re.compile(r"\d")
_LEADING_ACRONYM = re.compile(r"^[A-Z]{2,}[\-_/0-9]")
# A bare 1-3 digit token: too short to be a real reference id on the
# CMSes observed (Apimo / Hektor / Periscope / custom WP all use >= 4
# digits). Used to reject `,107`, `,123` and similar query-style tails.
_BARE_SHORT_NUMERIC = re.compile(r"^\d{1,3}$")
# Pure-digit tokens of any length without an internal separator are
# never accepted as references on their own; the typed-prefix or the
# explicit `Réf.` label paths cover legitimate numeric refs.
_BARE_DIGITS = re.compile(r"^\d+$")


def _is_junk(value: str) -> bool:
    lowered = (value or "").lower()
    return any(token in lowered for token in _JUNK_TOKENS)


def _is_identifier_shaped(value: str) -> bool:
    if not value or len(value) < 3:
        return False
    return bool(_IDENTIFIER_SHAPE.match(value))


def _slug_passes_shape(slug: str) -> bool:
    """True if `slug` looks like a real listing reference.

    Required:
        - length <= _MAX_SLUG_LENGTH
        - at most _MAX_SLUG_HYPHENS hyphens
        - contains a digit OR begins with a 2+ char upper-case acronym
        - is NOT a bare 1-3 digit number (those are query/page tails)
        - is NOT a bare pure-digit string without any separator
          (those are pagination indices on most CMSes)
    """
    if not slug or len(slug) > _MAX_SLUG_LENGTH:
        return False
    if slug.count("-") > _MAX_SLUG_HYPHENS:
        return False
    if _BARE_SHORT_NUMERIC.match(slug):
        return False
    if _BARE_DIGITS.match(slug):
        return False
    if _HAS_DIGIT.search(slug):
        return True
    if _LEADING_ACRONYM.match(slug):
        return True
    return False


def _stem_is_ui_verb(stem: str) -> bool:
    """True if a hyphenated stem starts with a UI-verb root.

    Rejects `estimez-votre-bien`, `mettre-en-location`, `vendre-mon-bien`,
    etc. - CTA pages on every CMS we observe.
    """
    if not stem:
        return False
    head = stem.split("-", 1)[0].lower()
    return head in _UI_VERB_ROOTS


def _from_slug(url: str) -> str:
    if not url:
        return ""
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    last = path.split("/")[-1]

    # URL-encoded query-like paths (`sale+house+ares+86927775`) are
    # search parameters, not listing references.
    if "+" in last:
        return ""

    # Comma-suffix path: validate BOTH the stem and the tail.
    if "," in last:
        stem, _, tail = last.rpartition(",")
        stem = stem.strip(".,;:")
        tail = tail.strip(".,;:")
        if not tail or len(tail) < 3:
            return ""
        if _is_junk(stem) or _is_junk(tail):
            return ""
        if _stem_is_ui_verb(stem):
            return ""
        # The stem must itself be identifier-shaped or empty (some
        # CMSes prefix the comma directly on a typed slug). A pure
        # lower-case phrase is rejected.
        if stem and not _is_identifier_shaped(stem):
            return ""
        # The tail standalone must pass the shape gate, which now
        # rejects bare 1-3 digit numbers and pure-digit strings.
        if not _slug_passes_shape(tail):
            return ""
        return tail

    last = last.strip(".,;:")
    if not last or len(last) < 3:
        return ""
    if _is_junk(last):
        return ""
    stem = last.rsplit(".", 1)[0] if "." in last else last
    if _NAV_ROOT.match(stem):
        return ""
    # No-comma path: reject CTA/UI-verb slugs at the segment level.
    if _stem_is_ui_verb(stem):
        return ""
    if not _is_identifier_shaped(stem):
        return ""
    if not _slug_passes_shape(stem):
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
    # The label path is deliberately more permissive than the slug
    # path because the literal "Réf." / "Ref:" prefix is itself
    # strong evidence; we still apply the digit-or-acronym shape so
    # "id : immobilier" cannot match.
    if not _slug_passes_shape(candidate):
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

        url = ctx.url or ""
        if url:
            for pattern in _URL_TAIL_PATTERNS:
                tail_match = pattern.search(url)
                if tail_match:
                    return ResolverResult(
                        tail_match.group(1), 0.7, "url_pattern",
                    )

        slug = _from_slug(ctx.url)
        if slug:
            return ResolverResult(slug, 0.5, "slug")

        return ResolverResult("", 0.0, "")
