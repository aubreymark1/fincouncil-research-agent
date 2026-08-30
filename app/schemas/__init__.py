"""The single public schema namespace for the research agent."""

from .claim import Claim
from .evidence import Evidence
from .evidence_types import ALLOWED_EVIDENCE_TYPES, EvidenceType
from .industry import IndustryConfig, MetricRule, RiskRule
from .report import NarrativeBlock, NarrativeDraft, NarrativeSegment, ResearchReport, RunMetadata
from .request import ResearchRequest
from .retrieval import RetrievedDocument, SearchHit, SearchQuery
from .run_event import RunEvent
from .source import SourceDocument, TextChunk
from .validation import ValidationIssue

__all__ = [
    "ALLOWED_EVIDENCE_TYPES",
    "Claim",
    "Evidence",
    "EvidenceType",
    "IndustryConfig",
    "MetricRule",
    "NarrativeBlock",
    "NarrativeDraft",
    "NarrativeSegment",
    "ResearchReport",
    "ResearchRequest",
    "RetrievedDocument",
    "SearchHit",
    "SearchQuery",
    "RunEvent",
    "RiskRule",
    "RunMetadata",
    "SourceDocument",
    "TextChunk",
    "ValidationIssue",
]
