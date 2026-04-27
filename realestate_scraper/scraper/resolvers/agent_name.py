"""Agent-name resolver.

Order of confidence:
    1. JSON-LD (`RealEstateAgent`, `offers.seller.name`, `author.name`).
    2. DOM containers (`.agent-name`, `[itemprop='salesAgent']`,
       `.contact-card .name`, `.team-member-name`, ...).
    3. Labelled inline text (`Conseiller : Jean Dupont`,
       `Votre négociateur : ...`, `Responsable du bien : ...`).
    4. Agency CSV `contact_person_last_name` (last-resort fallback).

Every branch is sanitised through the same `_clean_name` so an empty
or obviously-junk match does not block the next branch from running.
This is the bug that produced the 0.0% fill rate in the baseline.
"""
from __future__ import annotations

import re
from typing import Optional

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult
from ..utils.text import collapse_whitespace

_DOM_SELECTORS = (
    "[itemprop='salesAgent']",
    "[itemprop='author']",
    "[data-agent-name]",
    "[data-agent]",
    ".agent-name",
    ".agent .name",
    ".agent-card .name",
    ".property-agent .name",
    ".contact-card .name",
    ".contact-card__name",
    ".team-member-name",
    ".team-member .name",
    ".commercial",
    ".negociateur",
    ".conseiller",
    ".contact-name",
    ".bien-contact .name",
    ".bien-agent .name",
)

_LABEL_PATTERN = re.compile(
    r"(?:agent|n[ée]gociateur|conseiller(?:\s+immobilier)?|commercial|"
    r"responsable\s+du\s+bien|votre\s+(?:conseiller|n[ée]gociateur|contact))"
    r"\s*[:\-]?\s*"
    r"((?:M(?:me|lle|\.)?\s+|Mme\s+|Mlle\s+)?"
    r"[A-ZÀ-Ý][\wÀ-ÿ'\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'\-]+){0,3})",
    re.IGNORECASE,
)

_HONORIFICS_RE = re.compile(
    r"^(?:m\.|mme|mlle|monsieur|madame|mademoiselle)\s+",
    re.IGNORECASE,
)

_JUNK_NAME_TOKENS = (
    "contact", "contactez", "appeler", "agence", "votre conseiller",
    "nous joindre", "telephone", "hotline", "service", "email",
    "horaires", "ouvert", "footer", "newsletter",
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
    lowered = text.lower()
    if any(token in lowered for token in _JUNK_NAME_TOKENS):
        return ""
    # A real name has at least one alphabetic character and at most a
    # few words; rejecting digit-heavy strings filters phone numbers
    # that slipped through DOM selectors.
    letters = sum(1 for ch in text if ch.isalpha())
    if letters < 2:
        return ""
    return text


def _from_dom(parser: HTMLParser) -> str:
    for selector in _DOM_SELECTORS:
        try:
            node = parser.css_first(selector)
        except Exception:
            continue
        if not node:
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


class AgentNameResolver:
    name = "agent_name"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_agent = ctx.json_ld.get("agent_name") if ctx.json_ld else None
        cleaned = _clean_name(ld_agent if isinstance(ld_agent, str) else None)
        if cleaned:
            return ResolverResult(cleaned, 0.95, "json_ld")

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

        if ctx.domain_job and ctx.domain_job.agent_name:
            cleaned = _clean_name(ctx.domain_job.agent_name)
            if cleaned:
                return ResolverResult(cleaned, 0.4, "agency_csv")

        return ResolverResult("", 0.0, "")
