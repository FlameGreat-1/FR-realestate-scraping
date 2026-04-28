"""Agent-name resolver.

Order of confidence:
    1. JSON-LD: top-level / nested `RealEstateAgent` or `Person`,
       plus `offers.seller.name` and `author.name`.
    2. DOM containers in agent / contact / team / fiche-contact /
       responsable / referent / signature contexts.
    3. Labelled inline text: both prefix (`Conseiller : Jean Dupont`)
       and postfix (`Jean Dupont - Conseiller`) shapes.
    4. Agency CSV `contact_person_last_name`, but only on pages that
       look like real listing detail pages.

Guards:
    * `_clean_name` rejects template disclaimers and UI labels
      ("Commercial indépendant du réseau", "Rechercher mon espace",
      "Espace client", "Newsletter", ...).
    * Word-shape sanity check: a real name is one of the two shapes
      observed across French agency templates: 2-4 mixed-case tokens
      OR an ALL-CAPS surname optionally preceded by a mixed-case
      given name. Single mixed-case tokens are rejected; bare role
      labels ("Commercial", "Négociateur") would otherwise pass.
    * DOM matches require an agent / contact / team / fiche / card
      ancestor scope so a `.name` inside a footer or login form is
      not adopted.
"""
from __future__ import annotations

import re
from typing import Optional

from selectolax.parser import HTMLParser, Node

from ..models import PageContext, ResolverResult
from ..utils.text import collapse_whitespace, normalize_for_match

_DOM_SELECTORS = (
    "[itemprop='salesAgent']",
    "[itemprop='author']",
    "[data-agent-name]",
    "[data-agent]",
    "[data-conseiller]",
    "[data-negociateur]",
    ".agent-card .name",
    ".agent-card__name",
    ".agent-name",
    ".agent-info .name",
    ".property-agent .name",
    ".contact-card .name",
    ".contact-card__name",
    ".contact-bien .name",
    ".contact-bien__name",
    ".bloc-contact .name",
    ".card-contact .name",
    ".author-card .name",
    ".fiche-contact .name",
    ".fiche-contact__name",
    ".team-member-name",
    ".team-member .name",
    ".bien-contact .name",
    ".bien-agent .name",
    ".bien-card .name",
    ".commercial-name",
    ".consultant-name",
    ".negociateur-name",
    ".negociateur .name",
    ".conseiller-name",
    ".conseiller .name",
    ".responsable .name",
    ".referent .name",
    ".intervenant .name",
    ".expert-immobilier .name",
    ".signature .name",
    ".signature-author",
    ".author .name",
    "[itemprop='name'][itemtype*='Person']",
    "[itemprop='name'][itemtype*='RealEstateAgent']",
)

# Class fragments that mark the surrounding wrapper as a legitimate
# agent / contact / team context. We require at least one such ancestor
# so a generic `.name` inside footer / login / newsletter does not pass.
_AGENT_CONTEXT_FRAGMENTS: tuple[str, ...] = (
    # Round 1-3 vocabulary, preserved.
    "agent", "agents", "team", "equipe", "contact-card", "contact_card",
    "contact-info", "contact_info", "property-agent", "property_agent",
    "bien-contact", "bien_contact", "bien-agent", "bien_agent",
    "negociateur", "conseiller", "commercial", "sales-agent", "salesperson",
    # Round 4 additions: French agency template wrappers observed in
    # the Round-3 input domains.
    "fiche-contact", "fiche_contact",
    "contact-bien", "contact_bien",
    "bloc-contact", "bloc_contact",
    "card-contact", "card_contact",
    "author-card", "author_card",
    "agent-card", "agent_card",
    "bien-card", "bien_card",
    "agent-info", "agent_info",
    "signature", "signature-author", "signature_author",
    "responsable", "referent", "intervenant",
    "expert", "expert-immobilier", "expert_immobilier",
    "consultant", "proprietaire", "vendeur",
    "agent-immobilier", "agent_immobilier",
    "nego", "author",
)
_AGENT_CONTEXT_DEPTH = 5

# Role vocabulary used by both the prefix and postfix label patterns.
_ROLE_ALTERNATION = (
    r"agent(?:\s+immobilier)?|n[ée]gociateur|conseiller(?:\s+immobilier)?|"
    r"commercial|consultant(?:\s+immobilier)?|expert(?:\s+immobilier)?|"
    r"responsable\s+du\s+bien|votre\s+(?:conseiller|n[ée]gociateur|contact)|"
    r"mandataire(?:\s+immobilier)?|referent"
)

