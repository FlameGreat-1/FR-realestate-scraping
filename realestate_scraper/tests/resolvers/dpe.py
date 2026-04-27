from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.dpe import DpeResolver

RESOLVER = DpeResolver()


def test_dpe_labelled():
    html = "<html><body>DPE : C</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "C"


def test_dpe_classe_energie():
    html = "<html><body>Classe énergie : D</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "D"


def test_dpe_returns_empty_when_unlabelled():
    html = "<html><body>F. Description without DPE marker.</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == ""
