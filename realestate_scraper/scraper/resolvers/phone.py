"""Phone-number resolver.

French numbers normalise to the 10-digit `0X XX XX XX XX` form. We
return the digits-only `0XXXXXXXXX` (no separators) so downstream
systems can format consistently.

Order of confidence:
    1. JSON-LD `telephone`/`phone`/`phoneNumber`.
    2. `tel:` anchor href.
    3. Visible labelled phone text near `Tél.` / `phone`.
    4. Free regex sweep over the page text.
    5. Agency-CSV fallback (rows_merged metadata).
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult
from ..utils.text import digits_only

_FRENCH_FREE = re.compile(
    r"((?:0|\+33|0033)[\s.\-]?[1-9](?:[\s.\-]?\d{2}){4})"
)
_LABEL_BEFORE = re.compile(
    r"(?:t[ée]l(?:[ée]phone)?|phone|portable|mobile)\s*[:\-]?\s*"
    r"((?:\+|00)?[\d][\d\s().\-]{7,})",
    re.IGNORECASE,
)
_LABEL_AFTER = re.compile(
    r"((?:\+|00)?[\d][\d\s().\-]{7,})\s*(?:t[ée]l(?:[ée]phone)?|phone)",
    re.IGNORECASE,
)


def _normalise(raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip()
    digits = digits_only(text)
    if not digits:
        return ""
    if text.startswith("+33"):
        local = digits[2:] if digits.startswith("33") else digits
        return f"0{local}" if len(local) == 9 else digits
    if text.startswith("0033") or digits.startswith("0033"):
        local = digits[4:]
        return f"0{local}" if len(local) == 9 else digits
    if digits.startswith("33") and len(digits) == 11:
        return f"0{digits[2:]}"
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) < 8:
        return ""
    if len(digits) == 9 and not digits.startswith("0"):
        return f"0{digits}"
    return digits


def _from_tel_links(parser: HTMLParser) -> str:
    try:
        nodes = parser.css("a[href^='tel:']")
    except Exception:
        return ""
    for node in nodes:
        href = node.attributes.get("href", "") or ""
        if ":" in href:
            value = _normalise(href.split(":", 1)[1])
            if value:
                return value
    return ""


class PhoneResolver:
    name = "phone_number"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_phone = ctx.json_ld.get("phone") if ctx.json_ld else None
        if isinstance(ld_phone, str):
            value = _normalise(ld_phone)
            if value:
                return ResolverResult(value, 0.95, "json_ld")

        if ctx.html:
            try:
                parser = HTMLParser(ctx.html)
            except Exception:
                parser = None
            if parser is not None:
                value = _from_tel_links(parser)
                if value:
                    return ResolverResult(value, 0.9, "tel_link")

        for pattern in (_LABEL_BEFORE, _LABEL_AFTER):
            match = pattern.search(ctx.text or "")
            if match:
                value = _normalise(match.group(1))
                if value:
                    return ResolverResult(value, 0.75, "label")

        match = _FRENCH_FREE.search(ctx.text or "")
        if match:
            value = _normalise(match.group(1))
            if value:
                return ResolverResult(value, 0.55, "text_sweep")

        if ctx.domain_job and ctx.domain_job.phone:
            value = _normalise(ctx.domain_job.phone)
            if value:
                return ResolverResult(value, 0.3, "agency_csv")

        return ResolverResult("", 0.0, "")