# A name token: optional honorific + capitalised given/surname.
_NAME_TOKEN = (
    r"(?:M(?:me|lle|\.)?\s+|Mme\s+|Mlle\s+)?"
    r"[A-ZÀ-Ý][\wÀ-ÿ'\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'\-]+){1,3}"
)

# Prefix shape: `Conseiller : Jean Dupont`.
_LABEL_PATTERN_PREFIX = re.compile(
    rf"(?:{_ROLE_ALTERNATION})\s*[:\-–—]?\s*({_NAME_TOKEN})",
    re.IGNORECASE,
)
# Postfix shape: `Jean Dupont - Conseiller`, `Jean Dupont, Conseiller`.
_LABEL_PATTERN_POSTFIX = re.compile(
    rf"({_NAME_TOKEN})\s*[\-–—,]\s*(?:{_ROLE_ALTERNATION})\b",
    re.IGNORECASE,
)

_HONORIFICS_RE = re.compile(
    r"^(?:m\.|mme|mlle|monsieur|madame|mademoiselle)\s+",
    re.IGNORECASE,
)

# Phrases / fragments that prove the candidate is NOT a person's name.
# Compared after `normalize_for_match` (lower-cased, accents stripped).
_JUNK_FRAGMENTS: tuple[str, ...] = (
    "contact", "contactez", "appeler", "appelez", "agence",
    "votre conseiller", "votre negociateur", "votre contact",
    "nous joindre", "nous contacter", "telephone", "hotline",
    "service", "email", "horaires", "ouvert", "footer",
    "newsletter", "abonnez", "abonner",
    "independant", "reseau", "mandataire",
    "rechercher", "recherche", "mon espace", "espace client",
    "connexion", "se connecter", "connectez",
    "menu", "accueil", "bienvenue",
    "formulaire", "envoyer", "valider", "rappel", "rappelez",
    "callback", "call back",
    "toutes nos agences", "trouver une agence",
    "plan du site", "mentions legales", "politique", "cookies",
    "estimer", "estimation", "simulateur", "financement",
    "deconnexion", "inscription",
)

# Mixed-case shape: 2-4 capitalised tokens. The original Round 1-3
# pattern. Real names like `Jean Dupont`, `Marie-Hélène Martin` match.
_NAME_SHAPE_MULTI = re.compile(
    r"^[A-ZÀ-Ý][\wÀ-ÿ'\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'\-]+){1,3}$"
)

# All-caps shape: an ALL-CAPS surname (>= 2 letters), optionally
# preceded by a mixed-case given name. French agency templates
# routinely render names this way: `Jean DUPONT`, `DUPONT`,
# `MARTIN-DUPONT`, `Marie DUPONT-MARTIN`.
_NAME_SHAPE_CAPS = re.compile(
    r"^(?:[A-ZÀ-Ý][\wÀ-ÿ'\-]+\s+)?"
    r"[A-ZÀ-Ý]{2,}(?:[\-' ][A-ZÀ-Ý]{2,})*$"
)

# Reference shape used to gate the agency-csv fallback to detail pages.
_REFERENCE_SHAPE = re.compile(
    r"(?:/\d{5,}|-vp\d{3,}|-vm\d{3,}|/[a-z0-9-]{12,}-\d{3,}|,[A-Z]{1,3}\d{3,})",
    re.IGNORECASE,
)


def _has_agent_context(node: Optional[Node]) -> bool:
    """True if `node` or any close ancestor has an agent-coded class."""
    current = node
    for _ in range(_AGENT_CONTEXT_DEPTH):
        if current is None:
            return False
        attrs = current.attributes if current.attributes else {}
        klass = (attrs.get("class") or "").lower()
        ident = (attrs.get("id") or "").lower()
        haystack = klass + " " + ident
        if haystack:
            for fragment in _AGENT_CONTEXT_FRAGMENTS:
                if fragment in haystack:
                    return True
        current = current.parent
    return False


def _matches_name_shape(text: str) -> bool:
    """True if `text` matches either of the accepted name shapes."""
    if not text:
        return False
    return bool(
        _NAME_SHAPE_MULTI.match(text) or _NAME_SHAPE_CAPS.match(text)
    )


def _clean_name(value: Optional[str]) -> str:
    """Normalise a candidate, return empty string if unusable."""
    if not value:
        return ""
    text = collapse_whitespace(value)
    if not text or len(text) > 80:
        return ""
    text = _HONORIFICS_RE.sub("", text).strip()
    if not text:
        return ""

    normalised = normalize_for_match(text)
    if not normalised:
        return ""
    if any(fragment in normalised for fragment in _JUNK_FRAGMENTS):
        return ""

    # Shape gate: must look like a proper name in either of the two
    # observed templates (mixed-case tokens, or capitalised given +
    # ALL-CAPS surname).
    if not _matches_name_shape(text):
        return ""

    # No digits in real names.
    if any(ch.isdigit() for ch in text):
        return ""

    return text


