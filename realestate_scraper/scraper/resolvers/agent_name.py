"""Agent-name resolver.

Order of confidence:
    1. JSON-LD (`RealEstateAgent`, `offers.seller.name`, `author.name`).
    2. Specific DOM containers in agent / contact / team contexts.
    3. Labelled inline text (`Conseiller : Jean Dupont`,
       `Votre négociateur : ...`, `Responsable du bien : ...`).
    4. Agency CSV `contact_person_last_name`, but only on pages that
       look like real listing detail pages.

Guards:
    * `_clean_name` rejects template disclaimers and UI labels
       ("Commercial indépendant du réseau", "Rechercher mon espace",
       "Espace client", "Newsletter", ...).
    * Word-shape sanity check: a real name is 2 to 4 whitespace-
       delimited tokens, each starting with an upper-case letter,
       no digits.
    * DOM matches require an agent / contact / team ancestor scope
       so a `.name` inside a footer or login form is not adopted.
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
    ".agent-card .name",
    ".agent-name",
    ".property-agent .name",
    ".contact-card .name",
    ".contact-card__name",
    ".team-member-name",
    ".team-member .name",
    ".bien-contact .name",
    ".bien-agent .name",
    ".commercial-name",
    ".negociateur-name",
    ".conseiller-name",
    "[itemprop='name'][itemtype*='Person']",
)

# Class fragments that mark the surrounding wrapper as a legitimate
# agent / contact / team context. We require at least one such ancestor
# so a generic `.name` inside footer / login / newsletter does not pass.
_AGENT_CONTEXT_FRAGMENTS: tuple[str, ...] = (
    "agent", "agents", "team", "equipe", "contact-card", "contact_card",
    "contact-info", "contact_info", "property-agent", "property_agent",
    "bien-contact", "bien_contact", "bien-agent", "bien_agent",
    "negociateur", "conseiller", "commercial", "sales-agent", "salesperson",
)
_AGENT_CONTEXT_DEPTH = 5

_LABEL_PATTERN = re.compile(
    r"(?:agent|n[ée]gociateur|conseiller(?:\s+immobilier)?|commercial|"
    r"responsable\s+du\s+bien|votre\s+(?:conseiller|n[ée]gociateur|contact))"
    r"\s*[:\-]?\s*"
    r"((?:M(?:me|lle|\.)?\s+|Mme\s+|Mlle\s+)?"
    r"[A-ZÀ-Ý][\wÀ-ÿ'\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'\-]+){1,3})",
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
)

# After honorifics are stripped, the remaining string must look like a
# proper name. We accept 2 to 4 tokens, each starting with an upper-case
# letter (or a French accented capital), with internal hyphens and
# apostrophes allowed. Crucially, single-token candidates are rejected;
# real estate sites never publish bare first names without a surname,
# but they do publish bare role labels ("Commercial", "Négociateur")
# that would otherwise pass the cleaner.
_NAME_SHAPE = re.compile(
    r"^[A-ZÀ-Ý][\wÀ-ÿ'\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'\-]+){1,3}$"
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

    # Shape gate: must look like a proper name (>= 2 capitalised tokens).
    if not _NAME_SHAPE.match(text):
        return ""

    # No digits in real names.
    if any(ch.isdigit() for ch in text):
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
        ld_agent = ctx.json_ld.get("agent_name") if ctx.json_ld else None
        cleaned = _clean_name(ld_agent if isinstance(ld_agent, str) else None)
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

        match = _LABEL_PATTERN.search(ctx.text or "")
        if match:
            cleaned = _clean_name(match.group(1))
            if cleaned:
                return ResolverResult(cleaned, 0.7, "label")

        # Agency-csv fallback only on detail pages.
        if (
            ctx.domain_job
            and ctx.domain_job.agent_name
            and _is_detail_page(ctx, parser)
        ):
            cleaned = _clean_name(ctx.domain_job.agent_name)
            if cleaned:
                return ResolverResult(cleaned, 0.4, "agency_csv")

        return ResolverResult("", 0.0, "")
