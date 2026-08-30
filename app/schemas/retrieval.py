"""Schemas shared by retrieval connectors and the research orchestrator."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1)
    ticker: str | None = Field(default=None, min_length=1)
    query: str = Field(min_length=1)
    start_date: date | None = None
    end_date: date
    categories: list[str] = Field(default_factory=list)


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    source_url: HttpUrl
    publisher: str = Field(min_length=1)
    published_at: date
    source_type: Literal[
        "annual_report",
        "interim_report",
        "announcement",
        "regulation",
        "company_release",
    ]


class RetrievedDocument(SearchHit):
    downloaded_at: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_path: str = Field(min_length=1)
    review_status: Literal["verified", "pending", "rejected"]
