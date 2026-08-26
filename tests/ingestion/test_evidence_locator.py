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
    doc_id: str = "DOC-001",
    page: int = 3,
) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
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
    evidence = locate_evidence(
        [_chunk("本期营业收入同比增长 12.0%。这是其他内容。")],
        ["营业收入"],
        documents=[_document()],
        evidence_type="financial",
    )

    assert len(evidence) == 1
    assert evidence[0].doc_id == "DOC-001"
    assert evidence[0].chunk_id == "CHUNK-DOC-001-P1"


def test_quote_is_verbatim_from_source() -> None:
    source_text = "本期营业收入同比增长 12.0%。这是其他内容。"
    evidence = locate_evidence(
        [_chunk(source_text)],
        ["营业收入"],
        documents=[_document()],
        evidence_type="financial",
    )

    assert "营业收入" in evidence[0].quote
    assert evidence[0].quote in source_text


def test_published_at_comes_from_document() -> None:
    evidence = locate_evidence(
        [_chunk("本期营业收入同比增长 12.0%。")],
        ["营业收入"],
        documents=[_document()],
        evidence_type="financial",
    )

    assert evidence[0].published_at == date(2026, 3, 30)


def test_locator_includes_page_and_chunk() -> None:
    evidence = locate_evidence(
        [_chunk("本期营业收入同比增长 12.0%。", page=3)],
        ["营业收入"],
        documents=[_document()],
        evidence_type="financial",
    )

    assert "page 3" in evidence[0].locator
    assert "CHUNK-DOC-001-P1" in evidence[0].locator


def test_evidence_type_is_propagated() -> None:
    evidence = locate_evidence(
        [_chunk("本期营业收入同比增长 12.0%。")],
        ["营业收入"],
        documents=[_document()],
        evidence_type="policy",
    )

    assert evidence[0].evidence_type == "policy"


def test_no_keyword_hit_returns_empty() -> None:
    evidence = locate_evidence(
        [_chunk("本期利润保持稳定。")],
        ["营业收入"],
        documents=[_document()],
        evidence_type="financial",
    )

    assert evidence == []


def test_empty_evidence_type_raises() -> None:
    with pytest.raises(ValueError, match="evidence_type"):
        locate_evidence(
            [_chunk("本期营业收入同比增长 12.0%。")],
            ["营业收入"],
            documents=[_document()],
            evidence_type="",
        )


def test_document_without_published_at_raises() -> None:
    with pytest.raises(ValueError, match="published_at"):
        locate_evidence(
            [_chunk("本期营业收入同比增长 12.0%。")],
            ["营业收入"],
            documents=[_document(published_at=None)],
            evidence_type="financial",
        )


def test_missing_document_raises() -> None:
    with pytest.raises(ValueError, match="DOC-UNKNOWN"):
        locate_evidence(
            [_chunk("本期营业收入同比增长 12.0%。", doc_id="DOC-UNKNOWN")],
            ["营业收入"],
            documents=[_document()],
            evidence_type="financial",
        )


def test_empty_keyword_is_ignored() -> None:
    evidence = locate_evidence(
        [_chunk("本期利润稳定。")],
        ["", "不存在词"],
        documents=[_document()],
        evidence_type="financial",
    )

    assert evidence == []


def test_duplicate_keywords_are_deduplicated() -> None:
    evidence = locate_evidence(
        [_chunk("本期利润稳定增长。")],
        ["利润", "利润"],
        documents=[_document()],
        evidence_type="financial",
    )

    assert len(evidence) == 1


def test_whitespace_evidence_type_raises() -> None:
    with pytest.raises(ValueError, match="evidence_type"):
        locate_evidence(
            [_chunk("本期营业收入同比增长 12.0%。")],
            ["营业收入"],
            documents=[_document()],
            evidence_type="   ",
        )


def test_keyword_match_evidence_type_raises() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        locate_evidence(
            [_chunk("本期营业收入同比增长 12.0%。")],
            ["营业收入"],
            documents=[_document()],
            evidence_type="keyword_match",
        )


def test_whitespace_keyword_is_ignored() -> None:
    evidence = locate_evidence(
        [_chunk("本期利润稳定。")],
        [" "],
        documents=[_document()],
        evidence_type="financial",
    )

    assert evidence == []


def test_keywords_are_normalized_and_deduplicated() -> None:
    evidence = locate_evidence(
        [_chunk("本期营业收入同比增长。")],
        [" 营业收入 ", "营业收入"],
        documents=[_document()],
        evidence_type="financial",
    )

    assert len(evidence) == 1


def test_evidence_id_does_not_collide_across_evidence_types() -> None:
    chunk = _chunk("本期营业收入同比增长 12.0%。")

    financial = locate_evidence(
        [chunk], ["营业收入"], documents=[_document()], evidence_type="financial"
    )
    policy = locate_evidence(
        [chunk], ["营业收入"], documents=[_document()], evidence_type="policy"
    )

    assert financial[0].evidence_id != policy[0].evidence_id


def test_evidence_id_is_stable_across_keyword_order() -> None:
    chunk = _chunk("本期营业收入同比增长。政策利好频出。")

    first = locate_evidence(
        [chunk], ["营业收入", "政策"], documents=[_document()], evidence_type="financial"
    )
    second = locate_evidence(
        [chunk], ["政策", "营业收入"], documents=[_document()], evidence_type="financial"
    )

    ids_first = {evidence.quote: evidence.evidence_id for evidence in first}
    ids_second = {evidence.quote: evidence.evidence_id for evidence in second}
    assert ids_first == ids_second
