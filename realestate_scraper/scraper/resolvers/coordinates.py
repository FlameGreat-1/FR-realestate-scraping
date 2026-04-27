"""Coordinates resolver (latitude, longitude as `lat, lng`).

We pull from JSON-LD first, then inline JS variables, then Google Maps
embeds. Geocoding (network call) is reserved for the orchestrator,
invoked only when this resolver returned nothing.
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult

_LAT = re.compile(r"(?:lat|latitude)\s*[:=]\s*([+-]?\d+\.\d+)", re.IGNORECASE)
_LNG = re.compile(r"(?:lng|longitude)\s*[:=]\s*([+-]?\d+\.\d+)", re.IGNORECASE)
_LL_QUERY = re.compile(r"[?&]ll=([\d.\-]+),([\d.\-]+)")
_Q_QUERY = re.compile(r"[?&]q=([\d.\-]+),([\d.\-]+)")
_AT_PATTERN = re.compile(r"/@([\d.\-]+),([\d.\-]+)")


def _from_iframes(parser: HTMLParser) -> str:
    try:
        nodes = parser.css("iframe[src]")
    except Exception:
        return ""
    for node in nodes:
        src = node.attributes.get("src", "") or ""
        if "google" not in src and "maps" not in src:
            continue
        for pattern in (_LL_QUERY, _Q_QUERY, _AT_PATTERN):
            match = pattern.search(src)
            if match:
                return f"{match.group(1)}, {match.group(2)}"
    return ""


class CoordinatesResolver:
    name = "coordinates"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_coords = ctx.json_ld.get("coordinates") if ctx.json_ld else ""
        if isinstance(ld_coords, str) and ld_coords.strip():
            return ResolverResult(ld_coords.strip(), 0.95, "json_ld")

        if ctx.html:
            lat = _LAT.search(ctx.html)
            lng = _LNG.search(ctx.html)
            if lat and lng:
                return ResolverResult(
                    f"{lat.group(1)}, {lng.group(1)}", 0.8, "inline_js"
                )
            try:
                parser = HTMLParser(ctx.html)
            except Exception:
                parser = None
            if parser is not None:
                value = _from_iframes(parser)
                if value:
                    return ResolverResult(value, 0.7, "iframe")

        return ResolverResult("", 0.0, "")
