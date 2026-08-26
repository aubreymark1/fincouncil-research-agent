"""HTML text extraction for source documents.

B-003: read a local HTML fixture and produce :class:`TextChunk` objects that
preserve heading structure and paragraph order. The public signature follows
``docs/CONTRACTS.md``::

    extract_html(document: SourceDocument) -> list[TextChunk]

Only local HTML files are supported (no live web scraping). ``script``,
``style``, navigation and other non-content tags are dropped. Headings become
the ``section`` of the paragraphs that follow them. Dates are never guessed
from the text — extraction only returns the verbatim cleaned text.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from app.schemas import SourceDocument, TextChunk


#: Absolute project root, used to resolve manifest-relative ``local_path``.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Tags whose content is never article body text.
_SKIP_TAGS = {
    "script", "style", "nav", "header", "footer", "aside", "noscript",
    "template", "iframe", "form", "button", "select", "option",
    "head", "title",
}

#: Tags that end the current paragraph and start a new one.
_BLOCK_TAGS = {
    "p", "div", "li", "tr", "blockquote", "section", "article", "br",
    "ul", "ol", "table", "pre", "hr", "figure", "figcaption",
}

#: Heading tags: their text becomes the section for following paragraphs.
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class HtmlExtractionError(Exception):
    """Raised when a local HTML file cannot be read or yields no body text.

    ``code`` is E100 ("source file unavailable"); the ``message`` names the
    concrete cause.
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


class _ArticleParser(HTMLParser):
    """Collect (section, paragraph) pairs from a local HTML document."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._buf: list[str] = []
        self._section: str | None = None
        self._paragraphs: list[tuple[str | None, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in _HEADING_TAGS:
            self._flush()
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in _HEADING_TAGS:
            self._flush_heading()
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._buf.append(data)

    def _clean(self) -> str:
        return " ".join("".join(self._buf).split())

    def _flush(self) -> None:
        text = self._clean()
        self._buf = []
        if text:
            self._paragraphs.append((self._section, text))

    def _flush_heading(self) -> None:
        text = self._clean()
        self._buf = []
        if text:
            self._paragraphs.append((self._section, text))
            self._section = text

    def finalize(self) -> None:
        """Flush trailing text left in the buffer at end of document.

        ``<html><body>正文</body></html>`` and ``<main>正文</main>`` contain no
        block-level child tags, so their body text is only collected here, at
        EOF. Callers must invoke this after ``feed``/``close`` and before
        reading ``_paragraphs``.
        """
        self._flush()


def extract_html(document: SourceDocument) -> list[TextChunk]:
    """Extract one TextChunk per body paragraph of ``document``.

    Raises :class:`HtmlExtractionError` when the file is missing, cannot be
    read, or contains no extractable body text.
    """
    path = _resolve(document.local_path)
    if not path.is_file():
        raise HtmlExtractionError(
            "E100", document.local_path, "source file does not exist"
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise HtmlExtractionError(
            "E100", document.local_path, f"unable to read HTML: {exc}"
        ) from exc

    parser = _ArticleParser()
    try:
        parser.feed(raw)
        parser.close()
        parser.finalize()
    except Exception as exc:  # noqa: BLE001 - malformed HTML must not crash
        raise HtmlExtractionError(
            "E100", document.local_path, f"unable to parse HTML: {exc}"
        ) from exc

    paragraphs = parser._paragraphs
    if not paragraphs:
        raise HtmlExtractionError(
            "E100", document.local_path, "no extractable body text found in HTML"
        )

    chunks: list[TextChunk] = []
    offset = 0
    for index, (section, text) in enumerate(paragraphs):
        chunks.append(
            TextChunk(
                chunk_id=f"CHUNK-{document.doc_id.removeprefix('DOC-')}-H{index}",
                doc_id=document.doc_id,
                text=text,
                page=None,
                section=section,
                paragraph_index=index,
                char_start=offset,
                char_end=offset + len(text),
            )
        )
        offset += len(text) + 1

    return chunks
