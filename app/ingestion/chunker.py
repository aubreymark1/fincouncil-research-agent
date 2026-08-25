"""Text chunking for source documents.

B-003: split over-long :class:`TextChunk` objects (typically one per PDF page)
into smaller pieces that fit a character budget. Splitting happens only inside
a single page, never across pages, and prefers sentence boundaries so numbers
and units are not cut mid-token.
"""

from __future__ import annotations

from app.schemas import TextChunk


#: Sentence/paragraph separators used to pick split points.
_BOUNDARIES = ("。", "！", "？", "；", "\n", ". ", "! ", "? ", "; ")


def _last_boundary(window: str) -> int:
    """Return the right-most boundary index in ``window``, or -1."""
    best = -1
    for separator in _BOUNDARIES:
        index = window.rfind(separator)
        if index > best:
            best = index
    return best


def _split_text(text: str, max_chars: int) -> list[tuple[str, int, int]]:
    """Split ``text`` into (piece, start, end) entries no longer than max_chars."""
    if len(text) <= max_chars:
        return [(text, 0, len(text))]

    pieces: list[tuple[str, int, int]] = []
    start = 0
    total = len(text)
    while start < total:
        end = min(start + max_chars, total)
        if end < total:
            window = text[start:end]
            # Prefer a sentence boundary, then a word boundary, in the back
            # half of the window; otherwise cut at max_chars.
            boundary = _last_boundary(window)
            if boundary < max_chars // 2:
                boundary = window.rfind(" ")
            if boundary >= max_chars // 2:
                end = start + boundary + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append((piece, start, end))
        start = end
    return pieces


def chunk_text(chunks: list[TextChunk], max_chars: int) -> list[TextChunk]:
    """Split chunks that exceed ``max_chars``; short chunks pass through.

    Chunks are never merged across documents or pages. Split pieces keep the
    original ``doc_id``, ``page``, ``section``, and ``paragraph_index`` and get
    a unique, stable ``chunk_id`` suffix.
    """
    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}")

    result: list[TextChunk] = []
    for chunk in chunks:
        if len(chunk.text) <= max_chars:
            result.append(chunk)
            continue

        for index, (piece, start, end) in enumerate(_split_text(chunk.text, max_chars)):
            offset = chunk.char_start or 0
            result.append(
                TextChunk(
                    chunk_id=f"{chunk.chunk_id}-{index}",
                    doc_id=chunk.doc_id,
                    text=piece,
                    page=chunk.page,
                    section=chunk.section,
                    paragraph_index=chunk.paragraph_index,
                    char_start=offset + start,
                    char_end=offset + end,
                )
            )
    return result
