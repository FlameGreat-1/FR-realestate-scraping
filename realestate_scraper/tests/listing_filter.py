from __future__ import annotations

from scraper.listing_filter import classify_url, is_candidate_listing_url

# Use a host that is NOT in `_SOCIAL_HOSTS` so the classifier exercises
# its real heuristics rather than short-circuiting on the social-host
# filter. `x.com` is Twitter and is correctly rejected by the social
# filter; using it here used to mask hub/non-listing test failures.
_HOST = "https://agency.example"


def test_rejects_assets_and_social():
    assert classify_url(f"{_HOST}/img.jpg").score < 0
    assert classify_url("https://facebook.com/agency").score < 0
    assert classify_url("mailto:foo@bar.com").score < 0


def test_rejects_hub_pages():
    assert classify_url(f"{_HOST}/recherche").score < 0
    assert classify_url(f"{_HOST}/biens/result").score < 0
    assert classify_url(f"{_HOST}/annonces").score < 0


def test_rejects_obviously_non_listing_pages():
    assert classify_url(f"{_HOST}/contact").score < 0
    assert classify_url(f"{_HOST}/blog/article-1").score < 0
    assert classify_url(f"{_HOST}/mentions-legales").score < 0


def test_accepts_real_detail_urls():
    accepted_urls = [
        f"{_HOST}/vente/maison-3-pieces-bordeaux-33000-ref-VP12345",
        f"{_HOST}/biens/appartement-t3-paris-75011,VA47923",
        f"{_HOST}/annonce/123456-villa-cannes",
        f"{_HOST}/property/123456789",
    ]
    for url in accepted_urls:
        assert is_candidate_listing_url(url), url


def test_shallow_paths_with_no_signal_rejected():
    assert classify_url(f"{_HOST}/about-us").score <= 0
    assert classify_url(f"{_HOST}/team").score <= 0


def test_reference_shape_outranks_category_hub():
    """A reference-shape detail URL must rank strictly above a category page."""
    detail = classify_url(
        f"{_HOST}/vente/maison-bordeaux-33000-ref-39416895"
    )
    hub = classify_url(f"{_HOST}/biens/maisons-vente")
    assert detail.score > hub.score, (detail, hub)


def test_bare_hub_tail_anti_boost():
    """A path ending in a bare property-type token is heavily downranked."""
    assert classify_url(f"{_HOST}/biens/vente/maison").score < 0
    assert classify_url(f"{_HOST}/recherche/appartements").score < 0
