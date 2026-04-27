from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.coordinates import CoordinatesResolver

RESOLVER = CoordinatesResolver()


def test_coordinates_from_inline_js():
    html = '<html><body><script>var lat = 44.84; var lng = -0.58;</script></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "44.84, -0.58"


def test_coordinates_from_iframe_query():
    html = (
        '<html><body><iframe src="https://maps.google.com/?ll=43.7,7.27&z=12">'
        '</iframe></body></html>'
    )
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "43.7, 7.27"


def test_coordinates_returns_empty_when_absent():
    ctx = parse_page("https://x.com/x", "<html><body>nothing</body></html>")
    assert RESOLVER.resolve(ctx).value == ""
