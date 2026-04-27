from __future__ import annotations

from scraper.extractors.pipeline_extract import build_listing, parse_page
from scraper.models import DomainJob

_FULL_PAGE = '''
<html><head>
<title>Maison T4 à vendre - Bordeaux 33000</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Belle maison",
  "sku": "VP12345",
  "offers": {"@type": "Offer", "price": "450000"},
  "address": {"@type": "PostalAddress",
    "addressLocality": "Bordeaux", "postalCode": "33000"},
  "geo": {"@type": "GeoCoordinates",
    "latitude": 44.84, "longitude": -0.58},
  "telephone": "+33556440607"
}
</script>
</head>
<body>
<h1>Belle maison T4 - Bordeaux</h1>
<p>Surface : 120,5 m² - 4 pièces - 3 chambres - DPE : C</p>
<a href="mailto:contact@agency.fr">Email</a>
<a href="tel:+33 5 56 44 06 07">Phone</a>
<span class="agent-name">Marie Dupont</span>
</body></html>
'''


def test_build_listing_full_page():
    job = DomainJob(
        domain="agency.fr",
        url="https://agency.fr",
        agency_name="Agency",
        city="Bordeaux",
        postalcode="33000",
    )
    ctx = parse_page(
        "https://agency.fr/vente/maison-bordeaux-33000-VP12345",
        _FULL_PAGE,
        domain_job=job,
    )
    listing = build_listing(ctx)

    assert listing.is_publishable()
    assert listing.reference_id == "VP12345"
    assert listing.price == "450000"
    assert listing.property_type == "maison"
    assert listing.surface_area == "120.5"
    assert listing.rooms == "4"
    assert listing.bedrooms == "3"
    assert listing.dpe_rating == "C"
    assert "Bordeaux" in listing.location
    assert listing.coordinates.startswith("44.84")
    assert listing.phone_number == "0556440607"
    assert listing.email == "contact@agency.fr"
    assert listing.agent_name == "Marie Dupont"
    assert listing.agency_name == "Agency"
    assert listing.source_domain == "agency.fr"
    assert listing.source_url.endswith("VP12345")


def test_build_listing_skips_unpublishable_when_no_price():
    html = "<html><body><p>No price page</p></body></html>"
    ctx = parse_page("https://agency.fr/page", html)
    listing = build_listing(ctx)
    assert not listing.is_publishable()