def _accept_csv_agent_name(value: Optional[str]) -> str:
    """Looser cleaner for the agency-CSV fallback path.

    The CSV value is itself authoritative evidence - it was supplied
    as input data, not parsed from arbitrary HTML. We therefore admit
    single-token names (e.g. "Yves") which the strict shape gate
    would otherwise reject as ambiguous role labels. Junk-fragment
    and digit guards still apply.
    """
    if not value:
        return ""
    text = collapse_whitespace(value)
    if not text or len(text) > 80:
        return ""
    text = _HONORIFICS_RE.sub("", text).strip()
    if not text:
        return ""
    normalised = normalize_for_match(text)
    if not normalised:
        return ""
    if any(fragment in normalised for fragment in _JUNK_FRAGMENTS):
        return ""
    if any(ch.isdigit() for ch in text):
        return ""
    # Must contain at least one capitalised letter; the CSV may ship
    # the value lower-cased on some sources, in which case we title-case.
    if not re.search(r"[A-ZÀ-Ý]", text):
        text = text.title()
    if not re.match(r"^[A-ZÀ-Ý]", text):
        return ""
    return text


def _from_dom(parser: HTMLParser) -> str:
    """Walk DOM selectors, accepting only agent-context-scoped matches."""
    for selector in _DOM_SELECTORS:
        try:
            nodes = parser.css(selector)
        except Exception:
            continue
        for node in nodes:
            if not _has_agent_context(node):
                continue
            attr = (
                node.attributes.get("data-agent-name")
                or node.attributes.get("data-agent")
                or node.attributes.get("data-conseiller")
                or node.attributes.get("data-negociateur")
                or node.attributes.get("content")
            )
            cleaned = _clean_name(attr)
            if cleaned:
                return cleaned
            cleaned = _clean_name(
                node.text(deep=True, separator=" ", strip=True)
            )
            if cleaned:
                return cleaned
    return ""


def _from_labels(text: str) -> str:
    """Run both the prefix and postfix label patterns, return the first hit."""
    if not text:
        return ""
    for pattern in (_LABEL_PATTERN_PREFIX, _LABEL_PATTERN_POSTFIX):
        match = pattern.search(text)
        if not match:
            continue
        cleaned = _clean_name(match.group(1))
        if cleaned:
            return cleaned
    return ""


def _is_detail_page(ctx: PageContext, parser: Optional[HTMLParser]) -> bool:
    """Mirror of `location._is_listing_page`, kept local to avoid coupling."""
    if ctx.json_ld:
        for key in ("price", "reference_id", "description", "name"):
            if ctx.json_ld.get(key):
                return True
    if ctx.url and _REFERENCE_SHAPE.search(ctx.url):
        return True
    if parser is not None:
        try:
            crumbs = parser.css(".breadcrumb, .breadcrumbs, [class*='breadcrumb' i]")
        except Exception:
            crumbs = []
        for node in crumbs:
            items = node.css("li, a")
            if len(items) >= 3:
                return True
    return False


class AgentNameResolver:
    name = "agent_name"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        # JSON-LD path: `utils.json_ld._walk` emits `agent_name` from
        # both top-level Person/RealEstateAgent nodes and nested
        # author/seller/publisher/provider/agent keys.
        if ctx.json_ld:
            for key in ("agent_name", "realestate_agent", "agent"):
                value = ctx.json_ld.get(key)
                if isinstance(value, str):
                    cleaned = _clean_name(value)
                    if cleaned:
                        return ResolverResult(cleaned, 0.95, "json_ld")

        parser: Optional[HTMLParser] = None
        if ctx.html:
            try:
                parser = HTMLParser(ctx.html)
            except Exception:
                parser = None
            if parser is not None:
                cleaned = _from_dom(parser)
                if cleaned:
                    return ResolverResult(cleaned, 0.85, "dom")

        cleaned = _from_labels(ctx.text or "")
        if cleaned:
            return ResolverResult(cleaned, 0.7, "label")

        # Agency-csv fallback only on detail pages, with the looser
        # cleaner. The CSV is its own authoritative source; we don't
        # need to gate it on the strict shape regex.
        if (
            ctx.domain_job
            and ctx.domain_job.agent_name
            and _is_detail_page(ctx, parser)
        ):
            cleaned = _accept_csv_agent_name(ctx.domain_job.agent_name)
            if cleaned:
                return ResolverResult(cleaned, 0.4, "agency_csv")

        return ResolverResult("", 0.0, "")
