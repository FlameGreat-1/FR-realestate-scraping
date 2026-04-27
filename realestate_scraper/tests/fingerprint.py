from __future__ import annotations

from scraper.fingerprint import _looks_dynamic


def test_dense_html_is_static():
    body = "<p>" + ("property description " * 200) + "</p>"
    html = f"<html><body>{body}</body></html>"
    assert _looks_dynamic(html, families=()) is False


def test_thin_html_is_dynamic():
    html = "<html><body><div id='app'></div></body></html>"
    assert _looks_dynamic(html, families=()) is True


def test_nuxt_marker_is_dynamic():
    html = (
        "<html><body>" + ("text " * 200) + "<script>window.__NUXT__={}</script></body></html>"
    )
    assert _looks_dynamic(html, families=()) is True


def test_cloudflare_challenge_is_dynamic():
    html = (
        "<html><body>" + ("x " * 200) + '<div id="cf-browser-verification"></div></body></html>'
    )
    assert _looks_dynamic(html, families=()) is True
