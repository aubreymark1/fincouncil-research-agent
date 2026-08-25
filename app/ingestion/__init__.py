"""Source ingestion: manifest loading, text extraction, and evidence location."""

from .manifest import ManifestError, load_manifest, validate_manifest

__all__ = ["ManifestError", "load_manifest", "validate_manifest"]
