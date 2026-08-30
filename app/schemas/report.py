"""Report and run metadata schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .claim import Claim
from .evidence import Evidence
from .validation import ValidationIssue


class NarrativeSegment(BaseModel):
    """One sentence of report prose with explicit evidence support."""

    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(min_length=1, pattern=r"^SEG-[A-Za-z0-9][A-Za-z0-9._-]*$")
    text: str = Field(min_length=1)
    evidence_ids: list[str]
    claim_type: Literal["fact", "change", "analysis", "risk", "unresolved"]
    status: Literal["pass", "review"]

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        if any(not value.startswith("EV-") for value in values):
            raise ValueError("evidence_ids must contain stable EV- identifiers")
        return values

    @model_validator(mode="after")
    def validate_support(self) -> Self:
        if self.claim_type != "unresolved" and not self.evidence_ids:
            raise ValueError("reportable narrative segments require evidence_ids")
        if self.claim_type == "unresolved" and self.status != "review":
            raise ValueError("unresolved narrative segments must be review")
        return self


class NarrativeBlock(BaseModel):
    """A named report section containing sentence-level narrative segments."""

    model_config = ConfigDict(extra="forbid")

    section: str = Field(min_length=1)
    segments: list[NarrativeSegment] = Field(min_length=1)


class NarrativeDraft(BaseModel):
    """LLM response envelope for sentence-level report prose."""

    model_config = ConfigDict(extra="forbid")

    blocks: list[NarrativeBlock] = Field(min_length=1)


class ResearchReport(BaseModel):
    """Complete structured output for one research run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, pattern=r"^RUN-[A-Za-z0-9][A-Za-z0-9._-]*$")
    company_name: str = Field(min_length=1)
    industry_id: str = Field(min_length=1)
    cutoff_date: date
    summary: list[str]
    narrative: list[NarrativeBlock] = Field(default_factory=list)
    claims: list[Claim]
    risks: list[Claim]
    unresolved_items: list[Claim]
    evidence_index: list[Evidence]
    validation_issues: list[ValidationIssue]
    generated_at: datetime
    report_version: str = Field(min_length=1)


class RunMetadata(BaseModel):
    """Reproducibility and execution metadata for one run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, pattern=r"^RUN-[A-Za-z0-9][A-Za-z0-9._-]*$")
    mode: str = Field(default="rule-engine", min_length=1)
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "success", "partial", "failed"]
    model_provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    prompt_versions: dict[str, str]
    input_hashes: dict[str, str]
    module_versions: dict[str, str]
    errors: list[str]
