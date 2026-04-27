"""Discover candidate listing URLs without per-domain hardcoded seeds.

Strategy:
    1. Sitemap traversal (handled by `sitemap.py`).
    2. Homepage link harvesting: every `<a href>` on the homepage that
       points to the same registrable domain is a seed candidate.

The `listing_filter` module decides which seeds look like real listing
links; this module is purely about *discovery*.
"""
from __future__ import annotations

import logging
from typing import Iterable

from selectolax.parser import HTMLParser

from .http_client import HttpFetcher
from .utils.url import (
    canonicalize,
    join_url,
    same_registrable_domain,
)

log = logging.getLogger(__name__)


def _extract_anchor_hrefs(html: str) -> list[str]:
    if not html:
        return []
    try:
        parser = HTMLParser(html)
    except Exception:
        return []
    out: list[str] = []
    for node in parser.css("a[href]"):
        href = node.attributes.get("href")
        if href:
            out.append(href.strip())
    return out


def _dedup(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        key = canonicalize(url)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


async def harvest_homepage_links(
    base_url: str,
    fetcher: HttpFetcher,
) -> tuple[str, list[str]]:
    """Fetch the homepage and return (html, same-host link list)."""
    if not base_url:
        return "", []
    outcome = await fetcher.fetch(base_url)
    if not outcome.ok or not outcome.is_html_like or not outcome.text:
        return "", []
    html = outcome.text
    anchored = _extract_anchor_hrefs(html)
    same_host: list[str] = []
    for href in anchored:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = join_url(outcome.final_url or base_url, href)
        if not absolute.startswith(("http://", "https://")):
            continue
        if not same_registrable_domain(absolute, base_url):
            continue
        same_host.append(absolute)
    return html, _dedup(same_host)
