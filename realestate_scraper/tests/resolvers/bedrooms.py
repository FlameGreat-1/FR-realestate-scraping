from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.bedrooms import BedroomsResolver

RESOLVER = BedroomsResolver()


def test_bedrooms_label_first():
    html = "<html><body>Chambres : 2</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "2"


def test_bedrooms_label_after():
    html = "<html><body>3 chambres</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "3"


def test_bedrooms_falls_back_to_t_notation():
    html = "<html><head><title>T4 Lyon</title></head><body></body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "3"
