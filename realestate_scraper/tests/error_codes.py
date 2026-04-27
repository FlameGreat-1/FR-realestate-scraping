from __future__ import annotations

import httpx

from scraper.error_codes import (
    ErrorReason,
    classify_exception,
    classify_http_status,
)


def test_values_match_brief():
    assert set(ErrorReason.values()) == {
        "no_website",
        "no_listings_found",
        "site_not_reachable",
        "blocked_403",
        "dynamic_js_required",
        "parsing_failed",
    }


def test_classify_http_status_blocks_403_429():
    assert classify_http_status(403) is ErrorReason.BLOCKED_403
    assert classify_http_status(429) is ErrorReason.BLOCKED_403
    assert classify_http_status(401) is ErrorReason.BLOCKED_403


def test_classify_http_status_5xx_unreachable():
    assert classify_http_status(500) is ErrorReason.SITE_NOT_REACHABLE
    assert classify_http_status(502) is ErrorReason.SITE_NOT_REACHABLE
    assert classify_http_status(None) is ErrorReason.SITE_NOT_REACHABLE


def test_classify_http_status_2xx_3xx_returns_none():
    assert classify_http_status(200) is None
    assert classify_http_status(301) is None


def test_classify_exception_network():
    exc = httpx.ConnectTimeout("timed out")
    assert classify_exception(exc) is ErrorReason.SITE_NOT_REACHABLE


def test_classify_exception_dynamic_js_marker():
    class _Boom(Exception):
        pass

    assert (
        classify_exception(_Boom("Execution context was destroyed by navigation"))
        is ErrorReason.DYNAMIC_JS_REQUIRED
    )


def test_classify_exception_default_parsing():
    assert classify_exception(ValueError("bad html")) is ErrorReason.PARSING_FAILED
