"""Tests for the B-003 evidence locator."""

from __future__ import annotations

from datetime import date

import pytest

from app.ingestion import locate_evidence
from app.schemas import SourceDocument, TextChunk


def _chunk(
    text: str,
    *,
    chunk_id: str = "CHUNK-DOC-001-P1",
    page: int = 3,
) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        doc_id="DOC-001",
        text=text,
        page=page,
        section="经营情况",
        paragraph_index=0,
        char_start=0,
        char_end=len(text),
    )


def _document(published_at: str | None = "2026-03-30") -> SourceDocument:
    return SourceDocument(
        doc_id="DOC-001",
        title="测试资料",
        source_type="annual_report",
        publisher="测试机构",
        source_url=None,
        local_path="data/raw/food_beverage/placeholder_source.txt",
        published_at=published_at,
        event_date=None,
        retrieved_at="2026-08-25T12:00:00+08:00",
        company_name="测试公司",
        industry_id="food_beverage",
        trust_level=5,
        content_hash="sha256:fixture",
        review_status="formal",
    )


def test_keyword_hit_generates_evidence() -> None:
    chunks = [_chunk("本期营业收入同比增长 12.0%。这是其他内容。")]

    evidence = locate_evidence(chunks, ["营业收入"], documents=[_document()])

    assert len(evidence) == 1
    assert evidence[0].doc_id == "DOC-001"
    assert evidence[0].chunk_id == "CHUNK-DOC-001-P1"


def test_quote_is_verbatim_from_source() -> None:
    source_text = "本期营业收入同比增长 12.0%。这是其他内容。"
    evidence = locate_evidence(
        [_chunk(source_text)], ["营业收入"], documents=[_document()]
    )

    assert "营业收入" in evidence[0].quote
    assert evidence[0].quote in source_text


def test_published_at_comes_from_document() -> None:
    evidence = locate_evidence(
        [_chunk("本期营业收入同比增长 12.0%。")],
        ["营业收入"],
        documents=[_document()],
    )

    assert evidence[0].published_at == date(2026, 3, 30)


def test_locator_includes_page_and_chunk() -> None:
    evidence = locate_evidence(
        [_chunk("本期营业收入同比增长 12.0%。", page=3)],
        ["营业收入"],
        documents=[_document()],
    )

    assert "page 3" in evidence[0].locator
    assert "CHUNK-DOC-001-P1" in evidence[0].locator


def test_no_keyword_hit_returns_empty() -> None:
    evidence = locate_evidence(
        [_chunk("本期利润保持稳定。")], ["营业收入"], documents=[_document()]
    )

    assert evidence == []


def test_requires_documents() -> None:
    with pytest.raises(ValueError, match="documents"):
        locate_evidence([_chunk("本期营业收入同比增长 12.0%。")], ["营业收入"])


def test_document_without_published_at_is_skipped() -> None:
    evidence = locate_evidence(
        [_chunk("本期营业收入同比增长 12.0%。")],
        ["营业收入"],
        documents=[_document(published_at=None)],
    )

    assert evidence == []
