from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.property_type import PropertyTypeResolver

RESOLVER = PropertyTypeResolver()


def test_property_type_from_title():
    html = "<html><head><title>Maison à vendre - Bordeaux</title></head><body></body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "maison"


def test_property_type_from_h1():
    html = "<html><body><h1>Bel appartement T3</h1></body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "appartement"


def test_property_type_falls_back_to_url():
    ctx = parse_page("https://x.com/vente/villa-luxe", "<html></html>")
    assert RESOLVER.resolve(ctx).value == "villa"


def test_property_type_returns_empty_when_unknown():
    html = "<html><body><h1>Visite virtuelle</h1></body></html>"
    ctx = parse_page("https://x.com/page", html)
    assert RESOLVER.resolve(ctx).value == ""
