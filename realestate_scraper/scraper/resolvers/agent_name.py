"""Agent-name resolver.

A listing's responsible agent is rarely modelled in JSON-LD beyond a
free-form string, so we look for explicit DOM containers first
(`.agent-name`, `.commercial`, `[itemprop='name']` inside an agent
block) and only fall back to the agency CSV's `contact_person_last_name`.
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult
from ..utils.text import collapse_whitespace

_DOM_SELECTORS = (
    ".agent-name",
    ".agent .name",
    ".commercial",
    ".negociateur",
    ".contact-name",
    "[itemprop='salesAgent']",
    "[data-agent-name]",
)

_LABEL_PATTERNS = (
    re.compile(
        r"(?:agent|n[ée]gociateur|conseiller|commercial)\s*[:\-]?\s*"
        r"([A-ZÉÀÈÊËÎÏÔÙÛÜÒÖÂÄ][\wÀ-ÿ'\.\- ]{2,40})",
    ),
)


def _from_dom(parser: HTMLParser) -> str:
    for selector in _DOM_SELECTORS:
        try:
            node = parser.css_first(selector)
        except Exception:
            continue
        if not node:
            continue
        attr = node.attributes.get("data-agent-name")
        if attr:
            value = collapse_whitespace(attr)
            if value:
                return value
        value = collapse_whitespace(node.text(deep=True, separator=" ", strip=True))
        if value and len(value) <= 80:
            return value
    return ""


class AgentNameResolver:
    name = "agent_name"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        if ctx.html:
            try:
                parser = HTMLParser(ctx.html)
            except Exception:
                parser = None
            if parser is not None:
                value = _from_dom(parser)
                if value:
                    return ResolverResult(value, 0.85, "dom")

        for pattern in _LABEL_PATTERNS:
            match = pattern.search(ctx.text or "")
            if match:
                value = collapse_whitespace(match.group(1))
                if value:
                    return ResolverResult(value, 0.7, "label")

        if ctx.domain_job and ctx.domain_job.agent_name:
            return ResolverResult(
                collapse_whitespace(ctx.domain_job.agent_name),
                0.4,
                "agency_csv",
            )

        return ResolverResult("", 0.0, "")
