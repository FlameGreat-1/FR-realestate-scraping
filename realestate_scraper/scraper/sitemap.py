"""Sitemap discovery and traversal.

We try the standard locations (`/sitemap.xml`, `/sitemap_index.xml`,
`/robots.txt` Sitemap directives) on both `https://host` and
`https://www.host`, then walk one level of sitemap-index children that
look listing-relevant. Depth is bounded by configuration.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from .http_client import HttpFetcher
from .utils.url import both_www_variants, canonicalize, ensure_scheme

log = logging.getLogger(__name__)

_LISTING_HINTS = re.compile(
    r"(annonce|annonces|vente|location|bien|biens|property|properties|"
    r"listing|listings|maison|appartement|achat|propriete|immobilier)",
    re.IGNORECASE,
)
_SITEMAP_DIRECTIVE = re.compile(r"^\s*sitemap\s*:\s*(\S+)", re.IGNORECASE | re.MULTILINE)


def _candidate_sitemap_urls(base_url: str) -> list[str]:
    base = ensure_scheme(base_url)
    if not base:
        return []
    www, bare = both_www_variants(base)
    seeds = {www, bare}
    paths = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml")
    out: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        for path in paths:
            url = urljoin(seed, path)
            key = canonicalize(url)
            if key not in seen:
                seen.add(key)
                out.append(url)
    return out


def _looks_like_sitemap(text: str) -> bool:
    if not text:
        return False
    head = text[:4096].lower()
    return "<urlset" in head or "<sitemapindex" in head or "<loc>" in head


def _extract_locs(xml_text: str) -> list[str]:
    if not xml_text:
        return []
    try:
        parser = HTMLParser(xml_text)
    except Exception:
        return []
    out: list[str] = []
    for node in parser.css("loc"):
        value = node.text(deep=True, separator="", strip=True)
        if value:
            out.append(value.strip())
    return out


def _is_index_xml(xml_text: str) -> bool:
    head = (xml_text or "")[:4096].lower()
    return "<sitemapindex" in head


def _rank_index_children(urls: Iterable[str]) -> list[str]:
    """Prioritise child sitemaps that look listing-related."""
    scored: list[tuple[int, str]] = []
    for url in urls:
        score = 1 if _LISTING_HINTS.search(url) else 0
        scored.append((score, url))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    return [url for _, url in scored]


async def _read_robots_sitemaps(
    base_url: str, fetcher: HttpFetcher
) -> list[str]:
    candidates: list[str] = []
    for variant in both_www_variants(ensure_scheme(base_url)):
        outcome = await fetcher.fetch(
            urljoin(variant, "/robots.txt"),
            timeout=fetcher.probe_timeout,
        )
        if outcome.ok and outcome.text:
            for match in _SITEMAP_DIRECTIVE.finditer(outcome.text):
                candidates.append(match.group(1).strip())
    seen: set[str] = set()
    out: list[str] = []
    for url in candidates:
        key = canonicalize(url)
        if key and key not in seen:
            seen.add(key)
            out.append(url)
    return out


async def discover_sitemap_urls(
    base_url: str,
    fetcher: HttpFetcher,
    *,
    max_depth: int,
) -> list[str]:
    """Return all `<loc>` entries discovered for `base_url`.

    Walks at most `max_depth` levels of sitemap indexes.
    """
    if not base_url:
        return []

    visited: set[str] = set()
    found: list[str] = []

    seeds = _candidate_sitemap_urls(base_url)
    seeds.extend(await _read_robots_sitemaps(base_url, fetcher))

    queue: list[tuple[str, int]] = [(url, 0) for url in seeds]

    while queue:
        url, depth = queue.pop(0)
        key = canonicalize(url)
        if not key or key in visited:
            continue
        visited.add(key)

        outcome = await fetcher.fetch(url)
        if not outcome.ok or not _looks_like_sitemap(outcome.text):
            continue

        if _is_index_xml(outcome.text):
            children = _rank_index_children(_extract_locs(outcome.text))
            if depth + 1 < max_depth:
                queue.extend((child, depth + 1) for child in children)
            continue

        for loc in _extract_locs(outcome.text):
            found.append(loc)

    log.debug("sitemap discovery for %s: %d urls", base_url, len(found))
    return found
