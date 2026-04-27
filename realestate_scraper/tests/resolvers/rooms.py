from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.rooms import RoomsResolver

RESOLVER = RoomsResolver()


def test_rooms_label_first():
    html = "<html><body>Pièces : 4</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "4"


def test_rooms_label_after():
    html = "<html><body>3 pièces lumineuses</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "3"


def test_rooms_t_notation_in_title():
    html = "<html><head><title>T5 - Bordeaux</title></head><body></body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "5"


def test_rooms_rejects_oversize_value():
    html = "<html><body>40 pièces</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == ""
