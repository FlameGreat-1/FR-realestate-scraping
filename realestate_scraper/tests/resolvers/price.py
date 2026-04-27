from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.price import PriceResolver

RESOLVER = PriceResolver()


def test_price_from_json_ld():
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type":"Product","offers":{"price":"450000"}}'
        '</script></head><body></body></html>'
    )
    ctx = parse_page("https://x.com/vente/maison-1", html)
    result = RESOLVER.resolve(ctx)
    assert result.value == "450000"
    assert result.confidence > 0.9


def test_price_from_dom_class_with_euro():
    html = (
        '<html><body><span class="price">621 000 \xa0€</span></body></html>'
    )
    ctx = parse_page("https://x.com/vente/maison-1", html)
    assert RESOLVER.resolve(ctx).value == "621000"


def test_price_from_label_in_text():
    html = "<html><body><p>Prix : 170 000 € (Fixe)</p></body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "170000"


def test_price_skips_per_m2_text():
    html = "<html><body><p>Prix au m2 : 5 000 €/m²</p></body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == ""


def test_price_handles_sur_demande():
    html = '<html><body><span class="price">Prix sur demande</span></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == ""
