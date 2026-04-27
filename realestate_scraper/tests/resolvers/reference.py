from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.reference import ReferenceResolver

RESOLVER = ReferenceResolver()


def test_reference_from_json_ld_sku():
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type":"Product","sku":"REF-12345","offers":{"price":"1"}}'
        '</script></head><body></body></html>'
    )
    ctx = parse_page("https://x.com/p", html)
    assert RESOLVER.resolve(ctx).value == "REF-12345"


def test_reference_from_label():
    html = "<html><body><p>Réf.: ABC987</p></body></html>"
    ctx = parse_page("https://x.com/page", html)
    assert RESOLVER.resolve(ctx).value == "ABC987"


def test_reference_from_url_pattern_vp():
    ctx = parse_page("https://x.com/vente/maison-bordeaux-VP12345", "<html></html>")
    assert RESOLVER.resolve(ctx).value == "VP12345"


def test_reference_from_slug_when_nothing_else():
    ctx = parse_page(
        "https://x.com/biens/appartement-t3-paris-75011,VA47923",
        "<html></html>",
    )
    assert RESOLVER.resolve(ctx).value == "VA47923"


def test_reference_rejects_junk_slugs():
    ctx = parse_page("https://x.com/page", "<html></html>")
    assert RESOLVER.resolve(ctx).value == ""
