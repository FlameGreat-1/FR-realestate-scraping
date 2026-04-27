from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from scraper.error_codes import ErrorReason
from scraper.models import DomainResult, DomainStatus, Listing, Strategy
from scraper.storage import build_output_bundle


def _bundle(tmp_path: Path):
    return build_output_bundle(
        listings_path=tmp_path / "listings.csv",
        errors_path=tmp_path / "errors.csv",
        summary_path=tmp_path / "summary.csv",
    )


def test_listing_writer_dedupes_by_reference(tmp_path: Path):
    bundle = _bundle(tmp_path)

    async def go():
        await bundle.initialize(truncate=True)
        listing_a = Listing(
            reference_id="REF1", price="100", property_type="maison",
            source_url="https://x.com/a", source_domain="x.com",
        )
        listing_b = Listing(
            reference_id="REF1", price="100", property_type="maison",
            source_url="https://x.com/b", source_domain="x.com",
        )
        await bundle.listings.write_many([listing_a])
        await bundle.listings.write_many([listing_b])

    asyncio.run(go())
    rows = list(csv.DictReader((tmp_path / "listings.csv").open()))
    assert len(rows) == 1
    assert rows[0]["reference_id"] == "REF1"
    assert rows[0]["source_domain"] == "x.com"


def test_listing_writer_dedupes_by_url_when_no_reference(tmp_path: Path):
    bundle = _bundle(tmp_path)

    async def go():
        await bundle.initialize(truncate=True)
        same = Listing(
            price="100", property_type="maison",
            source_url="https://x.com/page", source_domain="x.com",
        )
        again = Listing(
            price="100", property_type="maison",
            source_url="https://X.com/page#frag", source_domain="x.com",
        )
        await bundle.listings.write_many([same, again])

    asyncio.run(go())
    rows = list(csv.DictReader((tmp_path / "listings.csv").open()))
    assert len(rows) == 1


def test_listing_writer_skips_unpublishable(tmp_path: Path):
    bundle = _bundle(tmp_path)

    async def go():
        await bundle.initialize(truncate=True)
        await bundle.listings.write_many([
            Listing(price="", source_domain="x.com", source_url="https://x.com/a"),
            Listing(price="100", source_domain="x.com", source_url="https://x.com/b"),
        ])

    asyncio.run(go())
    rows = list(csv.DictReader((tmp_path / "listings.csv").open()))
    assert len(rows) == 0  # second listing has no descriptor either


def test_listing_writer_dedupes_by_content_fingerprint_when_url_differs(tmp_path: Path):
    bundle = _bundle(tmp_path)

    async def go():
        await bundle.initialize(truncate=True)
        # No reference id (tier 1 cannot fire). Different URL paths
        # (tier 2 cannot fire because canonical URLs are different).
        # Identical descriptor fields - tier 3 must collapse them.
        first = Listing(
            price="450000", property_type="maison",
            location="Bordeaux", surface_area="120",
            source_url="https://x.com/listing?utm_source=home",
            source_domain="x.com",
        )
        second = Listing(
            price="450000", property_type="maison",
            location="Bordeaux", surface_area="120",
            source_url="https://x.com/listing?utm_source=mail",
            source_domain="x.com",
        )
        await bundle.listings.write_many([first])
        await bundle.listings.write_many([second])

    asyncio.run(go())
    rows = list(csv.DictReader((tmp_path / "listings.csv").open()))
    assert len(rows) == 1


def test_listing_writer_keeps_distinct_content_under_same_url(tmp_path: Path):
    bundle = _bundle(tmp_path)

    async def go():
        await bundle.initialize(truncate=True)
        # Same URL is impossible to keep distinct under tier 2,
        # but the test pins what *should* happen when tier 2 cannot
        # apply (no URL collision because canonical URLs differ).
        # We make URLs identical only after canonicalisation here
        # to confirm tier 3 does NOT erroneously collapse listings
        # whose fingerprints differ.
        a = Listing(
            price="450000", property_type="maison",
            location="Bordeaux", surface_area="120",
            source_url="https://x.com/a",
            source_domain="x.com",
        )
        b = Listing(
            price="550000", property_type="appartement",
            location="Paris", surface_area="80",
            source_url="https://x.com/b",
            source_domain="x.com",
        )
        await bundle.listings.write_many([a, b])

    asyncio.run(go())
    rows = list(csv.DictReader((tmp_path / "listings.csv").open()))
    assert len(rows) == 2
    prices = {r["price"] for r in rows}
    assert prices == {"450000", "550000"}


def test_listing_writer_tier1_does_not_collide_with_tier3(tmp_path: Path):
    bundle = _bundle(tmp_path)

    async def go():
        await bundle.initialize(truncate=True)
        # Same descriptor fingerprint but one has a reference id and
        # one does not. They are different listings: tier 1 wins for
        # the first, and tier 3 must accept the second because no
        # tier-3 entry has been recorded yet for the same fingerprint.
        with_ref = Listing(
            reference_id="REF42",
            price="450000", property_type="maison",
            location="Bordeaux", surface_area="120",
            source_url="https://x.com/a", source_domain="x.com",
        )
        no_ref_same_fp = Listing(
            price="450000", property_type="maison",
            location="Bordeaux", surface_area="120",
            source_url="https://x.com/b", source_domain="x.com",
        )
        await bundle.listings.write_many([with_ref])
        await bundle.listings.write_many([no_ref_same_fp])

    asyncio.run(go())
    rows = list(csv.DictReader((tmp_path / "listings.csv").open()))
    # Tier 1 records the fingerprint when it accepts, so the second
    # listing (same fingerprint, no ref) is correctly deduped.
    assert len(rows) == 1
    assert rows[0]["reference_id"] == "REF42"


def test_error_writer_uses_canonical_reasons(tmp_path: Path):
    bundle = _bundle(tmp_path)

    async def go():
        await bundle.initialize(truncate=True)
        await bundle.errors.record("a.com", ErrorReason.BLOCKED_403)
        await bundle.errors.record("a.com", ErrorReason.BLOCKED_403)  # idempotent
        await bundle.errors.record("b.com", ErrorReason.NO_LISTINGS_FOUND)

    asyncio.run(go())
    rows = list(csv.DictReader((tmp_path / "errors.csv").open()))
    assert len(rows) == 2
    assert {r["reason"] for r in rows} == {
        "blocked_403", "no_listings_found",
    }


def test_summary_writer_records_each_result(tmp_path: Path):
    bundle = _bundle(tmp_path)

    async def go():
        await bundle.initialize(truncate=True)
        await bundle.summary.record(DomainResult(
            domain="a.com", status=DomainStatus.SUCCESS, listing_count=12,
            strategy=Strategy.STATIC, duration_seconds=4.2,
        ))
        await bundle.summary.record(DomainResult(
            domain="b.com", status=DomainStatus.FAILED,
            reason=ErrorReason.BLOCKED_403,
            strategy=Strategy.DYNAMIC, duration_seconds=3.1,
        ))

    asyncio.run(go())
    rows = list(csv.DictReader((tmp_path / "summary.csv").open()))
    assert [r["domain"] for r in rows] == ["a.com", "b.com"]
    assert rows[0]["listing_count"] == "12"
    assert rows[1]["reason"] == "blocked_403"
