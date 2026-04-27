from __future__ import annotations

from scraper.utils.json_ld import extract_json_ld

_LISTING_HTML = '''
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Belle maison",
  "sku": "REF-12345",
  "offers": {"@type": "Offer", "price": "450000", "priceCurrency": "EUR"},
  "address": {
    "@type": "PostalAddress",
    "addressLocality": "Bordeaux",
    "postalCode": "33000"
  },
  "geo": {"@type": "GeoCoordinates", "latitude": 44.84, "longitude": -0.58},
  "telephone": "+33556440607"
}
</script>
</head><body></body></html>
'''


def test_extract_json_ld_collects_core_fields():
    out = extract_json_ld(_LISTING_HTML)
    assert out["price"] == "450000"
    assert out["reference_id"] == "REF-12345"
    assert "Bordeaux" in out["location"]
    assert "33000" in out["location"]
    assert out["coordinates"].startswith("44.84")
    assert out["phone"] == "+33556440607"


def test_extract_json_ld_handles_missing_blocks():
    assert extract_json_ld("") == {}
    assert extract_json_ld("<html></html>") == {}


def test_extract_json_ld_tolerates_invalid_json():
    bad = '<script type="application/ld+json">{ invalid }</script>'
    assert extract_json_ld(bad) == {}
