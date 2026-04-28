"""Coordinates resolver (latitude, longitude as `lat, lng`).

We pull from a layered set of in-page signals, in decreasing order of
trust. Geocoding (network call) is reserved for the orchestrator,
invoked only when this resolver returned nothing.

Signals checked, top to bottom:
    1. JSON-LD `geo`.
    2. OpenGraph / place / geo `<meta>` tags.
    3. `data-lat*` / `data-lng*` / `data-latitude` / `data-longitude`
       attributes on any element. Stable across CMS template churn.
    4. Leaflet conventions: `L.marker([lat, lng])`, `L.latLng(lat, lng)`,
       `map.setView([lat, lng], zoom)`.
    5. Mapbox conventions: `center: [lng, lat]` (note: longitude first).
    6. Generic inline `lat=...`, `latitude=...` keys.
    7. Google Maps iframe `src` queries.

Every candidate goes through `_format_pair` which validates the
numeric range, so junk strings (template placeholders, swapped axes
that would land outside Earth) cannot reach the output CSV.
"""
from __future__ import annotations

import re
from typing import Optional

from selectolax.parser import HTMLParser

from ..models import PageContext, ResolverResult

_FLOAT = r"[+-]?\d{1,3}(?:\.\d+)?"

_LAT_KEY = re.compile(
    rf"(?:\"|\b)(?:lat|latitude)(?:\"|\b)\s*[:=]\s*({_FLOAT})",
    re.IGNORECASE,
)
_LNG_KEY = re.compile(
    rf"(?:\"|\b)(?:lng|lon|long|longitude)(?:\"|\b)\s*[:=]\s*({_FLOAT})",
    re.IGNORECASE,
)
_LEAFLET_MARKER = re.compile(
    rf"L\.(?:marker|latLng)\(\s*\[?\s*({_FLOAT})\s*,\s*({_FLOAT})\s*\]?",
)
_LEAFLET_SETVIEW = re.compile(
    rf"setView\(\s*\[\s*({_FLOAT})\s*,\s*({_FLOAT})\s*\]",
)
_MAPBOX_CENTER = re.compile(
    rf"center\s*:\s*\[\s*({_FLOAT})\s*,\s*({_FLOAT})\s*\]",
)
_LL_QUERY = re.compile(rf"[?&]ll=({_FLOAT}),({_FLOAT})")
_Q_QUERY = re.compile(rf"[?&]q=({_FLOAT}),({_FLOAT})")
_AT_PATTERN = re.compile(rf"/@({_FLOAT}),({_FLOAT})")

_DATA_LNG_ATTRS = (
    "data-lng", "data-lon", "data-long", "data-longitude",
)
_DATA_LAT_ATTRS = (
    "data-lat", "data-latitude",
)

_META_LAT = (
    "meta[property='og:latitude']",
    "meta[property='place:location:latitude']",
    "meta[name='geo.position']",
)
_META_LNG = (
    "meta[property='og:longitude']",
    "meta[property='place:location:longitude']",
)


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _format_pair(lat: Optional[str], lng: Optional[str]) -> str:
    """Validate and format a (lat, lng) pair, return empty if invalid."""
    lat_f = _to_float(lat)
    lng_f = _to_float(lng)
    if lat_f is None or lng_f is None:
        return ""
    # Reject pairs that would not be valid Earth coordinates - including
    # the (0, 0) sentinel that templates often default to.
    if not (-90.0 <= lat_f <= 90.0):
        return ""
    if not (-180.0 <= lng_f <= 180.0):
        return ""
    if lat_f == 0.0 and lng_f == 0.0:
        return ""
    return f"{lat_f}, {lng_f}"


def _from_meta(parser: HTMLParser) -> str:
    lat = lng = ""
    for selector in _META_LAT:
        try:
            node = parser.css_first(selector)
        except Exception:
            continue
        if node:
            content = (node.attributes.get("content") or "").strip()
            if not content:
                continue
            if selector.endswith("geo.position']"):
                # geo.position is `lat;lng` (or `lat,lng`).
                parts = re.split(r"[;,]", content, maxsplit=1)
                if len(parts) == 2:
                    return _format_pair(parts[0], parts[1])
                continue
            lat = content
            break
    for selector in _META_LNG:
        try:
            node = parser.css_first(selector)
        except Exception:
            continue
        if node:
            content = (node.attributes.get("content") or "").strip()
            if content:
                lng = content
                break
    return _format_pair(lat, lng)


def _from_data_attributes(parser: HTMLParser) -> str:
    """Find an element that carries both a lat and a lng data attribute."""
    try:
        candidates = parser.css(
            ", ".join(f"[{name}]" for name in _DATA_LAT_ATTRS)
        )
    except Exception:
        return ""
    for node in candidates:
        attrs = node.attributes
        lat = next(
            (attrs.get(name) for name in _DATA_LAT_ATTRS if attrs.get(name)),
            None,
        )
        lng = next(
            (attrs.get(name) for name in _DATA_LNG_ATTRS if attrs.get(name)),
            None,
        )
        result = _format_pair(lat, lng)
        if result:
            return result
    return ""


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
                result = _format_pair(match.group(1), match.group(2))
                if result:
                    return result
    return ""


def _from_inline_js(html: str) -> str:
    # Mapbox first: it uses [lng, lat] (longitude first), so a generic
    # `lat=`/`lng=` sweep would silently produce a swapped pair if a
    # page ships both notations.
    match = _MAPBOX_CENTER.search(html)
    if match:
        result = _format_pair(match.group(2), match.group(1))
        if result:
            return result
    for pattern in (_LEAFLET_MARKER, _LEAFLET_SETVIEW):
        match = pattern.search(html)
        if match:
            result = _format_pair(match.group(1), match.group(2))
            if result:
                return result
    lat_match = _LAT_KEY.search(html)
    lng_match = _LNG_KEY.search(html)
    if lat_match and lng_match:
        return _format_pair(lat_match.group(1), lng_match.group(1))
    return ""


class CoordinatesResolver:
    name = "coordinates"

    def resolve(self, ctx: PageContext) -> ResolverResult:
        ld_coords = ctx.json_ld.get("coordinates") if ctx.json_ld else ""
        if isinstance(ld_coords, str) and ld_coords.strip():
            # JSON-LD already passed through _harvest_address; still
            # validate so a malformed feed cannot leak garbage.
            parts = re.split(r"[,\s]+", ld_coords.strip(), maxsplit=1)
            if len(parts) == 2:
                formatted = _format_pair(parts[0], parts[1])
                if formatted:
                    return ResolverResult(formatted, 0.95, "json_ld")

        if not ctx.html:
            return ResolverResult("", 0.0, "")

        try:
            parser = HTMLParser(ctx.html)
        except Exception:
            parser = None

        if parser is not None:
            value = _from_meta(parser)
            if value:
                return ResolverResult(value, 0.85, "meta")

            value = _from_data_attributes(parser)
            if value:
                return ResolverResult(value, 0.85, "data_attr")

        value = _from_inline_js(ctx.html)
        if value:
            return ResolverResult(value, 0.75, "inline_js")

        if parser is not None:
            value = _from_iframes(parser)
            if value:
                return ResolverResult(value, 0.7, "iframe")

        return ResolverResult("", 0.0, "")
