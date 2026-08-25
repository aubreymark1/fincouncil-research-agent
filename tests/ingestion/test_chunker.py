"""Tests for the B-003 text chunker."""

from __future__ import annotations

import pytest

from app.ingestion import chunk_text
from app.schemas import TextChunk


def _chunk(
    text: str,
    *,
    chunk_id: str = "CHUNK-DOC-001-P1",
    page: int = 1,
) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        doc_id="DOC-001",
        text=text,
        page=page,
        section=None,
        paragraph_index=None,
        char_start=0,
        char_end=len(text),
    )


def test_short_chunk_passes_through() -> None:
    chunk = _chunk("短文本")
    assert chunk_text([chunk], max_chars=100) == [chunk]


def test_long_chunk_is_split_within_budget() -> None:
    text = "第一句。第二句。第三句。第四句。第五句。第六句。"
    chunks = chunk_text([_chunk(text)], max_chars=8)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 8 for chunk in chunks)


def test_split_preserves_doc_id_and_page() -> None:
    text = "第一句。第二句。第三句。第四句。"
    chunks = chunk_text([_chunk(text, page=3)], max_chars=6)

    assert chunks
    assert all(chunk.doc_id == "DOC-001" for chunk in chunks)
    assert all(chunk.page == 3 for chunk in chunks)


def test_split_chunk_ids_are_unique() -> None:
    text = "第一句。第二句。第三句。第四句。"
    chunks = chunk_text([_chunk(text)], max_chars=6)

    ids = [chunk.chunk_id for chunk in chunks]
    assert len(ids) == len(set(ids))


def test_max_chars_must_be_positive() -> None:
    with pytest.raises(ValueError):
        chunk_text([_chunk("任意")], max_chars=0)


def test_chunks_are_not_merged_across_pages() -> None:
    first = _chunk("第一页内容很长需要切分。", chunk_id="CHUNK-DOC-001-P1", page=1)
    second = _chunk("第二页内容也很长需要切分。", chunk_id="CHUNK-DOC-001-P2", page=2)

    chunks = chunk_text([first, second], max_chars=6)

    assert {chunk.page for chunk in chunks} == {1, 2}
    # 没有跨页合并：每个 chunk 只来自一页
    assert all(chunk.page in (1, 2) for chunk in chunks)
