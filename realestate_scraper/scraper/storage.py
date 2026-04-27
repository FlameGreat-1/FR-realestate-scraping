"""Streaming, dedup-aware CSV writers for listings, errors, and summaries.

Design notes:
    * Append-only writers with header initialisation; safe to call from
      many coroutines through an internal `asyncio.Lock`.
    * In-memory dedup keyed on `(source_domain, reference_id)` falling
      back to `(source_domain, canonical_url)`. No post-hoc rewrite of
      the whole file - critical when scaling to 55k+ domains.
    * Headers and column order are sourced from `models.py` so the brief
      contract has a single point of truth.
"""
from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path
from typing import Iterable, Optional

from .error_codes import ErrorReason
from .models import (
    DOMAIN_SUMMARY_FIELDS,
    DomainResult,
    ERROR_FIELDS,
    ErrorRecord,
    LISTING_FIELDS,
    Listing,
)
from .utils.text import normalize_for_match
from .utils.url import dedup_key

import hashlib


def _content_fingerprint(listing: Listing) -> str:
    """Stable per-listing content key used as the third dedup tier.

    Built from the resolved descriptor fields we already have on
    `Listing`. Returns an empty string when there is not enough
    signal to distinguish two rows - in which case the caller falls
    back to the previous behaviour and accepts the row.
    """
    parts = [
        normalize_for_match(listing.location),
        normalize_for_match(listing.property_type),
        normalize_for_match(listing.surface_area),
        (listing.price or "").strip(),
    ]
    payload = "|".join(part for part in parts if part)
    if not payload:
        return ""
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

log = logging.getLogger(__name__)


def _ensure_header(path: Path, header: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(header)


def _truncate(path: Path, header: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(header)


class ListingWriter:
    """Append-only listing writer with cross-domain deduplication."""

    def __init__(self, csv_path: Path) -> None:
        self._path = csv_path
        self._lock = asyncio.Lock()
        self._seen_ref: set[tuple[str, str]] = set()
        self._seen_url: set[tuple[str, str]] = set()
        self._seen_content: set[tuple[str, str]] = set()
        self._written = 0

    @property
    def written(self) -> int:
        return self._written

    async def initialize(self, *, truncate: bool) -> None:
        async with self._lock:
            if truncate:
                _truncate(self._path, LISTING_FIELDS)
            else:
                _ensure_header(self._path, LISTING_FIELDS)

    async def write_many(self, listings: Iterable[Listing]) -> int:
        accepted: list[Listing] = []
        for listing in listings:
            if not isinstance(listing, Listing):
                continue
            if not listing.is_publishable():
                continue
            if not self._register(listing):
                continue
            accepted.append(listing)
        if not accepted:
            return 0

        async with self._lock:
            with self._path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=LISTING_FIELDS,
                    extrasaction="raise",
                    quoting=csv.QUOTE_MINIMAL,
                )
                for listing in accepted:
                    writer.writerow(listing.to_row())
            self._written += len(accepted)
        return len(accepted)

    def _register(self, listing: Listing) -> bool:
        domain = (listing.source_domain or "").strip().lower()
        ref = (listing.reference_id or "").strip()
        url_key = dedup_key(listing.source_url)

        # Tier 1: stable reference id wins outright.
        if domain and ref:
            key = (domain, ref.lower())
            if key in self._seen_ref:
                return False
            self._seen_ref.add(key)
            if url_key:
                self._seen_url.add((domain, url_key))
            content_key = _content_fingerprint(listing)
            if content_key:
                self._seen_content.add((domain, content_key))
            return True

        # Tier 2: canonical URL collapse.
        if domain and url_key:
            key = (domain, url_key)
            if key in self._seen_url:
                return False
            self._seen_url.add(key)
            content_key = _content_fingerprint(listing)
            if content_key:
                self._seen_content.add((domain, content_key))
            return True

        # Tier 3: content fingerprint catches the rows tiers 1 and 2 leak.
        if domain:
            content_key = _content_fingerprint(listing)
            if content_key:
                key = (domain, content_key)
                if key in self._seen_content:
                    return False
                self._seen_content.add(key)
                return True

        return True


class ErrorLogWriter:
    """Append-only writer for the brief-mandated error log."""

    def __init__(self, csv_path: Path) -> None:
        self._path = csv_path
        self._lock = asyncio.Lock()
        self._written: dict[str, str] = {}

    async def initialize(self, *, truncate: bool) -> None:
        async with self._lock:
            if truncate:
                _truncate(self._path, ERROR_FIELDS)
            else:
                _ensure_header(self._path, ERROR_FIELDS)

    async def record(
        self,
        domain: str,
        reason: ErrorReason,
        *,
        status: str = "failed",
    ) -> None:
        domain = (domain or "").strip().lower()
        if not domain:
            return
        record = ErrorRecord(domain=domain, status=status, reason=reason)
        async with self._lock:
            # Idempotent per domain - keep the first authoritative reason.
            if self._written.get(domain) == reason.value:
                return
            self._written[domain] = reason.value
            with self._path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=ERROR_FIELDS,
                    extrasaction="raise",
                    quoting=csv.QUOTE_MINIMAL,
                )
                writer.writerow(record.to_row())


class DomainSummaryWriter:
    """Append-only writer for the per-domain status summary CSV."""

    def __init__(self, csv_path: Path) -> None:
        self._path = csv_path
        self._lock = asyncio.Lock()

    async def initialize(self, *, truncate: bool) -> None:
        async with self._lock:
            if truncate:
                _truncate(self._path, DOMAIN_SUMMARY_FIELDS)
            else:
                _ensure_header(self._path, DOMAIN_SUMMARY_FIELDS)

    async def record(self, result: DomainResult) -> None:
        async with self._lock:
            with self._path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=DOMAIN_SUMMARY_FIELDS,
                    extrasaction="raise",
                    quoting=csv.QUOTE_MINIMAL,
                )
                writer.writerow(result.to_row())


class OutputBundle:
    """Convenience holder so the pipeline only depends on one object."""

    def __init__(
        self,
        listings: ListingWriter,
        errors: ErrorLogWriter,
        summary: DomainSummaryWriter,
    ) -> None:
        self.listings = listings
        self.errors = errors
        self.summary = summary

    async def initialize(self, *, truncate: bool) -> None:
        await asyncio.gather(
            self.listings.initialize(truncate=truncate),
            self.errors.initialize(truncate=truncate),
            self.summary.initialize(truncate=truncate),
        )


def build_output_bundle(
    *,
    listings_path: Path,
    errors_path: Path,
    summary_path: Path,
) -> OutputBundle:
    return OutputBundle(
        listings=ListingWriter(listings_path),
        errors=ErrorLogWriter(errors_path),
        summary=DomainSummaryWriter(summary_path),
    )


def cleanup_legacy_outputs(*paths: Optional[Path]) -> None:
    """Best-effort removal of stale output artifacts before a fresh run."""
    for path in paths:
        if path and path.exists():
            try:
                path.unlink()
            except OSError as exc:
                log.debug("could not remove %s: %s", path, exc)
