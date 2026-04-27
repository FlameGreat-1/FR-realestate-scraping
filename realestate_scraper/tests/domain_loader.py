from __future__ import annotations

from pathlib import Path

import pytest

from scraper.domain_loader import DomainLoader, LoaderError

_HEADER = (
    "company_name,contact_person_last_name,siren,siret,phone_1,"
    "postalcode,street,city,website\n"
)


def _write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "input.csv"
    path.write_text(_HEADER + content, encoding="utf-8")
    return path


def test_loader_dedupes_by_registrable_domain(tmp_path: Path):
    csv_data = (
        "AGENCY A,Smith,1,11,33111,75001,1 rue X,Paris,a.example.com\n"
        "AGENCY A2,Smith,1,11,null,75001,1 rue X,Paris,www.a.example.com\n"
    )
    jobs, no_site = DomainLoader(_write_csv(tmp_path, csv_data)).load()
    assert len(jobs) == 1
    assert jobs[0].domain == "example.com"
    assert jobs[0].rows_merged == 2
    assert jobs[0].phone == "33111"
    assert no_site == []


def test_loader_records_no_website_rows(tmp_path: Path):
    csv_data = (
        "AGENCY,Last,2,22,33222,75002,2 rue Y,Paris,\n"
        "AGENCY2,Last,3,33,null,75002,3 rue Z,Paris,nan\n"
    )
    jobs, no_site = DomainLoader(_write_csv(tmp_path, csv_data)).load()
    assert jobs == []
    assert sorted(no_site) == ["AGENCY", "AGENCY2"]


def test_loader_rejects_csv_with_missing_columns(tmp_path: Path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(LoaderError):
        DomainLoader(bad).load()


def test_loader_raises_when_file_missing(tmp_path: Path):
    with pytest.raises(LoaderError):
        DomainLoader(tmp_path / "missing.csv").load()
