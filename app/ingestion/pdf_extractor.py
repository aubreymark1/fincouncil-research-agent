"""PDF text extraction for source documents.

B-002: read a PDF page by page and produce location-preserving
:class:`TextChunk` objects. The public signature follows ``docs/CONTRACTS.md``::

    extract_pdf(document: SourceDocument) -> list[TextChunk]

The original PDF is never modified and its text is never rewritten; each chunk
keeps the page number so evidence can later be located. Blank pages are skipped
(and logged) rather than producing empty-text chunks.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.schemas import SourceDocument, TextChunk


logger = logging.getLogger(__name__)

#: pypdf emits noisy warnings (e.g. "invalid pdf header") that duplicate the
#: E100 error already raised below; quiet them so failures surface only through
#: :class:`PdfExtractionError`.
logging.getLogger("pypdf").setLevel(logging.ERROR)

#: Absolute project root, used to resolve manifest-relative ``local_path``.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PdfExtractionError(Exception):
    """Raised when a PDF cannot be read, with a shared error code.

    ``code`` is one of the shared error codes from docs/CONTRACTS.md (E100).
    """

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{code} module=ingestion file={path}: {message}")


def _resolve(local_path: str) -> Path:
    path = Path(local_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def extract_pdf(document: SourceDocument) -> list[TextChunk]:
    """Extract one TextChunk per non-blank page of ``document``.

    Raises :class:`PdfExtractionError` with code E100 when the file is missing,
    corrupted, unsupported, or encrypted without a password.
    """
    path = _resolve(document.local_path)
    if not path.is_file():
        raise PdfExtractionError("E100", document.local_path, "source file does not exist")

    try:
        reader = PdfReader(str(path))
    except (PyPdfError, OSError, ValueError) as exc:
        raise PdfExtractionError(
            "E100",
            document.local_path,
            f"unable to open PDF (corrupted or unsupported): {exc}",
        ) from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except (PyPdfError, NotImplementedError):
            pass
        if reader.is_encrypted:
            raise PdfExtractionError(
                "E100",
                document.local_path,
                "PDF is encrypted and cannot be read without a password",
            )

    chunks: list[TextChunk] = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except PyPdfError as exc:
            logger.warning(
                "failed to extract text from page %d of %s: %s",
                page_index,
                document.doc_id,
                exc,
            )
            continue

        if not text:
            logger.info("skipped blank page %d of %s", page_index, document.doc_id)
            continue

        chunks.append(
            TextChunk(
                chunk_id=f"CHUNK-{document.doc_id.removeprefix('DOC-')}-P{page_index}",
                doc_id=document.doc_id,
                text=text,
                page=page_index,
                section=None,
                paragraph_index=None,
                char_start=0,
                char_end=len(text),
            )
        )

    return chunks
