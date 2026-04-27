from __future__ import annotations

from scraper.utils.text import (
    clean_price,
    collapse_whitespace,
    digits_only,
    find_euro_amounts,
    find_priced_labels,
    normalize_for_match,
    strip_accents,
)


def test_collapse_whitespace_normalises_runs():
    assert collapse_whitespace("a   b\n\tc") == "a b c"
    assert collapse_whitespace("") == ""


def test_strip_accents_removes_diacritics():
    assert strip_accents("élève") == "eleve"
    assert strip_accents("Château") == "Chateau"


def test_digits_only_keeps_only_digits():
    assert digits_only("+33 (0)6 12 34 56 78") == "33061234567 8".replace(" ", "")


def test_clean_price_strips_separators_and_currency():
    assert clean_price("621 000 \xa0€") == "621000"
    assert clean_price("170,000 € (Fixe)") == "170000"
    assert clean_price("€ 89.000") == "89000"


def test_clean_price_preserves_long_legitimate_prices():
    # Legacy bug regression: 200200 must NOT be halved into 200.
    assert clean_price("200200") == "200200"
    assert clean_price("1234567 €") == "1234567"


def test_clean_price_rejects_zeros_and_empty():
    assert clean_price("") == ""
    assert clean_price("0") == ""
    assert clean_price("00") == ""
    assert clean_price("abc") == ""


def test_find_euro_amounts_returns_raw_captures():
    found = find_euro_amounts("Vente 250 000 €, hors frais 280 000 €")
    assert len(found) == 2


def test_find_priced_labels_extracts_label_value():
    labels = find_priced_labels("Prix : 621 000 €")
    assert labels and "621" in labels[0]


def test_normalize_for_match_lowercases_and_strips():
    assert normalize_for_match("  ChÂTEAU  ") == "chateau"
