"""End-of-run human-readable summary generator.

Reads the three output CSVs (`listings_consolidated.csv`,
`error_log.csv`, `domain_status_summary.csv`) and writes a Markdown
file summarising the run. Streaming, O(1) memory, safe at 55k+ scale.

The markdown is purely informational: the three CSVs are the
contract output. A failure to write the report never aborts the run.
"""
from __future__ import annotations

import csv
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import Settings
from .models import LISTING_FIELDS

log = logging.getLogger(__name__)

_REPORT_FILENAME = "scrape_report.md"
_TOP_DOMAINS_LIMIT = 25


@dataclass(slots=True)
class _SummaryCounts:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0


def _read_summary(path: Path) -> tuple[_SummaryCounts, Counter, dict[str, str]]:
    counts = _SummaryCounts()
    reasons: Counter = Counter()
    statuses: dict[str, str] = {}
    if not path.exists() or path.stat().st_size == 0:
        return counts, reasons, statuses
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            counts.total += 1
            status = (row.get("status") or "").strip().lower()
            statuses[(row.get("domain") or "").strip().lower()] = status
            if status == "success":
                counts.success += 1
            elif status == "failed":
                counts.failed += 1
            elif status == "skipped":
                counts.skipped += 1
            reason = (row.get("reason") or "").strip()
            if reason:
                reasons[reason] += 1
    return counts, reasons, statuses


def _read_listings(path: Path) -> tuple[int, dict[str, int], Counter]:
    """Stream the listings CSV; return (row_count, fill_counts, per_domain)."""
    fill: dict[str, int] = {field: 0 for field in LISTING_FIELDS}
    per_domain: Counter = Counter()
    rows = 0
    if not path.exists() or path.stat().st_size == 0:
        return rows, fill, per_domain
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows += 1
            for field in LISTING_FIELDS:
                if (row.get(field) or "").strip():
                    fill[field] += 1
            domain = (row.get("source_domain") or "").strip().lower()
            if domain:
                per_domain[domain] += 1
    return rows, fill, per_domain


def _read_errors(path: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if not path.exists() or path.stat().st_size == 0:
        return rows
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append((
                (row.get("domain") or "").strip(),
                (row.get("status") or "").strip(),
                (row.get("reason") or "").strip(),
            ))
    return rows


def _format_table(rows: Iterable[tuple[str, ...]], headers: tuple[str, ...]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _percent(part: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{(part / total) * 100:.1f}%"


def generate_report(settings: Settings) -> Path | None:
    """Write `output/scrape_report.md` summarising the latest run.

    Returns the path on success, or None when the report could not
    be written (logged at WARNING). Never raises.
    """
    out_dir = settings.output_dir_path
    summary_path = settings.domain_summary_csv_path
    listings_path = settings.listings_csv_path
    errors_path = settings.error_log_csv_path
    report_path = out_dir / _REPORT_FILENAME

    try:
        counts, reasons, _ = _read_summary(summary_path)
        listing_rows, fill, per_domain = _read_listings(listings_path)
        errors = _read_errors(errors_path)
    except OSError as exc:
        log.warning("report: cannot read output CSVs: %s", exc)
        return None

    sections: list[str] = []
    sections.append("# Real Estate Scraping Report")
    sections.append("")
    sections.append("## Overview")
    sections.append(f"- Total domains processed: `{counts.total}`")
    sections.append(f"- Successful domains: `{counts.success}`")
    sections.append(f"- Failed domains: `{counts.failed}`")
    if counts.skipped:
        sections.append(f"- Skipped domains: `{counts.skipped}`")
    sections.append(
        f"- Domain success rate: `{_percent(counts.success, counts.total)}`"
    )
    sections.append(f"- Total listings written: `{listing_rows}`")
    sections.append("")
    sections.append("## Field Completeness")
    sections.append(_format_table(
        tuple(
            (field, str(fill[field]), _percent(fill[field], listing_rows))
            for field in LISTING_FIELDS
        ),
        ("Field", "Filled rows", "Fill rate"),
    ))
    sections.append("")
    sections.append("## Top Successful Domains")
    top = per_domain.most_common(_TOP_DOMAINS_LIMIT)
    if top:
        sections.append(_format_table(
            tuple((domain, str(count)) for domain, count in top),
            ("Domain", "Listings"),
        ))
    else:
        sections.append("_No listings were extracted._")
    sections.append("")
    sections.append("## Failure Reasons")
    if reasons:
        sections.append(_format_table(
            tuple(
                (reason, str(count))
                for reason, count in reasons.most_common()
            ),
            ("Reason", "Count"),
        ))
    else:
        sections.append("_No failures._")
    sections.append("")
    sections.append("## Failed Domains")
    if errors:
        sections.append(_format_table(
            tuple(errors),
            ("Domain", "Status", "Reason"),
        ))
    else:
        sections.append("_No failed domains._")
    sections.append("")

    payload = "\n".join(sections)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload, encoding="utf-8")
    except OSError as exc:
        log.warning("report: cannot write %s: %s", report_path, exc)
        return None
    log.info("report written: %s", report_path)
    return report_path
