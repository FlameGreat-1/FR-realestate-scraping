"""URL normalization and same-host helpers.

Using `tldextract` makes registrable-domain comparisons safe across
subdomains and locale TLDs (`stephaneplazaimmobilier.com` vs
`dunkerque.stephaneplazaimmobilier.com`, etc.).
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse, urlunparse, urljoin

import tldextract

_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


def ensure_scheme(url: str, default_scheme: str = "https") -> str:
    if not url:
        return ""
    value = str(url).strip()
    if not value or value.lower() in {"nan", "none", "null"}:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return f"{default_scheme}://{value.lstrip('/')}"


def parse_registrable_domain(url: str) -> str:
    """Return the registrable domain (e.g. `agency.fr`) without subdomain."""
    if not url:
        return ""
    extracted = _EXTRACT(url)
    if not extracted.domain or not extracted.suffix:
        return urlparse(ensure_scheme(url)).netloc.lower().lstrip("www.")
    return f"{extracted.domain}.{extracted.suffix}".lower()


def parse_host(url: str) -> str:
    """Return the full host (with subdomain) lower-cased, no `www.` prefix."""
    if not url:
        return ""
    netloc = urlparse(ensure_scheme(url)).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def same_registrable_domain(a: str, b: str) -> bool:
    return parse_registrable_domain(a) == parse_registrable_domain(b)


def canonicalize(url: str) -> str:
    """Drop fragment, normalise scheme/host casing, strip trailing slash."""
    if not url:
        return ""
    parsed = urlparse(ensure_scheme(url))
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def dedup_key(url: str) -> str:
    return canonicalize(url).lower()


def join_url(base: str, href: Optional[str]) -> str:
    if not href:
        return ""
    return urljoin(base, href)


def both_www_variants(url: str) -> tuple[str, str]:
    """Return (`https://www.host/...`, `https://host/...`) for redundancy."""
    parsed = urlparse(ensure_scheme(url))
    host = parsed.netloc.lower()
    bare = host[4:] if host.startswith("www.") else host
    www = host if host.startswith("www.") else f"www.{host}"
    rest = (parsed.path or "/", parsed.params, parsed.query, "")
    return (
        urlunparse((parsed.scheme, www, *rest)),
        urlunparse((parsed.scheme, bare, *rest)),
    )
