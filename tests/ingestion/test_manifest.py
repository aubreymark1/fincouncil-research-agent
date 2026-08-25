"""Tests for the B-001 manifest loader and validator."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.ingestion import ManifestError, load_manifest, validate_manifest
from app.schemas import SourceDocument


ROOT = Path(__file__).parents[2]
VALID_MANIFEST = ROOT / "fixtures" / "sources" / "manifest_valid.csv"
INVALID_MANIFEST = ROOT / "fixtures" / "sources" / "manifest_invalid.csv"

HEADER = [
    "doc_id",
    "title",
    "source_type",
    "publisher",
    "source_url",
    "local_path",
    "published_at",
    "event_date",
    "retrieved_at",
    "company_name",
    "industry_id",
    "trust_level",
    "review_status",
]

LOCAL_PLACEHOLDER = "data/raw/food_beverage/placeholder_source.txt"


def _row(**overrides: str) -> list[str]:
    values = {
        "doc_id": "DOC-TEST-001",
        "title": "测试资料",
        "source_type": "news",
        "publisher": "测试机构",
        "source_url": "",
        "local_path": LOCAL_PLACEHOLDER,
        "published_at": "2026-03-30",
        "event_date": "2025-12-31",
        "retrieved_at": "2026-08-20T09:30:00+08:00",
        "company_name": "测试公司",
        "industry_id": "food_beverage",
        "trust_level": "5",
        "review_status": "formal",
    }
    values.update(overrides)
    return [values[field] for field in HEADER]


def _write_manifest(tmp_path: Path, *rows: list[str]) -> str:
    path = tmp_path / "manifest.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return str(path)


def test_valid_manifest_loads_and_validates_cleanly() -> None:
    documents = load_manifest(str(VALID_MANIFEST))

    assert len(documents) == 1
    document = documents[0]
    assert isinstance(document, SourceDocument)
    assert document.doc_id == "DOC-FOOD-001"
    assert document.review_status == "formal"
    assert document.published_at is not None
    assert document.content_hash.startswith("sha256:")

    assert validate_manifest(documents) == []


def test_missing_doc_id_raises_e101(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, _row(doc_id=""))

    with pytest.raises(ManifestError) as exc_info:
        load_manifest(path)

    assert exc_info.value.code == "E101"
    assert "doc_id" in exc_info.value.message


def test_bad_published_at_format_raises_e102(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, _row(published_at="2026/03/30"))

    with pytest.raises(ManifestError) as exc_info:
        load_manifest(path)

    assert exc_info.value.code == "E102"
    assert "published_at" in exc_info.value.message


def test_local_path_missing_raises_e100(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        _row(local_path="data/raw/food_beverage/does_not_exist.pdf"),
    )

    with pytest.raises(ManifestError) as exc_info:
        load_manifest(path)

    assert exc_info.value.code == "E100"
    assert "local_path" in exc_info.value.message


def test_invalid_review_status_raises_e101(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, _row(review_status="not-a-status"))

    with pytest.raises(ManifestError) as exc_info:
        load_manifest(path)

    assert exc_info.value.code == "E101"
    assert "review_status" in exc_info.value.message


def test_formal_document_missing_published_at_is_reported() -> None:
    documents = load_manifest(str(INVALID_MANIFEST))
    issues = validate_manifest(documents)

    no_date_issues = [i for i in issues if i.issue_type == "missing_published_at"]
    assert len(no_date_issues) == 1
    assert "DOC-NODATE-001" in no_date_issues[0].message
    assert no_date_issues[0].human_confirmation_required is True


def test_duplicate_doc_id_is_reported_once() -> None:
    documents = load_manifest(str(INVALID_MANIFEST))
    issues = validate_manifest(documents)

    duplicate_issues = [i for i in issues if i.issue_type == "duplicate_doc_id"]
    assert len(duplicate_issues) == 1
    assert "DOC-DUP-001" in duplicate_issues[0].message
    assert "2 times" in duplicate_issues[0].message


def test_missing_manifest_file_raises_e100() -> None:
    with pytest.raises(ManifestError) as exc_info:
        load_manifest("data/manifests/does_not_exist.csv")

    assert exc_info.value.code == "E100"


def test_invalid_manifest_reports_two_issues() -> None:
    documents = load_manifest(str(INVALID_MANIFEST))
    issues = validate_manifest(documents)

    # one duplicate doc_id + one formal-without-date
    assert len(issues) == 2


def test_json_manifest_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "doc_id": "DOC-JSON-001",
                        "title": "JSON 资料",
                        "source_type": "news",
                        "publisher": "测试机构",
                        "source_url": None,
                        "local_path": LOCAL_PLACEHOLDER,
                        "published_at": "2026-03-30",
                        "event_date": None,
                        "retrieved_at": "2026-08-20T09:30:00+08:00",
                        "company_name": "测试公司",
                        "industry_id": "food_beverage",
                        "trust_level": 5,
                        "review_status": "formal",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    documents = load_manifest(str(path))

    assert len(documents) == 1
    assert documents[0].doc_id == "DOC-JSON-001"
    assert documents[0].trust_level == 5


def test_invalid_doc_id_format_raises_e101(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, _row(doc_id="BAD-001"))

    with pytest.raises(ManifestError) as exc_info:
        load_manifest(path)

    assert exc_info.value.code == "E101"
    assert "record 1" in exc_info.value.message


def test_cli_exits_2_on_invalid_doc_id(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path, _row(doc_id="BAD-001"))

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_manifest.py"), path],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "E101" in result.stderr


def test_json_non_object_record_raises_e101(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "doc_id": "DOC-JSON-001",
                        "title": "JSON 资料",
                        "source_type": "news",
                        "publisher": "测试机构",
                        "source_url": None,
                        "local_path": LOCAL_PLACEHOLDER,
                        "published_at": "2026-03-30",
                        "event_date": None,
                        "retrieved_at": "2026-08-20T09:30:00+08:00",
                        "company_name": "测试公司",
                        "industry_id": "food_beverage",
                        "trust_level": 5,
                        "review_status": "formal",
                    },
                    None,
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError) as exc_info:
        load_manifest(str(path))

    assert exc_info.value.code == "E101"
    assert "record 2" in exc_info.value.message
