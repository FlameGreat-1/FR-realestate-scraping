"""Price resolver.

Order of confidence:
    1. JSON-LD `offers.price` (highest).
    2. Microdata `[itemprop=price]` and `[data-price*]` attributes.
    3. Class-named price elements (`.price`, `.prix`, `.bien-prix`).
    4. Labelled inline text (`Prix : 621 000 €`).
    5. First trailing-€ amount in body text.

We never accept a price extracted from a *hub* URL; the listing filter
gates that upstream, but we still skip explicit "sur demande" markers
and obvious m²-rate captures.
"""
from __future__ import annotations

import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult
from ..utils.text import clean_price, find_euro_amounts, find_priced_labels

# Match per-m2 *rate* contexts only; a bare "120 m2" must NOT trip this.
# Required: explicit currency-per-area or explicit "prix au m2" wording.
_M2_NOISE = re.compile(
    r"(?:€|eur|euro[s]?)\s*(?:/|par)\s*m\s*[²2²]"
    r"|prix\s*(?:au|/|-)\s*m\s*[²2²]"
    r"|prix-rues"
    r"|cost\s*per\s*m\s*[²2²]",
    re.IGNORECASE,
)
_ON_REQUEST = re.compile(
    r"sur\s+demande|on\s+request|prix\s+sur\s+demande|nous\s+consulter",
    re.IGNORECASE,
)

_DOM_SELECTORS = (
    "[itemprop='price']",
    "[data-price]",
    "[data-price-value]",
    "[data-price-amount]",
    "meta[itemprop='price']",
    ".price",
    ".prix",
    ".bien-prix",
    ".property-price",
    ".listing-price",
)


def _candidate_texts(parser: HTMLParser, selectors: Iterable[str]) -> list[str]:
    out: list[str] = []
    for selector in selectors:
        try:
            nodes = parser.css(selector)
        except Exception:
            continue
        for node in nodes:
            attr_value = (
                node.attributes.get("content")
                or node.attributes.get("data-price")
                or node.attributes.get("data-price-value")
                or node.attributes.get("data-price-amount")
            )
            if attr_value:
                out.append(attr_value)
            text = node.text(deep=True, separator=" ", strip=True)
            if text:
                out.append(text)
    return out


def _is_per_m2(candidate: str) -> bool:
    return bool(_M2_NOISE.search(candidate or ""))


def _accept(candidate: str, *, surrounding: str = "") -> str:
    if not candidate or _ON_REQUEST.search(candidate):
        return ""
    # The per-m2 guard runs against both the candidate and the
    # surrounding text. Path 5 (`find_euro_amounts`) captures only the
    # digit fragment, so the per-m2 marker is in the surrounding text,
    # not in the candidate itself.
    if _is_per_m2(candidate) or (surrounding and _is_per_m2(surrounding)):
        return ""
    if "€" not in candidate and not re.search(r"(prix|price)", candidate, re.IGNORECASE):
        return ""
    return clean_price(candidate)


class PriceResolver:
    name = "price"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        # 1. JSON-LD
        ld_price = ctx.json_ld.get("price") if ctx.json_ld else None
        if ld_price:
            cleaned = clean_price(str(ld_price))
            if cleaned:
                return ResolverResult(cleaned, 0.95, "json_ld")

        if not ctx.html:
            return ResolverResult("", 0.0, "")

        try:
            parser = HTMLParser(ctx.html)
        except Exception:
            return ResolverResult("", 0.0, "")

        # 2 & 3. DOM selectors
        for candidate in _candidate_texts(parser, _DOM_SELECTORS):
            cleaned = _accept(candidate)
            if cleaned:
                return ResolverResult(cleaned, 0.85, "dom")

        # 4. Labelled text
        for candidate in find_priced_labels(ctx.text):
            cleaned = _accept(candidate)
            if cleaned:
                return ResolverResult(cleaned, 0.7, "label")

        # 5. Trailing euro amounts. Pass `ctx.text` as surrounding so
        # the per-m2 guard sees the rate marker even though the
        # captured fragment is just digits.
        for candidate in find_euro_amounts(ctx.text):
            cleaned = _accept(candidate + " €", surrounding=ctx.text)
            if cleaned:
                return ResolverResult(cleaned, 0.55, "euro")

        return ResolverResult("", 0.0, "")
