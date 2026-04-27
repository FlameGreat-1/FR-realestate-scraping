from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.email import EmailResolver

RESOLVER = EmailResolver()


def test_email_from_mailto():
    html = '<html><body><a href="mailto:hello@agency.fr?subject=info">mail</a></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "hello@agency.fr"


def test_email_skips_image_filenames():
    html = '<html><body><img src="foo@x320.jpg"><p>contact: real@agency.fr</p></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "real@agency.fr"


def test_email_returns_empty_when_none_present():
    html = "<html><body>No address here.</body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == ""
