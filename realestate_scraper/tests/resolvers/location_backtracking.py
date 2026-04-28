"""Regression coverage for the regex-backtracking freeze.

The original `_BODY_COMMUNE_POSTAL` and `_TITLE_AT_COMMUNE` patterns
wedged a parse thread for minutes on adversarial inputs. The defect
was silent against benign inputs, so we pin the worst-case shapes
here with a wall-clock assertion. Any future tweak that re-introduces
the defect fails the suite immediately instead of surfacing as a
production freeze.
"""
from __future__ import annotations

import time

import pytest

from scraper.resolvers.location import (
    _BODY_COMMUNE_POSTAL,
    _TITLE_AT_COMMUNE,
    _TITLE_COMMUNE_POSTAL,
    _TITLE_POSTAL_COMMUNE,
    _from_body_postal,
    _from_title_or_h1,
)

# Wall-clock budget for any single regex-match call. The broken
# patterns took tens of seconds on these inputs; the fixed patterns
# return in under 50ms. 1 second is generous enough to absorb CI
# jitter on shared runners while still failing decisively on any
# catastrophic-backtracking regression.
_BUDGET_SECONDS: float = 1.0


def _assert_under_budget(label: str, fn) -> object:
    """Run `fn` and assert it returns within the regex-time budget."""
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    assert elapsed < _BUDGET_SECONDS, (
        f"{label} took {elapsed:.2f}s (budget {_BUDGET_SECONDS:.2f}s) - "
        "regex backtracking regression"
    )
    return result


# --- Backtracking adversarial inputs ---------------------------------

def test_body_postal_no_anchor_returns_under_budget():
    """Long capitalised run with NO trailing 5-digit anchor.

    This is the body-postal worst case. The original pattern's nested
    quantifier over a class containing both space and word characters
    made the engine retry every {0,3} alternation at every starting
    position, producing O(n * 4^k) work.
    """
    # 200 capitalised tokens joined by spaces and hyphens, mixing
    # accented characters that the class includes. No 5-digit number
    # anywhere, so the engine must scan the entire input to fail.
    tokens = [
        "Saint-Jean-de-Luz",
        "Saint-P\u00e9e-sur-Nivelle",
        "Bordeaux",
        "Toulouse",
        "Lyon",
        "Marseille",
    ] * 40
    pathological = " ".join(tokens)
    _assert_under_budget(
        "_BODY_COMMUNE_POSTAL.search",
        lambda: _BODY_COMMUNE_POSTAL.search(pathological),
    )
    # And through the public entry point, which also caps the input
    # length defensively.
    _assert_under_budget(
        "_from_body_postal",
        lambda: _from_body_postal(pathological),
    )


def test_body_postal_huge_input_capped_under_budget():
    """Even a multi-megabyte body must be processed within budget.

    The public entry point caps input at 32 KB; the underlying
    pattern is also bounded-shape, so the cap is belt-and-braces.
    """
    huge = ("Bordeaux Toulouse Lyon Marseille " * 50_000).strip()
    assert len(huge) > 1_000_000
    _assert_under_budget(
        "_from_body_postal(1MB)",
        lambda: _from_body_postal(huge),
    )


def test_title_at_commune_no_anchor_returns_under_budget():
    """Long title with descriptor noise but no postal code.

    This was the `_TITLE_AT_COMMUNE` worst case: a lazy quantifier
    on an embedded-space character class with a broad trailing
    lookahead. The fix replaces it with a fixed-shape NFA built on
    `_COMMUNE_TOKEN`.
    """
    # 'a ' anchor followed by an unbounded run of mixed-case word
    # fragments and punctuation, forcing the lazy quantifier (broken
    # pattern) to expand and contract repeatedly.
    pathological = (
        " a " + "Maison Studio T2 Appartement Villa Loft Duplex " * 200
    )
    _assert_under_budget(
        "_TITLE_AT_COMMUNE.search",
        lambda: _TITLE_AT_COMMUNE.search(pathological),
    )
    _assert_under_budget(
        "_from_title_or_h1",
        lambda: _from_title_or_h1(pathological, ""),
    )


# --- Positive correctness paths --------------------------------------

@pytest.mark.parametrize(
    "title, expected",
    [
        ("Appartement \u00e0 Toulon - 80m\u00b2", "Toulon"),
        ("Maison \u00e0 Saint-Jean-de-Luz vue mer", "Saint-Jean-de-Luz"),
    ],
)
def test_title_at_commune_extracts_commune(title, expected):
    result = _from_title_or_h1(title, "")
    assert result.startswith(expected), (
        f"expected commune {expected!r} from {title!r}, got {result!r}"
    )


def test_title_postal_after_extracts():
    result = _from_title_or_h1("Appartement Bordeaux 33000", "")
    assert "Bordeaux" in result and "33000" in result


def test_title_postal_first_extracts():
    result = _from_title_or_h1("75011 Paris - Appartement T2", "")
    assert "Paris" in result and "75011" in result


def test_body_postal_co_occurrence_extracts():
    body = (
        "Notre agence vous propose ce bien situ\u00e9 \u00e0 "
        "Bordeaux 33000, dans un quartier prestigieux. "
        "Surface: 80m\u00b2."
    )
    result = _from_body_postal(body)
    assert "Bordeaux" in result and "33000" in result


# --- Static shape assertions -----------------------------------------

def test_commune_token_shape_assertions():
    """All three commune-shaped patterns share the bounded NFA shape.

    A regression that introduces a lazy quantifier on a class
    containing whitespace would let the catastrophic backtracking
    back in. We assert the absence of that shape directly.
    """
    for pattern in (
        _BODY_COMMUNE_POSTAL,
        _TITLE_AT_COMMUNE,
        _TITLE_COMMUNE_POSTAL,
        _TITLE_POSTAL_COMMUNE,
    ):
        # No lazy quantifier against a class that embeds a literal
        # space. Catches the exact defect class that produced the
        # freeze (`[... ' \-]{2,40}?`).
        src = pattern.pattern
        assert " \\-]{" not in src and " -]{" not in src, (
            f"pattern {pattern!r} embeds whitespace inside a quantified "
            "class - reintroduces backtracking risk"
        )
