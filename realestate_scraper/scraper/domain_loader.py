"""Load and deduplicate the input CSV into actionable `DomainJob` units.

The input file shape is fixed by the brief:
    company_name, contact_person_last_name, siren, siret, phone_1,
    postalcode, street, city, website

Multiple rows can point to the same registrable domain (different agency
branches sharing one website). We collapse those into one job so we never
scrape the same site twice, and we merge contact metadata across rows so
the richest available phone / city / postcode survives.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

from .models import DomainJob
from .utils.url import ensure_scheme, parse_registrable_domain

log = logging.getLogger(__name__)

_REQUIRED_COLUMNS: tuple[str, ...] = (
    "company_name",
    "contact_person_last_name",
    "phone_1",
    "postalcode",
    "city",
    "website",
)

_NULLISH = {"", "nan", "none", "null", "n/a"}


def _clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in _NULLISH else text


def _better(current: str, candidate: str) -> str:
    """Pick the most informative non-empty value (preferring longer text)."""
    current = _clean(current)
    candidate = _clean(candidate)
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if len(candidate) > len(current) else current


class LoaderError(RuntimeError):
    """Raised when the input CSV is missing or structurally invalid."""


class DomainLoader:
    """Streaming CSV loader that yields deduplicated `DomainJob` objects."""

    def __init__(self, csv_path: Path) -> None:
        self._csv_path = csv_path

    def load(self) -> tuple[list[DomainJob], list[str]]:
        """Return (deduplicated jobs, names of rows with no website)."""
        if not self._csv_path.exists():
            raise LoaderError(f"Input CSV not found: {self._csv_path}")

        jobs_by_domain: dict[str, DomainJob] = {}
        no_website: list[str] = []

        with self._csv_path.open(
            newline="", encoding="utf-8-sig", errors="replace"
        ) as handle:
            reader = csv.DictReader(handle)
            self._validate_header(reader.fieldnames or [])
            for raw_row in reader:
                self._absorb(raw_row, jobs_by_domain, no_website)

        log.info(
            "input loaded: %d unique domains, %d rows without website",
            len(jobs_by_domain),
            len(no_website),
        )
        return list(jobs_by_domain.values()), no_website

    @staticmethod
    def _validate_header(fieldnames: Iterable[str]) -> None:
        present = {name.strip().lower() for name in fieldnames if name}
        missing = [col for col in _REQUIRED_COLUMNS if col not in present]
        if missing:
            raise LoaderError(
                f"input CSV is missing required columns: {missing}"
            )

    @staticmethod
    def _absorb(
        row: dict[str, object],
        jobs: dict[str, DomainJob],
        no_website: list[str],
    ) -> None:
        website_raw = _clean(row.get("website"))
        agency_name = _clean(row.get("company_name")) or "Unknown Agency"
        agent_name = _clean(row.get("contact_person_last_name"))

        if not website_raw:
            no_website.append(agency_name)
            return

        url = ensure_scheme(website_raw)
        domain = parse_registrable_domain(url)
        if not domain:
            no_website.append(agency_name)
            return

        existing = jobs.get(domain)
        if existing is None:
            jobs[domain] = DomainJob(
                domain=domain,
                url=url,
                agency_name=agency_name,
                agent_name=agent_name,
                phone=_clean(row.get("phone_1")),
                city=_clean(row.get("city")),
                postalcode=_clean(row.get("postalcode")),
                rows_merged=1,
            )
            return

        existing.rows_merged += 1
        existing.agency_name = _better(existing.agency_name, agency_name)
        existing.agent_name = _better(existing.agent_name, agent_name)
        existing.phone = _better(existing.phone, _clean(row.get("phone_1")))
        existing.city = _better(existing.city, _clean(row.get("city")))
        existing.postalcode = _better(
            existing.postalcode, _clean(row.get("postalcode"))
        )
