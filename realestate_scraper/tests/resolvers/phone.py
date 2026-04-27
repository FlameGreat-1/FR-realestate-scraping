from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.models import DomainJob
from scraper.resolvers.phone import PhoneResolver

RESOLVER = PhoneResolver()


def test_phone_from_tel_link():
    html = '<html><body><a href="tel:+33 1 23 45 67 89">call</a></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "0123456789"


def test_phone_from_label():
    html = "<html><body><p>Tél : 04 78 99 33 11</p></body></html>"
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "0478993311"


def test_phone_falls_back_to_agency_csv():
    job = DomainJob(domain="x.com", url="https://x.com", phone="+33240853232")
    ctx = parse_page("https://x.com/x", "<html></html>", domain_job=job)
    assert RESOLVER.resolve(ctx).value == "0240853232"
