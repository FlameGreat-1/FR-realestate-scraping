"""Email resolver.

We trust `mailto:` anchors first, then a strict regex sweep on the raw
HTML excluding asset filenames (`.jpg`, `x320`, etc.) and obvious
placeholders.
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_BAD_FRAGMENTS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    "x320", "x640", "x1024", "sentry", "example.com",
)


def _is_acceptable(email: str) -> bool:
    lowered = email.lower()
    if any(fragment in lowered for fragment in _BAD_FRAGMENTS):
        return False
    if lowered.startswith("noreply@") or lowered.startswith("no-reply@"):
        return False
    return True


def _from_mailto(parser: HTMLParser) -> str:
    try:
        nodes = parser.css("a[href^='mailto:']")
    except Exception:
        return ""
    for node in nodes:
        href = node.attributes.get("href", "") or ""
        if ":" not in href:
            continue
        value = href.split(":", 1)[1].split("?", 1)[0].strip()
        if value and _is_acceptable(value):
            return value
    return ""


class EmailResolver:
    name = "email"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        if ctx.html:
            try:
                parser = HTMLParser(ctx.html)
            except Exception:
                parser = None
            if parser is not None:
                value = _from_mailto(parser)
                if value:
                    return ResolverResult(value, 0.95, "mailto")

            for match in _EMAIL.finditer(ctx.html):
                candidate = match.group(0)
                if _is_acceptable(candidate):
                    return ResolverResult(candidate, 0.7, "regex")

        return ResolverResult("", 0.0, "")
