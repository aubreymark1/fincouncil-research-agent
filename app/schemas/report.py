"""Report and run metadata schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Self

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

    blocks: list[NarrativeBlock] = Field(default_factory=list)
    # Compatibility with the response envelope used by the first online demo.
    narrative: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_legacy_blocks(self) -> Self:
        if self.blocks or not self.narrative:
            return self
        blocks: list[NarrativeBlock] = []
        for index, item in enumerate(self.narrative, start=1):
            section = str(item.get("section") or "核心判断")
            text = str(item.get("text") or "").strip()
            evidence_ids = [str(value) for value in item.get("evidence_ids", [])]
            if not text:
                continue
            claim_type = "risk" if "风险" in section and evidence_ids else "unresolved" if not evidence_ids else "analysis"
            blocks.append(NarrativeBlock(
                section=section,
                segments=[NarrativeSegment(
                    segment_id=f"SEG-LEGACY-{index:03d}",
                    text=text,
                    evidence_ids=evidence_ids,
                    claim_type=claim_type,
                    status="pass" if evidence_ids else "review",
                )],
            ))
        self.blocks = blocks
        return self


class InvestmentDecisionSupport(BaseModel):
    """Evidence-bounded decision support, never an automatic trading signal."""

    model_config = ConfigDict(extra="forbid")

    stance: Literal["值得深入跟踪", "中性观察", "当前证据不足"]
    horizon: str = Field(min_length=1)
    thesis: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    entry_conditions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    valuation_status: Literal["not_available", "available"] = "not_available"
    confidence: float = Field(ge=0, le=1)


class ResearchReport(BaseModel):
    """Complete structured output for one research run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, pattern=r"^RUN-[A-Za-z0-9][A-Za-z0-9._-]*$")
    company_name: str = Field(min_length=1)
    industry_id: str = Field(min_length=1)
    cutoff_date: date
    summary: list[str]
    narrative: list[NarrativeBlock] = Field(default_factory=list)
    investment_view: InvestmentDecisionSupport | None = None
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
