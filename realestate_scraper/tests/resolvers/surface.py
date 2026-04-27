from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.surface import SurfaceResolver

RESOLVER = SurfaceResolver()


def test_surface_with_label_and_comma():
    html = "<html><body>Surface habitable : 90,76 m²</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "90.76"


def test_surface_loose_match():
    html = "<html><body>Description... 120 m2 ...</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "120"


def test_surface_handles_thousand_separator_dot():
    html = "<html><body>Surface : 1.302 m²</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "1302"


def test_surface_returns_empty_when_missing():
    html = "<html><body>No info</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == ""
