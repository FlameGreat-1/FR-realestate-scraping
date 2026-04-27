from __future__ import annotations

from scraper.listing_filter import classify_url, is_candidate_listing_url


def test_rejects_assets_and_social():
    assert classify_url("https://x.com/img.jpg").score < 0
    assert classify_url("https://facebook.com/agency").score < 0
    assert classify_url("mailto:foo@bar.com").score < 0


def test_rejects_hub_pages():
    assert classify_url("https://x.com/recherche").score < 0
    assert classify_url("https://x.com/biens/result").score < 0
    assert classify_url("https://x.com/annonces").score < 0


def test_rejects_obviously_non_listing_pages():
    assert classify_url("https://x.com/contact").score < 0
    assert classify_url("https://x.com/blog/article-1").score < 0
    assert classify_url("https://x.com/mentions-legales").score < 0


def test_accepts_real_detail_urls():
    accepted_urls = [
        "https://x.com/vente/maison-3-pieces-bordeaux-33000-ref-VP12345",
        "https://x.com/biens/appartement-t3-paris-75011,VA47923",
        "https://x.com/annonce/123456-villa-cannes",
        "https://x.com/property/123456789",
    ]
    for url in accepted_urls:
        assert is_candidate_listing_url(url), url


def test_shallow_paths_with_no_signal_rejected():
    assert classify_url("https://x.com/about-us").score <= 0
    assert classify_url("https://x.com/team").score <= 0
