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


def test_location_from_title_overrides_agency_csv():
    """A page title carrying `à <Commune>` must beat the agency CSV.

    Reproduces the Nestenn regression: the input CSV row says the
    Nestenn agency is in Saint-Lys 31470, but the actual property
    page is for an apartment in Nice. The resolver must return Nice.
    """
    job = DomainJob(
        domain="nestenn.com", url="https://nestenn.com",
        city="Saint-Lys", postalcode="31470",
    )
    html = (
        "<html><head><title>Appartement 3 pièces à vendre à Nice - Nestenn</title>"
        "</head><body><h1>Appartement à Nice</h1></body></html>"
    )
    ctx = parse_page(
        "https://immobilier-nice-port.nestenn.com/appartement-ref-39416895",
        html,
        domain_job=job,
    )
    assert RESOLVER.resolve(ctx).value == "Nice"


def test_location_from_body_postal_overrides_agency_csv():
    """`<Commune> <postal>` co-occurrence in body text wins over the CSV."""
    job = DomainJob(
        domain="x.com", url="https://x.com",
        city="Bordeaux", postalcode="33000",
    )
    html = (
        "<html><body>Maison à vendre dans le Bassin d'Arcachon, "
        "située à Lege Cap Ferret 33950, vue panoramique."
        "</body></html>"
    )
    ctx = parse_page(
        "https://x.com/biens/86083117", html, domain_job=job,
    )
    assert RESOLVER.resolve(ctx).value == "Lege Cap Ferret 33950"


def test_location_falls_back_to_agency_csv_when_page_has_nothing():
    job = DomainJob(
        domain="x.com", url="https://x.com", city="Toulouse", postalcode="31000"
    )
    ctx = parse_page("https://x.com/listing/12345", "<html></html>", domain_job=job)
    assert RESOLVER.resolve(ctx).value == "Toulouse 31000"


def test_location_title_pattern_does_not_match_descriptor_runs():
    """Numeric-laden descriptor titles must never produce a false commune."""
    job = DomainJob(
        domain="x.com", url="https://x.com", city="Lyon", postalcode="69001",
    )
    html = (
        "<html><head><title>Appartement studio 22 75011 Paris</title>"
        "</head><body></body></html>"
    )
    ctx = parse_page(
        "https://x.com/biens/86927775", html, domain_job=job,
    )
    # The page genuinely names Paris 75011 - the resolver should
    # capture that, not the descriptor run preceding it.
    assert RESOLVER.resolve(ctx).value == "Paris"
