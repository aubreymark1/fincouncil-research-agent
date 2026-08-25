"""Tests for the B-002 PDF extractor."""

from __future__ import annotations

from pathlib import Path

import pytest
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

from app.ingestion import PdfExtractionError, extract_pdf
from app.schemas import SourceDocument


ROOT = Path(__file__).parents[2]
SAMPLE_PDF = ROOT / "fixtures" / "sources" / "sample_report.pdf"


def _document(local_path: str) -> SourceDocument:
    return SourceDocument(
        doc_id="DOC-TEST-001",
        title="测试资料",
        source_type="annual_report",
        publisher="测试机构",
        source_url=None,
        local_path=local_path,
        published_at="2026-03-30",
        event_date=None,
        retrieved_at="2026-08-25T12:00:00+08:00",
        company_name=None,
        industry_id=None,
        trust_level=5,
        content_hash="sha256:fixture",
        review_status="formal",
    )


def _write_pdf(tmp_path: Path, name: str, *, pages_with_text: list[bool]) -> Path:
    pdf = FPDF()
    for has_text in pages_with_text:
        pdf.add_page()
        if has_text:
            pdf.set_font("Helvetica", size=12)
            pdf.cell(text="Some extractable text.")
    path = tmp_path / name
    pdf.output(str(path))
    return path


def _write_encrypted_pdf(tmp_path: Path) -> Path:
    plain = _write_pdf(tmp_path, "plain.pdf", pages_with_text=[True])
    reader = PdfReader(str(plain))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("userpass", "ownerpass")
    encrypted = tmp_path / "encrypted.pdf"
    with encrypted.open("wb") as handle:
        writer.write(handle)
    return encrypted


def test_two_page_pdf_produces_paged_chunks() -> None:
    chunks = extract_pdf(_document(str(SAMPLE_PDF)))

    assert len(chunks) == 2
    assert [chunk.page for chunk in chunks] == [1, 2]
    assert all(chunk.doc_id == "DOC-TEST-001" for chunk in chunks)
    assert all(chunk.text for chunk in chunks)


def test_blank_page_does_not_produce_empty_chunk(tmp_path: Path) -> None:
    path = _write_pdf(tmp_path, "with_blank.pdf", pages_with_text=[True, False])

    chunks = extract_pdf(_document(str(path)))

    assert len(chunks) == 1
    assert chunks[0].page == 1


def test_missing_file_raises_e100(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.pdf"

    with pytest.raises(PdfExtractionError) as exc_info:
        extract_pdf(_document(str(missing)))

    assert exc_info.value.code == "E100"


def test_corrupted_pdf_raises_e100(tmp_path: Path) -> None:
    corrupted = tmp_path / "corrupted.pdf"
    corrupted.write_bytes(b"this is definitely not a pdf file")

    with pytest.raises(PdfExtractionError) as exc_info:
        extract_pdf(_document(str(corrupted)))

    assert exc_info.value.code == "E100"


def test_encrypted_pdf_raises_e100(tmp_path: Path) -> None:
    encrypted = _write_encrypted_pdf(tmp_path)

    with pytest.raises(PdfExtractionError) as exc_info:
        extract_pdf(_document(str(encrypted)))

    assert exc_info.value.code == "E100"
