"""Canonical error codes mandated by the test brief.

The brief lists exactly six allowed reason codes for the error log. Any
internal classification must map to one of these. Centralising the
vocabulary here is the only way to guarantee compliance.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class ErrorReason(str, Enum):
    NO_WEBSITE = "no_website"
    NO_LISTINGS_FOUND = "no_listings_found"
    SITE_NOT_REACHABLE = "site_not_reachable"
    BLOCKED_403 = "blocked_403"
    DYNAMIC_JS_REQUIRED = "dynamic_js_required"
    PARSING_FAILED = "parsing_failed"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


def classify_http_status(status: Optional[int]) -> Optional[ErrorReason]:
    """Map an HTTP status code to a canonical reason, or None if it is OK."""
    if status is None:
        return ErrorReason.SITE_NOT_REACHABLE
    if status in (401, 403):
        return ErrorReason.BLOCKED_403
    if status == 429:
        return ErrorReason.BLOCKED_403
    if 500 <= status <= 599:
        return ErrorReason.SITE_NOT_REACHABLE
    if 200 <= status < 400:
        return None
    return ErrorReason.SITE_NOT_REACHABLE


def classify_exception(exc: BaseException) -> ErrorReason:
    """Map an exception raised during scraping to a canonical reason."""
    name = type(exc).__name__.lower()
    msg = (str(exc) or "").lower()

    network_markers = (
        "connect", "timeout", "timed out", "dns", "name or service",
        "econnrefused", "unreachable", "reset", "closed",
        "ssl", "certificate", "handshake", "remote disconnected",
    )
    if any(marker in name for marker in ("timeout", "connect", "network", "dns")):
        return ErrorReason.SITE_NOT_REACHABLE
    if any(marker in msg for marker in network_markers):
        return ErrorReason.SITE_NOT_REACHABLE

    js_markers = ("navigation", "execution context", "detached", "frame was")
    if any(marker in msg for marker in js_markers):
        return ErrorReason.DYNAMIC_JS_REQUIRED

    return ErrorReason.PARSING_FAILED
