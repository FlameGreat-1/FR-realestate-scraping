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

# A French residential sale price never exceeds 9 digits (i.e. <= 999
# 999 999 EUR). Any "price" longer than this is the result of
# concatenating adjacent numeric runs (multiple amounts on one line, a
# phone number rendered next to an amount, a year list, etc.).
_MAX_PRICE_DIGITS = 9

# Detect digit fragments inside a raw match. We only declare a capture
# "concatenated" when the cleaned digit string is also long.
_DIGIT_RUN = re.compile(r"\d+")
_CONCAT_LENGTH_THRESHOLD = 7


def collapse_whitespace(value: str) -> str:
    return _WHITESPACE.sub(" ", value or "").strip()


def strip_accents(value: str) -> str:
    if not value:
        return ""
    nfkd = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def digits_only(value: str) -> str:
    return _DIGITS_ONLY.sub("", value or "")


def _looks_concatenated(raw: str, digits: str) -> bool:
    """True when `raw` clearly stitches together more than one amount.

    Heuristic: a legitimate price has at most one numeric run separated
    only by thousand separators. "1 250 000" reads as three runs but
    each is exactly three digits and the total is consistent with a
    single value. Multi-run captures whose runs don't follow the
    thousand-separator rhythm, AND whose total digit count exceeds the
    concat threshold, are concatenations.
    """
    runs = _DIGIT_RUN.findall(raw or "")
    if len(runs) <= 1:
        return False
    if len(digits) <= _CONCAT_LENGTH_THRESHOLD:
        return False
    # Allow `<1-3>(<3>)+` rhythm: 1-3 digits, then any number of 3-digit
    # groups. That's the European thousands-separator format.
    if 1 <= len(runs[0]) <= 3 and all(len(r) == 3 for r in runs[1:]):
        return False
    return True


def clean_price(raw: str) -> str:
    """Extract the first monetary amount from a raw price string.

    Returns the canonical digits-only price (no currency, no
    separators). Empty string when no usable amount is found, when
    the captured value clearly stitches multiple amounts together,
    or when the digit count exceeds the realistic ceiling for a
    French residential sale price.
    """
    if not raw:
        return ""
    match = _PRICE_NUMBER.search(str(raw))
    if not match:
        return ""
    captured = match.group(0)
    digits = digits_only(captured)
    if not digits or digits in {"0", "00", "000"}:
        return ""
    if len(digits) > _MAX_PRICE_DIGITS:
        return ""
    if _looks_concatenated(captured, digits):
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
