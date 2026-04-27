from __future__ import annotations

from scraper.utils.url import (
    both_www_variants,
    canonicalize,
    dedup_key,
    ensure_scheme,
    parse_host,
    parse_registrable_domain,
    same_registrable_domain,
)


def test_ensure_scheme_adds_https():
    assert ensure_scheme("example.com") == "https://example.com"
    assert ensure_scheme("http://example.com") == "http://example.com"
    assert ensure_scheme("") == ""
    assert ensure_scheme("NaN") == ""


def test_parse_registrable_domain_collapses_subdomains():
    assert parse_registrable_domain(
        "https://www.foo.bar.example.co.uk/x"
    ) == "example.co.uk"
    assert parse_registrable_domain(
        "https://dunkerque.stephaneplazaimmobilier.com/page"
    ) == "stephaneplazaimmobilier.com"


def test_parse_host_drops_www_prefix():
    assert parse_host("https://www.example.com/x") == "example.com"
    assert parse_host("https://sub.example.com/y") == "sub.example.com"


def test_same_registrable_domain():
    assert same_registrable_domain(
        "https://a.example.com", "https://b.example.com"
    )
    assert not same_registrable_domain(
        "https://example.com", "https://example.fr"
    )


def test_canonicalize_drops_fragment_and_trailing_slash():
    assert canonicalize(
        "HTTPS://EX.COM/page/#section"
    ) == "https://ex.com/page"
    assert canonicalize("") == ""


def test_dedup_key_is_lowercase_canonical():
    a = dedup_key("https://Ex.com/PATH/")
    b = dedup_key("https://ex.com/PATH#frag")
    assert a == b


def test_both_www_variants_produces_pair():
    www, bare = both_www_variants("https://example.com/x")
    assert www.startswith("https://www.example.com")
    assert bare.startswith("https://example.com")
