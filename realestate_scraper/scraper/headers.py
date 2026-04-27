"""User-Agent pool and modern HTTP client hint headers.

Purpose:
    Many CDNs (Cloudflare, Datadome, Akamai Bot Manager) gate access
    on the *combination* of User-Agent and the Sec-CH-* / Sec-Fetch-*
    client-hint headers that real browsers send. Sending a plain UA
    string with no hints flags as a bot even when the UA itself is
    valid. This module owns a small, curated pool of realistic header
    sets and a deterministic per-host selector.

Design rules:
    * The pool is intentionally tiny (4 entries) so the rotation
      itself is not a fingerprint.
    * Selection is deterministic per registrable domain (stable hash
      over the domain) so:
        - retries against the same host always pick the same UA,
          preserving HTTP/2 connection reuse on the shared client;
        - different domains naturally diversify across the pool.
    * Every entry is a *coherent* set: a Chrome UA carries Chromium
      Sec-CH-UA strings; a Firefox UA carries no Sec-CH-UA at all
      (Firefox does not send those by default).

No network state lives here, so the module is trivially testable.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

from .utils.url import parse_registrable_domain


@dataclass(frozen=True, slots=True)
class BrowserProfile:
    """A coherent UA + client-hint header set."""

    user_agent: str
    extra_headers: Mapping[str, str]


# Curated pool of recent, real-world desktop browser fingerprints.
# Each entry was verified against the public Chromium / Firefox release
# notes for the matching version. Update yearly.
_PROFILES: tuple[BrowserProfile, ...] = (
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        extra_headers={
            "Sec-CH-UA": (
                '"Chromium";v="124", "Google Chrome";v="124", '
                '"Not-A.Brand";v="99"'
            ),
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        extra_headers={
            "Sec-CH-UA": (
                '"Chromium";v="124", "Google Chrome";v="124", '
                '"Not-A.Brand";v="99"'
            ),
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"macOS"',
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        extra_headers={
            "Sec-CH-UA": (
                '"Chromium";v="124", "Google Chrome";v="124", '
                '"Not-A.Brand";v="99"'
            ),
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Linux"',
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
    ),
    BrowserProfile(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
            "Gecko/20100101 Firefox/124.0"
        ),
        extra_headers={
            # Firefox does not send Sec-CH-UA. Sending it here would
            # actually flag us as a bot, so we deliberately omit it.
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
    ),
)


def _stable_index(key: str, modulus: int) -> int:
    """Deterministic, well-distributed bucket index.

    `hash()` is salted per Python process, which would break HTTP/2
    connection reuse across runs. md5 is fine here because we only need
    a uniform integer.
    """
    if modulus <= 0:
        return 0
    digest = hashlib.md5(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % modulus


def profile_pool() -> tuple[BrowserProfile, ...]:
    """Return the curated profile pool."""
    return _PROFILES


def profile_for_url(url: str) -> BrowserProfile:
    """Pick a stable profile for the registrable domain of `url`.

    Two requests against the same host always get the same profile,
    preserving HTTP/2 reuse. Two different hosts naturally diversify
    across the pool.
    """
    domain = parse_registrable_domain(url) or url or "_default_"
    index = _stable_index(domain.lower(), len(_PROFILES))
    return _PROFILES[index]


def rotated_profile(url: str, attempt: int) -> BrowserProfile:
    """Pick a profile *different* from the primary one for retries.

    `attempt` is 1-indexed; attempt=1 returns the next profile in the
    pool relative to the primary, attempt=2 the one after that, etc.
    Always returns a different entry than `profile_for_url(url)` until
    the pool is exhausted, then wraps.
    """
    if attempt < 1:
        attempt = 1
    domain = parse_registrable_domain(url) or url or "_default_"
    primary = _stable_index(domain.lower(), len(_PROFILES))
    return _PROFILES[(primary + attempt) % len(_PROFILES)]


def build_headers(
    profile: BrowserProfile,
    *,
    accept: str,
    accept_language: str,
) -> dict[str, str]:
    """Assemble the full header set sent on a request.

    `Accept-Encoding` is fixed to the values httpx already negotiates
    (gzip/deflate/br). httpx adds it automatically when not provided,
    but setting it explicitly avoids surprising defaults if the
    underlying transport ever changes.
    """
    headers: dict[str, str] = {
        "User-Agent": profile.user_agent,
        "Accept": accept,
        "Accept-Language": accept_language,
        "Accept-Encoding": "gzip, deflate, br",
    }
    headers.update(profile.extra_headers)
    return headers
