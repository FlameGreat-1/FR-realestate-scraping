"""DPE / energy-class resolver.

French DPE labels are letters A-G. We only accept *labelled*
appearances to avoid catching standalone single letters in unrelated
text.

Sources, in order of confidence:
    1. JSON-LD `dpe` (already normalised by `utils.json_ld`).
    2. Inline `data-dpe` / `data-classe-energie` attributes.
    3. CSS-class-encoded badges (`<span class="dpe dpe-c">`,
       `<div class="etiquette-energie classe-d">`).
    4. Image `alt` attributes carrying the rating in human text.
    5. Labelled inline text (DPE, Diagnostic, Classe energie,
       Etiquette energie, Consommation, DPE collectif, ...).

Numeric `kWh/m².an` thresholds are intentionally not converted to
class letters - the regulatory mapping depends on climate zone, so
doing it here risks silently mis-labelling listings.
"""
from __future__ import annotations

import re
from typing import Optional

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult
from ..utils.text import normalize_for_match

_LABELLED = (
    re.compile(
        r"\bdpe(?:\s+collectif)?\b\s*[:\-]?\s*(?:classe\s*)?([A-G])\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdiagnostic(?:\s+de\s+performance)?(?:\s+energetique)?\b\s*"
        r"[:\-]?\s*(?:classe\s*)?([A-G])\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:classe(?:ment)?|etiquette)"
        r"(?:\s+energie|\s+energetique)?\b\s*[:\-]?\s*([A-G])\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bconsommation(?:\s+energetique)?\b\s*[:\-]?\s*([A-G])\b",
        re.IGNORECASE,
    ),
)

_DATA_ATTR_NAMES = (
    "data-dpe",
    "data-classe-energie",
    "data-classe-dpe",
    "data-energy-class",
    "data-energie",
)

_IMG_ALT_PATTERN = re.compile(
    r"(?:dpe|etiquette\s+energie|classe\s+energie)[\s\-:]*(?:lettre\s+)?([A-G])\b",
    re.IGNORECASE,
)

# Class-name-encoded DPE badges. Matches:
#   class="dpe dpe-c"
#   class="etiquette-energie classe-d"
#   class="energy-class-e"
#   class="dpe-letter-a"
_CLASS_ENCODED = re.compile(
    r"(?:^|[\s\-_])(?:dpe|classe|class|letter|lettre|energy)"
    r"[\s\-_]?([A-G])(?:[\s\-_]|$)",
    re.IGNORECASE,
)
# Selector to narrow class search to plausibly-DPE-related elements.
_CLASS_SCOPE_SELECTOR = (
    "[class*='dpe' i], [class*='energie' i], [class*='energy' i], "
    "[class*='etiquette' i]"
)

_LETTER_RE = re.compile(r"^[A-G]$")


def _clean_letter(value: Optional[str]) -> str:
    if not value:
        return ""
    candidate = value.strip().upper()
    return candidate if _LETTER_RE.match(candidate) else ""


def _from_data_attributes(parser: HTMLParser) -> str:
    selector = ", ".join(f"[{name}]" for name in _DATA_ATTR_NAMES)
    try:
        nodes = parser.css(selector)
    except Exception:
        return ""
    for node in nodes:
        for attr_name in _DATA_ATTR_NAMES:
            value = node.attributes.get(attr_name)
            cleaned = _clean_letter(value)
            if cleaned:
                return cleaned
    return ""


def _from_class_encoded(parser: HTMLParser) -> str:
    """Pull the DPE letter out of CSS class names on badge elements."""
    try:
        nodes = parser.css(_CLASS_SCOPE_SELECTOR)
    except Exception:
        return ""
    for node in nodes:
        klass = (node.attributes.get("class") or "").strip()
        if not klass:
            continue
        match = _CLASS_ENCODED.search(klass)
        if not match:
            continue
        cleaned = _clean_letter(match.group(1))
        if cleaned:
            return cleaned
    return ""


def _from_badge_text(parser: HTMLParser) -> str:
    """Read the visible letter content of DPE-scoped badge elements.

    Many CMSes render DPE as `<div class="dpe-badge">B</div>` where
    the class name marks the element as DPE-related but does not
    itself encode the letter. The element text is exactly the
    rating letter. The selector scope is the same DPE-only one used
    by the class-encoded path, so we cannot pick up unrelated body
    letters elsewhere on the page.
    """
    try:
        nodes = parser.css(_CLASS_SCOPE_SELECTOR)
    except Exception:
        return ""
    for node in nodes:
        text = (
            node.text(deep=False, separator=" ", strip=True) or ""
        ).strip()
        if not text:
            # Some templates wrap the letter in a single child element
            # (`<div class="dpe-badge"><span>B</span></div>`); in that
            # case `deep=False` returns empty. Fall back to the deep
            # text but require it to still be a single letter.
            text = (
                node.text(deep=True, separator=" ", strip=True) or ""
            ).strip()
        if not text:
            continue
        # Must be exactly a single A-G letter, ignoring trailing
        # punctuation. Anything else is a richer label that the
        # labelled-text path already handles.
        if len(text) > 3:
            continue
        cleaned = _clean_letter(text.strip(".:- "))
        if cleaned:
            return cleaned
    return ""


def _from_image_alts(parser: HTMLParser) -> str:
    try:
        nodes = parser.css("img[alt]")
    except Exception:
        return ""
    for node in nodes:
        alt = node.attributes.get("alt") or ""
        if not alt:
            continue
        match = _IMG_ALT_PATTERN.search(alt)
        if match:
            cleaned = _clean_letter(match.group(1))
            if cleaned:
                return cleaned
    return ""


class DpeResolver:
    name = "dpe_rating"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_dpe = ctx.json_ld.get("dpe") if ctx.json_ld else None
        if isinstance(ld_dpe, str):
            match = re.search(r"\b([A-G])\b", ld_dpe, re.IGNORECASE)
            if match:
                cleaned = _clean_letter(match.group(1))
                if cleaned:
                    return ResolverResult(cleaned, 0.95, "json_ld")

        parser: Optional[HTMLParser] = None
        if ctx.html:
            try:
                parser = HTMLParser(ctx.html)
            except Exception:
                parser = None
            if parser is not None:
                value = _from_data_attributes(parser)
                if value:
                    return ResolverResult(value, 0.9, "data_attr")
                value = _from_class_encoded(parser)
                if value:
                    return ResolverResult(value, 0.85, "class_encoded")
                value = _from_badge_text(parser)
                if value:
                    return ResolverResult(value, 0.82, "badge_text")
                value = _from_image_alts(parser)
                if value:
                    return ResolverResult(value, 0.8, "img_alt")

        if not ctx.text:
            return ResolverResult("", 0.0, "")
        normalised = normalize_for_match(ctx.text)
        for pattern in _LABELLED:
            match = pattern.search(normalised)
            if match:
                cleaned = _clean_letter(match.group(1))
                if cleaned:
                    return ResolverResult(cleaned, 0.75, "label")

        return ResolverResult("", 0.0, "")
