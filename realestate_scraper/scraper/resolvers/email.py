"""Email resolver.

Order of confidence:
    1. Cloudflare-protected `data-cfemail` / `.__cf_email__` payloads.
    2. `mailto:` anchors (HTML-entity decoded).
    3. Human-readable obfuscation (`name [at] domain [dot] tld`).
    4. Plaintext regex sweep on the raw HTML.

We never accept asset filenames, `noreply@`, or known placeholders;
the `_is_acceptable` filter is the single point of truth for that.

Robustness:
    Every regex sweep runs against a SIZE-CAPPED slice of the source
    text/HTML. Even a perfectly engineered regex should not run
    unbounded over arbitrary network input - the caps are the
    defence-in-depth backstop against any future pathological input.
    The obfuscated-email pattern is also engineered with
    word-boundary anchors and bounded character-class quantifiers
    so it cannot catastrophically backtrack on long French body
    text containing words like `attribute`, `attestation`,
    `attendre`, `dotation`, etc.
"""
from __future__ import annotations

import html
import re

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult

# Hard caps on regex input size. Real contact information lives in
# contact / agent blocks near the top of the page; scanning MBs of
# below-the-fold text is wasted work and a backtracking risk.
_MAX_OBFUSCATED_TEXT_BYTES = 32_000
_MAX_PLAINTEXT_HTML_BYTES = 256_000

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,253}\.[A-Za-z]{2,24}")
_BAD_FRAGMENTS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    "x320", "x640", "x1024", "sentry", "example.com",
)

# `name [at] domain [dot] tld` - both markers required, BOTH literals
# anchored with `\b` on both sides so they only match standalone
# tokens (never substrings inside `attribute`, `attestation`,
# `attendre`, `dotation`, etc.). Local-part and domain bounded to
# RFC 5321 maxima so the engine cannot backtrack across thousands of
# possible lengths on each false start.
_OBFUSCATED = re.compile(
    r"([A-Za-z0-9._%+\-]{1,64})\s*[\[\(]\s*\bat\b\s*[\]\)]\s*"
    r"([A-Za-z0-9.\-]{1,64})\s*[\[\(]\s*\bdot\b\s*[\]\)]\s*"
    r"([A-Za-z]{2,8})",
    re.IGNORECASE,
)

_CF_HEX = re.compile(r"^[0-9a-fA-F]+$")


def _is_acceptable(email: str) -> bool:
    lowered = email.lower()
    if any(fragment in lowered for fragment in _BAD_FRAGMENTS):
        return False
    if lowered.startswith("noreply@") or lowered.startswith("no-reply@"):
        return False
    return True


def _decode_cfemail(hex_payload: str) -> str:
    """Decode Cloudflare's `data-cfemail` hex payload.

    Algorithm: the first byte is the XOR key, the remaining bytes are
    the address XORed with that key. Returns an empty string on any
    structural error - we never raise.
    """
    if not hex_payload or len(hex_payload) < 4 or len(hex_payload) % 2:
        return ""
    if not _CF_HEX.match(hex_payload):
        return ""
    try:
        data = bytes.fromhex(hex_payload)
    except ValueError:
        return ""
    key = data[0]
    decoded = bytes(b ^ key for b in data[1:])
    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _from_cloudflare(parser: HTMLParser) -> str:
    try:
        nodes = parser.css("[data-cfemail]")
    except Exception:
        nodes = []
    for node in nodes:
        payload = (node.attributes.get("data-cfemail") or "").strip()
        decoded = _decode_cfemail(payload)
        if decoded and _is_acceptable(decoded):
            return decoded

    try:
        anchors = parser.css("a[href*='/cdn-cgi/l/email-protection']")
    except Exception:
        anchors = []
    for anchor in anchors:
        href = anchor.attributes.get("href") or ""
        if "#" not in href:
            continue
        payload = href.rsplit("#", 1)[1].strip()
        decoded = _decode_cfemail(payload)
        if decoded and _is_acceptable(decoded):
            return decoded
    return ""


def _from_mailto(parser: HTMLParser) -> str:
    try:
        nodes = parser.css("a[href^='mailto:']")
    except Exception:
        return ""
    for node in nodes:
        href = node.attributes.get("href", "") or ""
        if ":" not in href:
            continue
        href = html.unescape(href)
        value = href.split(":", 1)[1].split("?", 1)[0].strip()
        if value and _is_acceptable(value):
            return value
    return ""


def _from_obfuscated(text: str) -> str:
    if not text:
        return ""
    # Hard input cap: real contact info lives near the top of the
    # page, never thousands of bytes deep into body text. The cap is
    # also a backstop against any pathological future input.
    capped = text[:_MAX_OBFUSCATED_TEXT_BYTES]
    for match in _OBFUSCATED.finditer(capped):
        local, domain, tld = match.group(1), match.group(2), match.group(3)
        candidate = f"{local}@{domain}.{tld}".lower()
        if _is_acceptable(candidate):
            return candidate
    return ""


class EmailResolver:
    name = "email"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        if not ctx.html:
            return ResolverResult("", 0.0, "")

        try:
            parser = HTMLParser(ctx.html)
        except Exception:
            parser = None

        if parser is not None:
            value = _from_cloudflare(parser)
            if value:
                return ResolverResult(value, 0.95, "cf_email")

            value = _from_mailto(parser)
            if value:
                return ResolverResult(value, 0.9, "mailto")

        for source in (ctx.text, ctx.html):
            value = _from_obfuscated(source)
            if value:
                return ResolverResult(value, 0.7, "obfuscated")

        # Plaintext sweep, also size-capped.
        for match in _EMAIL.finditer(ctx.html[:_MAX_PLAINTEXT_HTML_BYTES]):
            candidate = match.group(0)
            if _is_acceptable(candidate):
                return ResolverResult(candidate, 0.6, "regex")

        return ResolverResult("", 0.0, "")
