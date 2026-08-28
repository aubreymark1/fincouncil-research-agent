"""Report and run metadata schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .claim import Claim
from .evidence import Evidence
from .validation import ValidationIssue


class ReportBlock(BaseModel):
    """One natural-language report paragraph with evidence references."""

    model_config = ConfigDict(extra="forbid")

    section: str = Field(min_length=1)
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        for evidence_id in values:
            if not evidence_id.startswith("EV-"):
                raise ValueError("evidence_ids must contain stable EV- identifiers")
        return values


class ResearchReport(BaseModel):
    """Complete structured output for one research run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, pattern=r"^RUN-[A-Za-z0-9][A-Za-z0-9._-]*$")
    company_name: str = Field(min_length=1)
    industry_id: str = Field(min_length=1)
    cutoff_date: date
    summary: list[str]
    narrative: list[ReportBlock] = Field(default_factory=list)
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
