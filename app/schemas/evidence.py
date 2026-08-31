"""Evidence schema used to trace claims back to source text."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .evidence_types import EvidenceType


class Evidence(BaseModel):
    """A verbatim, locatable excerpt with normalized provenance."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, pattern=r"^EV-[A-Za-z0-9][A-Za-z0-9._-]*$")
    doc_id: str = Field(min_length=1, pattern=r"^DOC-[A-Za-z0-9][A-Za-z0-9._-]*$")
    # Stable doc_id remains the audit key; these fields are the user-facing provenance.
    source_title: str | None = Field(default=None, min_length=1)
    publisher: str | None = Field(default=None, min_length=1)
    source_url: str | None = Field(default=None, min_length=1)
    source_type: str | None = Field(default=None, min_length=1)
    chunk_id: str = Field(min_length=1, pattern=r"^CHUNK-[A-Za-z0-9][A-Za-z0-9._-]*$")
    fact_text: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    published_at: date
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1)
    locator: str = Field(min_length=1)
    company_name: str | None = Field(default=None, min_length=1)
    industry_id: str | None = Field(default=None, min_length=1)
    evidence_type: EvidenceType
    confidence: float = Field(ge=0, le=1)
    review_status: Literal["verified", "pending", "rejected"]


Evidence.model_rebuild()
