"""Location resolver.

We collect, in order of confidence:
    1. JSON-LD `address` already normalised by `utils.json_ld`.
    2. The French URL pattern `<slug>-<postal_code>` (`...-bordeaux-33000`).
    3. The breadcrumb trail's last meaningful node.
    4. `og:locality` / `place:location:locality` meta tags.
    5. The agency's CSV-provided city/postal code as a last resort.

The output is a free-form string (the brief stores `location` as text).
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult

_URL_LOCATION = re.compile(r"([a-z][a-z0-9-]+)-(\d{5})(?:[,/]|$)", re.IGNORECASE)
_BREADCRUMB_SELECTOR = (
    ".breadcrumb, .breadcrumbs, nav.breadcrumb, ol.breadcrumb, ul.breadcrumb, "
    "[itemtype*='BreadcrumbList'], [class*='breadcrumb' i], [class*='chemin' i]"
)


def _from_breadcrumb(parser: HTMLParser) -> str:
    try:
        nodes = parser.css(_BREADCRUMB_SELECTOR)
    except Exception:
        return ""
    for node in nodes:
        items = node.css("li, a, span")
        candidates = [
            item.text(deep=True, separator=" ", strip=True) for item in items
        ]
        for candidate in reversed(candidates):
            if not candidate:
                continue
            if re.search(r"\d{5}", candidate):
                return candidate.strip()
            if len(candidate) > 3 and candidate.replace(" ", "").isalpha():
                return candidate.strip()
    return ""


def _from_meta(parser: HTMLParser) -> str:
    selectors = (
        "meta[property='og:locality']",
        "meta[property='place:location:locality']",
        "meta[name='geo.placename']",
    )
    for selector in selectors:
        try:
            node = parser.css_first(selector)
        except Exception:
            continue
        if node:
            content = node.attributes.get("content", "")
            if content and content.strip():
                return content.strip()
    return ""


class LocationResolver:
    name = "location"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_loc = ctx.json_ld.get("location") if ctx.json_ld else ""
        if isinstance(ld_loc, str) and ld_loc.strip():
            return ResolverResult(ld_loc.strip(), 0.9, "json_ld")

        match = _URL_LOCATION.search(ctx.url or "")
        if match:
            slug = match.group(1).split("-")[-1]
            postal = match.group(2)
            if slug and postal:
                return ResolverResult(f"{slug.capitalize()} {postal}", 0.7, "url")

        if ctx.html:
            try:
                parser = HTMLParser(ctx.html)
            except Exception:
                parser = None
            if parser is not None:
                value = _from_breadcrumb(parser)
                if value:
                    return ResolverResult(value, 0.65, "breadcrumb")
                value = _from_meta(parser)
                if value:
                    return ResolverResult(value, 0.6, "meta")

        if ctx.domain_job:
            fallback = f"{ctx.domain_job.city} {ctx.domain_job.postalcode}".strip()
            if fallback:
                return ResolverResult(fallback, 0.3, "agency_csv")

        return ResolverResult("", 0.0, "")
