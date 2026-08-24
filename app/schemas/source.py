"""Source document and extracted text schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceDocument(BaseModel):
    """Normalized metadata for one source document."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1, pattern=r"^DOC-[A-Za-z0-9][A-Za-z0-9._-]*$")
    title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    source_url: str | None = Field(default=None, min_length=1)
    local_path: str = Field(min_length=1)
    published_at: date | None = None
    event_date: date | None = None
    retrieved_at: datetime
    company_name: str | None = Field(default=None, min_length=1)
    industry_id: str | None = Field(default=None, min_length=1)
    trust_level: int
    content_hash: str = Field(min_length=1)
    review_status: Literal[
        "formal",
        "background",
        "pending_date",
        "red_team",
        "rejected",
    ]


class TextChunk(BaseModel):
    """A location-preserving piece of text from one source document."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1, pattern=r"^CHUNK-[A-Za-z0-9][A-Za-z0-9._-]*$")
    doc_id: str = Field(min_length=1, pattern=r"^DOC-[A-Za-z0-9][A-Za-z0-9._-]*$")
    text: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1)
    paragraph_index: int | None = Field(default=None, ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
