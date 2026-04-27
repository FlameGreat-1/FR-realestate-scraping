from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.resolvers.email import EmailResolver, _decode_cfemail

RESOLVER = EmailResolver()


def _encode_cfemail(plaintext: str, key: int = 0xA5) -> str:
    """Inverse of `_decode_cfemail`, used to build deterministic test fixtures."""
    if not 0 <= key <= 0xFF:
        raise ValueError("key must be a single byte")
    encoded = bytearray([key])
    for ch in plaintext.encode("utf-8"):
        encoded.append(ch ^ key)
    return encoded.hex()


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


def test_decode_cfemail_round_trips():
    payload = _encode_cfemail("contact@agency.fr", key=0x4B)
    assert _decode_cfemail(payload) == "contact@agency.fr"


def test_decode_cfemail_rejects_malformed():
    assert _decode_cfemail("") == ""
    assert _decode_cfemail("abc") == ""          # odd length
    assert _decode_cfemail("zzzz") == ""          # non-hex


def test_email_from_cf_data_attribute():
    payload = _encode_cfemail("hello@agency.fr", key=0xA5)
    html = f'<html><body><span data-cfemail="{payload}"></span></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "hello@agency.fr"


def test_email_from_cf_anchor_href():
    payload = _encode_cfemail("sales@agency.fr", key=0x10)
    html = (
        '<html><body>'
        f'<a class="__cf_email__" href="/cdn-cgi/l/email-protection#{payload}">x</a>'
        '</body></html>'
    )
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "sales@agency.fr"


def test_email_decodes_html_entity_mailto():
    # `mailto:contact@agency.fr` with the c, o, and @ as entities.
    href = "mailto:&#99;&#111;ntact&#64;agency.fr"
    html = f'<html><body><a href="{href}">click</a></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "contact@agency.fr"


def test_email_reconstructs_at_dot_obfuscation_brackets():
    html = '<html><body><p>Email: jean [at] agency [dot] fr</p></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "jean@agency.fr"


def test_email_reconstructs_at_dot_obfuscation_parens():
    html = '<html><body><p>info (AT) myagency (DOT) com</p></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "info@myagency.com"


def test_email_does_not_reconstruct_when_dot_marker_missing():
    # Only [at] is present; no [dot]. Must NOT invent an address.
    html = '<html><body><p>jean [at] agency.fr -- visit our site</p></body></html>'
    ctx = parse_page("https://x.com/x", html)
    # No mailto, no cf_email, no `[at]...[dot]` pair, but the raw
    # `agency.fr` does contain `agency.fr` as plain text - so the
    # plaintext regex sweep should NOT find an `@` either. Result: "".
    assert RESOLVER.resolve(ctx).value == ""


def test_email_rejects_noreply_even_from_cf():
    payload = _encode_cfemail("noreply@agency.fr", key=0x77)
    html = f'<html><body><span data-cfemail="{payload}"></span></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == ""
