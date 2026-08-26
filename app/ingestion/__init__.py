"""Source ingestion: manifest loading, text extraction, and evidence location."""

from .chunker import chunk_text
from .evidence_locator import locate_evidence
from .manifest import ManifestError, load_manifest, validate_manifest
from .pdf_extractor import PdfExtractionError, extract_pdf

__all__ = [
    "ManifestError",
    "PdfExtractionError",
    "chunk_text",
    "extract_pdf",
    "load_manifest",
    "locate_evidence",
    "validate_manifest",
]
