"""Keyword-based evidence location for source documents.

B-003: scan text chunks for industry keywords and produce verbatim, locatable
:class:`Evidence` objects. The first version is plain keyword matching — no
vector database.

Note on ``published_at``: :class:`Evidence` requires a publication date, which
only lives on :class:`SourceDocument`. The frozen CONTRACTS signature
``locate_evidence(chunks, keywords)`` has no document argument, so this module
adds an optional keyword-only ``documents`` parameter to resolve it. This is a
contract gap to confirm with role A (see handoff note).
"""

from __future__ import annotations

import logging

from app.schemas import Evidence, SourceDocument, TextChunk


logger = logging.getLogger(__name__)

#: Separators used to trim a keyword-bearing sentence from the surrounding text.
_BOUNDARIES = "。！？；\n"


def _extract_sentence(text: str, keyword: str) -> str:
    """Return the verbatim sentence containing ``keyword``."""
    index = text.find(keyword)
    if index == -1:
        return ""

    start = index
    while start > 0 and text[start - 1] not in _BOUNDARIES:
        start -= 1

    end = index + len(keyword)
    while end < len(text) and text[end] not in _BOUNDARIES:
        end += 1

    return text[start:end].strip()


def _build_locator(chunk: TextChunk) -> str:
    parts: list[str] = []
    if chunk.page is not None:
        parts.append(f"page {chunk.page}")
    if chunk.section:
        parts.append(f"section {chunk.section}")
    parts.append(f"chunk {chunk.chunk_id}")
    return ", ".join(parts)


def locate_evidence(
    chunks: list[TextChunk],
    keywords: list[str],
    *,
    documents: list[SourceDocument] | None = None,
) -> list[Evidence]:
    """Return Evidence for every (chunk, keyword) hit, with verbatim quotes.

    ``documents`` resolves ``published_at`` (and company/industry metadata) per
    chunk. It is required because :class:`Evidence.published_at` is mandatory
    and cannot be derived from :class:`TextChunk` alone.
    """
    if documents is None:
        raise ValueError(
            "locate_evidence requires documents to resolve Evidence.published_at"
        )

    # Drop empty keywords (which would match every chunk) and deduplicate
    # while preserving order.
    keywords = [keyword for keyword in dict.fromkeys(keywords) if keyword]

    doc_by_id = {document.doc_id: document for document in documents}
    evidence_list: list[Evidence] = []
    seen_ids: set[str] = set()

    for chunk in chunks:
        document = doc_by_id.get(chunk.doc_id)
        if document is None:
            raise ValueError(
                f"no SourceDocument registered for chunk doc_id {chunk.doc_id}"
            )
        if document.published_at is None:
            logger.info(
                "skipped chunk %s: document %s has no published_at",
                chunk.chunk_id,
                document.doc_id,
            )
            continue

        for keyword_index, keyword in enumerate(keywords):
            if keyword not in chunk.text:
                continue

            sentence = _extract_sentence(chunk.text, keyword)
            if not sentence:
                continue

            evidence_id = (
                f"EV-{chunk.chunk_id.removeprefix('CHUNK-')}-K{keyword_index}"
            )
            if evidence_id in seen_ids:
                continue
            seen_ids.add(evidence_id)

            evidence_list.append(
                Evidence(
                    evidence_id=evidence_id,
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    fact_text=sentence,
                    quote=sentence,
                    published_at=document.published_at,
                    page=chunk.page,
                    section=chunk.section,
                    locator=_build_locator(chunk),
                    company_name=document.company_name,
                    industry_id=document.industry_id,
                    evidence_type="keyword_match",
                    confidence=0.5,
                    review_status="pending",
                )
            )

    return evidence_list
