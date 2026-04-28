from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.models import DomainJob
from scraper.resolvers.location import LocationResolver

RESOLVER = LocationResolver()


def test_location_from_url_pattern():
    ctx = parse_page("https://x.com/vente/maison-bordeaux-33000", "<html></html>")
    assert RESOLVER.resolve(ctx).value == "Bordeaux 33000"


def test_location_from_breadcrumb():
    html = (
        '<html><body><nav class="breadcrumb">'
        '<a>Accueil</a><a>Vente</a><a>Lyon 69001</a>'
        '</nav></body></html>'
    )
    ctx = parse_page("https://x.com/page", html)
    assert RESOLVER.resolve(ctx).value == "Lyon 69001"


def test_location_falls_back_to_agency_csv():
    job = DomainJob(
        domain="x.com", url="https://x.com", city="Toulouse", postalcode="31000"
    )
    ctx = parse_page("https://x.com/listing/12345", "<html></html>", domain_job=job)
    assert RESOLVER.resolve(ctx).value == "Toulouse 31000"
