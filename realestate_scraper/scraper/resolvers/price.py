"""Price resolver.

Order of confidence:
    1. JSON-LD `offers.price` (highest).
    2. Microdata `[itemprop=price]` and `[data-price*]` attributes.
    3. Class-named price elements (`.price`, `.prix`, `.bien-prix`).
    4. Labelled inline text (`Prix : 621 000 €`).
    5. First trailing-€ amount in body text, only when the surrounding
       window carries an explicit sale marker.

Guards:
    * Per-m2 *rate* contexts are filtered using a window-scoped check
      so unrelated neighbourhood stats elsewhere on the page do not
      reject a valid price.
    * Rent / charges / honoraires contexts are rejected outright; this
      brief is for sale listings.
    * DOM matches whose ancestor classes are rent-coded are skipped.
    * "Sur demande" / "on request" markers leave the field empty
      rather than guessing.
    * Realistic numeric range: >= 1000 EUR and <= 50,000,000 EUR.
      Combined with the digit-length ceiling in `utils.text.clean_price`
      this excludes shared template numbers, concatenated digit runs,
      and impossibly large values.
    * DOM nodes that look like reference fields (small bare integer,
      no EUR sign, no "prix" label) are rejected so a `.price`-shaped
      node carrying just "1075" cannot leak the reference id into
      the price field.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from selectolax.parser import HTMLParser, Node

from ..models import PageContext, ResolverResult
from ..utils.text import clean_price, find_priced_labels

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
_RENT_CONTEXT = re.compile(
    r"loyer(?:\s+(?:mensuel|charges))?|/\s*mois|par\s+mois|monthly\s+rent"
    r"|charges?\s+comprises|honoraires?\s+(?:de\s+)?location",
    re.IGNORECASE,
)
_SALE_MARKER = re.compile(
    r"vente|achat|à\s+vendre|a\s+vendre|prix\s+de\s+vente|\bfai\b|net\s+vendeur"
    r"|honoraires?\s+(?:d['’]?|de\s+)?(?:vente|charge\s+vendeur|charge\s+acqu[ée]reur)"
    r"|\bprice\b|sale\s+price",
    re.IGNORECASE,
)
_PRICE_LABEL_INLINE = re.compile(r"\bprix\b|\bprice\b", re.IGNORECASE)
_HAS_CURRENCY = re.compile(r"€|\beur(?:o|os)?\b", re.IGNORECASE)

_EURO_AMOUNT = re.compile(r"([0-9][0-9\s\xa0.,]*)\s*€")

# Window (in characters) around a captured amount used for context guards.
_GUARD_WINDOW = 120

# Realistic absolute bounds for a French residential sale price (EUR).
_MIN_SALE_PRICE_EUR = 1_000
_MAX_SALE_PRICE_EUR = 50_000_000

# A capture that is both small (<= 4 digits) and has neither a currency
# symbol nor a "prix" label in its surrounding window is far more often
# a reference id than a price, so we reject it.
_SMALL_VALUE_DIGITS = 4

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

_RENT_CLASS_FRAGMENTS: tuple[str, ...] = (
    "loyer", "rent", "location-prix", "location_price", "location-price",
    "charges", "honoraires", "mensualite",
)
_RENT_ANCESTOR_DEPTH = 4


def _around(text: str, span: tuple[int, int], window: int = _GUARD_WINDOW) -> str:
    if not text:
        return ""
    start = max(0, span[0] - window)
    end = min(len(text), span[1] + window)
    return text[start:end]


def _is_per_m2(snippet: str) -> bool:
    return bool(_M2_NOISE.search(snippet or ""))


def _is_rent(snippet: str) -> bool:
    return bool(_RENT_CONTEXT.search(snippet or ""))


def _has_sale_marker(snippet: str) -> bool:
    return bool(_SALE_MARKER.search(snippet or ""))


def _has_currency_or_label(snippet: str) -> bool:
    return bool(_HAS_CURRENCY.search(snippet or "")) or bool(
        _PRICE_LABEL_INLINE.search(snippet or "")
    )


def _passes_sale_range(digits: str) -> bool:
    """Reject implausibly small or large absolute amounts."""
    if not digits:
        return False
    try:
        value = int(digits)
    except ValueError:
        return False
    return _MIN_SALE_PRICE_EUR <= value <= _MAX_SALE_PRICE_EUR


def _node_is_rent_coded(node: Optional[Node]) -> bool:
    current = node
    for _ in range(_RENT_ANCESTOR_DEPTH):
        if current is None:
            return False
        attrs = current.attributes if current.attributes else {}
        klass = (attrs.get("class") or "").lower()
        if klass:
            for fragment in _RENT_CLASS_FRAGMENTS:
                if fragment in klass:
                    return True
        current = current.parent
    return False


def _candidate_dom_nodes(
    parser: HTMLParser, selectors: Iterable[str]
) -> list[tuple[Node, str]]:
    out: list[tuple[Node, str]] = []
    for selector in selectors:
        try:
            nodes = parser.css(selector)
        except Exception:
            continue
        for node in nodes:
            if _node_is_rent_coded(node):
                continue
            attr_value = (
                node.attributes.get("content")
                or node.attributes.get("data-price")
                or node.attributes.get("data-price-value")
                or node.attributes.get("data-price-amount")
            )
            if attr_value:
                out.append((node, attr_value))
            text = node.text(deep=True, separator=" ", strip=True)
            if text:
                out.append((node, text))
    return out


def _accept_amount(
    candidate: str,
    *,
    guard_text: str = "",
    require_sale_marker: bool = False,
    require_currency_or_label: bool = False,
) -> str:
    """Validate `candidate`, return the canonical digits-only price or empty."""
    if not candidate:
        return ""
    text = str(candidate)
    if _ON_REQUEST.search(text):
        return ""
    if _is_per_m2(text) or _is_per_m2(guard_text):
        return ""
    if _is_rent(text) or _is_rent(guard_text):
        return ""
    if require_sale_marker and not _has_sale_marker(guard_text):
        return ""
    if require_currency_or_label:
        # Either the candidate itself or the surrounding window must
        # contain a currency token or an explicit price label. This
        # prevents a bare 4-digit reference id inside a `.price`-shaped
        # node from leaking into the price field.
        if not (
            _has_currency_or_label(text)
            or _has_currency_or_label(guard_text)
        ):
            return ""
    digits = clean_price(text)
    if not digits or not _passes_sale_range(digits):
        return ""
    # A small bare integer (<= 4 digits) with no currency or label
    # signal anywhere is more often a reference than a price.
    if (
        len(digits) <= _SMALL_VALUE_DIGITS
        and not _has_currency_or_label(text)
        and not _has_currency_or_label(guard_text)
    ):
        return ""
    return digits


def _node_window(node: Node) -> str:
    parent = node.parent
    if parent is None:
        return ""
    try:
        return parent.text(deep=True, separator=" ", strip=True) or ""
    except Exception:
        return ""


class PriceResolver:
    name = "price"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        # 1. JSON-LD
        ld_price = ctx.json_ld.get("price") if ctx.json_ld else None
        if ld_price:
            cleaned = clean_price(str(ld_price))
            if cleaned and _passes_sale_range(cleaned):
                return ResolverResult(cleaned, 0.95, "json_ld")

        if not ctx.html:
            return ResolverResult("", 0.0, "")

        try:
            parser = HTMLParser(ctx.html)
        except Exception:
            return ResolverResult("", 0.0, "")

        # 2 & 3. DOM selectors. We require a currency token or an
        # explicit "prix" label in the candidate or its parent text,
        # so a `.price`-classed wrapper carrying only a reference id
        # cannot leak.
        for node, candidate in _candidate_dom_nodes(parser, _DOM_SELECTORS):
            cleaned = _accept_amount(
                candidate,
                guard_text=_node_window(node),
                require_currency_or_label=True,
            )
            if cleaned:
                return ResolverResult(cleaned, 0.85, "dom")

        # 4. Labelled text. The label *is* the sale marker.
        for candidate in find_priced_labels(ctx.text):
            cleaned = _accept_amount(candidate, guard_text=candidate)
            if cleaned:
                return ResolverResult(cleaned, 0.7, "label")

        # 5. Trailing euro amounts. The EUR sign is the currency token
        # and we additionally require an explicit sale marker in the
        # local window.
        text = ctx.text or ""
        for match in _EURO_AMOUNT.finditer(text):
            window = _around(text, match.span())
            cleaned = _accept_amount(
                match.group(1) + " €",
                guard_text=window,
                require_sale_marker=True,
            )
            if cleaned:
                return ResolverResult(cleaned, 0.55, "euro")

        return ResolverResult("", 0.0, "")
