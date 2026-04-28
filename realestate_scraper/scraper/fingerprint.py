"""Cheap site fingerprinting.

The fingerprint runs once per domain at the start of processing. It
combines an HTTP probe and the first ~64KB of homepage HTML to decide:

    * Is the site reachable at all? -> SITE_NOT_REACHABLE / BLOCKED_403.
    * Which family does it belong to? -> selector & URL hints.
    * Does it look like a SPA / Cloudflare-protected page that needs
      Playwright? -> Strategy.DYNAMIC.

Its cost is bounded (one HEAD/GET probe + one homepage GET) so we can
run it for every domain even at 55k scale.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .error_codes import ErrorReason, classify_http_status
from .families import Family, get_registry
from .families.base import FamilySignals
from .http_client import HttpFetcher
from .models import Strategy
from .utils.url import parse_host

log = logging.getLogger(__name__)

_HEAD_BYTES = 65_536

# Strong markers: presence of any one is enough to require Playwright.
_STRONG_DYNAMIC_MARKERS = (
    re.compile(r"window\.__NUXT__", re.IGNORECASE),
    re.compile(r"window\.__NEXT_DATA__", re.IGNORECASE),
    re.compile(r"id=\"__next\"", re.IGNORECASE),
    re.compile(r"data-react-helmet", re.IGNORECASE),
    re.compile(r"ng-app=", re.IGNORECASE),
    re.compile(r"cf-browser-verification|challenge-platform", re.IGNORECASE),
)

# Weak markers: only count when the page has no structural anchor.
# An empty <body><div id="app"></div></body> shell is dynamic; the
# same div on a page that also has <main> or <article> is just a JS
# carousel widget on an otherwise-static site.
_WEAK_DYNAMIC_MARKERS = (
    re.compile(r"<noscript[^>]*>\s*(?:you|enable javascript)", re.IGNORECASE),
    re.compile(r"id=\"app\"[^>]*></div>", re.IGNORECASE),
)

_BODY_PRESENCE = re.compile(r"<body[^>]*>(.{200,})</body>", re.IGNORECASE | re.DOTALL)
_STRUCTURAL_ANCHOR = re.compile(
    r"<(?:main|article|section)\b", re.IGNORECASE,
)


@dataclass(slots=True)
class Fingerprint:
    """All cheap signals collected for one domain."""

    url: str
    host: str
    probe_status: Optional[int]
    homepage_status: Optional[int]
    homepage_html: str
    final_url: str
    families: tuple[Family, ...]
    suggested_strategy: Strategy
    failure_reason: Optional[ErrorReason]

    @property
    def primary_family(self) -> Optional[Family]:
        return self.families[0] if self.families else None

    @property
    def reachable(self) -> bool:
        return self.failure_reason is None


def _looks_dynamic(html: str, families: tuple[Family, ...]) -> bool:
    """Decide whether a domain genuinely needs Playwright.

    The previous heuristic (text_density < 400 OR any marker) was
    over-eager: Apimo / Periscope / Hektor agency sites have a
    JS-heavy homepage (carousel, search widget) over a perfectly
    static detail-page CMS, so the homepage sample at fingerprint
    time misled it into the dynamic branch. Result: ~50% of sites
    were flagged DYNAMIC when ~25% truly were, doubling browser-pool
    contention.

    New rules, in order:
      * Family says it requires JS -> dynamic.
      * Any STRONG marker present (Nuxt/Next/React/Angular/Cloudflare
        challenge) -> dynamic.
      * No body content at all -> dynamic.
      * Weak marker present AND no <main>/<article>/<section> anchor
        AND text_density < 400 -> dynamic.
      * Otherwise -> static. The static path will fall back to
        dynamic on a per-domain basis if it produces zero listings.
    """
    if any(family.requires_dynamic for family in families):
        return True
    if not html:
        return True
    if any(pattern.search(html) for pattern in _STRONG_DYNAMIC_MARKERS):
        return True
    body_match = _BODY_PRESENCE.search(html)
    body_text = body_match.group(1) if body_match else ""
    text_density = len(re.sub(r"<[^>]+>", " ", body_text or "").strip())
    has_anchor = bool(_STRUCTURAL_ANCHOR.search(html))
    has_weak_marker = any(
        pattern.search(html) for pattern in _WEAK_DYNAMIC_MARKERS
    )
    # Empty body shell with weak marker: dynamic.
    if has_weak_marker and not has_anchor and text_density < 400:
        return True
    return False


async def fingerprint_site(
    url: str,
    fetcher: HttpFetcher,
) -> Fingerprint:
    host = parse_host(url)
    probe = await fetcher.probe(url)
    probe_status = probe.status_code
    failure_from_probe = classify_http_status(probe_status)

    # Use whichever variant actually answered as the basis for the
    # homepage GET, so we don't waste time re-probing a non-answering
    # host/scheme combo.
    effective_url = probe.final_url or url

    homepage_status: Optional[int] = None
    homepage_html = ""
    final_url = effective_url
    homepage_failure: Optional[ErrorReason] = None

    if failure_from_probe is None or failure_from_probe == ErrorReason.BLOCKED_403:
        outcome = await fetcher.fetch(effective_url)
        homepage_status = outcome.status
        final_url = outcome.final_url or effective_url
        if outcome.ok and outcome.is_html_like:
            homepage_html = outcome.text[:_HEAD_BYTES]
        else:
            homepage_failure = classify_http_status(outcome.status)

    failure_reason = failure_from_probe
    if homepage_failure and not failure_reason:
        failure_reason = homepage_failure

    signals = FamilySignals(
        url=url,
        host=host,
        html_head=homepage_html,
        headers={},
    )
    families = get_registry().detect_many(signals)

    if failure_reason == ErrorReason.BLOCKED_403:
        strategy = Strategy.DYNAMIC
    elif failure_reason in (ErrorReason.SITE_NOT_REACHABLE,):
        strategy = Strategy.NONE
    elif _looks_dynamic(homepage_html, families):
        strategy = Strategy.DYNAMIC
    else:
        strategy = Strategy.STATIC

    log.debug(
        "fingerprint host=%s status=%s/%s strategy=%s families=%s reason=%s",
        host, probe_status, homepage_status, strategy.value,
        [f.name for f in families],
        failure_reason.value if failure_reason else "",
    )

    return Fingerprint(
        url=effective_url,
        host=host,
        probe_status=probe_status,
        homepage_status=homepage_status,
        homepage_html=homepage_html,
        final_url=final_url,
        families=families,
        suggested_strategy=strategy,
        failure_reason=failure_reason,
    )
