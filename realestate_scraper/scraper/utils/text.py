"""Pure text/regex helpers shared by all resolvers."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_WHITESPACE = re.compile(r"\s+")
_DIGITS_ONLY = re.compile(r"\D+")
_PRICE_NUMBER = re.compile(r"\d[\d\s\xa0.,]*")
_EURO_AMOUNT = re.compile(r"([0-9][0-9\s\xa0.,]*)\s*€")
_PRICE_LABEL = re.compile(
    r"(?:prix(?:\s+de\s+vente)?|price)\s*[:\-]?\s*([^\n\r<]{2,60})",
    re.IGNORECASE,
)


def collapse_whitespace(value: str) -> str:
    return _WHITESPACE.sub(" ", value or "").strip()


def strip_accents(value: str) -> str:
    if not value:
        return ""
    nfkd = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def digits_only(value: str) -> str:
    return _DIGITS_ONLY.sub("", value or "")


def clean_price(raw: str) -> str:
    """Extract the first monetary amount from a raw price string.

    Returns the canonical digits-only price (no currency, no separators).
    Empty string when no usable amount is found.
    """
    if not raw:
        return ""
    match = _PRICE_NUMBER.search(str(raw))
    if not match:
        return ""
    digits = digits_only(match.group(0))
    if not digits:
        return ""
    if digits in {"0", "00", "000"}:
        return ""
    return digits


def find_euro_amounts(text: str) -> list[str]:
    return [m.group(1) for m in _EURO_AMOUNT.finditer(text or "")]


def find_priced_labels(text: str) -> list[str]:
    return [m.group(1) for m in _PRICE_LABEL.finditer(text or "")]


def any_in(text: str, needles: Iterable[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def normalize_for_match(value: str) -> str:
    """Lower-cased, accent-stripped, whitespace-collapsed text for matching."""
    return collapse_whitespace(strip_accents(value or "")).lower()
