"""Mutable internal state for the minimum research pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ResearchReport,
    ResearchRequest,
    RunMetadata,
    SourceDocument,
    TextChunk,
    ValidationIssue,
)


@dataclass
class ResearchState:
    """State passed between the small A-003 orchestration stages."""

    request: ResearchRequest
    documents: list[SourceDocument] = field(default_factory=list)
    chunks: list[TextChunk] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    config: IndustryConfig | None = None
    claims: list[Claim] = field(default_factory=list)
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    report: ResearchReport | None = None
    metadata: RunMetadata | None = None
