"""Keyword-based evidence location for source documents.

B-003: scan text chunks for industry keywords and produce verbatim, locatable
:class:`Evidence` objects. The first version is plain keyword matching — no
vector database.

Aligned with CONTRACT-CHANGE-002: ``documents`` and ``evidence_type`` are
required keyword-only inputs. Missing metadata is a hard failure, never a
silent skip, so downstream modules cannot mistake absent evidence for "no
evidence".
"""

from __future__ import annotations

from app.schemas import Evidence, SourceDocument, TextChunk


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
    documents: list[SourceDocument],
    evidence_type: str,
) -> list[Evidence]:
    """Return Evidence for every (chunk, keyword) hit, with verbatim quotes.

    ``documents`` supplies ``published_at``, ``company_name`` and
    ``industry_id`` per chunk. ``evidence_type`` labels the retrieval channel
    (e.g. ``financial``, ``policy``, ``news``). Both are required; a chunk
    whose document is missing or lacks ``published_at``, or an empty
    ``evidence_type``, raises instead of silently dropping evidence.
    """
    if not evidence_type:
        raise ValueError("evidence_type must not be empty")

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
            raise ValueError(
                f"document {document.doc_id} has no published_at; "
                "cannot build Evidence without a publication date"
            )

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
                    evidence_type=evidence_type,
                    confidence=0.5,
                    review_status="pending",
                )
            )

    return evidence_list
